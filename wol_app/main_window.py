"""Main Window for Wake-on-LAN Application."""

import os
import sys
from datetime import datetime
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QMenuBar, QMenu, QStatusBar, QGroupBox, QFrame,
    QDialog, QTextEdit,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSlot, QThread, pyqtSignal, QObject
from PyQt6.QtGui import QAction, QFont, QIcon, QPalette, QColor
import subprocess
import shlex

from wol_app import __version__
from wol_app.config import ConfigManager
from wol_app.wol_engine import WOLEngine
from wol_app.device_dialog import DeviceManagerDialog
from wol_app.settings_dialog import SettingsDialog
from wol_app.schedule_dialog import ScheduleDialog
from wol_app.log_dialog import LogDialog
from wol_app.network_scan_dialog import NetworkScanDialog
from wol_app.updater import UpdateChecker, check_for_updates_sync
from wol_app.update_dialog import (
    UpdateAvailableDialog, UpdateInfoDialog, UpdateErrorDialog,
)

# Module-level registry to hold thread references until native threads truly finish
# Prevents premature GC of QThread wrapper objects while C-level I/O is blocked
_active_threads = []

# Headless/test mode: disables all background threads to avoid QThread shutdown warnings
# Set WOL_HEADLESS=1 in test/headless environments (CI, automated tests, no display)
HEADLESS_MODE = os.environ.get("WOL_HEADLESS", "").lower() in ("1", "true", "yes")


class StatusWorker(QObject):
    """Background worker for checking device statuses without blocking the UI."""
    finished = pyqtSignal(list)  # Emits list of (device_id, name, status, msg)

    def __init__(self, engine):
        super().__init__()
        self.engine = engine
        self._cancelled = False

    def cancel(self):
        """Signal the worker to stop."""
        self._cancelled = True

    def run(self):
        results = []
        for device in self.engine.config.get_devices():
            if self._cancelled:
                break
            if device.get("enabled", True):
                status, msg = self.engine.check_device_status(device["id"])
                results.append((device["id"], device["name"], status, msg))
        self.finished.emit(results)


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.config = ConfigManager()
        self.engine = WOLEngine(self.config)

        # Load device sort settings
        sort_settings = self.config.get_device_sort_settings()
        self.device_sort_column = sort_settings["sort_column"]
        self.device_sort_order = sort_settings["sort_order"]

        self.setWindowTitle("Wake-on-LAN Manager")
        self.setMinimumSize(800, 600)

        # Keep references to prevent garbage collection while threads run
        self._status_thread = None
        self._status_worker = None
        self._status_check_running = False

        # Update checker references
        self._update_thread = None
        self._update_worker = None
        self._update_check_running = False


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
            self.engine.start_scheduler(self._on_schedule_fired)

        # Auto-check for updates on startup (skip if no display/headless mode)
        if not HEADLESS_MODE:
            try:
                from PyQt6.QtGui import QScreen
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

    def _check_for_updates_async(self):
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

        def on_async_done():
            self._update_check_running = False
            if self._update_worker is not None:
                self._update_worker.deleteLater()
            # Remove from module-level registry after thread finishes
            if self._update_thread is not None and self._update_thread in _active_threads:
                _active_threads.remove(self._update_thread)
            self._update_worker = None
            self._update_thread = None
        self._update_thread.finished.connect(on_async_done)
        
        # Track in module-level registry to prevent GC while native thread runs
        _active_threads.append(self._update_thread)
        self._update_thread.start()

    def _on_update_check_finished(self, release_info, has_update):
        """Handle result of background update check."""
        if has_update and release_info:
            # Show update available dialog for the auto-check
            dlg = UpdateAvailableDialog(release_info, __version__, self)
            dlg.exec()

    def _manual_update_check(self):
        """Manually check for updates via Help menu."""
        if self._update_check_running:
            QMessageBox.information(
                self, "Update Check Running",
                "An update check is already in progress. Please wait.",
            )
            return

        result = check_for_updates_sync(current_version=__version__)

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

    def _setup_menu(self):
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")
        devices_action = QAction("Manage &Devices...", self)
        devices_action.setShortcut("Ctrl+D")
        devices_action.triggered.connect(self._open_device_manager)
        file_menu.addAction(devices_action)

        schedules_action = QAction("Manage &Schedules...", self)
        schedules_action.setShortcut("Ctrl+S")
        schedules_action.triggered.connect(self._open_schedule_manager)
        file_menu.addAction(schedules_action)

        file_menu.addSeparator()
        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Tools menu
        tools_menu = menubar.addMenu("&Tools")
        network_scan_action = QAction("Netzwerk &scannen...", self)
        network_scan_action.setShortcut("Ctrl+N")
        network_scan_action.triggered.connect(self._open_network_scan)
        tools_menu.addAction(network_scan_action)

        settings_action = QAction("&Network Settings...", self)
        settings_action.setShortcut("Ctrl+E")
        settings_action.triggered.connect(self._open_settings)
        tools_menu.addAction(settings_action)

        logs_action = QAction("View &Logs...", self)
        logs_action.setShortcut("Ctrl+L")
        logs_action.triggered.connect(self._open_logs)
        tools_menu.addAction(logs_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")
        check_updates_action = QAction("Nach &Updates suchen...", self)
        check_updates_action.setShortcut("Ctrl+U")
        check_updates_action.triggered.connect(self._manual_update_check)
        help_menu.addAction(check_updates_action)
        help_menu.addSeparator()

        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        # Title
        title_label = QLabel("Wake-on-LAN Manager")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(18)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_label)

        # Device list
        devices_group = QGroupBox("Devices")
        devices_layout = QVBoxLayout(devices_group)

        self.device_table = QTableWidget()
        self.device_table.setColumnCount(4)
        self.device_table.setHorizontalHeaderLabels(["Name", "MAC Address", "IP", "Status"])
        header = self.device_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(1, 160)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.device_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.device_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.device_table.setAlternatingRowColors(True)
        # Set alternating row color to a medium gray for better visibility
        palette = self.device_table.palette()
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(75, 75, 75))
        self.device_table.setPalette(palette)
        devices_layout.addWidget(self.device_table)

        # Action buttons row
        device_btn_layout = QHBoxLayout()

        self.shutdown_btn = QPushButton("Shut Down")
        self.shutdown_btn.clicked.connect(self._shutdown_selected)
        self.shutdown_btn.setMinimumHeight(35)
        device_btn_layout.addWidget(self.shutdown_btn)

        self.refresh_btn = QPushButton("Refresh Status")
        self.refresh_btn.clicked.connect(self._refresh_statuses)
        self.refresh_btn.setMinimumHeight(35)
        device_btn_layout.addWidget(self.refresh_btn)

        ping_selected_btn = QPushButton("Ping Selected")
        ping_selected_btn.clicked.connect(self._ping_selected)
        ping_selected_btn.setMinimumHeight(35)
        device_btn_layout.addWidget(ping_selected_btn)

        self.wake_all_btn = QPushButton("Wake All Devices")
        self.wake_all_btn.setObjectName("primaryButton")
        self.wake_all_btn.clicked.connect(self._wake_all)
        self.wake_all_btn.setMinimumHeight(35)
        device_btn_layout.addWidget(self.wake_all_btn)

        self.wake_selected_btn = QPushButton("Wake Selected")
        self.wake_selected_btn.clicked.connect(self._wake_selected)
        self.wake_selected_btn.setMinimumHeight(35)
        device_btn_layout.addWidget(self.wake_selected_btn)

        devices_layout.addLayout(device_btn_layout)
        main_layout.addWidget(devices_group, 1)  # Stretch factor 1

        # Status bar
        self.statusBar().showMessage("Ready")

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
            0: "name",    # Name
            1: "mac",     # MAC Address
            2: "ip",      # IP Address
        }
        
        key = sort_key_map.get(sort_column, "name")
        value = device.get(key, "")
        
        # Special handling for IP addresses
        if sort_column == 2:  # IP Address
            return self._get_ip_key(value)
        
        return value

    def _get_sorted_devices(self):
        """Get devices sorted according to current settings."""
        devices = self.config.get_devices()
        reverse_sort = self.device_sort_order == "descending"
        
        return sorted(devices, key=lambda d: self._get_sort_key(d, self.device_sort_column), reverse=reverse_sort)

    def _refresh_device_table(self):
        """Refresh the device table with current data."""
        self.device_table.setRowCount(0)
        sorted_devices = self._get_sorted_devices()
        
        for device in sorted_devices:
            row = self.device_table.rowCount()
            self.device_table.insertRow(row)

            name_item = QTableWidgetItem(device.get("name", ""))
            if not device.get("enabled", True):
                name_item.setForeground(Qt.GlobalColor.gray)
                name_item.setText(f"{device['name']} (disabled)")
            self.device_table.setItem(row, 0, name_item)

            self.device_table.setItem(row, 1, QTableWidgetItem(device.get("mac", "")))
            self.device_table.setItem(row, 2, QTableWidgetItem(device.get("ip", "")))

            status = self.engine.get_device_status(device["id"])
            status_item = QTableWidgetItem(status.capitalize())
            if status == "online":
                status_item.setForeground(Qt.GlobalColor.darkGreen)
            elif status == "offline":
                status_item.setForeground(Qt.GlobalColor.darkRed)
            else:
                status_item.setForeground(Qt.GlobalColor.darkYellow)
            self.device_table.setItem(row, 3, status_item)

    def _refresh_statuses(self):
        """Ping all devices and update statuses (runs in background thread)."""
        # Prevent concurrent status checks – ignore if one is already running
        if self._status_check_running:
            self.statusBar().showMessage("Status check already in progress...")
            return

        self._status_check_running = True
        self.statusBar().showMessage("Checking device statuses...")

        self._status_worker = StatusWorker(self.engine)
        self._status_thread = QThread()
        self._status_worker.moveToThread(self._status_thread)
        self._status_thread.started.connect(self._status_worker.run)
        self._status_worker.finished.connect(self._on_status_check_finished)
        self._status_worker.finished.connect(self._status_thread.quit)
        self._status_worker.finished.connect(self._status_worker.deleteLater)

        def on_thread_finished():
            self._status_check_running = False
            # Remove from module-level registry after thread finishes
            if self._status_thread is not None and self._status_thread in _active_threads:
                _active_threads.remove(self._status_thread)
            self._status_thread = None

        self._status_thread.finished.connect(on_thread_finished)
        
        # Track in module-level registry to prevent GC while native thread runs
        _active_threads.append(self._status_thread)
        self._status_thread.start()

    def _on_status_check_finished(self, results):
        """Callback when status check completes."""
        for device_id, name, status, msg in results:
            # Update table by finding the row with matching device name
            for row in range(self.device_table.rowCount()):
                item_name = self.device_table.item(row, 0).text().replace(" (disabled)", "")
                if item_name == name:
                    status_item = QTableWidgetItem(status.capitalize())
                    if status == "online":
                        status_item.setForeground(Qt.GlobalColor.darkGreen)
                    elif status == "offline":
                        status_item.setForeground(Qt.GlobalColor.darkRed)
                    else:
                        status_item.setForeground(Qt.GlobalColor.darkYellow)
                    self.device_table.setItem(row, 3, status_item)
                    break
        self.statusBar().showMessage(f"Status check complete at {datetime.now().strftime('%H:%M:%S')}")

    def _wake_selected(self):
        """Wake the currently selected device."""
        current_row = self.device_table.currentRow()
        if current_row < 0:
            QMessageBox.information(self, "Select Device", "Please select a device to wake.")
            return

        sorted_devices = self._get_sorted_devices()
        if current_row >= len(sorted_devices):
            return
        device = sorted_devices[current_row]

        if not device.get("enabled", True):
            QMessageBox.warning(self, "Device Disabled", f"'{device['name']}' is disabled.")
            return

        success, msg = self.engine.send_wake_packet(device["id"])
        if success:
            self.statusBar().showMessage(msg)
        else:
            QMessageBox.warning(self, "Wake Failed", msg)

    def _ping_selected(self):
        """Ping the currently selected device."""
        current_row = self.device_table.currentRow()
        if current_row < 0:
            QMessageBox.information(self, "Select Device", "Please select a device to ping.")
            return

        sorted_devices = self._get_sorted_devices()
        if current_row >= len(sorted_devices):
            return
        device = sorted_devices[current_row]

        status, msg = self.engine.check_device_status(device["id"])
        QMessageBox.information(self, f"Status: {status.upper()}", msg)

    def _shutdown_selected(self):
        """Show shutdown confirmation dialog for the selected device."""
        current_row = self.device_table.currentRow()
        if current_row < 0:
            QMessageBox.information(self, "Select Device", "Please select a device to shut down.")
            return

        sorted_devices = self._get_sorted_devices()
        if current_row >= len(sorted_devices):
            return
        device = sorted_devices[current_row]

        device_name = device.get("name", "")
        device_ip = device.get("ip", "")

        if not device_ip:
            QMessageBox.warning(self, "No IP Address", f"'{device_name}' has no IP address configured.")
            return

        # Build confirmation dialog
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Shut Down {device_name}")
        dialog.setMinimumWidth(450)
        layout = QVBoxLayout(dialog)

        label1 = QLabel(f"Would you like to shut down {device_name}?")
        layout.addWidget(label1)

        label2 = QLabel(
            "If local user and password do not match the remote device, "
            "they have to be added to the device entry."
        )
        layout.addWidget(label2)

        label3 = QLabel("To shut down device remotely following Settings are required:")
        layout.addWidget(label3)

        registry_text = QTextEdit()
        registry_text.setPlainText(
            "- [HKEY_LOCAL_MACHINE\\\\SOFTWARE\\\\Microsoft\\\\Windows\\\\CurrentVersion\\\\Policies\\\\System]\n"
            "  \"LocalAccountTokenFilterPolicy\"=dword:00000001\n"
            "\n"
            "- File- and Printer Sharing activated"
        )
        registry_text.setReadOnly(True)
        registry_text.setMaximumHeight(80)
        layout.addWidget(registry_text)

        # Buttons
        button_layout = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(dialog.reject)
        shutdown_confirm_btn = QPushButton("Shut Down")
        shutdown_confirm_btn.setObjectName("primaryButton")
        shutdown_confirm_btn.clicked.connect(lambda: self._execute_shutdown(device, dialog))
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(shutdown_confirm_btn)
        layout.addLayout(button_layout)

        dialog.exec()

    def _execute_shutdown(self, device, dialog):
        """Execute the remote shutdown sequence for a device."""
        dialog.accept()  # Close the confirmation dialog

        device_name = device.get("name", "")
        device_ip = device.get("ip", "")
        username = device.get("username", "")
        password = device.get("password", "")

        self.statusBar().showMessage(f"Shutting down {device_name}...")
        QApplication.processEvents()

        # Step 1: Connect to remote IPC$
        if username:
            # Delete any existing connection first
            delete_cmd = f'net use \\\\{device_ip} /delete /y'
            self.statusBar().showMessage(f"Lösche bestehende Verbindung zu {device_name}...")
            QApplication.processEvents()
            try:
                subprocess.run(
                    delete_cmd, shell=True, capture_output=True, encoding='utf-8', errors='replace', timeout=15
                )
            except Exception:
                pass  # Ignore errors from delete — connection may not exist yet

            # Connect with username and password
            cmd = f'net use \\\\{device_ip}\\IPC$ /user:{username} {password}'
            self.statusBar().showMessage(f"Verbinde mit {device_name} ({device_ip})...")
            QApplication.processEvents()
        else:
            # Connect without credentials
            cmd = f'net use \\\\{device_ip}\\IPC$'
            self.statusBar().showMessage(f"Verbinde mit {device_name} ({device_ip})...")
            QApplication.processEvents()

        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, encoding='utf-8', errors='replace', timeout=30
            )
            if result.returncode != 0:
                error_msg = result.stderr.strip() or result.stdout.strip()
                self.config.add_log(device_name, "SHUTDOWN", "ERROR", f"Connection failed: {error_msg}")
                QMessageBox.critical(
                    self, "Connection Failed",
                    f"Could not connect to {device_name} ({device_ip}).\n\n{error_msg}"
                )
                self.statusBar().showMessage(f"Shutdown of {device_name} failed.")
                return
        except subprocess.TimeoutExpired:
            self.config.add_log(device_name, "SHUTDOWN", "ERROR", "Connection timed out")
            QMessageBox.critical(
                self, "Connection Timeout",
                f"Connection to {device_name} ({device_ip}) timed out."
            )
            self.statusBar().showMessage(f"Shutdown of {device_name} failed.")
            return
        except Exception as e:
            self.config.add_log(device_name, "SHUTDOWN", "ERROR", f"Connection error: {str(e)}")
            QMessageBox.critical(
                self, "Connection Error",
                f"Could not connect to {device_name} ({device_ip}).\n\n{str(e)}"
            )
            self.statusBar().showMessage(f"Shutdown of {device_name} failed.")
            return

        # Step 2: Shutdown the remote PC
        shutdown_cmd = f'shutdown /m \\\\{device_ip} /s /t 0 /f'
        self.statusBar().showMessage(f"Fahre {device_name} herunter...")
        QApplication.processEvents()
        try:
            result = subprocess.run(
                shutdown_cmd, shell=True, capture_output=True, encoding='utf-8', errors='replace', timeout=30
            )
            if result.returncode != 0:
                error_msg = result.stderr.strip() or result.stdout.strip()
                self.config.add_log(device_name, "SHUTDOWN", "ERROR", f"Shutdown failed: {error_msg}")
                QMessageBox.critical(
                    self, "Shutdown Failed",
                    f"Could not shut down {device_name} ({device_ip}).\n\n{error_msg}"
                )
                self.statusBar().showMessage(f"Shutdown of {device_name} failed.")
                return
        except subprocess.TimeoutExpired:
            self.config.add_log(device_name, "SHUTDOWN", "ERROR", "Shutdown command timed out")
            QMessageBox.critical(
                self, "Shutdown Timeout",
                f"Shutdown command for {device_name} ({device_ip}) timed out."
            )
            self.statusBar().showMessage(f"Shutdown of {device_name} failed.")
            return
        except Exception as e:
            self.config.add_log(device_name, "SHUTDOWN", "ERROR", f"Shutdown error: {str(e)}")
            QMessageBox.critical(
                self, "Shutdown Error",
                f"Could not shut down {device_name} ({device_ip}).\n\n{str(e)}"
            )
            self.statusBar().showMessage(f"Shutdown of {device_name} failed.")
            return

        self.config.add_log(device_name, "SHUTDOWN", "SUCCESS", "Shutdown initiated successfully")
        QMessageBox.information(
            self, "Shutdown Successful",
            f"{device_name} ({device_ip}) is shutting down."
        )
        self.statusBar().showMessage(f"{device_name} shutdown initiated successfully.")

    def _wake_all(self):
        """Wake all enabled devices."""
        devices = [d for d in self.config.get_devices() if d.get("enabled", True)]
        if not devices:
            QMessageBox.information(self, "No Devices", "No enabled devices to wake.")
            return

        reply = QMessageBox.question(
            self, "Wake All",
            f"Wake all {len(devices)} enabled device(s)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        results = self.engine.wake_all()
        success_count = sum(1 for _, s, _ in results if s)
        fail_count = len(results) - success_count

        msg = f"Wake complete:\n{success_count} succeeded"
        if fail_count:
            msg += f", {fail_count} failed"
        QMessageBox.information(self, "Wake All Complete", msg)
        self.statusBar().showMessage(msg)

    @pyqtSlot(str, str)
    def _on_schedule_fired(self, device_id: str, action: str):
        """Handle scheduled action trigger - dispatch to wake or shutdown."""
        if action == "shutdown":
            self._scheduled_shutdown(device_id)
        else:
            self.engine.send_wake_packet(device_id)

    def _scheduled_shutdown(self, device_id: str):
        """Execute remote shutdown for a scheduled entry (no confirmation dialog)."""
        device = self.config.get_device_by_id(device_id)
        if not device:
            msg = f"Device {device_id} not found - scheduled shutdown skipped"
            self.statusBar().showMessage(msg, 5000)
            return

        device_name = device.get("name", "Unknown")
        ip = device.get("ip", "")
        
        self.statusBar().showMessage(f"Shutting down {device_name} ({ip})...", 0)
        self.config.add_log(device_name, "SHUTDOWN", "IN_PROGRESS", f"Scheduled shutdown for {device_name}")
        
        try:
            # Step 1: Establish IPC$ connection
            username = device.get("username", "")
            password = device.get("password", "")
            
            if username:
                cmd = rf'net use \\{ip}\IPC$ "{password}" /user:"{username}"'
            else:
                cmd = rf'net use \\{ip}\IPC$'
            
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=15
            )
            
            if result.returncode != 0:
                msg = f"SHUTDOWN FAILED - Could not connect to {device_name}: {result.stderr.strip()}"
                self.statusBar().showMessage(msg, 5000)
                self.config.add_log(device_name, "SHUTDOWN", "FAILED", msg)
                QApplication.processEvents()
                return
            
            # Step 2: Execute remote shutdown
            cmd = rf'shutdown /m \\{ip} /s /t 0 /f'
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=30
            )
            
            if result.returncode == 0:
                msg = f"Successfully initiated shutdown for {device_name}"
                self.statusBar().showMessage(msg, 5000)
                self.config.add_log(device_name, "SHUTDOWN", "SUCCESS", msg)
            else:
                msg = f"SHUTDOWN FAILED for {device_name}: {result.stderr.strip()}"
                self.statusBar().showMessage(msg, 5000)
                self.config.add_log(device_name, "SHUTDOWN", "FAILED", msg)
                
        except subprocess.TimeoutExpired:
            msg = f"SHUTDOWN TIMEOUT for {device_name}"
            self.statusBar().showMessage(msg, 5000)
            self.config.add_log(device_name, "SHUTDOWN", "TIMEOUT", msg)
        except Exception as e:
            msg = f"SHUTDOWN ERROR for {device_name}: {str(e)}"
            self.statusBar().showMessage(msg, 5000)
            self.config.add_log(device_name, "SHUTDOWN", "FAILED", msg)
        
        QApplication.processEvents()

    # --- Dialog openers ---

    def _open_network_scan(self):
        dialog = NetworkScanDialog(self.config, parent=self)
        dialog.exec()
        self._refresh_device_table()

    def _open_device_manager(self):
        dialog = DeviceManagerDialog(self.config, parent=self)
        dialog.exec()
        self._refresh_device_table()

    def _open_settings(self):
        dialog = SettingsDialog(self.config, parent=self)
        dialog.exec()

    def _open_schedule_manager(self):
        dialog = ScheduleDialog(self.config, parent=self)
        dialog.exec()

    def _open_logs(self):
        dialog = LogDialog(self.config, parent=self)
        dialog.exec()

    def _show_about(self):
        QMessageBox.about(
            self, "About Wake-on-LAN Manager",
            "<h3>Wake-on-LAN Manager</h3>"
            f"<p>Version {__version__}</p>"
            "<p>Send magic packets to wake up computers on your network.</p>"
            "<p>Supports up to 8 devices with scheduling and status monitoring.</p>"
        )

    def closeEvent(self, event):
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


def get_resource_path(filename):
    """Get absolute path to resource, works for dev and PyInstaller."""
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        base_path = sys._MEIPASS
    else:
        # Running in development mode
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, filename)


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # Clean modern look on Windows

    icon_path = get_resource_path("icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
