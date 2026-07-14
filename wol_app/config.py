"""Wake-on-LAN Application - Configuration Manager"""

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from wol_app.crypto import encrypt_password, decrypt_password, is_encrypted


def _fix_directory_permissions(config_dir: Path):
    """Ensure the config directory is accessible by the current user.
    When the app runs elevated (as admin), the directory may be created
    with admin-only permissions, blocking normal user access."""
    try:
        import subprocess
        username = os.environ.get("USERNAME", "")
        userdomain = os.environ.get("USERDOMAIN", ".")
        if username and hasattr(os, 'name') and os.name == 'nt':
            # Use icacls to grant full control to the current user
            subprocess.run(
                ["icacls", str(config_dir), "/grant:f", f"{userdomain}\\{username}",
                 "/T", "/C", "/Q"],
                capture_output=True, timeout=5
            )
    except Exception:
        pass


def _sanitize_path(path: str) -> Path:
    """Sanitize path to prevent path traversal attacks."""
    if not path:
        raise ValueError("Path cannot be empty")
    # Normalize path (removes .., ., etc.)
    path = os.path.normpath(path)
    # Ensure path is absolute
    path = os.path.abspath(path)
    return Path(path)


def _validate_device_name(name: str) -> bool:
    """Validate device name for safety."""
    if not name:
        return False
    if len(name) > 64:
        return False
    # No control characters
    if any(ord(c) < 32 or ord(c) > 126 for c in name):
        return False
    # No potentially dangerous characters
    forbidden_chars = ['<', '>', '"', "'", ';', '|', '&', '$', '`', '\\']
    if any(char in name for char in forbidden_chars):
        return False
    return True


def _validate_username(username: str) -> bool:
    """Validate username for safety."""
    if not username:
        return True  # Username is optional
    if len(username) > 64:
        return False
    if any(ord(c) < 32 or ord(c) > 126 for c in username):
        return False
    return True


def _validate_password(password: str) -> bool:
    """Validate password for safety."""
    if not password:
        return True  # Password is optional
    if len(password) > 128:
        return False
    if any(ord(c) > 126 for c in password):
        return False
    return True


# Default configuration
DEFAULT_CONFIG = {
    "devices": [],
    # Each device: {"id": uuid, "name": str, "mac": str, "ip": str, "username": str, "password": str, "enabled": bool}
    "network": {
        "broadcast_ip": "255.255.255.255",
        "broadcast_port": 9,
    },
    "schedules": [],
    # Each schedule: {"id": uuid, "device_id": str, "cron_hour": int, "cron_minute": int, "days": list, "enabled": bool}
    "logs": [],
    # Each log: {"timestamp": str, "device_name": str, "action": str, "status": str, "message": str}
    "max_logs": 100,
    "ui": {
        "device_sort_column": 0,  # 0: Name, 1: MAC, 2: IP, 3: Username, 4: Password
        "device_sort_order": "ascending"
    }
}


class ConfigManager:
    """Manages application configuration stored in a JSON file."""

    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            config_dir = Path.home() / ".wol_app"
            try:
                # Validate that the path is within the user's home directory
                home_path = Path.home().resolve()
                config_dir = config_dir.resolve()
                if not str(config_dir).startswith(str(home_path)):
                    raise ValueError(f"Invalid config directory path: {config_dir}")
                config_dir.mkdir(exist_ok=True, mode=0o700)  # Restrictive permissions
                self.config_path = config_dir / "config.json"
                # Fix ownership if running elevated (e.g., started as admin)
                _fix_directory_permissions(config_dir)
            except Exception as e:
                raise RuntimeError(f"Failed to initialize config directory: {e}")
        else:
            # Validate custom path
            self.config_path = _sanitize_path(config_path)

        self.config = self._load()

    def _load(self) -> dict:
        """Load configuration from file, auto-decrypt passwords and migrate old format."""
        if self.config_path.exists():
            try:
                with open(self.config_path, "r") as f:
                    data = json.load(f)
                # Deep merge with defaults to ensure all keys exist
                merged = self._deep_merge(DEFAULT_CONFIG.copy(), data)
                # Auto-decrypt passwords on load
                self._decrypt_devices(merged)
                return merged
            except (json.JSONDecodeError, IOError):
                return DEFAULT_CONFIG.copy()
        return DEFAULT_CONFIG.copy()

    @staticmethod
    def _deep_merge(base: dict, override: dict) -> dict:
        """Recursively merge override into base, preserving defaults for missing nested keys."""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                ConfigManager._deep_merge(base[key], value)
            else:
                base[key] = value
        return base

    def save(self):
        """Save current configuration to file with encrypted passwords."""
        # Trim logs if exceeding max
        max_logs = self.config.get("max_logs", 100)
        if len(self.config.get("logs", [])) > max_logs:
            self.config["logs"] = self.config["logs"][-max_logs:]

        # Encrypt passwords before saving
        self._encrypt_devices(self.config)
        try:
            # Save with secure permissions
            with open(self.config_path, "w") as f:
                json.dump(self.config, f, indent=2)
            # Set restrictive permissions (owner read/write only)
            if hasattr(os, 'chmod'):
                os.chmod(self.config_path, 0o600)
        except Exception as e:
            raise RuntimeError(f"Failed to save configuration: {e}")
        # Decrypt back so in-memory state stays plaintext
        self._decrypt_devices(self.config)

    # --- Devices ---

    def get_devices(self) -> list:
        return self.config.get("devices", [])

    def add_device(self, name: str, mac: str) -> Optional[dict]:
        """Add a new device. Returns the device dict or None if inputs invalid."""
        import uuid
        if not self._validate_mac(mac):
            return None
        if not _validate_device_name(name):
            return None

        device = {
            "id": str(uuid.uuid4()),
            "name": name[:64],  # Ensure name is within limits
            "mac": mac.upper(),
            "enabled": True,
            "username": "",
            "password": "",
        }
        self.config.setdefault("devices", []).append(device)
        self.save()
        return device

    def remove_device(self, device_id: str) -> bool:
        devices = self.config.get("devices", [])
        for i, dev in enumerate(devices):
            if dev["id"] == device_id:
                devices.pop(i)
                self.save()
                return True
        return False

    def update_device(self, device_id: str, **kwargs) -> bool:
        """Update device fields with validation. Updates name, mac, ip, enabled, username, password."""
        for dev in self.config.get("devices", []):
            if dev["id"] == device_id:
                if "name" in kwargs and _validate_device_name(kwargs["name"]):
                    dev["name"] = kwargs["name"][:64]
                if "mac" in kwargs and self._validate_mac(kwargs["mac"]):
                    dev["mac"] = kwargs["mac"].upper()
                if "ip" in kwargs:
                    dev["ip"] = kwargs["ip"][:15]  # Max IPv4 length
                if "enabled" in kwargs:
                    dev["enabled"] = bool(kwargs["enabled"])
                if "username" in kwargs and _validate_username(kwargs["username"]):
                    dev["username"] = kwargs["username"][:64]
                if "password" in kwargs and _validate_password(kwargs["password"]):
                    dev["password"] = kwargs["password"]
                self.save()
                return True
        return False

    def get_device_by_id(self, device_id: str) -> Optional[dict]:
        for dev in self.config.get("devices", []):
            if dev["id"] == device_id:
                return dev
        return None

    def get_device_by_name(self, name: str) -> Optional[dict]:
        for dev in self.config.get("devices", []):
            if dev["name"] == name:
                return dev
        return None

    # --- Network ---

    def get_network_settings(self) -> dict:
        return self.config.get("network", DEFAULT_CONFIG["network"])

    def update_network_settings(self, broadcast_ip: str = None, broadcast_port: int = None):
        net = self.config.setdefault("network", {})
        if broadcast_ip is not None:
            net["broadcast_ip"] = broadcast_ip
        if broadcast_port is not None:
            net["broadcast_port"] = broadcast_port
        self.save()

    # --- Schedules ---

    def get_schedules(self) -> list:
        return self.config.get("schedules", [])

    def add_schedule(self, device_id: str, hour: int, minute: int, days: list, enabled: bool = True) -> dict:
        import uuid
        schedule = {
            "id": str(uuid.uuid4()),
            "device_id": device_id,
            "hour": hour,
            "minute": minute,
            "days": days,  # e.g. ["Mon", "Tue", "Wed"]
            "enabled": enabled,
        }
        self.config.setdefault("schedules", []).append(schedule)
        self.save()
        return schedule

    def remove_schedule(self, schedule_id: str) -> bool:
        schedules = self.config.get("schedules", [])
        for i, sched in enumerate(schedules):
            if sched["id"] == schedule_id:
                schedules.pop(i)
                self.save()
                return True
        return False

    def update_schedule(self, schedule_id: str, **kwargs) -> bool:
        for sched in self.config.get("schedules", []):
            if sched["id"] == schedule_id:
                for key in ["hour", "minute", "days", "enabled", "device_id"]:
                    if key in kwargs:
                        sched[key] = kwargs[key]
                self.save()
                return True
        return False

    # --- Logs ---

    def add_log(self, device_name: str, action: str, status: str, message: str):
        """Add a log entry with sanitization to prevent injection."""
        # Sanitize inputs to prevent log injection
        def sanitize_log_string(value: str, max_length: int = 256) -> str:
            if not value:
                return ""
            # Truncate to max length
            value = value[:max_length]
            # Remove control characters except basic whitespace
            value = ''.join(c for c in value if 32 <= ord(c) <= 126 or c in '\n\r\t')
            return value
        
        sanitized_device_name = sanitize_log_string(device_name, 64)
        sanitized_action = sanitize_log_string(action, 32)
        sanitized_status = sanitize_log_string(status, 32)
        sanitized_message = sanitize_log_string(message)
        
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "device_name": sanitized_device_name,
            "action": sanitized_action,
            "status": sanitized_status,
            "message": sanitized_message,
        }
        self.config.setdefault("logs", []).append(log_entry)
        # Trim logs to prevent DoS via log flooding
        max_logs = self.config.get("max_logs", 100)
        if len(self.config.get("logs", [])) > max_logs:
            self.config["logs"] = self.config["logs"][-max_logs:]
        # Only save if config_path exists and is writable
        try:
            if self.config_path and self.config_path.parent.exists():
                self.save()
            elif self.config_path:
                # Ensure directory exists
                self.config_path.parent.mkdir(parents=True, exist_ok=True)
                self.save()
        except Exception as e:
            # Don't fail if logging fails - just lose the log entry
            # This prevents DoS via log flooding attacks on the filesystem
            pass
        return log_entry

    def get_logs(self, limit: int = None) -> list:
        logs = self.config.get("logs", [])
        if limit:
            return logs[-limit:]
        return logs

    def clear_logs(self):
        self.config["logs"] = []
        self.save()

    # --- UI Settings ---

    def get_device_sort_settings(self):
        ui_config = self.config.get("ui", {})
        return {
            "sort_column": ui_config.get("device_sort_column", 0),
            "sort_order": ui_config.get("device_sort_order", "ascending")
        }

    def set_device_sort_settings(self, sort_column: int, sort_order: str):
        self.config.setdefault("ui", {})
        self.config["ui"]["device_sort_column"] = sort_column
        self.config["ui"]["device_sort_order"] = sort_order
        self.save()

    # --- Encryption Helpers ---

    @staticmethod
    def _encrypt_devices(config: dict):
        """Encrypt all device passwords in-place before saving."""
        for dev in config.get("devices", []):
            pw = dev.get("password", "")
            if pw and not is_encrypted(pw):
                dev["password"] = encrypt_password(pw)

    @staticmethod
    def _decrypt_devices(config: dict):
        """Decrypt all device passwords in-place after loading."""
        for dev in config.get("devices", []):
            pw = dev.get("password", "")
            if pw and is_encrypted(pw):
                try:
                    dev["password"] = decrypt_password(pw)
                except Exception:
                    dev["password"] = ""

    # --- Validation ---

    @staticmethod
    def _validate_mac(mac: str) -> bool:
        """Validate MAC address format."""
        import re
        # Accept formats: AA:BB:CC:DD:EE:FF or AA-BB-CC-DD-EE-FF
        pattern = r"^([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}$"
        return bool(re.match(pattern, mac.strip()))
