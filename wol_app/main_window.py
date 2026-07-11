"""Main Window for Wake-on-LAN Application."""

import os
import sys
from datetime import datetime
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QMenuBar, QMenu, QStatusBar, QGroupBox, QFrame,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSlot, QThread, pyqtSignal, QObject
from PyQt6.QtGui import QAction, QFont, QIcon, QPalette, QColor

from wol_app.config import ConfigManager
from wol_app.wol_engine import WOLEngine
from wol_app.device_dialog import DeviceManagerDialog
from wol_app.settings_dialog import SettingsDialog
from wol_app.schedule_dialog import ScheduleDialog
from wol_app.log_dialog import LogDialog
from wol_app.network_scan_dialog import NetworkScanDialog


class StatusWorker(QObject):
    """Background worker for checking device statuses without blocking the UI."""
    finished = pyqtSignal(list)  # Emits list of (device_id, name, status, msg)

    def __init__(self, engine):
        super().__init__()
        self.engine = engine

    def run(self):
        results = []
        for device in self.engine.config.get_devices():
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

        self.setWindowTitle("Wake-on-LAN Manager")
        self.setMinimumSize(800, 600)

        # Keep references to prevent garbage collection while thread runs
        self._status_thread = None
        self._status_worker = None

        self._setup_menu()
        self._setup_ui()
        self._refresh_device_table()

        # Initial status check on startup
        self._refresh_statuses()

        # Start scheduler
        self.engine.start_scheduler(self._on_scheduled_wake)

        # Auto-refresh status every 30 seconds
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self._refresh_statuses)
        self.status_timer.start(30000)

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
        network_scan_action.triggered.connect(self._open_network_scan)
        tools_menu.addAction(network_scan_action)

        settings_action = QAction("&Network Settings...", self)
        settings_action.triggered.connect(self._open_settings)
        tools_menu.addAction(settings_action)

        logs_action = QAction("View &Logs...", self)
        logs_action.setShortcut("Ctrl+L")
        logs_action.triggered.connect(self._open_logs)
        tools_menu.addAction(logs_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")
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

        # Quick action buttons
        actions_frame = QFrame()
        actions_layout = QHBoxLayout(actions_frame)

        self.wake_all_btn = QPushButton("Wake All Devices")
        self.wake_all_btn.setObjectName("primaryButton")
        self.wake_all_btn.clicked.connect(self._wake_all)
        self.wake_all_btn.setMinimumHeight(40)

        self.refresh_btn = QPushButton("Refresh Status")
        self.refresh_btn.clicked.connect(self._refresh_statuses)
        self.refresh_btn.setMinimumHeight(40)

        actions_layout.addWidget(self.wake_all_btn)
        actions_layout.addWidget(self.refresh_btn)
        main_layout.addWidget(actions_frame)

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

        # Per-device wake buttons row
        device_btn_layout = QHBoxLayout()
        device_btn_layout.addStretch()
        self.wake_selected_btn = QPushButton("Wake Selected")
        self.wake_selected_btn.clicked.connect(self._wake_selected)
        self.wake_selected_btn.setMinimumHeight(35)
        device_btn_layout.addWidget(self.wake_selected_btn)

        ping_selected_btn = QPushButton("Ping Selected")
        ping_selected_btn.clicked.connect(self._ping_selected)
        ping_selected_btn.setMinimumHeight(35)
        device_btn_layout.addWidget(ping_selected_btn)

        devices_layout.addLayout(device_btn_layout)
        main_layout.addWidget(devices_group, 1)  # Stretch factor 1

        # Status bar
        self.statusBar().showMessage("Ready")

    def _refresh_device_table(self):
        """Refresh the device table with current data."""
        self.device_table.setRowCount(0)
        for device in self.config.get_devices():
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
        self.statusBar().showMessage("Checking device statuses...")

        # Cancel any previous running status check
        if self._status_thread is not None:
            try:
                if self._status_thread.isRunning():
                    self._status_thread.quit()
                    self._status_thread.wait(1000)
            except RuntimeError:
                # Thread was already deleted, reset reference
                self._status_thread = None

        self._status_worker = StatusWorker(self.engine)
        self._status_thread = QThread()
        self._status_worker.moveToThread(self._status_thread)
        self._status_thread.started.connect(self._status_worker.run)
        self._status_worker.finished.connect(self._on_status_check_finished)
        self._status_worker.finished.connect(self._status_thread.quit)
        self._status_worker.finished.connect(self._status_worker.deleteLater)

        def on_thread_finished():
            self._status_thread.deleteLater()
            self._status_thread = None  # Clear reference after deletion

        self._status_thread.finished.connect(on_thread_finished)
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

        devices = self.config.get_devices()
        if current_row >= len(devices):
            return
        device = devices[current_row]

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

        devices = self.config.get_devices()
        if current_row >= len(devices):
            return
        device = devices[current_row]

        status, msg = self.engine.check_device_status(device["id"])
        QMessageBox.information(self, f"Status: {status.upper()}", msg)

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

    @pyqtSlot(str)
    def _on_scheduled_wake(self, device_id: str):
        """Handle scheduled wake trigger."""
        self.engine.send_wake_packet(device_id)

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
            "<p>Send magic packets to wake up computers on your network.</p>"
            "<p>Supports up to 8 devices with scheduling and status monitoring.</p>"
            "<p>Version 1.1.0</p>"
        )

    def closeEvent(self, event):
        """Cleanup on close."""
        self.engine.stop_scheduler()
        if self.status_timer:
            self.status_timer.stop()
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
