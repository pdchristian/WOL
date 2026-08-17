"""Main Window for Wake-on-LAN Application."""

import os
import subprocess
import sys
from datetime import datetime
from typing import Any, Literal, NoReturn

from PyQt6.QtCore import QObject, Qt, QThread, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QAction, QFont, QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMenu,
    QMenuBar,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from wol_app import __version__
from wol_app.config import ConfigManager
from wol_app.device_dialog import DeviceManagerDialog
from wol_app.host_service_client import send_host_command
from wol_app.log_dialog import LogDialog
from wol_app.network_scan_dialog import NetworkScanDialog
from wol_app.schedule_dialog import ScheduleDialog
from wol_app.settings_dialog import SettingsDialog
from wol_app.theme import apply_display_mode
from wol_app.translations import Translations
from wol_app.update_dialog import (
    UpdateAvailableDialog,
    UpdateErrorDialog,
    UpdateInfoDialog,
)
from wol_app.updater import UpdateChecker, check_for_updates_sync
from wol_app.utils import get_ip_key, get_resource_path
from wol_app.wol_engine import WOLEngine

# Module-level registry to hold thread references until native threads truly finish
# Prevents premature GC of QThread wrapper objects while C-level I/O is blocked
_active_threads = []


def _track_thread(thread: "QThread") -> None:
    """Keep a strong reference to *thread* until it finishes, then auto-remove.

    This guarantees the registry never grows unbounded even if a worker's
    dedicated cleanup callback is missed or disconnected.
    """
    _active_threads.append(thread)

    def _on_finished() -> None:
        try:
            if thread in _active_threads:
                _active_threads.remove(thread)
        except Exception:
            pass

    thread.finished.connect(_on_finished)

# Headless/test mode: disables all background threads to avoid QThread shutdown warnings
# Set WOL_HEADLESS=1 in test/headless environments (CI, automated tests, no display)
HEADLESS_MODE: bool = os.environ.get("WOL_HEADLESS", "").lower() in ("1", "true", "yes")


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


class MainWindow(QMainWindow):
    """Main application window."""

    # Minimum column width enforced while resizing (prevents columns collapsing)
    _MIN_COLUMN_WIDTH = 50

    def __init__(self) -> None:
        super().__init__()
        self.config = ConfigManager()

        # Load language from config and initialize translations BEFORE any UI setup
        saved_language = self.config.config.get("ui", {}).get("language", "en")
        Translations.set_language(saved_language)

        self.engine: WOLEngine[ConfigManager] = WOLEngine(self.config)

        # Load device sort settings
        sort_settings = self.config.get_device_sort_settings()
        self.device_sort_column = sort_settings["sort_column"]
        self.device_sort_order = sort_settings["sort_order"]

        self.setWindowTitle(Translations.tr("app.name"))
        self.setMinimumSize(800, 600)

        # Keep references to prevent garbage collection while threads run
        self._status_thread = None
        self._status_worker = None
        self._status_check_running = False

        # Re-entrancy guard for programmatic column-width changes
        self._updating_widths = False

        # Update checker references
        self._update_thread = None
        self._update_worker = None
        self._update_check_running = False

        # References to refreshable UI widgets for language switching
        self._title_label = None


        self._setup_menu()
        self._setup_ui()
        self._refresh_device_table()

        # Initial status check on startup (skip in headless mode)
        if not HEADLESS_MODE:
            try:
                if self.screen() is not None:
                    self._refresh_statuses()
            except Exception:
                pass  # Skip status check if display unavailable

        # Start scheduler (skip in headless mode)
        if not HEADLESS_MODE:
            self.engine.schedule_fired.connect(self._on_schedule_fired)
            self.engine.start_scheduler()

        # Auto-check for updates on startup (skip if no display/headless mode)
        if not HEADLESS_MODE:
            try:
                if self.screen() is not None and self.config.should_check_for_updates():
                    QTimer.singleShot(5000, self._check_for_updates_async)
            except Exception:
                pass  # Skip update check if display unavailable

        # Auto-refresh status every 30 seconds (skip in headless mode)
        if not HEADLESS_MODE:
            self.status_timer = QTimer(self)
            self.status_timer.timeout.connect(self._refresh_statuses)
            self.status_timer.start(30000)
        else:
            self.status_timer = None

    # ---- Update Checker Methods ------------------------------------------------

    def _check_for_updates_async(self) -> None:
        """Check for updates in a background thread (follows StatusWorker pattern)."""
        if self._update_check_running:
            return
        self._update_check_running = True

        self._update_worker = UpdateChecker(current_version=__version__)
        self._update_thread = QThread()
        self._update_worker.moveToThread(self._update_thread)

        self._update_thread.started.connect(self._update_worker.run)
        self._update_worker.finished.connect(self._on_update_check_finished)
        self._update_worker.finished.connect(self._update_thread.quit)
        self._update_thread.finished.connect(self._update_thread.deleteLater)

        def on_async_done() -> None:
            self._update_check_running = False
            if self._update_worker is not None:
                self._update_worker.deleteLater()
            self._update_worker = None
            self._update_thread = None
        self._update_thread.finished.connect(on_async_done)
        
        # Track in module-level registry (auto-removes on finish) to prevent GC
        _track_thread(self._update_thread)
        self._update_thread.start()

    def _on_update_check_finished(self, release_info, has_update) -> None:
        """Handle result of background update check."""
        if has_update and release_info:
            # Show update available dialog for the auto-check
            dlg = UpdateAvailableDialog(release_info, __version__, self)
            dlg.exec()

    def _manual_update_check(self) -> None:
        """Manually check for updates via Help menu."""
        if self._update_check_running:
            QMessageBox.information(
                self, "Update Check Running",
                "An update check is already in progress. Please wait.",
            )
            return

        result: tuple[Any, bool] | tuple[None, Literal[False]] = check_for_updates_sync(current_version=__version__)

        if result is None:
            # No internet / network error
            dlg = UpdateErrorDialog(self)
            dlg.exec()
            return

        release_info, has_update = result
        if has_update and release_info:
            dlg = UpdateAvailableDialog(release_info, __version__, self)
            dlg.exec()
        else:
            # Current version is up to date
            dlg = UpdateInfoDialog(self)
            dlg.exec()

    def _setup_menu(self) -> None:
        menubar: QMenuBar | None = self.menuBar()

        # File menu
        file_menu: QMenu | None = menubar.addMenu(Translations.tr("menu.file.title"))
        devices_action = QAction(Translations.tr("menu.file.device"), self)
        devices_action.setShortcut("Ctrl+D")
        devices_action.triggered.connect(self._open_device_manager)
        file_menu.addAction(devices_action)

        schedules_action = QAction(Translations.tr("menu.file.schedule"), self)
        schedules_action.setShortcut("Ctrl+S")
        schedules_action.triggered.connect(self._open_schedule_manager)
        file_menu.addAction(schedules_action)

        file_menu.addSeparator()
        exit_action = QAction(Translations.tr("menu.file.exit"), self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Tools menu
        tools_menu: QMenu | None = menubar.addMenu(Translations.tr("menu.tools.title"))
        network_scan_action = QAction(Translations.tr("menu.file.scan"), self)
        network_scan_action.setShortcut("Ctrl+N")
        network_scan_action.triggered.connect(self._open_network_scan)
        tools_menu.addAction(network_scan_action)

        settings_action = QAction(Translations.tr("menu.tools.settings"), self)
        settings_action.setShortcut("Ctrl+E")
        settings_action.triggered.connect(self._open_settings)
        tools_menu.addAction(settings_action)

        logs_action = QAction(Translations.tr("menu.file.logs"), self)
        logs_action.setShortcut("Ctrl+L")
        logs_action.triggered.connect(self._open_logs)
        tools_menu.addAction(logs_action)

        # Help menu
        help_menu: QMenu | None = menubar.addMenu(Translations.tr("menu.help.title"))
        check_updates_action = QAction(Translations.tr("menu.tools.update"), self)
        check_updates_action.setShortcut("Ctrl+U")
        check_updates_action.triggered.connect(self._manual_update_check)
        help_menu.addAction(check_updates_action)
        help_menu.addSeparator()

        about_action = QAction(Translations.tr("menu.help.about"), self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        # Title
        self._title_label = QLabel(Translations.tr("app.name"))
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(18)
        self._title_label.setFont(title_font)
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self._title_label)

        # Device list
        self._devices_group = QGroupBox(Translations.tr("ui.devices_group"))
        devices_layout = QVBoxLayout(self._devices_group)

        self.device_table = QTableWidget()
        self.device_table.setColumnCount(4)
        self.device_table.setHorizontalHeaderLabels([
            Translations.tr("table.header.name"),
            Translations.tr("table.header.mac"),
            Translations.tr("table.header.ip"),
            Translations.tr("table.header.status")
        ])
        header: QHeaderView | None = self.device_table.horizontalHeader()
        # All columns interactive so the user can resize them by dragging.
        # Column 0 (Name) acts as a flexible buffer: it absorbs width changes
        # of the fixed columns so the total table width stays constant.
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        # Restore saved column widths (or apply sensible defaults on first run)
        saved_widths: list[int] = self.config.get_column_widths()
        if saved_widths and len(saved_widths) == self.device_table.columnCount():
            for col in range(self.device_table.columnCount()):
                header.resizeSection(col, saved_widths[col])
        else:
            header.resizeSection(0, 300)   # Name
            header.resizeSection(1, 160)   # MAC
            header.resizeSection(2, 140)   # IP
            header.resizeSection(3, 100)   # Status
        # Persist column widths whenever the user changes them
        header.sectionResized.connect(self._on_column_resized)
        # Clicking a column header sorts the table (1st A-Z, 2nd Z-A)
        header.setSortIndicatorShown(True)
        header.setSectionsClickable(True)
        header.sectionClicked.connect(self._on_header_clicked)
        for col in range(self.device_table.columnCount()):
            item = self.device_table.horizontalHeaderItem(col)
            if item is not None:
                item.setToolTip(Translations.tr("table.sort.tooltip"))
        self.device_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.device_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.device_table.setAlternatingRowColors(True)
        # Right-click context menu on the device list
        self.device_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.device_table.customContextMenuRequested.connect(self._show_device_context_menu)
        devices_layout.addWidget(self.device_table)

        # Action buttons row
        device_btn_layout = QHBoxLayout()

        self.shutdown_btn = QPushButton(Translations.tr("button.shutdown"))
        self.shutdown_btn.clicked.connect(self._shutdown_selected)
        self.shutdown_btn.setMinimumHeight(35)
        device_btn_layout.addWidget(self.shutdown_btn)

        self.refresh_btn = QPushButton(Translations.tr("button.refresh"))
        self.refresh_btn.clicked.connect(self._refresh_statuses)
        self.refresh_btn.setMinimumHeight(35)
        device_btn_layout.addWidget(self.refresh_btn)

        self.ping_btn = QPushButton(Translations.tr("button.ping"))
        self.ping_btn.clicked.connect(self._ping_selected)
        self.ping_btn.setMinimumHeight(35)
        device_btn_layout.addWidget(self.ping_btn)

        self.wake_all_btn = QPushButton(Translations.tr("button.wake_all"))
        self.wake_all_btn.setObjectName("primaryButton")
        self.wake_all_btn.clicked.connect(self._wake_all)
        self.wake_all_btn.setMinimumHeight(35)
        device_btn_layout.addWidget(self.wake_all_btn)

        self.wake_selected_btn = QPushButton(Translations.tr("button.wake_selected"))
        self.wake_selected_btn.clicked.connect(self._wake_selected)
        self.wake_selected_btn.setMinimumHeight(35)
        device_btn_layout.addWidget(self.wake_selected_btn)

        devices_layout.addLayout(device_btn_layout)
        main_layout.addWidget(self._devices_group, 1)  # Stretch factor 1

        # Status bar
        self.statusBar().showMessage(Translations.tr("status.ready"))

    @staticmethod
    def _translated_status(status: str) -> str:
        """Return the translated, display-ready status text for *status*."""
        key_map: dict[str, str] = {
            "online": "status.online",
            "offline": "status.offline",
            "unknown": "status.unknown",
        }
        key: str = key_map.get(status, "status.unknown")
        return Translations.tr(key)

    def _show_device_context_menu(self, pos) -> None:
        """Show the right-click context menu for the device at *pos*."""
        row: int = self.device_table.rowAt(pos.y())
        if row < 0:
            return
        # Select the row under the cursor so actions apply to it
        self.device_table.selectRow(row)
        self.device_table.setCurrentCell(row, 0)

        menu = QMenu(self)
        menu.addAction(
            Translations.tr("button.shutdown"),
            lambda: self._shutdown_selected(),
        )
        menu.addAction(
            Translations.tr("button.refresh"),
            lambda: self._refresh_statuses(),
        )
        menu.addAction(
            Translations.tr("button.ping"),
            lambda: self._ping_selected(),
        )
        menu.addAction(
            Translations.tr("button.wake_selected"),
            lambda: self._wake_selected(),
        )
        menu.exec(self.device_table.viewport().mapToGlobal(pos))

    def _on_column_resized(self, column: int, old_size: int, new_size: int) -> None:
        """Keep the total table width constant when a column divider is dragged.

        When the user drags the divider between *column* and *column+1*, the
        dragged column changes size; the *next* column absorbs the inverse
        delta so the divider moves but the total table width stays constant.
        """
        # Ignore programmatic width changes to avoid cascading resize signals
        if self._updating_widths:
            return
        # The last column has no neighbour to absorb the change
        if column >= self.device_table.columnCount() - 1:
            return

        delta = new_size - old_size
        next_width = self.device_table.columnWidth(column + 1)
        new_next_width = max(self._MIN_COLUMN_WIDTH, next_width - delta)

        self._updating_widths = True
        try:
            self.device_table.setColumnWidth(column + 1, new_next_width)
        finally:
            self._updating_widths = False

        widths: list[int] = [
            self.device_table.columnWidth(col)
            for col in range(self.device_table.columnCount())
        ]
        self.config.set_column_widths(widths)

    def _fill_name_column(self) -> None:
        """Resize column 0 (Name) so the table fills the current viewport width.

        The fixed columns (1..n-1) keep their widths; column 0 absorbs the
        remaining space so the table always spans the full window.
        """
        if self._updating_widths:
            return
        self._updating_widths = True
        try:
            fixed_total = sum(
                self.device_table.columnWidth(col)
                for col in range(1, self.device_table.columnCount())
            )
            table_width = self.device_table.viewport().width()
            self.device_table.setColumnWidth(
                0, max(self._MIN_COLUMN_WIDTH, table_width - fixed_total)
            )
        finally:
            self._updating_widths = False

    def resizeEvent(self, event) -> None:
        """Keep the table filling the window: adjust the Name column on resize."""
        super().resizeEvent(event)
        self._fill_name_column()

    def showEvent(self, event) -> None:
        """After the window is shown, fill the Name column once the layout has its real width."""
        super().showEvent(event)
        # Defer until the window is mapped and the viewport has its final size
        QTimer.singleShot(0, self._fill_name_column)

    def _get_sort_key(self, device, sort_column):
        """Get sort key for a device based on sort column with special handling for IPs."""
        sort_key_map: dict[int, str] = {
            0: "name",    # Name
            1: "mac",     # MAC Address
            2: "ip",      # IP Address
        }
        
        key: str = sort_key_map.get(sort_column, "name")
        value = device.get(key, "")
        
        # Special handling for IP addresses
        if sort_column == 2:  # IP Address
            return get_ip_key(value)
        
        # Status column (3) sorts by the raw status value
        if sort_column == 3:
            return self.engine.get_device_status(device["id"])
        
        return value

    def _on_header_clicked(self, column: int) -> None:
        """Sort the device table by the clicked column: 1st A-Z, 2nd Z-A."""
        if self.device_sort_column == column:
            self.device_sort_order = "descending" if self.device_sort_order == "ascending" else "ascending"
        else:
            self.device_sort_column = column
            self.device_sort_order = "ascending"
        self._refresh_device_table()

    def _get_sorted_devices(self):
        """Get devices sorted according to current settings."""
        devices = self.config.get_devices()
        reverse_sort = self.device_sort_order == "descending"
        
        return sorted(devices, key=lambda d: self._get_sort_key(d, self.device_sort_column), reverse=reverse_sort)

    def _refresh_device_table(self) -> None:
        """Refresh the device table with current data."""
        self.device_table.setRowCount(0)
        sorted_devices = self._get_sorted_devices()
        
        # Show the active sort indicator on the header
        header: QHeaderView | None = self.device_table.horizontalHeader()
        if self.device_sort_column is not None:
            order = Qt.SortOrder.DescendingOrder if self.device_sort_order == "descending" else Qt.SortOrder.AscendingOrder
            header.setSortIndicator(self.device_sort_column, order)
        else:
            header.setSortIndicator(-1, Qt.SortOrder.AscendingOrder)
        
        for device in sorted_devices:
            row: int = self.device_table.rowCount()
            self.device_table.insertRow(row)

            name_item = QTableWidgetItem(device.get("name", ""))
            name_item.setData(Qt.ItemDataRole.UserRole, device["id"])
            if not device.get("enabled", True):
                name_item.setForeground(Qt.GlobalColor.gray)
                name_item.setText(f"{device['name']} {Translations.tr('device.disabled')}")
            self.device_table.setItem(row, 0, name_item)

            self.device_table.setItem(row, 1, QTableWidgetItem(device.get("mac", "")))
            self.device_table.setItem(row, 2, QTableWidgetItem(device.get("ip", "")))

            status: str = self.engine.get_device_status(device["id"])
            status_item = QTableWidgetItem(self._translated_status(status))
            if status == "online":
                status_item.setForeground(Qt.GlobalColor.darkGreen)
            elif status == "offline":
                status_item.setForeground(Qt.GlobalColor.darkRed)
            else:
                status_item.setForeground(Qt.GlobalColor.darkYellow)
            self.device_table.setItem(row, 3, status_item)

    def _refresh_statuses(self) -> None:
        """Ping all devices and update statuses (runs in background thread)."""
        # Prevent concurrent status checks – ignore if one is already running
        if self._status_check_running:
            self.statusBar().showMessage(Translations.tr("status.check_in_progress"))
            return

        self._status_check_running = True
        self.statusBar().showMessage(Translations.tr("status.checking"))

        self._status_worker: StatusWorker[WOLEngine[ConfigManager]] = StatusWorker(self.engine)
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
        
        # Track in module-level registry (auto-removes on finish) to prevent GC
        _track_thread(self._status_thread)
        self._status_thread.start()

    def _on_status_check_finished(self, results) -> None:
        """Callback when status check completes."""
        # Map device_id -> (name, status, msg) for robust lookups
        by_id: dict[str, tuple[str, str, str]] = {
            device_id: (name, status, msg)
            for device_id, name, status, msg in results
        }
        # Update each table row using the device id stored in its item data
        for row in range(self.device_table.rowCount()):
            item = self.device_table.item(row, 0)
            if item is None:
                continue
            device_id = item.data(Qt.ItemDataRole.UserRole)
            if not device_id or device_id not in by_id:
                continue
            _, status, _msg = by_id[device_id]
            status_item = QTableWidgetItem(self._translated_status(status))
            if status == "online":
                status_item.setForeground(Qt.GlobalColor.darkGreen)
            elif status == "offline":
                status_item.setForeground(Qt.GlobalColor.darkRed)
            else:
                status_item.setForeground(Qt.GlobalColor.darkYellow)
            self.device_table.setItem(row, 3, status_item)
        self.statusBar().showMessage(Translations.tr("status.check_complete", time=datetime.now().strftime('%H:%M:%S')))

    def _wake_selected(self) -> None:
        """Wake the currently selected device."""
        current_row: int = self.device_table.currentRow()
        if current_row < 0:
            QMessageBox.information(self, Translations.tr("dialog.select_device.title"), Translations.tr("dialog.select_device.message"))
            return

        sorted_devices = self._get_sorted_devices()
        if current_row >= len(sorted_devices):
            return
        device = sorted_devices[current_row]

        if not device.get("enabled", True):
            QMessageBox.warning(self, Translations.tr("dialog.device_disabled.title"), Translations.tr("dialog.device_disabled.message", name=device["name"]))
            return

        success, msg = self.engine.send_wake_packet(device["id"])
        if success:
            self.statusBar().showMessage(msg)
        else:
            QMessageBox.warning(self, Translations.tr("dialog.wake_failed.title"), msg)

    def _ping_selected(self) -> None:
        """Ping the currently selected device."""
        current_row: int = self.device_table.currentRow()
        if current_row < 0:
            QMessageBox.information(self, Translations.tr("dialog.select_device.title"), Translations.tr("dialog.select_device_ping.message"))
            return

        sorted_devices = self._get_sorted_devices()
        if current_row >= len(sorted_devices):
            return
        device = sorted_devices[current_row]

        status, msg = self.engine.check_device_status(device["id"])
        QMessageBox.information(self, Translations.tr("dialog.status_result.title", status=self._translated_status(status)), msg)

    def _shutdown_selected(self) -> None:
        """Show shutdown confirmation dialog for the selected device."""
        current_row: int = self.device_table.currentRow()
        if current_row < 0:
            QMessageBox.information(self, Translations.tr("dialog.select_device.title"), Translations.tr("dialog.select_device_shutdown.message"))
            return

        sorted_devices = self._get_sorted_devices()
        if current_row >= len(sorted_devices):
            return
        device = sorted_devices[current_row]

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

        self.statusBar().showMessage(Translations.tr("status.host_service_sending", name=device_name))
        QApplication.processEvents()

        success, message = send_host_command(device_ip, "shutdown", username, password)

        if success:
            self.config.add_log(device_name, "SHUTDOWN", "SUCCESS", f"Host service: {message}")
            QMessageBox.information(
                self,
                Translations.tr("dialog.shutdown_successful.title"),
                Translations.tr("dialog.shutdown_successful.message", name=device_name, ip=device_ip),
            )
            self.statusBar().showMessage(Translations.tr("status.shutdown_success", name=device_name))
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
            self.statusBar().showMessage(Translations.tr("status.shutdown_failed", name=device_name))

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

        self.statusBar().showMessage(Translations.tr("status.shutting_down", name=device_name))
        QApplication.processEvents()

        # Step 1: Connect to remote IPC$
        if username:
            # Delete any existing connection first
            delete_cmd: str = f'net use \\\\{device_ip} /delete /y'
            self.statusBar().showMessage(Translations.tr("status.deleting_connection", name=device_name))
            QApplication.processEvents()
            try:
                subprocess.run(
                    delete_cmd, shell=True, capture_output=True, encoding='utf-8', errors='replace', timeout=15
                )
            except Exception:
                pass  # Ignore errors from delete — connection may not exist yet

            # Connect with username and password
            cmd: str = f'net use \\\\{device_ip}\\IPC$ /user:{username} {password}'
            self.statusBar().showMessage(Translations.tr("status.connecting", name=device_name, ip=device_ip))
            QApplication.processEvents()
        else:
            # Connect without credentials
            cmd: str = f'net use \\\\{device_ip}\\IPC$'
            self.statusBar().showMessage(Translations.tr("status.connecting", name=device_name, ip=device_ip))
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
                self.statusBar().showMessage(Translations.tr("status.shutdown_failed", name=device_name))
                return
        except subprocess.TimeoutExpired:
            self.config.add_log(device_name, "SHUTDOWN", "ERROR", "Connection timed out")
            QMessageBox.critical(
                self, Translations.tr("dialog.connection_timeout.title"),
                Translations.tr("dialog.connection_timeout.message", name=device_name, ip=device_ip)
            )
            self.statusBar().showMessage(Translations.tr("status.shutdown_failed", name=device_name))
            return
        except Exception as e:
            self.config.add_log(device_name, "SHUTDOWN", "ERROR", f"Connection error: {str(e)}")
            QMessageBox.critical(
                self, Translations.tr("dialog.connection_error.title"),
                Translations.tr("dialog.connection_error.message", name=device_name, ip=device_ip, error=str(e))
            )
            self.statusBar().showMessage(Translations.tr("status.shutdown_failed", name=device_name))
            return

        # Step 2: Shutdown the remote PC
        shutdown_cmd: str = f'shutdown /m \\\\{device_ip} /s /t 0 /f'
        self.statusBar().showMessage(Translations.tr("status.shutting_down_remote", name=device_name))
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
                self.statusBar().showMessage(Translations.tr("status.shutdown_failed", name=device_name))
                return
        except subprocess.TimeoutExpired:
            self.config.add_log(device_name, "SHUTDOWN", "ERROR", "Shutdown command timed out")
            QMessageBox.critical(
                self, Translations.tr("dialog.shutdown_timeout.title"),
                Translations.tr("dialog.shutdown_timeout.message", name=device_name, ip=device_ip)
            )
            self.statusBar().showMessage(Translations.tr("status.shutdown_failed", name=device_name))
            return
        except Exception as e:
            self.config.add_log(device_name, "SHUTDOWN", "ERROR", f"Shutdown error: {str(e)}")
            QMessageBox.critical(
                self, Translations.tr("dialog.shutdown_error.title"),
                Translations.tr("dialog.shutdown_error.message", name=device_name, ip=device_ip, error=str(e))
            )
            self.statusBar().showMessage(Translations.tr("status.shutdown_failed", name=device_name))
            return

        self.config.add_log(device_name, "SHUTDOWN", "SUCCESS", "Shutdown initiated successfully")
        QMessageBox.information(
            self, Translations.tr("dialog.shutdown_successful.title"),
            Translations.tr("dialog.shutdown_successful.message", name=device_name, ip=device_ip)
        )
        self.statusBar().showMessage(Translations.tr("status.shutdown_success", name=device_name))

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
        self.statusBar().showMessage(msg)

    @pyqtSlot(str, str)
    def _on_schedule_fired(self, device_id: str, action: str) -> None:
        """Handle scheduled action trigger - dispatch to wake or shutdown."""
        if action == "shutdown":
            self._scheduled_shutdown(device_id)
        else:
            self.engine.send_wake_packet(device_id)

    def _scheduled_host_service_shutdown(self, device_name: str, ip: str, device: dict) -> None:
        """Execute a scheduled shutdown via the WOL Host Service (no dialog)."""
        username = device.get("username", "")
        password = device.get("password", "")

        if not username or not password:
            msg = Translations.tr("status.scheduled_shutdown_fail", name=device_name, error=Translations.tr("status.scheduled_shutdown_missing_creds"))
            self.statusBar().showMessage(msg, 5000)
            self.config.add_log(device_name, "SHUTDOWN", "FAILED", msg)
            QApplication.processEvents()
            return

        try:
            success, message = send_host_command(ip, "shutdown", username, password)
            if success:
                msg = Translations.tr("status.scheduled_shutdown_success", name=device_name)
                self.statusBar().showMessage(msg, 5000)
                self.config.add_log(device_name, "SHUTDOWN", "SUCCESS", f"Host service: {message}")
            else:
                msg = Translations.tr("status.scheduled_shutdown_fail", name=device_name, error=message)
                self.statusBar().showMessage(msg, 5000)
                self.config.add_log(device_name, "SHUTDOWN", "FAILED", f"Host service: {message}")
        except Exception as e:
            msg = Translations.tr("status.scheduled_shutdown_error", name=device_name, error=str(e))
            self.statusBar().showMessage(msg, 5000)
            self.config.add_log(device_name, "SHUTDOWN", "FAILED", msg)

        QApplication.processEvents()

    def _scheduled_shutdown(self, device_id: str) -> None:
        """Execute remote shutdown for a scheduled entry (no confirmation dialog)."""
        device = self.config.get_device_by_id(device_id)
        if not device:
            msg: str = Translations.tr("status.device_not_found", device_id=device_id)
            self.statusBar().showMessage(msg, 5000)
            return

        device_name = device.get("name", Translations.tr("device.unknown"))
        ip = device.get("ip", "")

        self.statusBar().showMessage(Translations.tr("status.scheduled_shutdown_starting", name=device_name, ip=ip), 0)
        self.config.add_log(device_name, "SHUTDOWN", "IN_PROGRESS", Translations.tr("status.scheduled_shutdown_progress", name=device_name))

        # Dispatch on the device's shutdown method
        if self.config.get_device_shutdown_method(device) == "host_service":
            self._scheduled_host_service_shutdown(device_name, ip, device)
            return

        try:
            # Step 1: Establish IPC$ connection
            username = device.get("username", "")
            password = device.get("password", "")
            
            if username:
                cmd: str = rf'net use \\{ip}\IPC$ "{password}" /user:"{username}"'
            else:
                cmd: str = rf'net use \\{ip}\IPC$'
            
            result: subprocess.CompletedProcess[str] = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=15
            )
            
            if result.returncode != 0:
                msg: str = Translations.tr("status.scheduled_shutdown_conn_fail", name=device_name, error=result.stderr.strip())
                self.statusBar().showMessage(msg, 5000)
                self.config.add_log(device_name, "SHUTDOWN", "FAILED", msg)
                QApplication.processEvents()
                return
            
            # Step 2: Execute remote shutdown
            cmd: str = rf'shutdown /m \\{ip} /s /t 0 /f'
            result: subprocess.CompletedProcess[str] = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30
            )
            
            if result.returncode == 0:
                msg: str = Translations.tr("status.scheduled_shutdown_success", name=device_name)
                self.statusBar().showMessage(msg, 5000)
                self.config.add_log(device_name, "SHUTDOWN", "SUCCESS", msg)
            else:
                msg: str = Translations.tr("status.scheduled_shutdown_fail", name=device_name, error=result.stderr.strip())
                self.statusBar().showMessage(msg, 5000)
                self.config.add_log(device_name, "SHUTDOWN", "FAILED", msg)
                
        except subprocess.TimeoutExpired:
            msg: str = Translations.tr("status.scheduled_shutdown_timeout", name=device_name)
            self.statusBar().showMessage(msg, 5000)
            self.config.add_log(device_name, "SHUTDOWN", "TIMEOUT", msg)
        except Exception as e:
            msg: str = Translations.tr("status.scheduled_shutdown_error", name=device_name, error=str(e))
            self.statusBar().showMessage(msg, 5000)
            self.config.add_log(device_name, "SHUTDOWN", "FAILED", msg)
        
        QApplication.processEvents()

    # --- Dialog openers ---

    def _open_network_scan(self) -> None:
        dialog: NetworkScanDialog[ConfigManager] = NetworkScanDialog(self.config, parent=self)
        dialog.exec()
        self._refresh_device_table()

    def _open_device_manager(self) -> None:
        dialog: DeviceManagerDialog[ConfigManager] = DeviceManagerDialog(self.config, parent=self)
        dialog.exec()
        self._refresh_device_table()

    def _open_settings(self) -> None:
        dialog: SettingsDialog[ConfigManager] = SettingsDialog(self.config, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._apply_language()

    def _apply_language(self) -> None:
        """Refresh all UI text after language change."""
        # Refresh window title
        self.setWindowTitle(Translations.tr("app.name"))

        # Rebuild menu bar
        for child in self.menuBar().actions():
            self.menuBar().removeAction(child)
        self._setup_menu()

        # Refresh title label
        if self._title_label is not None:
            self._title_label.setText(Translations.tr("app.name"))

        # Refresh devices group box
        if self._devices_group is not None:
            self._devices_group.setTitle(Translations.tr("ui.devices_group"))

        # Refresh table headers
        self.device_table.setHorizontalHeaderLabels([
            Translations.tr("table.header.name"),
            Translations.tr("table.header.mac"),
            Translations.tr("table.header.ip"),
            Translations.tr("table.header.status")
        ])

        # Refresh action buttons
        self.shutdown_btn.setText(Translations.tr("button.shutdown"))
        self.refresh_btn.setText(Translations.tr("button.refresh"))
        self.ping_btn.setText(Translations.tr("button.ping"))
        self.wake_all_btn.setText(Translations.tr("button.wake_all"))
        self.wake_selected_btn.setText(Translations.tr("button.wake_selected"))

        # Refresh status bar
        self.statusBar().showMessage(Translations.tr("status.ready"))

    def _open_schedule_manager(self) -> None:
        dialog: ScheduleDialog[ConfigManager] = ScheduleDialog(self.config, parent=self)
        dialog.exec()

    def _open_logs(self) -> None:
        dialog: LogDialog[ConfigManager] = LogDialog(self.config, parent=self)
        dialog.exec()

    def _show_about(self) -> None:
        QMessageBox.about(
            self, Translations.tr("dialog.about.title"),
            "<h3>Wake-on-LAN Manager</h3>"
            f"<p>{Translations.tr('dialog.about.version')} {__version__}</p>"
            f"<p>{Translations.tr('dialog.about.description')}</p>"
            f"<p>{Translations.tr('dialog.about.supports')}</p>"
        )

    def closeEvent(self, event) -> None:
        """Wait for all background threads to finish before closing."""
        if self.status_timer:
            self.status_timer.stop()

        # Cancel all workers
        if hasattr(self, '_status_worker') and self._status_worker is not None:
            self._status_worker.cancel()
        if self._update_worker is not None:
            self._update_worker.cancel()

        self.engine.stop_scheduler()

        # Wait for threads to actually finish (blocking C-level I/O needs time)
        # urlopen(timeout=2) + 3 devices × subprocess ping (~2s each) = ~8-10s worst case
        if self._status_thread is not None and self._status_thread.isRunning():
            self._status_thread.quit()
            self._status_thread.wait(10000)
        if self._update_thread is not None and self._update_thread.isRunning():
            self._update_thread.quit()
            self._update_thread.wait(5000)

        # Clear worker references — don't use deleteLater (needs running event loop)
        if hasattr(self, '_status_worker') and self._status_worker is not None:
            self._status_worker = None
        if self._update_worker is not None:
            self._update_worker = None
        if self._status_thread is not None:
            self._status_thread = None
        if self._update_thread is not None:
            self._update_thread = None

        # Clear module-level registry — threads will be GC'd when MainWindow is destroyed
        _active_threads.clear()

        event.accept()


def main() -> NoReturn:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # Clean modern look on Windows

    # Initialize config and translations
    config = ConfigManager()
    trans = Translations()
    language = config.config.get("ui", {}).get("language", "en")
    trans.load(language)

    # Apply display mode (auto / light / dark)
    display_mode = config.config.get("ui", {}).get("display_mode", "auto")
    apply_display_mode(app, display_mode)

    icon_path: str = get_resource_path("icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
