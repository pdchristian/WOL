"""Wake-on-LAN Application - Configuration Manager"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional


# Default configuration
DEFAULT_CONFIG = {
    "devices": [],
    # Each device: {"id": uuid, "name": str, "mac": str, "enabled": bool}
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
        "device_sort_column": 0,  # 0: Name, 1: MAC, 2: IP
        "device_sort_order": "ascending"
    }
}


class ConfigManager:
    """Manages application configuration stored in a JSON file."""

    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            config_dir = Path.home() / ".wol_app"
            config_dir.mkdir(exist_ok=True)
            self.config_path = config_dir / "config.json"
        else:
            self.config_path = Path(config_path)

        self.config = self._load()

    def _load(self) -> dict:
        """Load configuration from file, or create default."""
        if self.config_path.exists():
            try:
                with open(self.config_path, "r") as f:
                    data = json.load(f)
                # Deep merge with defaults to ensure all keys exist
                merged = self._deep_merge(DEFAULT_CONFIG.copy(), data)
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
        """Save current configuration to file."""
        # Trim logs if exceeding max
        max_logs = self.config.get("max_logs", 100)
        if len(self.config.get("logs", [])) > max_logs:
            self.config["logs"] = self.config["logs"][-max_logs:]

        with open(self.config_path, "w") as f:
            json.dump(self.config, f, indent=2)

    # --- Devices ---

    def get_devices(self) -> list:
        return self.config.get("devices", [])

    def add_device(self, name: str, mac: str) -> Optional[dict]:
        """Add a new device. Returns the device dict or None if MAC invalid."""
        import uuid
        if not self._validate_mac(mac):
            return None

        device = {
            "id": str(uuid.uuid4()),
            "name": name,
            "mac": mac.upper(),
            "enabled": True,
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
        """Update device fields. Updates name, mac, ip, enabled."""
        for dev in self.config.get("devices", []):
            if dev["id"] == device_id:
                if "name" in kwargs:
                    dev["name"] = kwargs["name"]
                if "mac" in kwargs and self._validate_mac(kwargs["mac"]):
                    dev["mac"] = kwargs["mac"].upper()
                if "ip" in kwargs:
                    dev["ip"] = kwargs["ip"]
                if "enabled" in kwargs:
                    dev["enabled"] = kwargs["enabled"]
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
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "device_name": device_name,
            "action": action,
            "status": status,
            "message": message,
        }
        self.config.setdefault("logs", []).append(log_entry)
        self.save()
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

    # --- Validation ---

    @staticmethod
    def _validate_mac(mac: str) -> bool:
        """Validate MAC address format."""
        import re
        # Accept formats: AA:BB:CC:DD:EE:FF or AA-BB-CC-DD-EE-FF
        pattern = r"^([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}$"
        return bool(re.match(pattern, mac.strip()))
