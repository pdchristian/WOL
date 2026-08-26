"""Manage screen: device administration with import/export.

Provides the "Verwalten" view of the new design: a searchable device table,
actions to add/edit/delete devices, a network scan entry point, and JSON
import/export dialogs.
"""

import json

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from wol_app.crypto import decrypt_password, encrypt_password, is_encrypted
from wol_app.device_dialog import DeviceDialog
from wol_app.network_scan_dialog import NetworkScanDialog
from wol_app.translations import Translations
from wol_app.utils import validate_mac


class ManageScreen(QWidget):
    """Device administration screen (scan, add/edit, import/export)."""

    def __init__(self, config, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.config = config
        self._build_ui()
        self.refresh()

    # ---- UI ---------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(18)

        # Header: title + search
        header = QHBoxLayout()
        title = QLabel(Translations.tr("screen.manage.title"))
        header.addWidget(title)
        header.addStretch()
        self.search_input = QLineEdit()
        self.search_input.setObjectName("SearchBox")
        self.search_input.setPlaceholderText(Translations.tr("ui.search_devices_placeholder"))
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self.refresh)
        header.addWidget(self.search_input, 1)
        root.addLayout(header)

        # Toolbar
        toolbar = QHBoxLayout()
        self.add_btn = QPushButton(Translations.tr("device_manager.button.add"))
        self.add_btn.setObjectName("primaryButton")
        self.add_btn.clicked.connect(self._add_device)
        self.scan_btn = QPushButton(Translations.tr("device_manager.button.scan_network"))
        self.scan_btn.clicked.connect(self._scan_network)
        self.import_btn = QPushButton(Translations.tr("device_manager.button.import"))
        self.import_btn.clicked.connect(self._import_devices)
        self.export_btn = QPushButton(Translations.tr("device_manager.button.export"))
        self.export_btn.clicked.connect(self._export_devices)
        toolbar.addWidget(self.add_btn)
        toolbar.addWidget(self.scan_btn)
        toolbar.addWidget(self.import_btn)
        toolbar.addWidget(self.export_btn)
        toolbar.addStretch()
        root.addLayout(toolbar)

        # Device table
        self.table = QTableWidget()
        self.table.setObjectName("DeviceTable")
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels([
            Translations.tr("table.header.name"),
            Translations.tr("table.header.mac"),
            Translations.tr("table.header.ip"),
            Translations.tr("table.header.status"),
        ])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        header_view = self.table.horizontalHeader()
        header_view.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header_view.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.itemDoubleClicked.connect(lambda item: self._edit_device())
        root.addWidget(self.table)

    # ---- Data / refresh ---------------------------------------------------

    def _filtered_devices(self) -> list:
        query = self.search_input.text().strip().lower()
        devices = self.config.get_devices()
        if not query:
            return devices
        fields = ("name", "mac", "ip", "username")
        return [
            d for d in devices
            if any(query in str(d.get(f, "")).lower() for f in fields)
        ]

    def refresh(self) -> None:
        self.table.setRowCount(0)
        for dev in self._filtered_devices():
            row = self.table.rowCount()
            self.table.insertRow(row)
            name_item = QTableWidgetItem(dev.get("name", ""))
            name_item.setData(Qt.ItemDataRole.UserRole, dev.get("id", ""))
            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, QTableWidgetItem(dev.get("mac", "")))
            self.table.setItem(row, 2, QTableWidgetItem(dev.get("ip", "")))
            status_key = "status.online" if dev.get("enabled", True) else "device.disabled"
            self.table.setItem(row, 3, QTableWidgetItem(Translations.tr(status_key)))

    def _selected_device(self) -> dict | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if item is None:
            return None
        return self.config.get_device_by_id(item.data(Qt.ItemDataRole.UserRole))

    # ---- Actions ----------------------------------------------------------

    def _add_device(self) -> None:
        dialog = DeviceDialog(self.config, parent=self)
        dialog.device_saved.connect(lambda d: self.refresh())
        dialog.exec()

    def _edit_device(self) -> None:
        device = self._selected_device()
        if device is None:
            QMessageBox.information(
                self, Translations.tr("dialog.select_device.title"),
                Translations.tr("dialog.select_device.message"),
            )
            return
        dialog = DeviceDialog(self.config, device=device, parent=self)
        dialog.device_saved.connect(lambda d: self.refresh())
        dialog.exec()

    def _delete_device(self) -> None:
        device = self._selected_device()
        if device is None:
            QMessageBox.information(
                self, Translations.tr("dialog.select_device.title"),
                Translations.tr("dialog.select_device.message"),
            )
            return
        reply = QMessageBox.question(
            self,
            Translations.tr("dialog.confirm_delete.title"),
            Translations.tr("dialog.confirm_delete.message", name=device["name"]),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.config.remove_device(device["id"])
            self.refresh()

    def _scan_network(self) -> None:
        dialog: NetworkScanDialog = NetworkScanDialog(self.config, parent=self)
        dialog.exec()
        self.refresh()

    # ---- Import / Export --------------------------------------------------

    def _export_devices(self) -> None:
        """Export configured devices to a JSON file (passwords encrypted)."""
        file_path, _ = QFileDialog.getSaveFileName(
            self, Translations.tr("dialog.export.title"), "", "JSON Files (*.json)"
        )
        if not file_path:
            return

        export_data = []
        for dev in self.config.get_devices():
            export_data.append({
                "name": dev.get("name", ""),
                "mac": dev.get("mac", ""),
                "ip": dev.get("ip", ""),
                "username": dev.get("username", ""),
                "password": encrypt_password(dev.get("password", "")),
                "enabled": dev.get("enabled", True),
            })

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=2)
            QMessageBox.information(
                self,
                Translations.tr("dialog.export.success.title"),
                Translations.tr("dialog.export.success.message", count=len(export_data), path=file_path),
            )
        except OSError as e:
            QMessageBox.critical(
                self,
                Translations.tr("dialog.export.error.title"),
                Translations.tr("dialog.export.error.message", error=str(e)),
            )

    def _import_devices(self) -> None:
        """Import devices from a JSON file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, Translations.tr("dialog.import.title"), "", "JSON Files (*.json)"
        )
        if not file_path:
            return

        try:
            with open(file_path, encoding="utf-8") as f:
                import_data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            QMessageBox.critical(
                self,
                Translations.tr("dialog.import.error.title"),
                Translations.tr("dialog.import.read_error", error=str(e)),
            )
            return

        if not isinstance(import_data, list):
            QMessageBox.critical(
                self,
                Translations.tr("dialog.import.error.title"),
                Translations.tr("dialog.import.invalid_format"),
            )
            return

        imported = 0
        updated = 0
        errors = []

        for idx, dev_data in enumerate(import_data):
            name = dev_data.get("name", "").strip()
            mac = dev_data.get("mac", "").strip()

            if not name or not mac:
                errors.append(Translations.tr("dialog.import.missing_field", line=idx + 1))
                continue

            if not validate_mac(mac):
                errors.append(Translations.tr("dialog.import.invalid_mac", line=idx + 1, name=name))
                continue

            existing = self.config.get_device_by_name(name)
            pw = dev_data.get("password", "")
            if is_encrypted(pw):
                pw = decrypt_password(pw)

            if existing:
                self.config.update_device(
                    existing["id"],
                    mac=mac,
                    ip=dev_data.get("ip", ""),
                    username=dev_data.get("username", ""),
                    password=pw,
                    enabled=dev_data.get("enabled", True),
                )
                updated += 1
            else:
                device = self.config.add_device(name, mac)
                if device:
                    self.config.update_device(
                        device["id"],
                        ip=dev_data.get("ip", ""),
                        username=dev_data.get("username", ""),
                        password=pw,
                        enabled=dev_data.get("enabled", True),
                    )
                    imported += 1

        summary = [
            Translations.tr("dialog.import.summary.imported", count=imported),
            Translations.tr("dialog.import.summary.updated", count=updated),
        ]
        if errors:
            summary.append(Translations.tr("dialog.import.summary.errors", count=len(errors)))
            summary.extend(errors[:5])
            if len(errors) > 5:
                summary.append(Translations.tr("dialog.import.summary.more_errors", count=len(errors) - 5))

        QMessageBox.information(
            self,
            Translations.tr("dialog.import.result.title"),
            "\n".join(summary),
        )
        self.refresh()
