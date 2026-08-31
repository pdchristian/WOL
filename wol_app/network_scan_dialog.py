"""Network Scan Dialog - Discover and add devices from the local network."""

from typing import Any

from PyQt6.QtCore import Qt, QThread
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from wol_app.network_scanner import (
    get_dns_servers_for_interface,
    get_local_interfaces,
    is_real_interface,
)
from wol_app.scan_worker import ScanWorker
from wol_app.translations import Translations
from wol_app.utils import get_ip_key, sort_rows


class NetworkScanDialog(QDialog):
    """Dialog to scan the network and display discovered devices."""

    def __init__(self, config_manager, parent=None) -> None:
        super().__init__(parent)
        self.config: Any = config_manager
        self.setWindowTitle(Translations.tr("scan_dialog.title"))
        self.setMinimumSize(800, 500)

        # Keep references to prevent garbage collection while thread runs
        self._scan_thread = None
        self._scan_worker = None
        # Column header sort state (None = no sort, else column index)
        self._sort_column: int | None = None
        self._sort_descending: bool = False
        # Last scan results so the table can be re-sorted without re-scanning
        self._results: list = []

        self._setup_ui()

    def _get_interfaces(self):
        """Return list of local network interfaces.

        Dummy ranges (169.* APIPA / 172.* virtual adapters) are hidden so
        only real IP ranges are offered for scanning. Filtering here keeps
        the checkbox-to-interface mapping in _get_selected_interfaces()
        consistent.
        """
        return [iface for iface in get_local_interfaces()
                if is_real_interface(iface["ip"])]

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # --- Network selection group ---
        net_group = QGroupBox(Translations.tr("scan_dialog.group.network_select"))
        net_layout = QVBoxLayout(net_group)

        self.net_checkboxes = []
        for idx, iface in enumerate(self._get_interfaces()):
            dns_servers = get_dns_servers_for_interface(iface["ip"])
            label_text = f"{iface['ip']} / {iface['netmask']}"
            if dns_servers:
                # Show the primary (preferred IPv4) DNS server next to the IP range
                label_text += f"  |  {Translations.tr('scan_dialog.dns_server', dns=dns_servers[0])}"
            cb = QCheckBox(label_text)
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
        header: QHeaderView | None = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(3, 160)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        # Clicking a column header sorts the table (1st A-Z, 2nd Z-A)
        header.setSortIndicatorShown(True)
        header.setSectionsClickable(True)
        header.sectionClicked.connect(self._on_header_clicked)
        for col in range(self.table.columnCount()):
            item = self.table.horizontalHeaderItem(col)
            if item is not None:
                item.setToolTip(Translations.tr("table.sort.tooltip"))
        # Right-click context menu on the scan results table
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_scan_context_menu)

        # Search field: live-filters the results by name, IPv4, IPv6 or MAC
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(Translations.tr("scan_dialog.search_placeholder"))
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._refresh_table)
        layout.addWidget(self.search_input)

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
        for cb, iface in zip(self.net_checkboxes, all_ifaces, strict=False):
            if cb.isChecked():
                selected.append(iface)
        return selected

    def _start_scan(self) -> None:
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

        def on_thread_finished() -> None:
            self._scan_thread.deleteLater()
            self._scan_thread = None
            self.scan_btn.setEnabled(True)  # Re-enable scan button

        self._scan_thread.finished.connect(on_thread_finished)
        self._scan_thread.start()

    def _on_scan_progress(self, message: str, current: int, total: int) -> None:
        """Update progress display."""
        self.info_label.setText(message)
        if total > 0:
            percentage = int((current / total) * 100)
            self.progress_bar.setValue(percentage)

    def _on_header_clicked(self, column: int) -> None:
        """Sort by the clicked column: 1st click A-Z, 2nd click Z-A."""
        if self._sort_column == column:
            self._sort_descending = not self._sort_descending
        else:
            self._sort_column = column
            self._sort_descending = False
        self._refresh_table()

    def _get_filtered_results(self):
        """Get scan results matching the current search query.

        The query is matched as a case-insensitive substring against the
        host's name, IPv4 address, IPv6 address and MAC address. An empty
        query returns all results.
        """
        query = self.search_input.text().strip().lower()
        if not query:
            return self._results

        fields = ("hostname", "ipv4", "ipv6", "mac")
        return [
            host
            for host in self._results
            if any(query in str(host.get(field, "")).lower() for field in fields)
        ]

    def _refresh_table(self) -> None:
        """(Re)fill the table from the stored scan results, applying sorting."""
        self.table.setRowCount(0)
        results = self._get_filtered_results()

        # Build sortable rows: (key, hostname, ipv4, ipv6, mac)
        rows: list[tuple] = []
        for host in results:
            hostname = host.get("hostname", "Unknown")
            ipv4 = host.get("ipv4", "")
            ipv6 = host.get("ipv6", "N/A")
            mac = host.get("mac", "Unknown")
            values = [hostname, ipv4, ipv6, mac]
            if self._sort_column is None:
                key = hostname
            elif self._sort_column in (1, 2):  # IPv4 / IPv6 -> numeric sort
                key = get_ip_key(values[self._sort_column])
            else:
                key = values[self._sort_column]
            rows.append((key, hostname, ipv4, ipv6, mac))

        if self._sort_column is None:
            rows.sort(key=lambda r: r[0])
        else:
            rows = sort_rows(rows, 0, reverse=self._sort_descending)

        for _key, hostname, ipv4, ipv6, mac in rows:
            row: int = self.table.rowCount()
            self.table.insertRow(row)

            hostname_item = QTableWidgetItem(hostname)
            self.table.setItem(row, 0, hostname_item)

            ipv4_item = QTableWidgetItem(ipv4)
            self.table.setItem(row, 1, ipv4_item)

            ipv6_item = QTableWidgetItem(ipv6)
            ipv6_item.setForeground(Qt.GlobalColor.gray)
            self.table.setItem(row, 2, ipv6_item)

            mac_item = QTableWidgetItem(mac)
            self.table.setItem(row, 3, mac_item)

        # Show the active sort indicator on the header
        header: QHeaderView | None = self.table.horizontalHeader()
        if self._sort_column is not None:
            order = Qt.SortOrder.DescendingOrder if self._sort_descending else Qt.SortOrder.AscendingOrder
            header.setSortIndicator(self._sort_column, order)
        else:
            header.setSortIndicator(-1, Qt.SortOrder.AscendingOrder)

        self.add_btn.setEnabled(len(results) > 0)

    def _on_scan_finished(self, results: list) -> None:
        """Populate table with scan results."""
        self.progress_bar.setValue(100)
        self.info_label.setText(
            Translations.tr("scan_dialog.complete", count=len(results))
        )
        self._results = results
        self._sort_column = None
        self._sort_descending = False
        self._refresh_table()

    def _show_scan_context_menu(self, pos) -> None:
        """Show the right-click context menu for the scan result at *pos*."""
        row: int = self.table.rowAt(pos.y())
        if row < 0:
            return
        # Select the row under the cursor so the action applies to it
        self.table.selectRow(row)
        self.table.setCurrentCell(row, 0)

        menu = QMenu(self)
        menu.addAction(
            Translations.tr("scan_dialog.button.add_selected"),
            self._add_selected_device,
        )
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _add_selected_device(self) -> None:
        """Add the selected device to configured devices."""
        current_row: int = self.table.currentRow()
        if current_row < 0:
            QMessageBox.information(
                self, Translations.tr("scan_dialog.no_selection"),
                Translations.tr("scan_dialog.no_selection_msg")
            )
            return

        hostname: str = self.table.item(current_row, 0).text()
        ipv4: str = self.table.item(current_row, 1).text()
        mac: str = self.table.item(current_row, 3).text()

        # Check if MAC is valid (not "Unknown")
        if mac == "Unknown":
            reply: QMessageBox.StandardButton = QMessageBox.question(
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
