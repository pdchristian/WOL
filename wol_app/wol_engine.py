"""Wake-on-LAN Engine - Magic packet sending, ping checks, scheduling."""

import re
import socket
import subprocess
import threading
import time
from datetime import datetime
from typing import Optional

from wol_app.network_scanner import find_interface_for_device


def _validate_ip(ip: str) -> bool:
    """Validate IPv4 addresses with strict regex."""
    ipv4_pattern = r'^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
    return bool(re.match(ipv4_pattern, ip))


def _validate_mac(mac: str) -> bool:
    """Validate MAC addresses with strict regex."""
    mac_pattern = r'^([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}$'
    return bool(re.match(mac_pattern, mac))


def _run_subprocess_safe(command, timeout=5, **kwargs):
    """Safe execution of subprocess with strict limits."""
    try:
        # Set default security options
        safe_kwargs = {
            'stdout': subprocess.PIPE,
            'stderr': subprocess.PIPE,
            'timeout': timeout,
            'shell': False,  # CRITICAL: shell=False prevents command injection
            **kwargs
        }
        result = subprocess.run(command, **safe_kwargs)
        return result
    except subprocess.TimeoutExpired:
        raise TimeoutError(f"Command timed out: {' '.join(command)}")
    except Exception as e:
        raise RuntimeError(f"Command failed: {' '.join(command)} - {str(e)}")


from PyQt6.QtCore import QObject, pyqtSignal

class WOLEngine(QObject):
    """Handles Wake-on-LAN magic packets, device status checks, and scheduling."""

    schedule_fired = pyqtSignal(str, str)  # (device_id, action)

    def __init__(self, config_manager):
        super().__init__()
        self.config = config_manager
        self._scheduler_timer = None
        # Map of device_id -> last known status
        self._device_status = {}

    # --- Magic Packet ---

    @staticmethod
    def _create_magic_packet(mac: str) -> bytes:
        """Create a Wake-on-LAN magic packet."""
        if not _validate_mac(mac):
            raise ValueError(f"Invalid MAC address: {mac}")
        # Clean MAC - remove separators
        clean_mac = mac.replace(":", "").replace("-", "")
        if len(clean_mac) != 12:
            raise ValueError(f"Invalid MAC length after cleaning: {clean_mac}")
        mac_bytes = bytes.fromhex(clean_mac)

        # Magic packet: FF x 6 + MAC x 16
        packet = b"\xff" * 6 + mac_bytes * 16
        return packet

    def send_wake_packet(self, device_id: str) -> tuple[bool, str]:
        """Send a wake packet to a device. Returns (success, message)."""
        device = self.config.get_device_by_id(device_id)
        if not device:
            return False, "Device not found."

        mac = device["mac"]
        name = device["name"]
        network = self.config.get_network_settings()
        broadcast_port = network["broadcast_port"]

        # Determine the correct interface and broadcast address for this device
        target_ip = device.get("ip", "")
        iface = find_interface_for_device(target_ip) if target_ip else None

        if iface:
            broadcast_ip = iface["broadcast_ip"]
            local_ip = iface["local_ip"]
            info_suffix = f" via {local_ip} -> {broadcast_ip}:{broadcast_port}"
        else:
            # Fallback: use global broadcast settings
            broadcast_ip = network["broadcast_ip"]
            local_ip = None
            info_suffix = f" at {broadcast_ip}:{broadcast_port}"

        try:
            packet = self._create_magic_packet(mac)

            # Validate port
            if not (1 <= broadcast_port <= 65535):
                error_msg = f"Invalid broadcast port: {broadcast_port}"
                self.config.add_log(name, "WAKE", "ERROR", error_msg)
                return False, error_msg

            # Validate broadcast IP
            if broadcast_ip not in ["255.255.255.255"] and not _validate_ip(broadcast_ip):
                error_msg = f"Invalid broadcast IP: {broadcast_ip}"
                self.config.add_log(name, "WAKE", "ERROR", error_msg)
                return False, error_msg

            # Create UDP socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

            # Bind to the correct local interface so the packet goes out the right NIC
            if local_ip and _validate_ip(local_ip):
                try:
                    sock.bind((local_ip, 0))
                except Exception as e:
                    error_msg = f"Failed to bind to {local_ip}: {e}"
                    self.config.add_log(name, "WAKE", "ERROR", error_msg)
                    sock.close()
                    return False, error_msg

            sock.sendto(packet, (broadcast_ip, broadcast_port))
            sock.close()

            # Log without sensitive MAC address
            self.config.add_log(name, "WAKE", "SUCCESS", f"Magic packet sent{info_suffix}")
            return True, f"Wake packet sent to {name}."
        except socket.error as e:
            error_msg = f"Socket error: {e}"
            self.config.add_log(name, "WAKE", "ERROR", error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"Unexpected error: {e}"
            self.config.add_log(name, "WAKE", "ERROR", error_msg)
            return False, error_msg

    def wake_all(self) -> list[tuple[str, bool, str]]:
        """Wake all enabled devices. Returns list of (name, success, message)."""
        results = []
        for device in self.config.get_devices():
            if device.get("enabled", True):
                success, msg = self.send_wake_packet(device["id"])
                results.append((device["name"], success, msg))
                time.sleep(0.1)  # Small delay between packets
        return results

    # --- Status Check (Ping) ---

    def check_device_status(self, device_id: str) -> tuple[str, str]:
        """
        Ping a device to check if it's online.
        Returns ('online'/'offline'/'unknown', detail_message).
        Note: WOL doesn't inherently know IP from MAC - this is a limitation.
        We can optionally store an IP per device or just report 'unknown'.
        """
        device = self.config.get_device_by_id(device_id)
        if not device:
            return "unknown", "Device not found."

        name = device["name"]

        # Check if device has an optional IP stored
        ip = device.get("ip", "")
        if not ip:
            status = "unknown"
            message = f"No IP configured for {name}. Add an IP to enable ping checks."
        elif not _validate_ip(ip):
            status = "unknown"
            message = f"Invalid IP configured for {name}."
        else:
            try:
                # Use platform-appropriate ping
                param = "-n" if subprocess.os.name == "nt" else "-c"
                # Suppress console window on Windows
                kwargs = {}
                if subprocess.os.name == "nt":
                    kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
                result = _run_subprocess_safe(
                    ["ping", param, "1", ip],
                    timeout=5,
                    **kwargs,
                )
                # Check actual ping output, not just exit code
                # Windows may return 0 even when host is unreachable (router replies)
                output = result.stdout.decode("utf-8", errors="replace")
                if "TTL=" in output:
                    status = "online"
                    message = f"{name} is responding."
                else:
                    status = "offline"
                    message = f"{name} did not respond. May be off or sleeping."
            except subprocess.TimeoutExpired:
                status = "offline"
                message = f"Ping to {name} ({ip}) timed out."
            except Exception as e:
                status = "unknown"
                message = f"Error pinging {name}: {e}"

        self._device_status[device_id] = status
        return status, message

    def check_all_statuses(self) -> list[tuple[str, str, str]]:
        """Check all devices. Returns list of (name, status, message)."""
        results = []
        for device in self.config.get_devices():
            if device.get("enabled", True):
                status, msg = self.check_device_status(device["id"])
                results.append((device["name"], status, msg))
        return results

    def get_device_status(self, device_id: str) -> str:
        """Get cached status for a device."""
        return self._device_status.get(device_id, "unknown")

    # --- Scheduler ---

    def start_scheduler(self):
        """Start the scheduling timer (every 60 seconds)."""
        self._run_scheduler_check()

    def stop_scheduler(self):
        """Stop the scheduler."""
        if self._scheduler_timer:
            self._scheduler_timer.cancel()
            self._scheduler_timer = None

    def _run_scheduler_check(self):
        """Check schedules and re-arm timer for next minute."""
        # Cancel any pending timer before starting a new one
        if self._scheduler_timer:
            self._scheduler_timer.cancel()

        now = datetime.now()
        current_day = now.strftime("%a")  # e.g. "Mon"
        current_hour = now.hour
        current_minute = now.minute

        for schedule in self.config.get_schedules():
            if not schedule.get("enabled", True):
                continue

            sched_hour = schedule.get("hour", 0)
            sched_minute = schedule.get("minute", 0)
            days = schedule.get("days", [])

            if current_hour == sched_hour and current_minute == sched_minute:
                if current_day in days:
                    device_id = schedule["device_id"]
                    action = schedule.get("action", "wake")
                    # Verify device still exists
                    if self.config.get_device_by_id(device_id):
                        action_log = "AUTO_WAKE" if action == "wake" else "AUTO_SHUTDOWN"
                        action_desc = "wake" if action == "wake" else "shutdown"
                        self.config.add_log(
                            "Scheduler", action_log, "TRIGGERED",
                            f"Scheduled {action_desc} for device {device_id}"
                        )
                        # Emit signal to safely dispatch to main Qt thread
                        self.schedule_fired.emit(device_id, action)

        # Re-arm timer for next 60-second check
        self._scheduler_timer = threading.Timer(60.0, self._run_scheduler_check)
        self._scheduler_timer.daemon = True
        self._scheduler_timer.start()
