"""Network Scan Dialog - Discover and add devices from the local network."""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QProgressBar, QWidget, QCheckBox, QGroupBox,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QPalette, QColor

from wol_app.network_scanner import get_local_interfaces, scan_subnet
from wol_app.translations import Translations


class ScanWorker(QObject):
    """Background worker for network scanning."""
    progress = pyqtSignal(str, int, int)  # message, current, total
    finished = pyqtSignal(list)

    def __init__(self, interfaces: list, timeout: int = 1):
        super().__init__()
        self.interfaces = interfaces
        self.timeout = timeout

    def run(self):
        all_results = []
        seen_ips = set()

        for iface in self.interfaces:
            iface_msg = Translations.tr("scan.scanning_subnet", ip=iface["ip"])
            self.progress.emit(iface_msg, 0, 0)

            try:
                def on_progress(current, total, msg):
                    self.progress.emit(msg, current, total)

                hosts = scan_subnet(
                    iface["ip"], iface["netmask"],
                    self.timeout, progress_callback=on_progress
                )
                for host in hosts:
                    if host["ipv4"] not in seen_ips:
                        seen_ips.add(host["ipv4"])
                        all_results.append(host)
            except Exception as e:
                self.progress.emit(
                    Translations.tr("scan.error_interface", ip=iface["ip"], error=str(e)), 0, 0
                )

        self.progress.emit(
            Translations.tr("scan.total_found", count=len(all_results)), 0, 0
        )
        self.finished.emit(all_results)


class NetworkScanDialog(QDialog):
    """Dialog to scan the network and display discovered devices."""

    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.config = config_manager
        self.setWindowTitle(Translations.tr("scan_dialog.title"))
        self.setMinimumSize(800, 500)

        # Keep references to prevent garbage collection while thread runs
        self._scan_thread = None
        self._scan_worker = None

        self._setup_ui()

    def _get_interfaces(self):
        """Return list of local network interfaces."""
        return get_local_interfaces()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # --- Network selection group ---
        net_group = QGroupBox(Translations.tr("scan_dialog.group.network_select"))
        net_layout = QVBoxLayout(net_group)

        self.net_checkboxes = []
        for idx, iface in enumerate(self._get_interfaces()):
            cb = QCheckBox(f"{iface['ip']} / {iface['netmask']}")
            cb.setChecked(idx == 0)  # Only first network selected by default
            self.net_checkboxes.append(cb)
            net_layout.addWidget(cb)

        if not self.net_checkboxes:
            no_net_label = QLabel(Translations.tr("scan_dialog.no_interfaces"))
            no_net_label.setForeground(Qt.GlobalColor.red)
            net_layout.addWidget(no_net_label)

        layout.addWidget(net_group)

        # --- Scan button ---
        scan_btn_layout = QHBoxLayout()
        scan_btn_layout.addStretch()
        self.scan_btn = QPushButton(Translations.tr("scan_dialog.button.scan"))
        self.scan_btn.clicked.connect(self._start_scan)
        self.scan_btn.setMinimumHeight(35)
        scan_btn_layout.addWidget(self.scan_btn)
        layout.addLayout(scan_btn_layout)

        # Info label
        self.info_label = QLabel(Translations.tr("scan_dialog.info.initial"))
        info_font = QFont()
        info_font.setItalic(True)
        self.info_label.setFont(info_font)
        layout.addWidget(self.info_label)

        # Progress bar (hidden until scan starts)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)

        # Results table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels([
            Translations.tr("scan_dialog.col.name"),
            Translations.tr("scan_dialog.col.ipv4"),
            Translations.tr("scan_dialog.col.ipv6"),
            Translations.tr("scan_dialog.col.mac"),
        ])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(3, 160)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        palette = self.table.palette()
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(75, 75, 75))
        self.table.setPalette(palette)
        layout.addWidget(self.table)

        # Buttons
        btn_layout = QHBoxLayout()

        self.add_btn = QPushButton(Translations.tr("scan_dialog.button.add_selected"))
        self.add_btn.clicked.connect(self._add_selected_device)
        self.add_btn.setEnabled(False)
        btn_layout.addWidget(self.add_btn)

        close_btn = QPushButton(Translations.tr("dialog.button.close"))
        close_btn.clicked.connect(self.accept)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def _get_selected_interfaces(self):
        """Return list of interfaces the user checked."""
        selected = []
        all_ifaces = self._get_interfaces()
        for cb, iface in zip(self.net_checkboxes, all_ifaces):
            if cb.isChecked():
                selected.append(iface)
        return selected

    def _start_scan(self):
        """Start network scan in background thread."""
        selected = self._get_selected_interfaces()
        if not selected:
            QMessageBox.warning(
                self, Translations.tr("scan_dialog.no_network_selected"),
                Translations.tr("scan_dialog.no_network_selected_msg")
            )
            return

        self.table.setRowCount(0)
        self.add_btn.setEnabled(False)
        self.progress_bar.show()
        self.progress_bar.setValue(0)
        self.scan_btn.setEnabled(False)
        self.info_label.setText(Translations.tr("scan_dialog.scanning"))

        # Cancel any previous running scan
        if self._scan_thread is not None:
            try:
                if self._scan_thread.isRunning():
                    self._scan_thread.quit()
                    self._scan_thread.wait(1000)
            except RuntimeError:
                self._scan_thread = None

        self._scan_worker = ScanWorker(selected)
        self._scan_thread = QThread()
        self._scan_worker.moveToThread(self._scan_thread)
        self._scan_thread.started.connect(self._scan_worker.run)
        self._scan_worker.progress.connect(self._on_scan_progress)
        self._scan_worker.finished.connect(self._on_scan_finished)
        self._scan_worker.finished.connect(self._scan_thread.quit)
        self._scan_worker.finished.connect(self._scan_worker.deleteLater)

        def on_thread_finished():
            self._scan_thread.deleteLater()
            self._scan_thread = None
            self.scan_btn.setEnabled(True)  # Re-enable scan button

        self._scan_thread.finished.connect(on_thread_finished)
        self._scan_thread.start()

    def _on_scan_progress(self, message: str, current: int, total: int):
        """Update progress display."""
        self.info_label.setText(message)
        if total > 0:
            percentage = int((current / total) * 100)
            self.progress_bar.setValue(percentage)

    def _on_scan_finished(self, results: list):
        """Populate table with scan results."""
        self.progress_bar.setValue(100)
        self.info_label.setText(
            Translations.tr("scan_dialog.complete", count=len(results))
        )
        self.table.setRowCount(0)

        for host in results:
            row = self.table.rowCount()
            self.table.insertRow(row)

            hostname_item = QTableWidgetItem(host.get("hostname", "Unknown"))
            self.table.setItem(row, 0, hostname_item)

            ipv4_item = QTableWidgetItem(host.get("ipv4", ""))
            self.table.setItem(row, 1, ipv4_item)

            ipv6_item = QTableWidgetItem(host.get("ipv6", "N/A"))
            ipv6_item.setForeground(Qt.GlobalColor.gray)
            self.table.setItem(row, 2, ipv6_item)

            mac_item = QTableWidgetItem(host.get("mac", "Unknown"))
            self.table.setItem(row, 3, mac_item)

        self.add_btn.setEnabled(len(results) > 0)

    def _add_selected_device(self):
        """Add the selected device to configured devices."""
        current_row = self.table.currentRow()
        if current_row < 0:
            QMessageBox.information(
                self, Translations.tr("scan_dialog.no_selection"),
                Translations.tr("scan_dialog.no_selection_msg")
            )
            return

        hostname = self.table.item(current_row, 0).text()
        ipv4 = self.table.item(current_row, 1).text()
        mac = self.table.item(current_row, 3).text()

        # Check if MAC is valid (not "Unknown")
        if mac == "Unknown":
            reply = QMessageBox.question(
                self, Translations.tr("scan_dialog.mac_unknown"),
                Translations.tr(
                    "scan_dialog.mac_unknown_msg", hostname=hostname, ip=ipv4
                ),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            mac = "00:00:00:00:00:00"  # Placeholder

        # Check if device with this MAC already exists
        existing_devices = self.config.get_devices()
        for dev in existing_devices:
            if dev.get("mac", "").upper() == mac.upper():
                QMessageBox.warning(
                    self, Translations.tr("scan_dialog.already_exists"),
                    Translations.tr("scan_dialog.already_exists_msg", mac=mac)
                )
                return

        # Add device
        device = self.config.add_device(hostname, mac)
        if device:
            # Set IP address
            self.config.update_device(device["id"], ip=ipv4)
            QMessageBox.information(
                self, Translations.tr("scan_dialog.success"),
                Translations.tr("scan_dialog.success_msg", hostname=hostname)
            )
        else:
            QMessageBox.critical(
                self, Translations.tr("dialog.error"),
                Translations.tr("scan_dialog.add_failed", hostname=hostname)
            )
