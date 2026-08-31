"""Shared dispatch logic for fired schedule entries.

Used by both the classic ``MainWindow`` and the modern
``ModernMainWindow`` so scheduled wakes and remote shutdowns behave
identically in either layout. The UI feedback (status bar messages) is
injected via a ``status_fn(msg, timeout_ms)`` callback.
"""

import subprocess
from typing import Any, Callable

from PyQt6.QtWidgets import QApplication

from wol_app.host_service_client import send_host_command
from wol_app.translations import Translations

# Signature: (message, timeout_ms) -> None
StatusFn = Callable[[str, int], None]


def _noop_status(_msg: str, _timeout: int = 0) -> None:
    """Status callback for callers without a status bar."""


def dispatch_schedule_action(
    config: Any,
    engine: Any,
    device_id: str,
    action: str,
    status_fn: StatusFn = _noop_status,
) -> None:
    """Handle a fired schedule entry: wake the device or shut it down.

    Mirrors the classic ``MainWindow._on_schedule_fired`` flow, including
    the host-service and IPC$/shutdown.exe shutdown paths.
    """
    if action == "shutdown":
        scheduled_shutdown(config, device_id, status_fn)
    else:
        engine.send_wake_packet(device_id)


def _scheduled_host_service_shutdown(
    config: Any, device_name: str, ip: str, device: dict, status_fn: StatusFn
) -> None:
    """Execute a scheduled shutdown via the WOL Host Service (no dialog)."""
    username = device.get("username", "")
    password = device.get("password", "")

    if not username or not password:
        msg = Translations.tr(
            "status.scheduled_shutdown_fail",
            name=device_name,
            error=Translations.tr("status.scheduled_shutdown_missing_creds"),
        )
        status_fn(msg, 5000)
        config.add_log(device_name, "SHUTDOWN", "FAILED", msg)
        QApplication.processEvents()
        return

    try:
        success, message = send_host_command(ip, "shutdown", username, password)
        if success:
            msg = Translations.tr("status.scheduled_shutdown_success", name=device_name)
            status_fn(msg, 5000)
            config.add_log(device_name, "SHUTDOWN", "SUCCESS", f"Host service: {message}")
        else:
            msg = Translations.tr("status.scheduled_shutdown_fail", name=device_name, error=message)
            status_fn(msg, 5000)
            config.add_log(device_name, "SHUTDOWN", "FAILED", f"Host service: {message}")
    except Exception as e:
        msg = Translations.tr("status.scheduled_shutdown_error", name=device_name, error=str(e))
        status_fn(msg, 5000)
        config.add_log(device_name, "SHUTDOWN", "FAILED", msg)

    QApplication.processEvents()


def scheduled_shutdown(config: Any, device_id: str, status_fn: StatusFn = _noop_status) -> None:
    """Execute remote shutdown for a scheduled entry (no confirmation dialog)."""
    device = config.get_device_by_id(device_id)
    if not device:
        msg = Translations.tr("status.device_not_found", device_id=device_id)
        status_fn(msg, 5000)
        return

    device_name = device.get("name", Translations.tr("device.unknown"))
    ip = device.get("ip", "")

    status_fn(Translations.tr("status.scheduled_shutdown_starting", name=device_name, ip=ip), 0)
    config.add_log(
        device_name, "SHUTDOWN", "IN_PROGRESS",
        Translations.tr("status.scheduled_shutdown_progress", name=device_name),
    )

    # Dispatch on the device's shutdown method
    if config.get_device_shutdown_method(device) == "host_service":
        _scheduled_host_service_shutdown(config, device_name, ip, device, status_fn)
        return

    try:
        # Step 1: Establish IPC$ connection
        username = device.get("username", "")
        password = device.get("password", "")

        if username:
            cmd = rf'net use \\{ip}\IPC$ "{password}" /user:"{username}"'
        else:
            cmd = rf"net use \\{ip}\IPC$"

        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=15,
        )

        if result.returncode != 0:
            msg = Translations.tr(
                "status.scheduled_shutdown_conn_fail", name=device_name,
                error=result.stderr.strip(),
            )
            status_fn(msg, 5000)
            config.add_log(device_name, "SHUTDOWN", "FAILED", msg)
            QApplication.processEvents()
            return

        # Step 2: Execute remote shutdown
        cmd = rf"shutdown /m \\{ip} /s /t 0 /f"
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=30,
        )

        if result.returncode == 0:
            msg = Translations.tr("status.scheduled_shutdown_success", name=device_name)
            status_fn(msg, 5000)
            config.add_log(device_name, "SHUTDOWN", "SUCCESS", msg)
        else:
            msg = Translations.tr(
                "status.scheduled_shutdown_fail", name=device_name,
                error=result.stderr.strip(),
            )
            status_fn(msg, 5000)
            config.add_log(device_name, "SHUTDOWN", "FAILED", msg)

    except subprocess.TimeoutExpired:
        msg = Translations.tr("status.scheduled_shutdown_timeout", name=device_name)
        status_fn(msg, 5000)
        config.add_log(device_name, "SHUTDOWN", "TIMEOUT", msg)
    except Exception as e:
        msg = Translations.tr("status.scheduled_shutdown_error", name=device_name, error=str(e))
        status_fn(msg, 5000)
        config.add_log(device_name, "SHUTDOWN", "FAILED", msg)

    QApplication.processEvents()
