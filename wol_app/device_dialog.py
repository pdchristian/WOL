"""Device Management Dialog for Wake-on-LAN Application."""

import json
import subprocess
from datetime import datetime
from typing import Any

from PyQt6.QtCore import QObject, Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from wol_app.crypto import decrypt_password, encrypt_password, is_encrypted
from wol_app.host_service_client import send_host_command
from wol_app.theme import get_icon, status_badge_colors
from wol_app.translations import Translations
from wol_app.utils import (
    get_ip_key,
    launch_remote_desktop,
    validate_device_name,
    validate_mac,
    validate_password,
    validate_username,
)


class DeviceDialog(QDialog):
    """Dialog for adding/editing a device."""

    device_saved = pyqtSignal(dict)  # Emits device dict on save

    def __init__(self, config_manager, device: dict = None, parent=None) -> None:
        super().__init__(parent)
        self.config = config_manager
        self.editing_device = device
        self.setWindowTitle(Translations.tr("device_dialog.title.edit") if device else Translations.tr("device_dialog.title.add"))
        self.setMinimumWidth(450)
        self._setup_ui()
        if device:
            self._fill_form(device)
        else:
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
            device = self.config.add_device(name, mac)
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


class StatusWorker(QObject):
    """Background worker for checking device statuses without blocking the UI."""

    finished = pyqtSignal(list)  # Emits list of (device_id, name, status, msg)

    # Max concurrent pings to avoid overwhelming the network
    MAX_CONCURRENT = 16

    def __init__(self, engine) -> None:
        super().__init__()
        self.engine: Any = engine
        self._cancelled = False

    def cancel(self) -> None:
        """Signal the worker to stop."""
        self._cancelled = True

    def run(self) -> None:
        import concurrent.futures
        devices = [d for d in self.engine.config.get_devices() if d.get("enabled", True)]
        if self._cancelled or not devices:
            self.finished.emit([])
            return

        results: dict[str, tuple] = {}

        def _check(device_id: str) -> tuple[str, str, str]:
            status, msg = self.engine.check_device_status(device_id)
            return (device_id, status, msg)

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=min(self.MAX_CONCURRENT, len(devices))
        ) as pool:
            futures = {pool.submit(_check, d["id"]): d["id"] for d in devices}
            for future in concurrent.futures.as_completed(futures):
                if self._cancelled:
                    break
                device_id = futures[future]
                try:
                    did, status, msg = future.result()
                    results[did] = (did, status, msg)
                except Exception:
                    results[device_id] = (device_id, "unknown", "Error checking status")

        # Build ordered result list (device_id, name, status, msg)
        ordered = []
        for device in devices:
            did = device["id"]
            if did in results:
                _, status, msg = results[did]
                ordered.append((did, device["name"], status, msg))
        self.finished.emit(ordered)


class DeviceManagerPage(QWidget):
    """Devices page - list, manage and operate all devices (embedded in the main window)."""

    devices_changed = pyqtSignal()  # Emitted when the device set changes
    request_scan = pyqtSignal()     # Emitted when the user wants to run a network scan

    def __init__(self, config_manager, engine, parent=None) -> None:
        super().__init__(parent)
        self.config: Any = config_manager
        self.engine = engine

        # Load sort settings from config
        sort_settings = self.config.get_device_sort_settings()
        self.sort_column = sort_settings["sort_column"]
        self.sort_order: Qt.SortOrder = Qt.SortOrder.AscendingOrder if sort_settings["sort_order"] == "ascending" else Qt.SortOrder.DescendingOrder

        # Status-check machinery (background thread + 30 s timer)
        self._status_thread = None
        self._status_worker = None
        self._status_check_running = False
        self._status_timer = None

        self._setup_ui()
        self._refresh_table()

    def start_auto_refresh(self) -> None:
        """Start the periodic (30 s) status refresh timer (idempotent)."""
        from PyQt6.QtCore import QTimer
        if self._status_timer is not None:
            self._status_timer.stop()
            self._status_timer.deleteLater()
        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self._refresh_statuses)
        self._status_timer.start(30000)

    def stop_auto_refresh(self) -> None:
        """Stop the periodic status refresh timer."""
        if self._status_timer is not None:
            self._status_timer.stop()
            self._status_timer = None

    def cleanup(self) -> None:
        """Stop timers and cancel/wait for in-flight status checks."""
        self.stop_auto_refresh()
        if self._status_worker is not None:
            self._status_worker.cancel()
        if self._status_thread is not None and self._status_thread.isRunning():
            self._status_thread.quit()
            self._status_thread.wait(10000)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Device Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            Translations.tr("device_manager.table.header.name"),
            Translations.tr("device_manager.table.header.mac"),
            Translations.tr("device_manager.table.header.ip"),
            Translations.tr("device_manager.table.header.username"),
            Translations.tr("table.header.status"),
            Translations.tr("device_manager.table.header.password")
        ])
        header: QHeaderView | None = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(1, 160)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(3, 120)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(4, 100)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(5, 120)
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

        # Primary action buttons (operate the selected device)
        action_layout = QHBoxLayout()
        self.wake_selected_btn = QPushButton(Translations.tr("button.wake_selected"))
        self.wake_selected_btn.setIcon(get_icon("wake"))
        self.wake_selected_btn.clicked.connect(self._wake_selected)
        self.wake_all_btn = QPushButton(Translations.tr("button.wake_all"))
        self.wake_all_btn.setObjectName("primaryButton")
        self.wake_all_btn.setIcon(get_icon("wake"))
        self.wake_all_btn.clicked.connect(self._wake_all)
        self.shutdown_btn = QPushButton(Translations.tr("button.shutdown"))
        self.shutdown_btn.setIcon(get_icon("shutdown"))
        self.shutdown_btn.clicked.connect(self._shutdown_selected)
        self.ping_btn = QPushButton(Translations.tr("button.ping"))
        self.ping_btn.setIcon(get_icon("ping"))
        self.ping_btn.clicked.connect(self._ping_selected)
        self.refresh_btn = QPushButton(Translations.tr("button.refresh"))
        self.refresh_btn.setIcon(get_icon("refresh"))
        self.refresh_btn.clicked.connect(self._refresh_statuses)

        for b in (self.wake_selected_btn, self.wake_all_btn, self.shutdown_btn, self.ping_btn, self.refresh_btn):
            b.setMinimumHeight(35)
            action_layout.addWidget(b)
        action_layout.addStretch()

        # Management buttons (add/edit/delete/import/export/scan)
        mgmt_layout = QHBoxLayout()
        add_btn = QPushButton(Translations.tr("toolbar.add_device"))
        add_btn.setIcon(get_icon("add"))
        add_btn.clicked.connect(self._add_device)
        edit_btn = QPushButton(Translations.tr("device_manager.button.edit"))
        edit_btn.setIcon(get_icon("edit"))
        edit_btn.clicked.connect(self._edit_device)
        delete_btn = QPushButton(Translations.tr("device_manager.button.delete"))
        delete_btn.setIcon(get_icon("delete"))
        delete_btn.clicked.connect(self._delete_device)
        import_btn = QPushButton(Translations.tr("device_manager.button.import"))
        import_btn.setIcon(get_icon("import"))
        import_btn.clicked.connect(self._import_devices)
        export_btn = QPushButton(Translations.tr("device_manager.button.export"))
        export_btn.setIcon(get_icon("export"))
        export_btn.clicked.connect(self._export_devices)
        scan_btn = QPushButton(Translations.tr("device_manager.button.scan_network"))
        scan_btn.setIcon(get_icon("scan"))
        scan_btn.clicked.connect(self._scan_network)

        for b in (add_btn, edit_btn, delete_btn, import_btn, export_btn, scan_btn):
            mgmt_layout.addWidget(b)
        mgmt_layout.addStretch()

        # Search field: live-filters the table by name, MAC, IP or user
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(Translations.tr("ui.search_devices_placeholder"))
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._refresh_table)

        layout.addWidget(self.search_input)
        layout.addLayout(action_layout)
        layout.addLayout(mgmt_layout)
        layout.addWidget(self.table)

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

        The status (4) and password (5) columns are not sortable.
        """
        if column in (4, 5):
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

            name_item = QTableWidgetItem(device.get("name", ""))
            # Store the device id so row-based actions (Edit/Delete) stay
            # correct while the search filter hides other rows
            name_item.setData(Qt.ItemDataRole.UserRole, device["id"])
            if not device.get("enabled", True):
                name_item.setForeground(Qt.GlobalColor.gray)
                name_item.setText(f"{device['name']} {Translations.tr('device.disabled')}")
            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, QTableWidgetItem(device.get("mac", "")))
            self.table.setItem(row, 2, QTableWidgetItem(device.get("ip", "")))
            self.table.setItem(row, 3, QTableWidgetItem(device.get("username", "")))

            # Status column - shown as a colored dot + text
            status = self.engine.get_device_status(device["id"])
            self.table.setItem(row, 4, self._make_status_item(status))

            # Password column - display as asterisks
            password = device.get("password", "")
            password_display: str = "*" * len(password) if password else ""
            self.table.setItem(row, 5, QTableWidgetItem(password_display))

    def _make_status_item(self, status: str) -> QTableWidgetItem:
        """Build a status table item with a colored dot and badge text color."""
        from PyQt6.QtGui import QColor
        _bg, fg = status_badge_colors(status)
        item = QTableWidgetItem(f"● {self._translated_status(status)}")
        item.setForeground(QColor(fg))
        return item

    def _translated_status(self, status: str) -> str:
        """Return the translated, display-ready status text for *status*."""
        key_map: dict[str, str] = {
            "online": "status.online",
            "offline": "status.offline",
            "unknown": "status.unknown",
        }
        key: str = key_map.get(status, "status.unknown")
        return Translations.tr(key)

    def _show_device_manager_context_menu(self, pos) -> None:
        """Show the right-click context menu for the device table.

        Offers management (Add/Edit/Delete) and operation (Wake/Remote
        Desktop/Shutdown/Ping) actions. Edit and Delete act on the row
        under the cursor (selected automatically); Add is always available.
        """
        row: int = self.table.rowAt(pos.y())

        menu = QMenu(self)
        menu.addAction(
            Translations.tr("device_manager.button.add"),
            self._add_device,
        )
        if row >= 0:
            # Select the row under the cursor so actions apply to it
            self.table.selectRow(row)
            self.table.setCurrentCell(row, 0)
            menu.addSeparator()
            menu.addAction(
                Translations.tr("button.remote_fullscreen"),
                lambda: self._remote_desktop_selected(True),
            )
            menu.addAction(
                Translations.tr("button.remote_window"),
                lambda: self._remote_desktop_selected(False),
            )
            menu.addSeparator()
            menu.addAction(
                Translations.tr("button.wake_selected"),
                self._wake_selected,
            )
            menu.addAction(
                Translations.tr("button.shutdown"),
                self._shutdown_selected,
            )
            menu.addAction(
                Translations.tr("button.ping"),
                self._ping_selected,
            )
            menu.addSeparator()
            menu.addAction(
                Translations.tr("device_manager.button.edit"),
                self._edit_device,
            )
            menu.addAction(
                Translations.tr("device_manager.button.delete"),
                self._delete_device,
            )
        menu.exec(self.table.viewport().mapToGlobal(pos))

    # ---- Operational actions (wake / shutdown / ping / remote / status) ----

    def _status_message(self, message: str, timeout: int = 0) -> None:
        """Show a message in the main window status bar (if available)."""
        window = self.window()
        if hasattr(window, "statusBar"):
            window.statusBar().showMessage(message, timeout)

    def _wake_selected(self) -> None:
        """Wake the currently selected device."""
        device = self._get_selected_device()
        if device is None:
            QMessageBox.information(self, Translations.tr("dialog.select_device.title"), Translations.tr("dialog.select_device.message"))
            return

        if not device.get("enabled", True):
            QMessageBox.warning(self, Translations.tr("dialog.device_disabled.title"), Translations.tr("dialog.device_disabled.message", name=device["name"]))
            return

        success, msg = self.engine.send_wake_packet(device["id"])
        if success:
            self._status_message(msg)
        else:
            QMessageBox.warning(self, Translations.tr("dialog.wake_failed.title"), msg)

    def _wake_all(self) -> None:
        """Wake all enabled devices."""
        devices = [d for d in self.config.get_devices() if d.get("enabled", True)]
        if not devices:
            QMessageBox.information(self, Translations.tr("dialog.no_devices.title"), Translations.tr("dialog.no_devices.message"))
            return

        reply: QMessageBox.StandardButton = QMessageBox.question(
            self, Translations.tr("dialog.wake_all.title"),
            Translations.tr("dialog.wake_all.message", count=len(devices)),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        results: list[tuple[str, bool, str]] = self.engine.wake_all()
        success_count: int = sum(1 for _, s, _ in results if s)
        fail_count: int = len(results) - success_count

        msg: str = Translations.tr("dialog.wake_all_complete.success", count=success_count)
        if fail_count:
            msg += " " + Translations.tr("dialog.wake_all_complete.fail", count=fail_count)
        QMessageBox.information(self, Translations.tr("dialog.wake_all_complete.title"), msg)
        self._status_message(msg)

    def _ping_selected(self) -> None:
        """Ping the currently selected device."""
        device = self._get_selected_device()
        if device is None:
            QMessageBox.information(self, Translations.tr("dialog.select_device.title"), Translations.tr("dialog.select_device_ping.message"))
            return

        status, msg = self.engine.check_device_status(device["id"])
        QMessageBox.information(self, Translations.tr("dialog.status_result.title", status=self._translated_status(status)), msg)

    def _remote_desktop_selected(self, fullscreen: bool) -> None:
        """Start a Remote Desktop session for the selected device."""
        device = self._get_selected_device()
        if device is None:
            QMessageBox.information(self, Translations.tr("dialog.select_device.title"), Translations.tr("dialog.select_device.message"))
            return

        device_name = device.get("name", "")
        device_ip = device.get("ip", "")

        if not device_ip:
            QMessageBox.warning(self, Translations.tr("dialog.no_ip.title"), Translations.tr("dialog.no_ip.message", name=device_name))
            return

        username: str = device.get("username", "") or ""
        password: str = device.get("password", "") or ""

        width: int = 1920
        height: int = 1080
        if not fullscreen:
            try:
                w, h = self.config.get_remote_desktop_resolution().split("x")
                width, height = int(w), int(h)
            except (ValueError, AttributeError):
                pass  # keep 1920x1080 fallback

        try:
            launch_remote_desktop(
                ip=device_ip,
                username=username,
                password=password,
                fullscreen=fullscreen,
                width=width,
                height=height,
            )
        except Exception:
            QMessageBox.critical(self, Translations.tr("dialog.remote_desktop_error.title"), Translations.tr("dialog.remote_desktop_error.message"))

    def _shutdown_selected(self) -> None:
        """Show shutdown confirmation dialog for the selected device."""
        device = self._get_selected_device()
        if device is None:
            QMessageBox.information(self, Translations.tr("dialog.select_device.title"), Translations.tr("dialog.select_device_shutdown.message"))
            return

        device_name = device.get("name", "")
        device_ip = device.get("ip", "")

        if not device_ip:
            QMessageBox.warning(self, Translations.tr("dialog.no_ip.title"), Translations.tr("dialog.no_ip.message", name=device_name))
            return

        # Determine the shutdown method for this device
        method = self.config.get_device_shutdown_method(device)

        # Build confirmation dialog
        dialog = QDialog(self)
        dialog.setWindowTitle(Translations.tr("dialog.shutdown_confirm.title", name=device_name))
        dialog.setMinimumWidth(450)
        layout = QVBoxLayout(dialog)

        label1 = QLabel(Translations.tr("dialog.shutdown_confirm.label1", name=device_name))
        layout.addWidget(label1)

        label2 = QLabel(
            Translations.tr("dialog.shutdown_confirm.label2")
        )
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
        shutdown_confirm_btn.clicked.connect(lambda: self._execute_shutdown(device, dialog))
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(shutdown_confirm_btn)
        layout.addLayout(button_layout)

        dialog.exec()

    def _execute_host_service_shutdown(
        self, device_name: str, device_ip: str, username: str, password: str
    ) -> None:
        """Shut down a device via the WOL Host Service (TCP port 8765)."""
        if not username or not password:
            self.config.add_log(device_name, "SHUTDOWN", "ERROR", "Missing credentials for host service")
            QMessageBox.warning(
                self,
                Translations.tr("dialog.host_service_missing_creds.title"),
                Translations.tr("dialog.host_service_missing_creds.message", name=device_name),
            )
            return

        self._status_message(Translations.tr("status.host_service_sending", name=device_name))
        QApplication.processEvents()

        success, message = send_host_command(device_ip, "shutdown", username, password)

        if success:
            self.config.add_log(device_name, "SHUTDOWN", "SUCCESS", f"Host service: {message}")
            QMessageBox.information(
                self,
                Translations.tr("dialog.shutdown_successful.title"),
                Translations.tr("dialog.shutdown_successful.message", name=device_name, ip=device_ip),
            )
            self._status_message(Translations.tr("status.shutdown_success", name=device_name))
        else:
            self.config.add_log(device_name, "SHUTDOWN", "ERROR", f"Host service: {message}")
            # Distinguish authentication failures from connectivity problems
            if "Authentication failed" in message:
                QMessageBox.critical(
                    self,
                    Translations.tr("dialog.host_service_auth_failed.title"),
                    Translations.tr("dialog.host_service_auth_failed.message", name=device_name, ip=device_ip, error=message),
                )
            else:
                QMessageBox.critical(
                    self,
                    Translations.tr("dialog.host_service_error.title"),
                    Translations.tr("dialog.host_service_error.message", name=device_name, ip=device_ip, error=message),
                )
            self._status_message(Translations.tr("status.shutdown_failed", name=device_name))

    def _execute_shutdown(self, device, dialog):
        """Execute the remote shutdown sequence for a device."""
        dialog.accept()  # Close the confirmation dialog

        device_name = device.get("name", "")
        device_ip = device.get("ip", "")
        username = device.get("username", "")
        password = device.get("password", "")

        # Dispatch on the device's shutdown method
        method = self.config.get_device_shutdown_method(device)
        if method == "host_service":
            self._execute_host_service_shutdown(device_name, device_ip, username, password)
            return

        self._status_message(Translations.tr("status.shutting_down", name=device_name))
        QApplication.processEvents()

        # Step 1: Connect to remote IPC$
        if username:
            # Delete any existing connection first
            delete_cmd: str = f'net use \\\\{device_ip} /delete /y'
            self._status_message(Translations.tr("status.deleting_connection", name=device_name))
            QApplication.processEvents()
            try:
                subprocess.run(
                    delete_cmd, shell=True, capture_output=True, encoding='utf-8', errors='replace', timeout=15
                )
            except Exception:
                pass  # Ignore errors from delete — connection may not exist yet

            # Connect with username and password
            cmd: str = f'net use \\\\{device_ip}\\IPC$ /user:{username} {password}'
            self._status_message(Translations.tr("status.connecting", name=device_name, ip=device_ip))
            QApplication.processEvents()
        else:
            # Connect without credentials
            cmd: str = f'net use \\\\{device_ip}\\IPC$'
            self._status_message(Translations.tr("status.connecting", name=device_name, ip=device_ip))
            QApplication.processEvents()

        try:
            result: subprocess.CompletedProcess[str] = subprocess.run(
                cmd, shell=True, capture_output=True, encoding='utf-8', errors='replace', timeout=30
            )
            if result.returncode != 0:
                error_msg: str = result.stderr.strip() or result.stdout.strip()
                self.config.add_log(device_name, "SHUTDOWN", "ERROR", f"Connection failed: {error_msg}")
                QMessageBox.critical(
                    self, Translations.tr("dialog.connection_failed.title"),
                    Translations.tr("dialog.connection_failed.message", name=device_name, ip=device_ip, error=error_msg)
                )
                self._status_message(Translations.tr("status.shutdown_failed", name=device_name))
                return
        except subprocess.TimeoutExpired:
            self.config.add_log(device_name, "SHUTDOWN", "ERROR", "Connection timed out")
            QMessageBox.critical(
                self, Translations.tr("dialog.connection_timeout.title"),
                Translations.tr("dialog.connection_timeout.message", name=device_name, ip=device_ip)
            )
            self._status_message(Translations.tr("status.shutdown_failed", name=device_name))
            return
        except Exception as e:
            self.config.add_log(device_name, "SHUTDOWN", "ERROR", f"Connection error: {str(e)}")
            QMessageBox.critical(
                self, Translations.tr("dialog.connection_error.title"),
                Translations.tr("dialog.connection_error.message", name=device_name, ip=device_ip, error=str(e))
            )
            self._status_message(Translations.tr("status.shutdown_failed", name=device_name))
            return

        # Step 2: Shutdown the remote PC
        shutdown_cmd: str = f'shutdown /m \\\\{device_ip} /s /t 0 /f'
        self._status_message(Translations.tr("status.shutting_down_remote", name=device_name))
        QApplication.processEvents()
        try:
            result: subprocess.CompletedProcess[str] = subprocess.run(
                shutdown_cmd, shell=True, capture_output=True, encoding='utf-8', errors='replace', timeout=30
            )
            if result.returncode != 0:
                error_msg: str = result.stderr.strip() or result.stdout.strip()
                self.config.add_log(device_name, "SHUTDOWN", "ERROR", f"Shutdown failed: {error_msg}")
                QMessageBox.critical(
                    self, Translations.tr("dialog.shutdown_failed.title"),
                    Translations.tr("dialog.shutdown_failed.message", name=device_name, ip=device_ip, error=error_msg)
                )
                self._status_message(Translations.tr("status.shutdown_failed", name=device_name))
                return
        except subprocess.TimeoutExpired:
            self.config.add_log(device_name, "SHUTDOWN", "ERROR", "Shutdown command timed out")
            QMessageBox.critical(
                self, Translations.tr("dialog.shutdown_timeout.title"),
                Translations.tr("dialog.shutdown_timeout.message", name=device_name, ip=device_ip)
            )
            self._status_message(Translations.tr("status.shutdown_failed", name=device_name))
            return
        except Exception as e:
            self.config.add_log(device_name, "SHUTDOWN", "ERROR", f"Shutdown error: {str(e)}")
            QMessageBox.critical(
                self, Translations.tr("dialog.shutdown_error.title"),
                Translations.tr("dialog.shutdown_error.message", name=device_name, ip=device_ip, error=str(e))
            )
            self._status_message(Translations.tr("status.shutdown_failed", name=device_name))
            return

        self.config.add_log(device_name, "SHUTDOWN", "SUCCESS", "Shutdown initiated successfully")
        QMessageBox.information(
            self, Translations.tr("dialog.shutdown_successful.title"),
            Translations.tr("dialog.shutdown_successful.message", name=device_name, ip=device_ip)
        )
        self._status_message(Translations.tr("status.shutdown_success", name=device_name))

    def _refresh_statuses(self) -> None:
        """Ping all devices and update statuses (runs in background thread)."""
        if self._status_check_running:
            self._status_message(Translations.tr("status.check_in_progress"))
            return

        self._status_check_running = True
        self._status_message(Translations.tr("status.checking"))

        self._status_worker = StatusWorker(self.engine)
        self._status_thread = QThread()
        self._status_worker.moveToThread(self._status_thread)
        self._status_thread.started.connect(self._status_worker.run)
        self._status_worker.finished.connect(self._on_status_check_finished)
        self._status_worker.finished.connect(self._status_thread.quit)
        self._status_worker.finished.connect(self._status_worker.deleteLater)

        def on_thread_finished() -> None:
            self._status_check_running = False
            self._status_thread = None

        self._status_thread.finished.connect(on_thread_finished)
        self._status_thread.start()

    def _on_status_check_finished(self, results) -> None:
        """Callback when status check completes."""
        by_id: dict[str, tuple] = {
            device_id: (name, status, msg)
            for device_id, name, status, msg in results
        }
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is None:
                continue
            device_id = item.data(Qt.ItemDataRole.UserRole)
            if not device_id or device_id not in by_id:
                continue
            _, status, _msg = by_id[device_id]
            self.table.setItem(row, 4, self._make_status_item(status))
        self._status_message(Translations.tr("status.check_complete", time=datetime.now().strftime('%H:%M:%S')))

    def _add_device(self) -> None:
        dialog = DeviceDialog(self.config, parent=self)
        dialog.device_saved.connect(lambda d: self._refresh_table())
        dialog.exec()
        self.devices_changed.emit()

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
        self.devices_changed.emit()

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
            self.devices_changed.emit()

    def _scan_network(self) -> None:
        """Ask the main window to switch to the network scan page."""
        self.request_scan.emit()

    def _export_devices(self) -> None:
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
        except OSError as e:
            QMessageBox.critical(
                self,
                Translations.tr("dialog.export.error.title"),
                Translations.tr("dialog.export.error.message", error=str(e)),
            )

    def _import_devices(self) -> None:
        """Import devices from a JSON file. Existing devices with the same name are overwritten."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, Translations.tr("dialog.import.title"), "", "JSON Files (*.json)"
        )
        if not file_path:
            return

        try:
            with open(file_path) as f:
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
                errors.append(
                    Translations.tr("dialog.import.missing_field", line=idx + 1)
                )
                continue

            if not validate_mac(mac):
                errors.append(
                    Translations.tr("dialog.import.invalid_mac", line=idx + 1, name=name)
                )
                continue

            existing = self.config.get_device_by_name(name)
            if existing:
                # Update existing device
                pw = dev_data.get("password", "")
                if is_encrypted(pw):
                    pw: str = decrypt_password(pw)
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
                        pw: str = decrypt_password(pw)
                    self.config.update_device(
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
            self,
            Translations.tr("dialog.import.result.title"),
            "\n".join(summary_lines),
        )
        self._refresh_table()
        self.devices_changed.emit()
