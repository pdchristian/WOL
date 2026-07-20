"""Device Management Dialog for Wake-on-LAN Application."""

import json
import re
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QMessageBox, QGroupBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox,
    QFileDialog, QComboBox,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from wol_app.translations import Translations
from wol_app.network_scan_dialog import NetworkScanDialog
from wol_app.crypto import encrypt_password, decrypt_password, is_encrypted


def _validate_device_name(name: str) -> bool:
    """Validate device name for safety."""
    if not name or len(name) > 64:
        return False
    # No control characters
    if any(ord(c) < 32 or ord(c) > 126 for c in name):
        return False
    forbidden_chars = ['<', '>', '"', "'", ';', '|', '&', '$', '`', '\\']
    if any(char in name for char in forbidden_chars):
        return False
    return True


def _validate_mac(mac: str) -> bool:
    """Validate MAC address format."""
    mac_pattern = r'^([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}$'
    return bool(re.match(mac_pattern, mac.strip()))


def _validate_username(username: str) -> bool:
    """Validate username for safety."""
    if not username:
        return True
    if len(username) > 64:
        return False
    if any(ord(c) < 32 or ord(c) > 126 for c in username):
        return False
    return True


def _validate_password(password: str) -> bool:
    """Validate password for safety."""
    if not password:
        return True
    if len(password) > 128:
        return False
    if any(ord(c) > 126 for c in password):
        return False
    return True


class DeviceDialog(QDialog):
    """Dialog for adding/editing a device."""

    device_saved = pyqtSignal(dict)  # Emits device dict on save

    def __init__(self, config_manager, device: dict = None, parent=None):
        super().__init__(parent)
        self.config = config_manager
        self.editing_device = device
        self.setWindowTitle(Translations.tr("device_dialog.title.edit") if device else Translations.tr("device_dialog.title.add"))
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
        name_layout.addRow(Translations.tr("device_dialog.label.name"), self.name_input)

        # MAC Address
        mac_layout = QFormLayout()
        self.mac_input = QLineEdit()
        self.mac_input.setPlaceholderText("e.g., AA:BB:CC:DD:EE:FF")
        mac_layout.addRow(Translations.tr("device_dialog.label.mac"), self.mac_input)

        # Optional IP (for ping status checks)
        ip_layout = QFormLayout()
        self.ip_input = QLineEdit()
        self.ip_input.setPlaceholderText("e.g., 192.168.1.100 (optional)")
        ip_layout.addRow(Translations.tr("device_dialog.label.ip"), self.ip_input)

        # Username
        username_layout = QFormLayout()
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Benutzername (optional)")
        username_layout.addRow(Translations.tr("device_dialog.label.user"), self.username_input)

        # Password (displayed as asterisks)
        password_layout = QFormLayout()
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText(Translations.tr("device_dialog.placeholder.password"))
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        password_layout.addRow(Translations.tr("device_dialog.label.password"), self.password_input)

        # Enabled checkbox
        self.enabled_check = QCheckBox(Translations.tr("device_dialog.enabled"))
        self.enabled_check.setChecked(True)

        # Buttons
        btn_layout = QHBoxLayout()
        self.save_btn = QPushButton(Translations.tr("device_dialog.button.save") if not self.editing_device else Translations.tr("device_dialog.button.update"))
        self.save_btn.clicked.connect(self._save)
        self.cancel_btn = QPushButton(Translations.tr("device_dialog.button.cancel"))
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.cancel_btn)

        layout.addLayout(name_layout)
        layout.addLayout(mac_layout)
        layout.addLayout(ip_layout)
        layout.addLayout(username_layout)
        layout.addLayout(password_layout)
        layout.addWidget(self.enabled_check)
        layout.addLayout(btn_layout)

    def _fill_form(self, device: dict):
        self.name_input.setText(device.get("name", ""))
        self.mac_input.setText(device.get("mac", ""))
        self.ip_input.setText(device.get("ip", ""))
        self.username_input.setText(device.get("username", ""))
        self.password_input.setText(device.get("password", ""))
        self.enabled_check.setChecked(device.get("enabled", True))

    def _save(self):
        name = self.name_input.text().strip()
        mac = self.mac_input.text().strip()
        ip = self.ip_input.text().strip()

        if not name:
            QMessageBox.warning(self, Translations.tr("dialog.error.title"), Translations.tr("device_dialog.error.missing_name"))
            return
        if not _validate_device_name(name):
            QMessageBox.warning(self, Translations.tr("dialog.error.title"), Translations.tr("device_dialog.error.invalid_name"))
            return
        if not mac:
            QMessageBox.warning(self, Translations.tr("dialog.error.title"), Translations.tr("device_dialog.error.missing_mac"))
            return
        if not _validate_mac(mac):
            QMessageBox.warning(self, Translations.tr("dialog.error.title"), Translations.tr("device_dialog.error.invalid_mac"))
            return

        username = self.username_input.text().strip()
        password = self.password_input.text().strip()

        # Validate username and password
        if username and not _validate_username(username):
            QMessageBox.warning(self, Translations.tr("dialog.error.title"), Translations.tr("device_dialog.error.invalid_username"))
            return
        if password and not _validate_password(password):
            QMessageBox.warning(self, Translations.tr("dialog.error.title"), Translations.tr("device_dialog.error.invalid_password"))
            return

        if self.editing_device:
            updates = {"name": name, "mac": mac, "enabled": self.enabled_check.isChecked()}
            if ip:
                updates["ip"] = ip
            if username:
                updates["username"] = username
            if password:
                updates["password"] = password
            self.config.update_device(self.editing_device["id"], **updates)
            # Re-fetch updated device
            updated = self.config.get_device_by_id(self.editing_device["id"])
            self.device_saved.emit(updated)
        else:
            device = self.config.add_device(name, mac)
            if device:
                if ip:
                    self.config.update_device(device["id"], ip=ip)
                if username:
                    self.config.update_device(device["id"], username=username)
                if password:
                    self.config.update_device(device["id"], password=password)
                self.device_saved.emit(self.config.get_device_by_id(device["id"]))
            else:
                QMessageBox.warning(self, Translations.tr("dialog.error.title"), Translations.tr("device_dialog.error.save_failed"))
                return

        # Clear password from input field for security
        self.password_input.clear()
        self.accept()


class DeviceManagerDialog(QDialog):
    """Full device management dialog - list all devices, add/edit/delete."""

    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.config = config_manager
        self.setWindowTitle(Translations.tr("device_manager.title"))
        self.setMinimumSize(700, 500)
        
        # Load sort settings from config
        sort_settings = self.config.get_device_sort_settings()
        self.sort_column = sort_settings["sort_column"]
        self.sort_order = Qt.SortOrder.AscendingOrder if sort_settings["sort_order"] == "ascending" else Qt.SortOrder.DescendingOrder
        
        self._setup_ui()
        self._refresh_table()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Sort Control
        sort_layout = QHBoxLayout()
        sort_label = QLabel(Translations.tr("device_manager.sort_by"))
        self.sort_combo = QComboBox()
        self.sort_combo.addItems([
            Translations.tr("device_manager.sort.name"),
            Translations.tr("device_manager.sort.mac"),
            Translations.tr("device_manager.sort.ip"),
            Translations.tr("device_manager.sort.username")
        ])
        self.sort_combo.currentIndexChanged.connect(self._change_sort)
        sort_layout.addWidget(sort_label)
        sort_layout.addWidget(self.sort_combo)
        sort_layout.addStretch()

        # Device Table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            Translations.tr("device_manager.table.header.name"),
            Translations.tr("device_manager.table.header.mac"),
            Translations.tr("device_manager.table.header.ip"),
            Translations.tr("device_manager.table.header.username"),
            Translations.tr("device_manager.table.header.password")
        ])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(1, 160)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(3, 120)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(4, 120)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSortingEnabled(True)
        self.table.itemDoubleClicked.connect(lambda item: self._edit_device())

        layout.addLayout(sort_layout)

        # Buttons
        btn_layout = QHBoxLayout()
        add_btn = QPushButton(Translations.tr("device_manager.button.add"))
        add_btn.clicked.connect(self._add_device)
        edit_btn = QPushButton(Translations.tr("device_manager.button.edit"))
        edit_btn.clicked.connect(self._edit_device)
        delete_btn = QPushButton(Translations.tr("device_manager.button.delete"))
        delete_btn.clicked.connect(self._delete_device)
        import_btn = QPushButton(Translations.tr("device_manager.button.import"))
        import_btn.clicked.connect(self._import_devices)
        export_btn = QPushButton(Translations.tr("device_manager.button.export"))
        export_btn.clicked.connect(self._export_devices)
        refresh_btn = QPushButton(Translations.tr("device_manager.button.scan_network"))
        refresh_btn.clicked.connect(self._scan_network)

        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(edit_btn)
        btn_layout.addWidget(delete_btn)
        btn_layout.addWidget(import_btn)
        btn_layout.addWidget(export_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(refresh_btn)

        close_btn = QPushButton(Translations.tr("device_manager.button.close"))
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        layout.addWidget(self.table)
        layout.addLayout(btn_layout)

    def _get_ip_key(self, ip_str):
        """Convert IP address string to a tuple of integers for proper numerical sorting."""
        try:
            parts = list(map(int, ip_str.split('.') if ip_str else [0, 0, 0, 0]))
            # Pad with zeros if not exactly 4 parts
            while len(parts) < 4:
                parts.append(0)
            return tuple(parts)
        except (ValueError, AttributeError):
            return (0, 0, 0, 0)

    def _get_sort_key(self, device, sort_column):
        """Get sort key for a device based on sort column with special handling for IPs."""
        sort_key_map = {
            0: "name",  # Name
            1: "mac",  # MAC Address
            2: "ip",   # IP Address
            3: "username",  # Username
        }
        
        # Ensure sort_column is within valid range for backwards compatibility
        if sort_column < 0 or sort_column >= len(sort_key_map):
            sort_column = 0  # Default to name
        
        key = sort_key_map.get(sort_column, "name")
        value = device.get(key, "")
        
        # Special handling for IP addresses
        if sort_column == 2:  # IP Address
            return self._get_ip_key(value)
        
        return value

    def _get_sorted_devices(self):
        devices = self.config.get_devices()
        
        return sorted(devices, key=lambda d: self._get_sort_key(d, self.sort_column), reverse=(self.sort_order == Qt.SortOrder.DescendingOrder))

    def _change_sort(self, index):
        self.sort_column = index
        sort_order = "ascending" if self.sort_order == Qt.SortOrder.AscendingOrder else "descending"
        self.config.set_device_sort_settings(self.sort_column, sort_order)
        self._refresh_table()

    def _refresh_table(self):
        self.table.setRowCount(0)
        sorted_devices = self._get_sorted_devices()
        
        for device in sorted_devices:
            row = self.table.rowCount()
            self.table.insertRow(row)

            self.table.setItem(row, 0, QTableWidgetItem(device.get("name", "")))
            self.table.setItem(row, 1, QTableWidgetItem(device.get("mac", "")))
            self.table.setItem(row, 2, QTableWidgetItem(device.get("ip", "")))
            self.table.setItem(row, 3, QTableWidgetItem(device.get("username", "")))
            
            # Password column - display as asterisks
            password = device.get("password", "")
            password_display = "*" * len(password) if password else ""
            self.table.setItem(row, 4, QTableWidgetItem(password_display))

    def _add_device(self):
        dialog = DeviceDialog(self.config, parent=self)
        dialog.device_saved.connect(lambda d: self._refresh_table())
        dialog.exec()

    def _edit_device(self):
        current_row = self.table.currentRow()
        if current_row < 0:
            QMessageBox.information(self, Translations.tr("dialog.select_device.title"), Translations.tr("dialog.select_device.message"))
            return

        sorted_devices = self._get_sorted_devices()
        if current_row >= len(sorted_devices):
            return
        device = sorted_devices[current_row]

        dialog = DeviceDialog(self.config, device=device, parent=self)
        dialog.device_saved.connect(lambda d: self._refresh_table())
        dialog.exec()

    def _delete_device(self):
        current_row = self.table.currentRow()
        if current_row < 0:
            QMessageBox.information(
                self,
                Translations.tr("dialog.select_device.title"),
                Translations.tr("dialog.select_device.message"),
            )
            return

        sorted_devices = self._get_sorted_devices()
        if current_row >= len(sorted_devices):
            return
        device = sorted_devices[current_row]

        reply = QMessageBox.question(
            self,
            Translations.tr("dialog.confirm_delete.title"),
            Translations.tr("dialog.confirm_delete.message", name=device["name"]),
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
            self, Translations.tr("dialog.export.title"), "", "JSON Files (*.json)"
        )
        if not file_path:
            return

        devices = self.config.get_devices()
        # Export only relevant fields (exclude internal/status fields)
        # Passwords are encrypted in the export file for security
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
                self,
                Translations.tr("dialog.export.success.title"),
                Translations.tr("dialog.export.success.message", count=len(export_data), path=file_path),
            )
        except IOError as e:
            QMessageBox.critical(
                self,
                Translations.tr("dialog.export.error.title"),
                Translations.tr("dialog.export.error.message", error=str(e)),
            )

    def _import_devices(self):
        """Import devices from a JSON file. Existing devices with the same name are overwritten."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, Translations.tr("dialog.import.title"), "", "JSON Files (*.json)"
        )
        if not file_path:
            return

        try:
            with open(file_path, "r") as f:
                import_data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
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
                errors.append(
                    Translations.tr("dialog.import.missing_field", line=idx + 1)
                )
                continue

            if not self.config._validate_mac(mac):
                errors.append(
                    Translations.tr("dialog.import.invalid_mac", line=idx + 1, name=name)
                )
                continue

            existing = self.config.get_device_by_name(name)
            if existing:
                # Update existing device
                pw = dev_data.get("password", "")
                if is_encrypted(pw):
                    pw = decrypt_password(pw)
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
                # Add new device
                device = self.config.add_device(name, mac)
                if device:
                    pw = dev_data.get("password", "")
                    if is_encrypted(pw):
                        pw = decrypt_password(pw)
                    self.config.update_device(
                        device["id"],
                        ip=dev_data.get("ip", ""),
                        username=dev_data.get("username", ""),
                        password=pw,
                        enabled=dev_data.get("enabled", True),
                    )
                    imported += 1

        # Build summary message
        summary_lines = [
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
            self,
            Translations.tr("dialog.import.result.title"),
            "\n".join(summary_lines),
        )
        self._refresh_table()
