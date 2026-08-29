"""Device import/export shared by the classic dialogs and the modern UI.

The functions show their own file dialogs and result message boxes (with
*parent* as owner) and report success via return values, so both UIs can
simply call them and refresh their views afterwards.
"""

import json
from typing import Any

from PyQt6.QtWidgets import QFileDialog, QMessageBox

from wol_app.crypto import decrypt_password, encrypt_password, is_encrypted
from wol_app.translations import Translations
from wol_app.utils import validate_mac


def export_devices(config_manager: Any, parent=None) -> bool:
    """Export configured devices to a JSON file.

    Returns True when the export succeeded (view should refresh is not
    required — export does not modify data).
    """
    file_path, _ = QFileDialog.getSaveFileName(
        parent, Translations.tr("dialog.export.title"), "", "JSON Files (*.json)"
    )
    if not file_path:
        return False

    devices = config_manager.get_devices()
    # Export only relevant fields (exclude internal/status fields).
    # Passwords are encrypted in the export file for security.
    export_data = []
    for dev in devices:
        export_data.append({
            "name": dev.get("name", ""),
            "mac": dev.get("mac", ""),
            "ip": dev.get("ip", ""),
            "username": dev.get("username", ""),
            "password": encrypt_password(dev.get("password", "")),
            "enabled": dev.get("enabled", True),
        })

    try:
        with open(file_path, "w") as f:
            json.dump(export_data, f, indent=2)
        QMessageBox.information(
            parent,
            Translations.tr("dialog.export.success.title"),
            Translations.tr("dialog.export.success.message", count=len(export_data), path=file_path),
        )
        return True
    except OSError as e:
        QMessageBox.critical(
            parent,
            Translations.tr("dialog.export.error.title"),
            Translations.tr("dialog.export.error.message", error=str(e)),
        )
        return False


def import_devices(config_manager: Any, parent=None) -> bool:
    """Import devices from a JSON file. Existing devices with the same name are overwritten.

    Returns True when at least one device was imported or updated.
    """
    file_path, _ = QFileDialog.getOpenFileName(
        parent, Translations.tr("dialog.import.title"), "", "JSON Files (*.json)"
    )
    if not file_path:
        return False

    try:
        with open(file_path) as f:
            import_data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        QMessageBox.critical(
            parent,
            Translations.tr("dialog.import.error.title"),
            Translations.tr("dialog.import.read_error", error=str(e)),
        )
        return False

    if not isinstance(import_data, list):
        QMessageBox.critical(
            parent,
            Translations.tr("dialog.import.error.title"),
            Translations.tr("dialog.import.invalid_format"),
        )
        return False

    imported = 0
    updated = 0
    errors = []

    for idx, dev_data in enumerate(import_data):
        name = dev_data.get("name", "").strip()
        mac = dev_data.get("mac", "").strip()

        if not name or not mac:
            errors.append(
                Translations.tr("dialog.import.missing_field", line=idx + 1)
            )
            continue

        if not validate_mac(mac):
            errors.append(
                Translations.tr("dialog.import.invalid_mac", line=idx + 1, name=name)
            )
            continue

        existing = config_manager.get_device_by_name(name)
        if existing:
            # Update existing device
            pw = dev_data.get("password", "")
            if is_encrypted(pw):
                pw: str = decrypt_password(pw)
            config_manager.update_device(
                existing["id"],
                mac=mac,
                ip=dev_data.get("ip", ""),
                username=dev_data.get("username", ""),
                password=pw,
                enabled=dev_data.get("enabled", True),
            )
            updated += 1
        else:
            # Add new device
            device = config_manager.add_device(name, mac)
            if device:
                pw = dev_data.get("password", "")
                if is_encrypted(pw):
                    pw: str = decrypt_password(pw)
                config_manager.update_device(
                    device["id"],
                    ip=dev_data.get("ip", ""),
                    username=dev_data.get("username", ""),
                    password=pw,
                    enabled=dev_data.get("enabled", True),
                )
                imported += 1

    # Build summary message
    summary_lines: list[str] = [
        Translations.tr("dialog.import.summary.imported", count=imported),
        Translations.tr("dialog.import.summary.updated", count=updated),
    ]
    if errors:
        summary_lines.append(
            Translations.tr("dialog.import.summary.errors", count=len(errors))
        )
        summary_lines.extend(errors[:5])  # Show max 5 errors
        if len(errors) > 5:
            summary_lines.append(
                Translations.tr("dialog.import.summary.more_errors", count=len(errors) - 5)
            )

    QMessageBox.information(
        parent,
        Translations.tr("dialog.import.result.title"),
        "\n".join(summary_lines),
    )
    return imported > 0 or updated > 0
