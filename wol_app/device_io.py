"""Device import/export shared by the classic dialogs and the modern UI.

The functions show their own file dialogs and result message boxes (with
*parent* as owner) and report success via return values, so both UIs can
simply call them and refresh their views afterwards.
"""

import json
from typing import Any

from PyQt6.QtWidgets import QFileDialog, QMessageBox

from wol_app.config import (
    BATCH_TIMEOUT_MAX_S,
    BATCH_TIMEOUT_MIN_S,
    DEFAULT_BATCH_TIMEOUT_S,
    MAX_BATCHES_PER_DEVICE,
    MAX_BATCH_SCRIPT_CHARS,
)
from wol_app.crypto import decrypt_password, encrypt_password, is_encrypted
from wol_app.translations import Translations
from wol_app.utils import validate_ip_or_hostname, validate_mac


def _sanitize_batches(raw: Any) -> list[dict]:
    """Normalise an imported ``batches`` list (defensive: foreign files)."""
    if not isinstance(raw, list):
        return []
    result: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        script = str(item.get("script", ""))
        if not script.strip():
            continue
        try:
            timeout = int(item.get("timeout", DEFAULT_BATCH_TIMEOUT_S))
        except (TypeError, ValueError):
            timeout = DEFAULT_BATCH_TIMEOUT_S
        result.append({
            "id": str(item.get("id", "")) or f"b{len(result) + 1}-imp",
            "name": str(item.get("name", ""))[:64],
            "script": script[:MAX_BATCH_SCRIPT_CHARS],
            "timeout": min(BATCH_TIMEOUT_MAX_S,
                           max(BATCH_TIMEOUT_MIN_S, timeout)),
        })
    return result[:MAX_BATCHES_PER_DEVICE]


def _apply_batches(config_manager: Any, device_id: str, batches: list[dict],
                   allow_batch: bool) -> None:
    """Write imported batches only when the file actually carried them."""
    if not batches:
        return
    config_manager.set_device_batches(device_id, batches)
    config_manager.set_device_allow_batch(device_id, allow_batch)


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
        entry = {
            "name": dev.get("name", ""),
            "mac": dev.get("mac", ""),
            "ip": dev.get("ip", ""),
            "username": dev.get("username", ""),
            "password": encrypt_password(dev.get("password", "")),
            "enabled": dev.get("enabled", True),
        }
        # Dashboard batches (scripts may contain credentials, just like the
        # password field — they travel with the device).
        batches = dev.get("batches") or []
        if batches:
            entry["batches"] = batches
            entry["allow_batch"] = bool(dev.get("allow_batch", False))
        export_data.append(entry)

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

        ip = str(dev_data.get("ip", "") or "").strip()
        if ip and not validate_ip_or_hostname(ip):
            errors.append(
                Translations.tr("dialog.import.invalid_ip", line=idx + 1, name=name)
            )
            continue

        batches = _sanitize_batches(dev_data.get("batches"))
        allow_batch = bool(dev_data.get("allow_batch", False))
        existing = config_manager.get_device_by_name(name)
        if existing:
            # Update existing device
            pw = dev_data.get("password", "")
            if is_encrypted(pw):
                pw: str = decrypt_password(pw)
            config_manager.update_device(
                existing["id"],
                mac=mac,
                ip=ip,
                username=dev_data.get("username", ""),
                password=pw,
                enabled=dev_data.get("enabled", True),
            )
            _apply_batches(config_manager, existing["id"], batches,
                           allow_batch)
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
                    ip=ip,
                    username=dev_data.get("username", ""),
                    password=pw,
                    enabled=dev_data.get("enabled", True),
                )
                _apply_batches(config_manager, device["id"], batches,
                               allow_batch)
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
