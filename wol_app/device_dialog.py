"""Device Management Dialog for Wake-on-LAN Application."""

from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from wol_app.device_io import export_devices, import_devices
from wol_app.network_scan_dialog import NetworkScanDialog
from wol_app.network_scanner import get_local_ips
from wol_app.translations import Translations
from wol_app.widgets.toggle_switch import ToggleWithLabel
from wol_app.utils import (
    get_ip_key,
    validate_device_name,
    validate_ip_or_hostname,
    validate_mac,
    validate_password,
    validate_username,
)


class DeviceDialog(QDialog):
    """Dialog for adding/editing a device."""

    device_saved = pyqtSignal(dict)  # Emits device dict on save

    def __init__(self, config_manager, device: dict = None, parent=None,
                 preset: dict = None) -> None:
        super().__init__(parent)
        self.config = config_manager
        self.editing_device = device
        self.setWindowTitle(Translations.tr("device_dialog.title.edit") if device else Translations.tr("device_dialog.title.add"))
        self.setMinimumWidth(450)
        self._setup_ui()
        if device:
            self._fill_form(device)
        else:
            if preset:
                # Pre-fill from a scan result (name/mac/ip) without editing mode
                self.name_input.setText(preset.get("name", ""))
                self.mac_input.setText(preset.get("mac", ""))
                self.ip_input.setText(preset.get("ip", ""))
            # Pre-select the default shutdown method from settings
            default_method = self.config.get_default_shutdown_method()
            for idx in range(self.method_combo.count()):
                if self.method_combo.itemData(idx) == default_method:
                    self.method_combo.setCurrentIndex(idx)
                    break

    def _setup_ui(self) -> None:
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

        # Shutdown method (host service or SMB)
        method_layout = QFormLayout()
        self.method_combo = QComboBox()
        self.method_combo.addItem(
            Translations.tr("device_dialog.method.host_service"),
            "host_service",
        )
        self.method_combo.addItem(
            Translations.tr("device_dialog.method.smb"),
            "smb",
        )
        method_layout.addRow(Translations.tr("device_dialog.label.shutdown_method"), self.method_combo)

        # Enabled toggle (same switch widget as in the modern network scan)
        self.enabled_check = ToggleWithLabel(
            Translations.tr("device_dialog.enabled"), checked=True
        )

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
        layout.addLayout(method_layout)
        layout.addWidget(self.enabled_check)
        layout.addLayout(btn_layout)

    def _fill_form(self, device: dict) -> None:
        self.name_input.setText(device.get("name", ""))
        self.mac_input.setText(device.get("mac", ""))
        self.ip_input.setText(device.get("ip", ""))
        self.username_input.setText(device.get("username", ""))
        self.password_input.setText(device.get("password", ""))
        self.enabled_check.setChecked(device.get("enabled", True))
        # Set shutdown method (legacy devices default to "smb")
        method = self.config.get_device_shutdown_method(device)
        for idx in range(self.method_combo.count()):
            if self.method_combo.itemData(idx) == method:
                self.method_combo.setCurrentIndex(idx)
                break

    def _save(self) -> None:
        name: str = self.name_input.text().strip()
        mac: str = self.mac_input.text().strip()
        ip: str = self.ip_input.text().strip()

        if not name:
            QMessageBox.warning(self, Translations.tr("dialog.error.title"), Translations.tr("device_dialog.error.missing_name"))
            return
        if not validate_device_name(name):
            QMessageBox.warning(self, Translations.tr("dialog.error.title"), Translations.tr("device_dialog.error.invalid_name"))
            return
        if not mac:
            QMessageBox.warning(self, Translations.tr("dialog.error.title"), Translations.tr("device_dialog.error.missing_mac"))
            return
        if not validate_mac(mac):
            QMessageBox.warning(self, Translations.tr("dialog.error.title"), Translations.tr("device_dialog.error.invalid_mac"))
            return
        # The address is optional but must be a valid IPv4 or host name when set
        # (xrdp/Linux hosts are typically reached by name, e.g. ubuntu-mercury).
        if ip and not validate_ip_or_hostname(ip):
            QMessageBox.warning(self, Translations.tr("dialog.error.title"), Translations.tr("device_dialog.error.invalid_ip_or_host"))
            return

        username: str = self.username_input.text().strip()
        password: str = self.password_input.text().strip()

        # Validate username and password
        if username and not validate_username(username):
            QMessageBox.warning(self, Translations.tr("dialog.error.title"), Translations.tr("device_dialog.error.invalid_username"))
            return
        if password and not validate_password(password):
            QMessageBox.warning(self, Translations.tr("dialog.error.title"), Translations.tr("device_dialog.error.invalid_password"))
            return

        shutdown_method = self.method_combo.currentData()

        if self.editing_device:
            updates = {
                "name": name,
                "mac": mac,
                "enabled": self.enabled_check.isChecked(),
                "shutdown_method": shutdown_method,
            }
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
            device = self.config.add_device(
                name, mac, enabled=self.enabled_check.isChecked()
            )
            if device:
                if ip:
                    self.config.update_device(device["id"], ip=ip)
                if username:
                    self.config.update_device(device["id"], username=username)
                if password:
                    self.config.update_device(device["id"], password=password)
                # add_device already applied the default method; honour the
                # user's explicit selection (may differ from the default)
                if shutdown_method != device.get("shutdown_method"):
                    self.config.update_device(device["id"], shutdown_method=shutdown_method)
                self.device_saved.emit(self.config.get_device_by_id(device["id"]))
            else:
                QMessageBox.warning(self, Translations.tr("dialog.error.title"), Translations.tr("device_dialog.error.save_failed"))
                return

        # Clear password from input field for security
        self.password_input.clear()
        self.accept()


class DeviceManagerDialog(QDialog):
    """Full device management dialog - list all devices, add/edit/delete."""

    def __init__(self, config_manager, parent=None) -> None:
        super().__init__(parent)
        self.config: Any = config_manager
        self.setWindowTitle(Translations.tr("device_manager.title"))
        self.setMinimumSize(700, 500)
        
        # Load sort settings from config
        sort_settings = self.config.get_device_sort_settings()
        self.sort_column = sort_settings["sort_column"]
        self.sort_order: Qt.SortOrder = Qt.SortOrder.AscendingOrder if sort_settings["sort_order"] == "ascending" else Qt.SortOrder.DescendingOrder
        
        self._setup_ui()
        self._refresh_table()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

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
        header: QHeaderView | None = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(1, 160)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(3, 120)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(4, 120)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        # Clicking a column header sorts the table (1st A-Z, 2nd Z-A)
        # Password column (4) is not sortable (masked display)
        header.setSortIndicatorShown(True)
        header.setSectionsClickable(True)
        header.sectionClicked.connect(self._on_header_clicked)
        for col in range(self.table.columnCount()):
            item = self.table.horizontalHeaderItem(col)
            if item is not None:
                item.setToolTip(Translations.tr("table.sort.tooltip"))
        self.table.itemDoubleClicked.connect(lambda item: self._edit_device())
        # Right-click context menu on the device table
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_device_manager_context_menu)

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

        # Search field: live-filters the table by name, MAC, IP or user
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(Translations.tr("ui.search_devices_placeholder"))
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._refresh_table)

        layout.addWidget(self.search_input)
        layout.addWidget(self.table)
        layout.addLayout(btn_layout)

    def _get_sort_key(self, device, sort_column):
        """Get sort key for a device based on sort column with special handling for IPs."""
        sort_key_map: dict[int, str] = {
            0: "name",  # Name
            1: "mac",  # MAC Address
            2: "ip",   # IP Address
            3: "username",  # Username
        }
        
        # Ensure sort_column is within valid range for backwards compatibility
        if sort_column < 0 or sort_column >= len(sort_key_map):
            sort_column = 0  # Default to name
        
        key: str = sort_key_map.get(sort_column, "name")
        value = device.get(key, "")
        
        # Special handling for IP addresses
        if sort_column == 2:  # IP Address
            return get_ip_key(value)
        
        return value

    def _get_filtered_devices(self):
        """Get devices matching the current search query.

        The query is matched as a case-insensitive substring against the
        device's name, MAC address, IP address and username. An empty query
        returns all devices.
        """
        query = self.search_input.text().strip().lower()
        if not query:
            return self.config.get_devices()

        fields = ("name", "mac", "ip", "username")
        return [
            device
            for device in self.config.get_devices()
            if any(query in str(device.get(field, "")).lower() for field in fields)
        ]

    def _get_sorted_devices(self):
        """Get devices (filtered by the search field) sorted according to current settings."""
        devices = self._get_filtered_devices()
        
        return sorted(devices, key=lambda d: self._get_sort_key(d, self.sort_column), reverse=(self.sort_order == Qt.SortOrder.DescendingOrder))

    def _on_header_clicked(self, column: int) -> None:
        """Sort by the clicked column: 1st click A-Z, 2nd click Z-A.

        The password column (4) is not sortable because it is masked.
        """
        if column == 4:
            return
        if self.sort_column == column:
            self.sort_order = Qt.SortOrder.DescendingOrder if self.sort_order == Qt.SortOrder.AscendingOrder else Qt.SortOrder.AscendingOrder
        else:
            self.sort_column = column
            self.sort_order = Qt.SortOrder.AscendingOrder
        self._refresh_table()

    def _refresh_table(self) -> None:
        self.table.setRowCount(0)
        sorted_devices = self._get_sorted_devices()

        # Show the active sort indicator on the header
        header: QHeaderView | None = self.table.horizontalHeader()
        if self.sort_column is not None:
            order = Qt.SortOrder.DescendingOrder if self.sort_order == Qt.SortOrder.DescendingOrder else Qt.SortOrder.AscendingOrder
            header.setSortIndicator(self.sort_column, order)
        else:
            header.setSortIndicator(-1, Qt.SortOrder.AscendingOrder)
        
        for device in sorted_devices:
            row: int = self.table.rowCount()
            self.table.insertRow(row)

            display_name = device.get("name", "")
            if device.get("ip", "") in get_local_ips():
                display_name += f" {Translations.tr('device.me')}"
            name_item = QTableWidgetItem(display_name)
            # Store the device id so row-based actions (Edit/Delete) stay
            # correct while the search filter hides other rows
            name_item.setData(Qt.ItemDataRole.UserRole, device["id"])
            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, QTableWidgetItem(device.get("mac", "")))
            self.table.setItem(row, 2, QTableWidgetItem(device.get("ip", "")))
            self.table.setItem(row, 3, QTableWidgetItem(device.get("username", "")))
            
            # Password column - display as asterisks
            password = device.get("password", "")
            password_display: str = "*" * len(password) if password else ""
            self.table.setItem(row, 4, QTableWidgetItem(password_display))

    def _show_device_manager_context_menu(self, pos) -> None:
        """Show the right-click context menu for the device table.

        Offers Add/Edit/Delete. Edit and Delete act on the row under the
        cursor (selected automatically); Add is always available.
        """
        row: int = self.table.rowAt(pos.y())

        menu = QMenu(self)
        menu.addAction(
            Translations.tr("device_manager.button.add"),
            self._add_device,
        )
        if row >= 0:
            # Select the row under the cursor so Edit/Delete apply to it
            self.table.selectRow(row)
            self.table.setCurrentCell(row, 0)
            menu.addAction(
                Translations.tr("device_manager.button.edit"),
                self._edit_device,
            )
            menu.addAction(
                Translations.tr("device_manager.button.delete"),
                self._delete_device,
            )
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _add_device(self) -> None:
        dialog = DeviceDialog(self.config, parent=self)
        dialog.device_saved.connect(lambda d: self._refresh_table())
        dialog.exec()

    def _get_selected_device(self):
        """Resolve the device of the currently selected table row.

        The device id is read from the row's Name item (UserRole) so the
        lookup stays correct while the search filter hides other rows.
        Returns None if no row is selected.
        """
        current_row: int = self.table.currentRow()
        if current_row < 0:
            return None
        item = self.table.item(current_row, 0)
        if item is None:
            return None
        device_id = item.data(Qt.ItemDataRole.UserRole)
        if not device_id:
            return None
        return self.config.get_device_by_id(device_id)

    def _edit_device(self) -> None:
        device = self._get_selected_device()
        if device is None:
            QMessageBox.information(self, Translations.tr("dialog.select_device.title"), Translations.tr("dialog.select_device.message"))
            return

        dialog = DeviceDialog(self.config, device=device, parent=self)
        dialog.device_saved.connect(lambda d: self._refresh_table())
        dialog.exec()

    def _delete_device(self) -> None:
        device = self._get_selected_device()
        if device is None:
            QMessageBox.information(
                self,
                Translations.tr("dialog.select_device.title"),
                Translations.tr("dialog.select_device.message"),
            )
            return

        reply: QMessageBox.StandardButton = QMessageBox.question(
            self,
            Translations.tr("dialog.confirm_delete.title"),
            Translations.tr("dialog.confirm_delete.message", name=device["name"]),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.config.remove_device(device["id"])
            self._refresh_table()

    def _scan_network(self) -> None:
        """Open network scan dialog to discover active devices."""
        dialog: NetworkScanDialog[Any] = NetworkScanDialog(self.config, parent=self)
        dialog.exec()
        self._refresh_table()

    def _export_devices(self) -> None:
        """Export configured devices to a JSON file."""
        export_devices(self.config, parent=self)

    def _import_devices(self) -> None:
        """Import devices from a JSON file. Existing devices with the same name are overwritten."""
        if import_devices(self.config, parent=self):
            self._refresh_table()
