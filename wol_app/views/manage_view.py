"""Modern UI: "Verwalten" screen (device management + network scan).

Layout (top to bottom):

1. Section "Geräte-Verwaltung": toolbar (add / import / export / search)
   and a panel of fixed-height device rows: colored status dot, name,
   mono "IP · MAC" and edit/delete tile buttons.
   Scrolling happens via the page scrollbar, like the scan results.
2. Section "Netzwerk-Scan": interface checkboxes stacked vertically +
   primary scan button, progress bar and a results panel whose rows show
   a status dot, the hostname and a mono line "IPv4 · MAC" with an
   "Hinzufügen" button.

All persistence goes through the shared ``ConfigManager``; dialogs and
workers are reused from the classic UI (``DeviceDialog``, ``ScanWorker``,
``StatusWorker``, ``device_io``).
"""

from typing import Any

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from wol_app.device_dialog import DeviceDialog
from wol_app.device_io import export_devices, import_devices
from wol_app.main_window import HEADLESS_MODE, StatusWorker
from wol_app.network_scanner import (
    get_dns_servers_for_interface,
    get_local_interfaces,
    is_real_interface,
)
from wol_app.scan_worker import ScanWorker
from wol_app.translations import Translations
from wol_app.widgets.toggle_switch import ToggleWithLabel
from wol_app.wol_engine import WOLEngine

# Fixed height of one device / scan result row (px)
ROW_HEIGHT = 64


class ScanResultRow(QWidget):
    """One discovered host: dot · hostname / mono IPv4 · MAC · [Hinzufügen]."""

    add_requested = pyqtSignal(dict)  # host dict from the scanner

    def __init__(self, host: dict, parent=None) -> None:
        super().__init__(parent)
        self.host = host
        self.setObjectName("scanRow")
        self.setFixedHeight(ROW_HEIGHT)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 10, 18, 10)
        layout.setSpacing(16)

        # All discovered hosts answered a ping -> online dot
        self.dot = QLabel()
        self.dot.setObjectName("dotOnline")
        self.dot.setFixedSize(10, 10)
        layout.addWidget(self.dot)

        info = QVBoxLayout()
        info.setSpacing(2)
        hostname = host.get("hostname", "Unknown")
        title = QLabel(hostname)
        title.setObjectName("rowTitle")
        mono = QLabel(f"{host.get('ipv4', '')} · {host.get('mac', 'Unknown')}")
        mono.setObjectName("rowMono")
        info.addWidget(title)
        info.addWidget(mono)
        layout.addLayout(info)

        layout.addStretch()

        self.add_btn = QPushButton(Translations.tr("modern.manage.button.add"))
        self.add_btn.setObjectName("wakeButton")
        self.add_btn.clicked.connect(lambda: self.add_requested.emit(self.host))
        layout.addWidget(self.add_btn)

    def retranslate(self) -> None:
        self.add_btn.setText(Translations.tr("modern.manage.button.add"))


class DeviceRow(QWidget):
    """One configured device: dot · name / mono IP · MAC · action tiles."""

    edit_requested = pyqtSignal(str)
    delete_requested = pyqtSignal(str)

    def __init__(self, device: dict, status: str, parent=None) -> None:
        super().__init__(parent)
        self.device_id: str = device["id"]
        self.setObjectName("deviceRow")
        self.setFixedHeight(ROW_HEIGHT)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 10, 18, 10)
        layout.setSpacing(14)

        # Colored status dot (same look as the scan result rows)
        self.dot = QLabel()
        self.dot.setFixedSize(10, 10)
        layout.addWidget(self.dot, 0, Qt.AlignmentFlag.AlignVCenter)

        info = QVBoxLayout()
        info.setSpacing(2)
        self.title = QLabel(device.get("name", ""))
        # Disabled devices render the name dimmed
        self.title.setObjectName(
            "rowTitle" if device.get("enabled", True) else "rowTitleDisabled")
        ip = device.get("ip", "")
        mac = device.get("mac", "")
        mono_text = f"{ip} · {mac}" if ip else mac
        self.mono = QLabel(mono_text)
        self.mono.setObjectName("rowMono")
        info.addWidget(self.title)
        info.addWidget(self.mono)
        layout.addLayout(info)

        layout.addStretch()

        self.set_status(status)

        # Action tiles — exactly 36 px, icon vertically centered.
        # setFixedSize() is required in addition to the QSS min/max rules:
        # the emoji glyph + inherited button padding would otherwise inflate
        # the button beyond the QSS max-height.
        self.edit_btn = QPushButton("✏️")
        self.edit_btn.setObjectName("tileButton")
        self.edit_btn.setFixedSize(36, 36)
        self.edit_btn.setToolTip(Translations.tr("device_manager.button.edit"))
        self.edit_btn.clicked.connect(lambda: self.edit_requested.emit(self.device_id))
        layout.addWidget(self.edit_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        self.delete_btn = QPushButton("🗑️")
        self.delete_btn.setObjectName("tileDanger")
        self.delete_btn.setFixedSize(36, 36)
        self.delete_btn.setToolTip(Translations.tr("device_manager.button.delete"))
        self.delete_btn.clicked.connect(lambda: self.delete_requested.emit(self.device_id))
        layout.addWidget(self.delete_btn, 0, Qt.AlignmentFlag.AlignVCenter)

    def set_status(self, status: str) -> None:
        """Update the color of the status dot (objectName selects the style)."""
        self.dot.setToolTip(Translations.tr(f"status.{status}"))
        new_name = {"online": "dotOnline", "offline": "dotOffline"}.get(status, "dotUnknown")
        if self.dot.objectName() != new_name:
            self.dot.setObjectName(new_name)
            # Re-polish so the stylesheet rule for the new object name applies
            style = self.dot.style()
            style.unpolish(self.dot)
            style.polish(self.dot)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        self.edit_requested.emit(self.device_id)

    def retranslate(self, status: str | None = None) -> None:
        self.edit_btn.setToolTip(Translations.tr("device_manager.button.edit"))
        self.delete_btn.setToolTip(Translations.tr("device_manager.button.delete"))


class ManageView(QWidget):
    """The modern "Verwalten" screen."""

    devices_changed = pyqtSignal()  # device list changed (add/delete/import)

    def __init__(self, config_manager: Any, parent=None) -> None:
        super().__init__(parent)
        self.config: Any = config_manager
        self.engine: WOLEngine = WOLEngine(config_manager)
        self._scan_thread: QThread | None = None
        self._scan_worker: ScanWorker | None = None
        self._status_thread: QThread | None = None
        self._status_worker: StatusWorker | None = None
        self._scan_results: list[dict] = []

        self._setup_ui()
        self._refresh_device_list()

    # ── UI construction ──────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)

        content = QWidget()
        content.setObjectName("pageContent")
        content.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        scroll.setWidget(content)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(32, 26, 32, 26)
        layout.setSpacing(14)

        # ── Page header ──
        self.title = QLabel(Translations.tr("modern.manage.title"))
        self.title.setObjectName("pageTitle")
        self.subtitle = QLabel(Translations.tr("modern.manage.subtitle"))
        self.subtitle.setObjectName("pageSubtitle")
        layout.addWidget(self.title)
        layout.addWidget(self.subtitle)
        layout.addSpacing(10)

        # ── Section 1: Geräte-Verwaltung ──
        self.devices_heading = QLabel(Translations.tr("modern.manage.section.devices"))
        self.devices_heading.setObjectName("sectionHeading")
        layout.addWidget(self.devices_heading)

        dev_toolbar = QHBoxLayout()
        dev_toolbar.setSpacing(10)

        self.add_btn = QPushButton(Translations.tr("device_manager.button.add"))
        self.add_btn.setObjectName("primaryButton")
        self.add_btn.clicked.connect(self._add_device)
        dev_toolbar.addWidget(self.add_btn)

        self.import_btn = QPushButton(Translations.tr("device_manager.button.import"))
        self.import_btn.clicked.connect(self._import_devices)
        dev_toolbar.addWidget(self.import_btn)

        self.export_btn = QPushButton(Translations.tr("device_manager.button.export"))
        self.export_btn.clicked.connect(self._export_devices)
        dev_toolbar.addWidget(self.export_btn)

        dev_toolbar.addStretch()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(Translations.tr("ui.search_devices_placeholder"))
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._refresh_device_list)
        self.search_input.setFixedWidth(260)
        dev_toolbar.addWidget(self.search_input)
        layout.addLayout(dev_toolbar)

        # Device list panel (fixed-height rows; page scrollbar scrolls)
        self.device_panel = QWidget()
        self.device_panel.setObjectName("panel")
        self.device_list_layout = QVBoxLayout(self.device_panel)
        self.device_list_layout.setContentsMargins(0, 0, 0, 0)
        self.device_list_layout.setSpacing(0)
        layout.addWidget(self.device_panel)
        layout.addSpacing(18)

        # ── Section 2: Netzwerk-Scan ──
        self.scan_heading = QLabel(Translations.tr("modern.manage.section.scan"))
        self.scan_heading.setObjectName("sectionHeading")
        layout.addWidget(self.scan_heading)

        # Interface toggles stacked vertically (dummy APIPA/virtual ranges hidden)
        iface_col = QVBoxLayout()
        iface_col.setSpacing(6)
        self.iface_checkboxes: list[ToggleWithLabel] = []
        self._ifaces: list[dict] = [
            iface for iface in get_local_interfaces()
            if is_real_interface(iface["ip"])
        ]
        for idx, iface in enumerate(self._ifaces):
            dns_servers = get_dns_servers_for_interface(iface["ip"])
            label_text = f"{iface['ip']} / {iface['netmask']}"
            if dns_servers:
                label_text += f"  |  {Translations.tr('scan_dialog.dns_server', dns=dns_servers[0])}"
            cb = ToggleWithLabel(label_text, checked=idx == 0)
            self.iface_checkboxes.append(cb)
            iface_col.addWidget(cb)

        scan_col = QVBoxLayout()
        scan_col.setSpacing(10)
        scan_col.addLayout(iface_col)

        # "Scan starten" bottom-left, search field right of it (like device mgmt)
        scan_actions = QHBoxLayout()
        scan_actions.setSpacing(10)
        self.scan_btn = QPushButton(Translations.tr("modern.manage.button.scan"))
        self.scan_btn.setObjectName("primaryButton")
        self.scan_btn.clicked.connect(self._start_scan)
        scan_actions.addWidget(self.scan_btn)
        scan_actions.addStretch()

        self.result_search = QLineEdit()
        self.result_search.setPlaceholderText(Translations.tr("ui.search_devices_placeholder"))
        self.result_search.setClearButtonEnabled(True)
        self.result_search.textChanged.connect(self._render_results)
        self.result_search.setFixedWidth(260)
        self.result_search.hide()  # Appears together with the results
        scan_actions.addWidget(self.result_search)
        scan_col.addLayout(scan_actions)

        layout.addLayout(scan_col)

        self.scan_info = QLabel(Translations.tr("scan_dialog.info.initial"))
        self.scan_info.setObjectName("pageSubtitle")
        layout.addWidget(self.scan_info)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)

        # Results panel (rows added dynamically)
        self.results_panel = QWidget()
        self.results_panel.setObjectName("panel")
        self.results_panel.setVisible(False)
        self.results_layout = QVBoxLayout(self.results_panel)
        self.results_layout.setContentsMargins(0, 0, 0, 0)
        self.results_layout.setSpacing(0)
        layout.addWidget(self.results_panel)
        layout.addStretch()

    def retranslate(self) -> None:
        """Re-apply all texts after a language switch."""
        self.title.setText(Translations.tr("modern.manage.title"))
        self.subtitle.setText(Translations.tr("modern.manage.subtitle"))
        self.scan_heading.setText(Translations.tr("modern.manage.section.scan"))
        self.devices_heading.setText(Translations.tr("modern.manage.section.devices"))
        self.scan_btn.setText(Translations.tr("modern.manage.button.scan"))
        self.add_btn.setText(Translations.tr("device_manager.button.add"))
        self.import_btn.setText(Translations.tr("device_manager.button.import"))
        self.export_btn.setText(Translations.tr("device_manager.button.export"))
        self.search_input.setPlaceholderText(Translations.tr("ui.search_devices_placeholder"))
        self.result_search.setPlaceholderText(Translations.tr("ui.search_devices_placeholder"))
        for i in range(self.results_layout.count()):
            w = self.results_layout.itemAt(i).widget()
            if isinstance(w, ScanResultRow):
                w.retranslate()
        # Rebuild device rows so status/tooltip texts use the new language
        self._refresh_device_list()

    # ── Netzwerk-Scan ────────────────────────────────────────────────────

    def _selected_interfaces(self) -> list[dict]:
        return [
            iface for cb, iface in zip(self.iface_checkboxes, self._ifaces, strict=False)
            if cb.isChecked()
        ]

    def _start_scan(self) -> None:
        selected = self._selected_interfaces()
        if not selected:
            QMessageBox.warning(
                self,
                Translations.tr("scan_dialog.no_network_selected"),
                Translations.tr("scan_dialog.no_network_selected_msg"),
            )
            return
        if HEADLESS_MODE:
            return

        # Cancel a previous scan if still running
        if self._scan_thread is not None and self._scan_thread.isRunning():
            self._scan_thread.quit()
            self._scan_thread.wait(1000)

        self._clear_results()
        self.results_panel.setVisible(True)
        self.result_search.clear()
        self.result_search.hide()
        self.progress_bar.show()
        self.progress_bar.setValue(0)
        self.scan_btn.setEnabled(False)
        self.scan_info.setText(Translations.tr("scan_dialog.scanning"))

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
            self.scan_btn.setEnabled(True)

        self._scan_thread.finished.connect(on_thread_finished)
        self._scan_thread.start()

    def _on_scan_progress(self, message: str, current: int, total: int) -> None:
        self.scan_info.setText(message)
        if total > 0:
            self.progress_bar.setValue(int(current / total * 100))

    def _on_scan_finished(self, results: list) -> None:
        self.progress_bar.setValue(100)
        self.progress_bar.hide()
        self.scan_info.setText(
            Translations.tr("scan_dialog.complete", count=len(results))
        )
        self._scan_results = results
        self.result_search.show()
        self._render_results()

    def _filtered_results(self) -> list[dict]:
        query = self.result_search.text().strip().lower()
        if not query:
            return self._scan_results
        fields = ("hostname", "ipv4", "ipv6", "mac")
        return [
            h for h in self._scan_results
            if any(query in str(h.get(f, "")).lower() for f in fields)
        ]

    def _render_results(self) -> None:
        """Rebuild the result rows, honouring the search filter."""
        results = self._filtered_results()
        self._clear_results()
        for idx, host in enumerate(results):
            row = ScanResultRow(host)
            row.add_requested.connect(self._add_scanned_device)
            self.results_layout.addWidget(row)
            if idx < len(results) - 1:
                sep = QWidget()
                sep.setObjectName("rowSeparator")
                sep.setFixedHeight(1)
                self.results_layout.addWidget(sep)
        self.results_panel.setVisible(bool(results) or bool(self._scan_results))

    def _clear_results(self) -> None:
        while self.results_layout.count():
            item = self.results_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _add_scanned_device(self, host: dict) -> None:
        """Open the device dialog pre-filled from a scan result."""
        hostname: str = host.get("hostname", "Unknown")
        ipv4: str = host.get("ipv4", "")
        mac: str = host.get("mac", "Unknown")

        if not mac or mac == "Unknown":
            reply: QMessageBox.StandardButton = QMessageBox.question(
                self,
                Translations.tr("scan_dialog.mac_unknown"),
                Translations.tr(
                    "scan_dialog.mac_unknown_msg", hostname=hostname, ip=ipv4
                ),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            mac = "00:00:00:00:00:00"  # Placeholder

        for dev in self.config.get_devices():
            if dev.get("mac", "").upper() == mac.upper():
                QMessageBox.warning(
                    self,
                    Translations.tr("scan_dialog.already_exists"),
                    Translations.tr("scan_dialog.already_exists_msg", mac=mac),
                )
                return

        dialog = DeviceDialog(
            self.config,
            parent=self,
            preset={"name": "" if hostname == "Unknown" else hostname,
                    "mac": mac, "ip": ipv4},
        )
        dialog.device_saved.connect(lambda _d: self._on_devices_changed())
        dialog.exec()

    # ── Geräte-Verwaltung ────────────────────────────────────────────────

    def _filtered_devices(self) -> list[dict]:
        query = self.search_input.text().strip().lower()
        devices = sorted(self.config.get_devices(), key=lambda d: d.get("name", ""))
        if not query:
            return devices
        fields = ("name", "mac", "ip", "username")
        return [
            d for d in devices
            if any(query in str(d.get(f, "")).lower() for f in fields)
        ]

    def _refresh_device_list(self) -> None:
        """Rebuild the device rows; keep cached statuses from the engine."""
        while self.device_list_layout.count():
            item = self.device_list_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        devices = self._filtered_devices()
        for idx, device in enumerate(devices):
            status = self.engine.get_device_status(device["id"])
            row = DeviceRow(device, status)
            row.edit_requested.connect(self._edit_device)
            row.delete_requested.connect(self._delete_device)
            self.device_list_layout.addWidget(row)
            if idx < len(devices) - 1:
                sep = QWidget()
                sep.setObjectName("rowSeparator")
                sep.setFixedHeight(1)
                self.device_list_layout.addWidget(sep)

    def _device_rows(self) -> list[DeviceRow]:
        return [
            self.device_list_layout.itemAt(i).widget()
            for i in range(self.device_list_layout.count())
            if isinstance(self.device_list_layout.itemAt(i).widget(), DeviceRow)
        ]

    def _add_device(self) -> None:
        dialog = DeviceDialog(self.config, parent=self)
        dialog.device_saved.connect(lambda _d: self._on_devices_changed())
        dialog.exec()

    def _edit_device(self, device_id: str) -> None:
        device = self.config.get_device_by_id(device_id)
        if device is None:
            return
        dialog = DeviceDialog(self.config, device=device, parent=self)
        dialog.device_saved.connect(lambda _d: self._on_devices_changed())
        dialog.exec()

    def _delete_device(self, device_id: str) -> None:
        device = self.config.get_device_by_id(device_id)
        if device is None:
            return
        reply: QMessageBox.StandardButton = QMessageBox.question(
            self,
            Translations.tr("dialog.confirm_delete.title"),
            Translations.tr("dialog.confirm_delete.message", name=device["name"]),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.config.remove_device(device_id)
            self._on_devices_changed()

    def _export_devices(self) -> None:
        export_devices(self.config, parent=self)

    def _import_devices(self) -> None:
        if import_devices(self.config, parent=self):
            self._on_devices_changed()

    def _on_devices_changed(self) -> None:
        self._refresh_device_list()
        self.refresh_statuses()
        self.devices_changed.emit()

    # ── Status checks ────────────────────────────────────────────────────

    def refresh_statuses(self) -> None:
        """Check all device statuses in the background and update the tiles."""
        if HEADLESS_MODE:
            return
        if self._status_thread is not None and self._status_thread.isRunning():
            return

        self._status_worker = StatusWorker(self.engine)
        self._status_thread = QThread()
        self._status_worker.moveToThread(self._status_thread)
        self._status_thread.started.connect(self._status_worker.run)
        self._status_worker.finished.connect(self._on_statuses_finished)
        self._status_worker.finished.connect(self._status_thread.quit)
        self._status_worker.finished.connect(self._status_worker.deleteLater)

        def on_thread_finished() -> None:
            self._status_thread.deleteLater()
            self._status_thread = None

        self._status_thread.finished.connect(on_thread_finished)
        self._status_thread.start()

    def _on_statuses_finished(self, results: list) -> None:
        """Update the status tiles of the visible device rows in-place."""
        status_by_id = {did: status for did, _name, status, _msg in results}
        for row in self._device_rows():
            status = status_by_id.get(row.device_id)
            if status is not None:
                row.set_status(status)

    def showEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        super().showEvent(event)
        self.refresh_statuses()

    def cancel_workers(self) -> None:
        """Cancel background work on window close (mirrors MainWindow)."""
        if self._status_worker is not None:
            self._status_worker.cancel()
        for thread in (self._scan_thread, self._status_thread):
            if thread is not None and thread.isRunning():
                thread.quit()
                thread.wait(2000)
