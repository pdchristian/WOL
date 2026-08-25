"""Wake-on-LAN Application - Configuration Manager"""

import copy
import json
import logging
import os
import threading
from datetime import datetime
from pathlib import Path

from wol_app.crypto import decrypt_password, encrypt_password, is_encrypted
from wol_app.utils import (
    validate_device_name,
    validate_mac,
    validate_password,
    validate_username,
)

# ── Logging ─────────────────────────────────────────────────────────────────
# Lightweight file-based logger so security-relevant failures are never
# silently swallowed. Writes to ~/.wol_app/app.log alongside config.json.
_logger = logging.getLogger("wol_app.config")
if not _logger.handlers:
    _logger.setLevel(logging.INFO)
    try:
        _log_dir = Path.home() / ".wol_app"
        _log_dir.mkdir(exist_ok=True, mode=0o700)
        _handler = logging.FileHandler(_log_dir / "app.log", encoding="utf-8")
        _handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        _logger.addHandler(_handler)
    except Exception:
        # If logging cannot be initialized, fall back to stderr only
        _handler = logging.StreamHandler()
        _handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
        _logger.addHandler(_handler)


# Marker file name used to skip redundant permission fixes on subsequent starts
_PERMISSIONS_FIXED_MARKER = "permissions_fixed.marker"


def _fix_directory_permissions(config_dir: Path) -> None:
    """Ensure the config directory is accessible by the current user.

    When the app runs elevated (as admin), the directory may be created
    with admin-only permissions, blocking normal user access.

    **Lazy behaviour:** the fix only runs once per user profile (tracked by a
    marker file). It is re-run automatically only if a later ``PermissionError``
    indicates the directory became inaccessible again.

    Steps:
    1. Take ownership recursively (takeown)
    2. Reset DACL (icacls /reset)
    3. Grant full control to current user (icacls /grant)
    """
    marker = config_dir / _PERMISSIONS_FIXED_MARKER
    if marker.exists():
        return  # Already fixed for this profile — skip subprocess calls

    if os.name != "nt":
        return

    import subprocess
    username: str = os.environ.get("USERNAME", "")
    userdomain: str = os.environ.get("USERDOMAIN", ".")
    if not username:
        return

    user_account: str = f"{userdomain}\\{username}"

    steps = [
        # Step 1: Take ownership recursively
        (["takeown", "/F", str(config_dir), "/R", "/D", "Y"], "takeown"),
        # Step 2: Reset DACL
        (["icacls", str(config_dir), "/reset", "/T", "/C", "/Q"], "icacls/reset"),
        # Step 3: Grant full control to current user recursively
        (["icacls", str(config_dir), "/grant", user_account, "/T", "/C", "/Q"], "icacls/grant"),
    ]

    for cmd, label in steps:
        try:
            subprocess.run(
                cmd, capture_output=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except Exception as e:
            _logger.warning("Permission fix step '%s' failed: %s", label, e)
            return  # Do not write marker — fix will retry next start

    try:
        marker.write_text("fixed", encoding="utf-8")
    except Exception as e:
        _logger.warning("Could not write permission marker: %s", e)


def _clear_permissions_fix_marker(config_dir: Path) -> None:
    """Remove the marker so the permission fix re-runs on next start."""
    marker = config_dir / _PERMISSIONS_FIXED_MARKER
    try:
        if marker.exists():
            marker.unlink()
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


# Valid shutdown methods
SHUTDOWN_METHOD_HOST_SERVICE = "host_service"
SHUTDOWN_METHOD_SMB = "smb"
VALID_SHUTDOWN_METHODS = (SHUTDOWN_METHOD_HOST_SERVICE, SHUTDOWN_METHOD_SMB)

# Remote desktop resolutions offered in the settings dialog (windowed mode).
# Order matters: it defines the order in the resolution drop-down.
REMOTE_DESKTOP_RESOLUTIONS = (
    "1280x720",
    "1600x900",      # smaller than 1920x1080 (16:9, no scroll)
    "1920x1080",
    "1920x1200",
    "2400x1350",     # smaller than 2560x1440 (16:9, no scroll)
    "2560x1440",
    "3440x1440",
    "3840x2160",
)
DEFAULT_REMOTE_DESKTOP_RESOLUTION = "1920x1080"

# Sentinel for "Optimized 16:9": instead of a fixed resolution, the windowed
# remote desktop resolution is derived from the primary screen's current
# resolution (a 16:9 value slightly smaller than the display) so the window
# fits without scrolling.
REMOTE_DESKTOP_RESOLUTION_AUTO = "auto"
# Fraction of the screen size used by the auto resolution (window mode).
REMOTE_DESKTOP_AUTO_FRACTION = 0.888
# Minimum auto-resolution size (width, height) to keep the window usable.
REMOTE_DESKTOP_AUTO_MIN = (1280, 720)

# Default configuration
DEFAULT_CONFIG = {
    "devices": [],
    # Each device: {"id": uuid, "name": str, "mac": str, "ip": str, "username": str, "password": str, "enabled": bool, "shutdown_method": str}
    "network": {
        "broadcast_ip": "255.255.255.255",
        "broadcast_port": 9,
    },
    # Default shutdown method for newly added devices ("host_service" or "smb").
    # Devices created by older versions have no "shutdown_method" key and are
    # treated as "smb" (legacy behaviour).
    "default_shutdown_method": SHUTDOWN_METHOD_HOST_SERVICE,
    "schedules": [],
    # Each schedule: {"id": uuid, "device_id": str, "cron_hour": int, "cron_minute": int, "days": list, "enabled": bool}
    "logs": [],
    # Each log: {"timestamp": str, "device_name": str, "action": str, "status": str, "message": str}
    "max_logs": 100,
    "ui": {
        "device_sort_column": 0,  # 0: Name, 1: MAC, 2: IP, 3: Username, 4: Password
        "device_sort_order": "ascending",
        "language": "en",
        # Windowed remote desktop resolution (see REMOTE_DESKTOP_RESOLUTIONS).
        "remote_desktop_resolution": DEFAULT_REMOTE_DESKTOP_RESOLUTION,
    },
    "updates": {
        "auto_check_enabled": True,
        "check_interval_hours": 24,
        "last_check_timestamp": None,
    },
}


class ConfigManager:
    """Manages application configuration stored in a JSON file."""

    def __init__(self, config_path: str | None = None) -> None:
        # Thread-safe access to logs
        self._logs_lock: threading.Lock = threading.Lock()
        
        if config_path is None:
            config_dir: Path = Path.home() / ".wol_app"
            try:
                # Validate that the path is within the user's home directory
                home_path: Path = Path.home().resolve()
                config_dir: Path = config_dir.resolve()
                if not str(config_dir).startswith(str(home_path)):
                    raise ValueError(f"Invalid config directory path: {config_dir}")
                config_dir.mkdir(exist_ok=True, mode=0o700)  # Restrictive permissions
                self.config_path: Path = config_dir / "config.json"
                self._config_dir = config_dir
                # Fix ownership only once per profile (lazy, see marker)
                _fix_directory_permissions(config_dir)
            except Exception as e:
                raise RuntimeError(f"Failed to initialize config directory: {e}") from e
        else:
            # Validate custom path
            self.config_path: Path = _sanitize_path(config_path)
            self._config_dir = self.config_path.parent

        self.config = self._load()

    def _load(self) -> dict:
        """Load configuration from file, auto-decrypt passwords and migrate old format."""
        if self.config_path.exists():
            try:
                with open(self.config_path) as f:
                    data = json.load(f)
                # Deep merge with defaults to ensure all keys exist.
                # deepcopy so the loaded config never shares nested dict/list
                # references with the module-level DEFAULT_CONFIG (mutating a
                # setting must not pollute the defaults for other instances).
                merged = self._deep_merge(copy.deepcopy(DEFAULT_CONFIG), data)
                # Auto-decrypt passwords on load
                self._decrypt_devices(merged)
                # Detect legacy plaintext passwords and re-encrypt them (Phase 1.3)
                self.config = merged
                self._reencrypt_plaintext_passwords(merged)
                return merged
            except (OSError, json.JSONDecodeError) as e:
                _logger.warning("Could not load config file: %s", e)
                return copy.deepcopy(DEFAULT_CONFIG)
        return copy.deepcopy(DEFAULT_CONFIG)

    def _reencrypt_plaintext_passwords(self, config: dict) -> None:
        """Detect legacy plaintext passwords and persist them encrypted.

        Older versions stored passwords unencrypted in JSON. On load we
        encrypt them immediately so nothing sensitive is written back to
        disk as plaintext.
        """
        plaintext_found = False
        for dev in config.get("devices", []):
            pw = dev.get("password", "")
            if pw and not is_encrypted(pw):
                plaintext_found = True
                dev["password"] = encrypt_password(pw)

        if plaintext_found:
            _logger.warning("Legacy plaintext passwords detected — re-encrypting on save")
            self.save()

    @staticmethod
    def _deep_merge(base: dict, override: dict) -> dict:
        """Recursively merge override into base, preserving defaults for missing nested keys."""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                ConfigManager._deep_merge(base[key], value)
            else:
                base[key] = value
        return base

    def save(self) -> None:
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
        except PermissionError as e:
            # Directory became inaccessible — re-run the permission fix on next start
            _logger.warning("Permission error while saving config: %s", e)
            _clear_permissions_fix_marker(self._config_dir)
            raise RuntimeError(f"Failed to save configuration (permission error): {e}") from e
        except Exception as e:
            _logger.error("Failed to save configuration: %s", e)
            raise RuntimeError(f"Failed to save configuration: {e}") from e
        # Decrypt back so in-memory state stays plaintext
        self._decrypt_devices(self.config)

    # --- Devices ---

    def get_devices(self) -> list:
        return self.config.get("devices", [])

    def add_device(self, name: str, mac: str) -> dict | None:
        """Add a new device. Returns the device dict or None if inputs invalid."""
        import uuid
        if not validate_mac(mac):
            return None
        if not validate_device_name(name):
            return None

        device = {
            "id": str(uuid.uuid4()),
            "name": name[:64],  # Ensure name is within limits
            "mac": mac.upper(),
            "enabled": True,
            "username": "",
            "password": "",
            "shutdown_method": self.get_default_shutdown_method(),
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
        """Update device fields with validation.

        Updates name, mac, ip, enabled, username, password, shutdown_method.
        """
        for dev in self.config.get("devices", []):
            if dev["id"] == device_id:
                if "name" in kwargs and validate_device_name(kwargs["name"]):
                    dev["name"] = kwargs["name"][:64]
                if "mac" in kwargs and validate_mac(kwargs["mac"]):
                    dev["mac"] = kwargs["mac"].upper()
                if "ip" in kwargs:
                    dev["ip"] = kwargs["ip"][:15]  # Max IPv4 length
                if "enabled" in kwargs:
                    dev["enabled"] = bool(kwargs["enabled"])
                if "username" in kwargs and validate_username(kwargs["username"]):
                    dev["username"] = kwargs["username"][:64]
                if "password" in kwargs and validate_password(kwargs["password"]):
                    dev["password"] = kwargs["password"]
                if "shutdown_method" in kwargs and kwargs["shutdown_method"] in VALID_SHUTDOWN_METHODS:
                    dev["shutdown_method"] = kwargs["shutdown_method"]
                self.save()
                return True
        return False

    # --- Shutdown method ---

    @staticmethod
    def get_device_shutdown_method(device: dict) -> str:
        """Return the shutdown method of a device.

        Legacy devices (created before v1.7.0) have no "shutdown_method" key
        and are treated as "smb" to preserve the previous behaviour.
        """
        method = device.get("shutdown_method", SHUTDOWN_METHOD_SMB)
        return method if method in VALID_SHUTDOWN_METHODS else SHUTDOWN_METHOD_SMB

    def get_default_shutdown_method(self) -> str:
        """Return the default shutdown method for newly added devices."""
        method = self.config.get("default_shutdown_method", SHUTDOWN_METHOD_HOST_SERVICE)
        return method if method in VALID_SHUTDOWN_METHODS else SHUTDOWN_METHOD_HOST_SERVICE

    def set_default_shutdown_method(self, method: str) -> None:
        """Set the default shutdown method for newly added devices."""
        if method not in VALID_SHUTDOWN_METHODS:
            raise ValueError(f"Invalid shutdown method: {method}")
        self.config["default_shutdown_method"] = method
        self.save()

    def get_device_by_id(self, device_id: str) -> dict | None:
        for dev in self.config.get("devices", []):
            if dev["id"] == device_id:
                return dev
        return None

    def get_device_by_name(self, name: str) -> dict | None:
        for dev in self.config.get("devices", []):
            if dev["name"] == name:
                return dev
        return None

    # --- Network ---

    def get_network_settings(self) -> dict:
        return self.config.get("network", DEFAULT_CONFIG["network"])

    def update_network_settings(self, broadcast_ip: str = None, broadcast_port: int = None) -> None:
        net = self.config.setdefault("network", {})
        if broadcast_ip is not None:
            net["broadcast_ip"] = broadcast_ip
        if broadcast_port is not None:
            net["broadcast_port"] = broadcast_port
        self.save()
    def update_ui_settings(self, language: str = None, device_sort_column: int = None, device_sort_order: str = None, display_mode: str = None) -> None:
        """Update UI-related settings."""
        ui = self.config.setdefault("ui", {})
        if language is not None:
            ui["language"] = language
        if device_sort_column is not None:
            ui["device_sort_column"] = device_sort_column
        if device_sort_order is not None:
            ui["device_sort_order"] = device_sort_order
        if display_mode is not None:
            ui["display_mode"] = display_mode
        self.save()
    # --- Schedules ---

    def get_schedules(self) -> list:
        schedules = self.config.get("schedules", [])
        # Ensure all schedules have an "action" field (default: "wake")
        for s in schedules:
            s.setdefault("action", "wake")
        return schedules

    def add_schedule(self, device_id: str, hour: int, minute: int, days: list, enabled: bool = True, action: str = "wake") -> dict:
        import uuid
        schedule = {
            "id": str(uuid.uuid4()),
            "device_id": device_id,
            "hour": hour,
            "minute": minute,
            "days": days,  # e.g. ["Mon", "Tue", "Wed"]
            "enabled": enabled,
            "action": action,  # "wake" or "shutdown"
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
                for key in ["hour", "minute", "days", "enabled", "device_id", "action"]:
                    if key in kwargs:
                        sched[key] = kwargs[key]
                self.save()
                return True
        return False

    # --- Logs ---

    def add_log(self, device_name: str, action: str, status: str, message: str) -> dict[str, str]:
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
        
        sanitized_device_name: str = sanitize_log_string(device_name, 64)
        sanitized_action: str = sanitize_log_string(action, 32)
        sanitized_status: str = sanitize_log_string(status, 32)
        sanitized_message: str = sanitize_log_string(message)
        
        log_entry: dict[str, str] = {
            "timestamp": datetime.now().isoformat(),
            "device_name": sanitized_device_name,
            "action": sanitized_action,
            "status": sanitized_status,
            "message": sanitized_message,
        }
        with self._logs_lock:
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
        except Exception:
            # Don't fail if logging fails - just lose the log entry
            # This prevents DoS via log flooding attacks on the filesystem
            pass
        return log_entry

    def get_logs(self, limit: int = None) -> list:
        """Return a **copy** of the logs list to avoid concurrent modification."""
        with self._logs_lock:
            logs = self.config.get("logs", [])
            if limit:
                return copy.deepcopy(logs[-limit:])
            return copy.deepcopy(logs)

    def clear_logs(self) -> None:
        with self._logs_lock:
            self.config["logs"] = []
        self.save()

    # --- UI Settings ---

    def get_device_sort_settings(self):
        ui_config = self.config.get("ui", {})
        return {
            "sort_column": ui_config.get("device_sort_column", 0),
            "sort_order": ui_config.get("device_sort_order", "ascending")
        }

    def set_device_sort_settings(self, sort_column: int, sort_order: str) -> None:
        self.config.setdefault("ui", {})
        self.config["ui"]["device_sort_column"] = sort_column
        self.config["ui"]["device_sort_order"] = sort_order
        self.save()

    # --- Column Widths ---

    def get_column_widths(self) -> list[int]:
        """Return the saved device-table column widths (empty if unset)."""
        ui_config = self.config.get("ui", {})
        widths = ui_config.get("device_column_widths", [])
        return [int(w) for w in widths] if isinstance(widths, list) else []

    def set_column_widths(self, widths: list[int]) -> None:
        """Persist the device-table column widths."""
        self.config.setdefault("ui", {})
        self.config["ui"]["device_column_widths"] = [int(w) for w in widths]
        self.save()

    # --- Encryption Helpers ---

    @staticmethod
    def _encrypt_devices(config: dict) -> None:
        """Encrypt all device passwords in-place before saving."""
        for dev in config.get("devices", []):
            pw = dev.get("password", "")
            if pw and not is_encrypted(pw):
                dev["password"] = encrypt_password(pw)

    @staticmethod
    def _decrypt_devices(config: dict) -> None:
        """Decrypt all device passwords in-place after loading."""
        for dev in config.get("devices", []):
            pw = dev.get("password", "")
            if pw and is_encrypted(pw):
                try:
                    dev["password"] = decrypt_password(pw)
                except Exception:
                    dev["password"] = ""

    # --- Validation ---

    # --- Update Settings ---

    def get_update_settings(self) -> dict:
        """Return the updates configuration block, creating it with defaults if missing."""
        return self.config.setdefault("updates", DEFAULT_CONFIG["updates"].copy())

    def update_last_check_time(self) -> None:
        """Record the current time as the last update check and save."""
        settings = self.get_update_settings()
        settings["last_check_timestamp"] = datetime.now().isoformat()
        self.save()

    def should_check_for_updates(self) -> bool:
        """Determine whether an update check is due based on interval and last-check time."""
        from datetime import timedelta
        settings = self.get_update_settings()
        if not settings.get("auto_check_enabled", True):
            return False

        last_check = settings.get("last_check_timestamp")
        interval_hours = settings.get("check_interval_hours", 24)

        if not last_check:
            return True

        try:
            last_dt: datetime = datetime.fromisoformat(last_check)
        except (ValueError, TypeError):
            return True

        return datetime.now() > last_dt + timedelta(hours=interval_hours)

    def update_update_settings(self, auto_check_enabled: bool = None, check_interval_hours: int = None) -> None:
        """Persist user-chosen update preferences."""
        settings = self.get_update_settings()
        if auto_check_enabled is not None:
            settings["auto_check_enabled"] = bool(auto_check_enabled)
        if check_interval_hours is not None:
            settings["check_interval_hours"] = int(check_interval_hours)
        self.save()

    # --- Log Settings ---

    def get_max_logs(self) -> int:
        """Return the configured maximum number of log entries."""
        return int(self.config.get("max_logs", 100))

    def set_max_logs(self, max_logs: int) -> None:
        """Set the maximum number of log entries to keep."""
        max_logs = max(10, min(int(max_logs), 10000))  # Clamp for safety
        self.config["max_logs"] = max_logs
        self.save()

    # --- Remote Desktop ---

    def get_remote_desktop_resolution(self) -> str:
        """Return the configured windowed remote desktop resolution.

        Falls back to the default when the stored value is missing or
        invalid (e.g. an old config without the key).
        """
        value = self.config.get("ui", {}).get(
            "remote_desktop_resolution", DEFAULT_REMOTE_DESKTOP_RESOLUTION
        )
        if value == REMOTE_DESKTOP_RESOLUTION_AUTO or value in REMOTE_DESKTOP_RESOLUTIONS:
            return value
        return DEFAULT_REMOTE_DESKTOP_RESOLUTION

    def set_remote_desktop_resolution(self, resolution: str) -> None:
        """Set the windowed remote desktop resolution."""
        if resolution != REMOTE_DESKTOP_RESOLUTION_AUTO and resolution not in REMOTE_DESKTOP_RESOLUTIONS:
            raise ValueError(f"Invalid remote desktop resolution: {resolution}")
        ui = self.config.setdefault("ui", {})
        ui["remote_desktop_resolution"] = resolution
        self.save()

    # --- Validation ---

