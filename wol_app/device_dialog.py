"""Device Management Dialog for Wake-on-LAN Application."""

import json
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QMessageBox, QGroupBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox,
    QFileDialog,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from wol_app.network_scan_dialog import NetworkScanDialog


class DeviceDialog(QDialog):
    """Dialog for adding/editing a device."""

    device_saved = pyqtSignal(dict)  # Emits device dict on save

    def __init__(self, config_manager, device: dict = None, parent=None):
        super().__init__(parent)
        self.config = config_manager
        self.editing_device = device
        self.setWindowTitle("Edit Device" if device else "Add Device")
        self.setMinimumWidth(450)
        self._setup_ui()
        if device:
            self._fill_form(device)

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Name
        name_layout = QFormLayout()
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g., Office PC, Gaming Rig")
        name_layout.addRow("Device Name:", self.name_input)

        # MAC Address
        mac_layout = QFormLayout()
        self.mac_input = QLineEdit()
        self.mac_input.setPlaceholderText("e.g., AA:BB:CC:DD:EE:FF")
        mac_layout.addRow("MAC Address:", self.mac_input)

        # Optional IP (for ping status checks)
        ip_layout = QFormLayout()
        self.ip_input = QLineEdit()
        self.ip_input.setPlaceholderText("e.g., 192.168.1.100 (optional)")
        ip_layout.addRow("IP Address:", self.ip_input)

        # Enabled checkbox
        self.enabled_check = QCheckBox("Device is enabled")
        self.enabled_check.setChecked(True)

        # Buttons
        btn_layout = QHBoxLayout()
        self.save_btn = QPushButton("Save" if not self.editing_device else "Update")
        self.save_btn.clicked.connect(self._save)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.cancel_btn)

        layout.addLayout(name_layout)
        layout.addLayout(mac_layout)
        layout.addLayout(ip_layout)
        layout.addWidget(self.enabled_check)
        layout.addLayout(btn_layout)

    def _fill_form(self, device: dict):
        self.name_input.setText(device.get("name", ""))
        self.mac_input.setText(device.get("mac", ""))
        self.ip_input.setText(device.get("ip", ""))
        self.enabled_check.setChecked(device.get("enabled", True))

    def _save(self):
        name = self.name_input.text().strip()
        mac = self.mac_input.text().strip()
        ip = self.ip_input.text().strip()

        if not name:
            QMessageBox.warning(self, "Missing Name", "Please enter a device name.")
            return
        if not mac:
            QMessageBox.warning(self, "Missing MAC", "Please enter a MAC address.")
            return
        if not self.config._validate_mac(mac):
            QMessageBox.warning(self, "Invalid MAC", "MAC address format is invalid.\nUse format: AA:BB:CC:DD:EE:FF")
            return

        if self.editing_device:
            updates = {"name": name, "mac": mac, "enabled": self.enabled_check.isChecked()}
            if ip:
                updates["ip"] = ip
            self.config.update_device(self.editing_device["id"], **updates)
            # Re-fetch updated device
            updated = self.config.get_device_by_id(self.editing_device["id"])
            self.device_saved.emit(updated)
        else:
            device = self.config.add_device(name, mac)
            if device:
                if ip:
                    self.config.update_device(device["id"], ip=ip)
                self.device_saved.emit(self.config.get_device_by_id(device["id"]))
            else:
                QMessageBox.warning(self, "Error", "Failed to add device.")
                return

        self.accept()


class DeviceManagerDialog(QDialog):
    """Full device management dialog - list all devices, add/edit/delete."""

    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.config = config_manager
        self.setWindowTitle("Manage Devices")
        self.setMinimumSize(700, 500)
        self._setup_ui()
        self._refresh_table()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Device Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Name", "MAC Address", "IP Address", "Enabled", "Status", ""])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(1, 160)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        # Buttons
        btn_layout = QHBoxLayout()
        add_btn = QPushButton("+ Add Device")
        add_btn.clicked.connect(self._add_device)
        edit_btn = QPushButton("Edit")
        edit_btn.clicked.connect(self._edit_device)
        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(self._delete_device)
        import_btn = QPushButton("Import")
        import_btn.clicked.connect(self._import_devices)
        export_btn = QPushButton("Export")
        export_btn.clicked.connect(self._export_devices)
        refresh_btn = QPushButton("Netzwerk scannen")
        refresh_btn.clicked.connect(self._scan_network)

        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(edit_btn)
        btn_layout.addWidget(delete_btn)
        btn_layout.addWidget(import_btn)
        btn_layout.addWidget(export_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(refresh_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        layout.addWidget(self.table)
        layout.addLayout(btn_layout)

    def _refresh_table(self):
        self.table.setRowCount(0)
        for device in self.config.get_devices():
            row = self.table.rowCount()
            self.table.insertRow(row)

            self.table.setItem(row, 0, QTableWidgetItem(device.get("name", "")))
            self.table.setItem(row, 1, QTableWidgetItem(device.get("mac", "")))
            self.table.setItem(row, 2, QTableWidgetItem(device.get("ip", "")))

            enabled_check = QCheckBox()
            enabled_check.setChecked(device.get("enabled", True))
            enabled_check.toggled.connect(
                lambda checked, d_id=device["id"]: self.config.update_device(d_id, enabled=checked)
            )
            self.table.setCellWidget(row, 3, enabled_check)

            status_text = device.get("_status", "unknown")
            status_item = QTableWidgetItem(status_text)
            if status_text == "online":
                status_item.setForeground(Qt.GlobalColor.darkGreen)
            elif status_text == "offline":
                status_item.setForeground(Qt.GlobalColor.darkRed)
            self.table.setItem(row, 4, status_item)

    def _add_device(self):
        dialog = DeviceDialog(self.config, parent=self)
        dialog.device_saved.connect(lambda d: self._refresh_table())
        dialog.exec()

    def _edit_device(self):
        current_row = self.table.currentRow()
        if current_row < 0:
            QMessageBox.information(self, "Select Device", "Please select a device to edit.")
            return

        devices = self.config.get_devices()
        if current_row >= len(devices):
            return
        device = devices[current_row]

        dialog = DeviceDialog(self.config, device=device, parent=self)
        dialog.device_saved.connect(lambda d: self._refresh_table())
        dialog.exec()

    def _delete_device(self):
        current_row = self.table.currentRow()
        if current_row < 0:
            QMessageBox.information(self, "Select Device", "Please select a device to delete.")
            return

        devices = self.config.get_devices()
        if current_row >= len(devices):
            return
        device = devices[current_row]

        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete '{device['name']}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.config.remove_device(device["id"])
            self._refresh_table()

    def _scan_network(self):
        """Open network scan dialog to discover active devices."""
        dialog = NetworkScanDialog(self.config, parent=self)
        dialog.exec()
        self._refresh_table()

    def _export_devices(self):
        """Export configured devices to a JSON file."""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Devices", "", "JSON Files (*.json)"
        )
        if not file_path:
            return

        devices = self.config.get_devices()
        # Export only relevant fields (exclude internal/status fields)
        export_data = []
        for dev in devices:
            export_data.append({
                "name": dev.get("name", ""),
                "mac": dev.get("mac", ""),
                "ip": dev.get("ip", ""),
                "enabled": dev.get("enabled", True),
            })

        try:
            with open(file_path, "w") as f:
                json.dump(export_data, f, indent=2)
            QMessageBox.information(self, "Export Success", f"{len(export_data)} device(s) exported to:\n{file_path}")
        except IOError as e:
            QMessageBox.critical(self, "Export Error", f"Failed to save file:\n{e}")

    def _import_devices(self):
        """Import devices from a JSON file. Existing devices with the same name are overwritten."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Devices", "", "JSON Files (*.json)"
        )
        if not file_path:
            return

        try:
            with open(file_path, "r") as f:
                import_data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            QMessageBox.critical(self, "Import Error", f"Failed to read file:\n{e}")
            return

        if not isinstance(import_data, list):
            QMessageBox.critical(self, "Import Error", "Invalid file format. Expected a JSON array.")
            return

        imported = 0
        updated = 0
        errors = []

        for idx, dev_data in enumerate(import_data):
            name = dev_data.get("name", "").strip()
            mac = dev_data.get("mac", "").strip()

            if not name or not mac:
                errors.append(f"Zeile {idx + 1}: Fehlender Name oder MAC-Adresse.")
                continue

            if not self.config._validate_mac(mac):
                errors.append(f"Zeile {idx + 1} ('{name}'): Ungültiges MAC-Format.")
                continue

            existing = self.config.get_device_by_name(name)
            if existing:
                # Update existing device
                self.config.update_device(
                    existing["id"],
                    mac=mac,
                    ip=dev_data.get("ip", ""),
                    enabled=dev_data.get("enabled", True),
                )
                updated += 1
            else:
                # Add new device
                device = self.config.add_device(name, mac)
                if device:
                    self.config.update_device(
                        device["id"],
                        ip=dev_data.get("ip", ""),
                        enabled=dev_data.get("enabled", True),
                    )
                    imported += 1

        # Build summary message
        summary_lines = [f"Neu importiert: {imported}", f"Aktualisiert: {updated}"]
        if errors:
            summary_lines.append(f"Fehler: {len(errors)}")
            summary_lines.extend(errors[:5])  # Show max 5 errors
            if len(errors) > 5:
                summary_lines.append(f"... und {len(errors) - 5} weitere Fehler")

        QMessageBox.information(self, "Import Ergebnis", "\n".join(summary_lines))
        self._refresh_table()
