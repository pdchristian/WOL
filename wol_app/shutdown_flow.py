"""Shared remote-shutdown flow for the classic and modern layouts.

Extracted from ``MainWindow._shutdown_selected`` / ``_execute_shutdown`` /
``_execute_host_service_shutdown`` so both UIs show the same confirmation
dialog and use the same execution paths:

- ``host_service``: WOL Host Service over TCP (port 8765);
- otherwise: ``net use \\\\<ip>\\IPC$`` + ``shutdown /m \\\\<ip> /s /t 0 /f``.

UI status feedback is injected via ``status_fn(msg, timeout_ms)`` exactly
like :mod:`wol_app.schedule_runner`, so the modern layout (no status bar)
can pass a no-op.
"""

import subprocess
from typing import Any, Callable

from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from wol_app.host_service_client import send_host_command
from wol_app.translations import Translations

# Signature: (message, timeout_ms) -> None
StatusFn = Callable[[str, int], None]


def _noop_status(_msg: str, _timeout: int = 0) -> None:
    """Status callback for callers without a status bar."""


def confirm_shutdown(
    parent: QWidget,
    config: Any,
    device: dict,
    status_fn: StatusFn = _noop_status,
) -> None:
    """Show the shutdown confirmation dialog for *device* and execute on accept."""
    device_name = device.get("name", "")
    device_ip = device.get("ip", "")

    if not device_ip:
        QMessageBox.warning(
            parent,
            Translations.tr("dialog.no_ip.title"),
            Translations.tr("dialog.no_ip.message", name=device_name),
        )
        return

    # Determine the shutdown method for this device
    method = config.get_device_shutdown_method(device)

    # Build confirmation dialog
    dialog = QDialog(parent)
    dialog.setWindowTitle(Translations.tr("dialog.shutdown_confirm.title", name=device_name))
    dialog.setMinimumWidth(450)
    layout = QVBoxLayout(dialog)

    label1 = QLabel(Translations.tr("dialog.shutdown_confirm.label1", name=device_name))
    layout.addWidget(label1)

    label2 = QLabel(Translations.tr("dialog.shutdown_confirm.label2"))
    layout.addWidget(label2)

    label3 = QLabel(Translations.tr("dialog.shutdown_confirm.label3"))
    layout.addWidget(label3)

    # Method-specific prerequisite hint
    prereq_text = QTextEdit()
    if method == "host_service":
        prereq_text.setPlainText(
            Translations.tr("dialog.shutdown_confirm.prereq_host_service")
        )
    else:
        prereq_text.setPlainText(
            "- [HKEY_LOCAL_MACHINE\\\\SOFTWARE\\\\Microsoft\\\\Windows\\\\CurrentVersion\\\\Policies\\\\System]\n"
            "  \"LocalAccountTokenFilterPolicy\"=dword:00000001\n"
            "\n"
            "- " + Translations.tr("dialog.shutdown_confirm.sharing_activated")
        )
    prereq_text.setReadOnly(True)
    prereq_text.setMaximumHeight(90)
    layout.addWidget(prereq_text)

    # Buttons
    button_layout = QHBoxLayout()
    cancel_btn = QPushButton(Translations.tr("button.cancel"))
    cancel_btn.clicked.connect(dialog.reject)
    shutdown_confirm_btn = QPushButton(Translations.tr("button.shutdown_confirm"))
    shutdown_confirm_btn.setObjectName("primaryButton")
    shutdown_confirm_btn.clicked.connect(
        lambda: execute_shutdown(parent, config, device, dialog, status_fn)
    )
    button_layout.addWidget(cancel_btn)
    button_layout.addWidget(shutdown_confirm_btn)
    layout.addLayout(button_layout)

    dialog.exec()


def _host_service_shutdown(
    parent: QWidget,
    config: Any,
    device_name: str,
    device_ip: str,
    username: str,
    password: str,
    status_fn: StatusFn,
) -> None:
    """Shut down a device via the WOL Host Service (TCP port 8765)."""
    from PyQt6.QtWidgets import QApplication

    if not username or not password:
        config.add_log(device_name, "SHUTDOWN", "ERROR", "Missing credentials for host service")
        QMessageBox.warning(
            parent,
            Translations.tr("dialog.host_service_missing_creds.title"),
            Translations.tr("dialog.host_service_missing_creds.message", name=device_name),
        )
        return

    status_fn(Translations.tr("status.host_service_sending", name=device_name), 0)
    QApplication.processEvents()

    success, message = send_host_command(device_ip, "shutdown", username, password)

    if success:
        config.add_log(device_name, "SHUTDOWN", "SUCCESS", f"Host service: {message}")
        QMessageBox.information(
            parent,
            Translations.tr("dialog.shutdown_successful.title"),
            Translations.tr("dialog.shutdown_successful.message", name=device_name, ip=device_ip),
        )
        status_fn(Translations.tr("status.shutdown_success", name=device_name), 0)
    else:
        config.add_log(device_name, "SHUTDOWN", "ERROR", f"Host service: {message}")
        # Distinguish authentication failures from connectivity problems
        if "Authentication failed" in message:
            QMessageBox.critical(
                parent,
                Translations.tr("dialog.host_service_auth_failed.title"),
                Translations.tr("dialog.host_service_auth_failed.message", name=device_name, ip=device_ip, error=message),
            )
        else:
            QMessageBox.critical(
                parent,
                Translations.tr("dialog.host_service_error.title"),
                Translations.tr("dialog.host_service_error.message", name=device_name, ip=device_ip, error=message),
            )
        status_fn(Translations.tr("status.shutdown_failed", name=device_name), 0)


def execute_shutdown(
    parent: QWidget,
    config: Any,
    device: dict,
    dialog: QDialog | None,
    status_fn: StatusFn = _noop_status,
) -> None:
    """Execute the remote shutdown sequence for *device*.

    *dialog* is the open confirmation dialog (closed via accept); pass
    ``None`` when no dialog is shown.
    """
    from PyQt6.QtWidgets import QApplication

    if dialog is not None:
        dialog.accept()  # Close the confirmation dialog

    device_name = device.get("name", "")
    device_ip = device.get("ip", "")
    username = device.get("username", "")
    password = device.get("password", "")

    # Dispatch on the device's shutdown method
    method = config.get_device_shutdown_method(device)
    if method == "host_service":
        _host_service_shutdown(
            parent, config, device_name, device_ip, username, password, status_fn
        )
        return

    status_fn(Translations.tr("status.shutting_down", name=device_name), 0)
    QApplication.processEvents()

    # Step 1: Connect to remote IPC$
    if username:
        # Delete any existing connection first
        delete_cmd: str = f'net use \\\\{device_ip} /delete /y'
        status_fn(Translations.tr("status.deleting_connection", name=device_name), 0)
        QApplication.processEvents()
        try:
            subprocess.run(
                delete_cmd, shell=True, capture_output=True, encoding='utf-8', errors='replace', timeout=15
            )
        except Exception:
            pass  # Ignore errors from delete — connection may not exist yet

        # Connect with username and password
        cmd: str = f'net use \\\\{device_ip}\\IPC$ /user:{username} {password}'
        status_fn(Translations.tr("status.connecting", name=device_name, ip=device_ip), 0)
        QApplication.processEvents()
    else:
        # Connect without credentials
        cmd: str = f'net use \\\\{device_ip}\\IPC$'
        status_fn(Translations.tr("status.connecting", name=device_name, ip=device_ip), 0)
        QApplication.processEvents()

    try:
        result: subprocess.CompletedProcess[str] = subprocess.run(
            cmd, shell=True, capture_output=True, encoding='utf-8', errors='replace', timeout=30
        )
        if result.returncode != 0:
            error_msg: str = result.stderr.strip() or result.stdout.strip()
            config.add_log(device_name, "SHUTDOWN", "ERROR", f"Connection failed: {error_msg}")
            QMessageBox.critical(
                parent, Translations.tr("dialog.connection_failed.title"),
                Translations.tr("dialog.connection_failed.message", name=device_name, ip=device_ip, error=error_msg)
            )
            status_fn(Translations.tr("status.shutdown_failed", name=device_name), 0)
            return
    except subprocess.TimeoutExpired:
        config.add_log(device_name, "SHUTDOWN", "ERROR", "Connection timed out")
        QMessageBox.critical(
            parent, Translations.tr("dialog.connection_timeout.title"),
            Translations.tr("dialog.connection_timeout.message", name=device_name, ip=device_ip)
        )
        status_fn(Translations.tr("status.shutdown_failed", name=device_name), 0)
        return
    except Exception as e:
        config.add_log(device_name, "SHUTDOWN", "ERROR", f"Connection error: {str(e)}")
        QMessageBox.critical(
            parent, Translations.tr("dialog.connection_error.title"),
            Translations.tr("dialog.connection_error.message", name=device_name, ip=device_ip, error=str(e))
        )
        status_fn(Translations.tr("status.shutdown_failed", name=device_name), 0)
        return

    # Step 2: Shutdown the remote PC
    shutdown_cmd: str = f'shutdown /m \\\\{device_ip} /s /t 0 /f'
    status_fn(Translations.tr("status.shutting_down_remote", name=device_name), 0)
    QApplication.processEvents()
    try:
        result: subprocess.CompletedProcess[str] = subprocess.run(
            shutdown_cmd, shell=True, capture_output=True, encoding='utf-8', errors='replace', timeout=30
        )
        if result.returncode != 0:
            error_msg: str = result.stderr.strip() or result.stdout.strip()
            config.add_log(device_name, "SHUTDOWN", "ERROR", f"Shutdown failed: {error_msg}")
            QMessageBox.critical(
                parent, Translations.tr("dialog.shutdown_failed.title"),
                Translations.tr("dialog.shutdown_failed.message", name=device_name, ip=device_ip, error=error_msg)
            )
            status_fn(Translations.tr("status.shutdown_failed", name=device_name), 0)
            return
    except subprocess.TimeoutExpired:
        config.add_log(device_name, "SHUTDOWN", "ERROR", "Shutdown command timed out")
        QMessageBox.critical(
            parent, Translations.tr("dialog.shutdown_timeout.title"),
            Translations.tr("dialog.shutdown_timeout.message", name=device_name, ip=device_ip)
        )
        status_fn(Translations.tr("status.shutdown_failed", name=device_name), 0)
        return
    except Exception as e:
        config.add_log(device_name, "SHUTDOWN", "ERROR", f"Shutdown error: {str(e)}")
        QMessageBox.critical(
            parent, Translations.tr("dialog.shutdown_error.title"),
            Translations.tr("dialog.shutdown_error.message", name=device_name, ip=device_ip, error=str(e))
        )
        status_fn(Translations.tr("status.shutdown_failed", name=device_name), 0)
        return

    config.add_log(device_name, "SHUTDOWN", "SUCCESS", "Shutdown initiated successfully")
    QMessageBox.information(
        parent, Translations.tr("dialog.shutdown_successful.title"),
        Translations.tr("dialog.shutdown_successful.message", name=device_name, ip=device_ip)
    )
    status_fn(Translations.tr("status.shutdown_success", name=device_name), 0)
