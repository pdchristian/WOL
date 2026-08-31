"""Modern UI: "Geräte" screen (device status cards).

Layout mirrors the prototype's devices screen
(Design_Prototpye/dark_control_center_full.html, ``#devices``):

1. Page header (title + live summary "N Geräte · M online") and a search field.
2. Toolbar: refresh icon button and the primary "Alle aufwecken" button.
3. A responsive grid of device cards. Each card shows the device name with
   a colored status dot (top right), a mono IP/MAC block and, in the bottom
   row, two Remote-Desktop icon tiles (fullscreen / window) plus the primary
   action button: "Aufwecken" while offline/unknown, "Herunterfahren" while
   online.

All persistence goes through the shared ``ConfigManager``; the wake/ping
engine and the status worker are reused from the classic UI, the remote
desktop and shutdown flows from :mod:`wol_app.remote_desktop` /
:mod:`wol_app.shutdown_flow`.
"""

from typing import Any

from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from wol_app.main_window import HEADLESS_MODE, StatusWorker
from wol_app.network_scanner import get_local_ips
from wol_app.remote_desktop import start_remote_desktop
from wol_app.shutdown_flow import confirm_shutdown
from wol_app.translations import Translations
from wol_app.views.device_edit_dialog import ModernDeviceDialog
from wol_app.wol_engine import WOLEngine

# Minimum card width incl. gap (prototype .grid: minmax(230px, 1fr) + 16px gap)
CARD_MIN_WIDTH = 230
GRID_SPACING = 16

# Auto-refresh interval for the status dots (prototype footer: 30 s)
AUTO_REFRESH_MS = 30_000


class DeviceCard(QWidget):
    """One device card: name + status dot / mono IP · MAC / remote tiles + action."""

    wake_requested = pyqtSignal(str)
    shutdown_requested = pyqtSignal(str)
    remote_requested = pyqtSignal(str, bool)  # device id, fullscreen
    edit_requested = pyqtSignal(str)
    ping_requested = pyqtSignal(str)

    def __init__(self, device: dict, status: str, local_ips: set[str], parent=None) -> None:
        super().__init__(parent)
        self.device_id: str = device["id"]
        self.device_name: str = device.get("name", "")
        self._device_ip: str = device.get("ip", "")
        self.enabled: bool = device.get("enabled", True)
        self._status = status

        self.setObjectName("deviceCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        # Plain QWidget subclasses only paint QSS background/border with this
        # attribute set (same as #pageContent in ManageView).
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(10)

        # ── Row 1: name … status dot ──
        top = QHBoxLayout()
        top.setSpacing(10)
        self.title = QLabel(self._display_name(local_ips))
        self.title.setObjectName(
            "rowTitle" if self.enabled else "rowTitleDisabled")
        self.title.setWordWrap(True)
        self.dot = QLabel()
        self.dot.setFixedSize(10, 10)
        top.addWidget(self.title, 1)
        top.addWidget(self.dot, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(top)

        # ── Row 2: mono IP / MAC ──
        ip = device.get("ip", "")
        mac = device.get("mac", "")
        self.mono = QLabel(f"{ip}\n{mac}" if ip else mac)
        self.mono.setObjectName("rowMono")
        layout.addWidget(self.mono)

        # ── Row 3: remote tiles … wake/shutdown action ──
        bottom = QHBoxLayout()
        bottom.setSpacing(8)

        self.remote_fs_btn = QPushButton("🖥️")
        self.remote_fs_btn.setObjectName("tileButton")
        self.remote_fs_btn.setFixedSize(36, 36)
        self.remote_fs_btn.setToolTip(Translations.tr("button.remote_fullscreen"))
        self.remote_fs_btn.clicked.connect(
            lambda: self.remote_requested.emit(self.device_id, True))
        bottom.addWidget(self.remote_fs_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        self.remote_win_btn = QPushButton("🪟")
        self.remote_win_btn.setObjectName("tileButton")
        self.remote_win_btn.setFixedSize(36, 36)
        self.remote_win_btn.setToolTip(Translations.tr("button.remote_window"))
        self.remote_win_btn.clicked.connect(
            lambda: self.remote_requested.emit(self.device_id, False))
        bottom.addWidget(self.remote_win_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        bottom.addStretch()

        self.action_btn = QPushButton()
        self.action_btn.setObjectName("wakeButton")
        self.action_btn.setMinimumWidth(110)
        self.action_btn.clicked.connect(self._action_clicked)
        bottom.addWidget(self.action_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        layout.addLayout(bottom)

        self.set_status(status)
        if not self.enabled:
            # Disabled devices cannot be woken or reached remotely
            self.action_btn.setEnabled(False)
            self.remote_fs_btn.setEnabled(False)
            self.remote_win_btn.setEnabled(False)

    # ── Status ───────────────────────────────────────────────────────────

    def _display_name(self, local_ips: set[str]) -> str:
        """Device name with the classic "(ich)" marker for the local machine."""
        name = self.device_name
        if self._device_ip in local_ips:
            name = f"{name} {Translations.tr('device.me')}"
        if not self.enabled:
            name = f"{name} {Translations.tr('device.disabled')}"
        return name

    def set_status(self, status: str) -> None:
        """Update the status dot and swap the action button (wake ↔ shutdown)."""
        self._status = status
        dot_name = {
            "online": "dotOnline",
            "offline": "dotOffline",
        }.get(status, "dotUnknown")
        if self.dot.objectName() != dot_name:
            self.dot.setObjectName(dot_name)
            self._repolish(self.dot)

        online = status == "online"
        action_name = "shutdownButton" if online else "wakeButton"
        action_key = "button.shutdown" if online else "modern.devices.button.wake"
        if self.action_btn.objectName() != action_name:
            self.action_btn.setObjectName(action_name)
            self._repolish(self.action_btn)
        self.action_btn.setText(Translations.tr(action_key))

    @staticmethod
    def _repolish(widget: QWidget) -> None:
        """Re-apply the stylesheet rule for a changed objectName."""
        style = widget.style()
        style.unpolish(widget)
        style.polish(widget)

    def _action_clicked(self) -> None:
        if self._status == "online":
            self.shutdown_requested.emit(self.device_id)
        else:
            self.wake_requested.emit(self.device_id)

    # ── Mouse interaction ────────────────────────────────────────────────

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        self.edit_requested.emit(self.device_id)

    def contextMenuEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        menu = QMenu(self)
        act_fs = menu.addAction(Translations.tr("button.remote_fullscreen"))
        act_win = menu.addAction(Translations.tr("button.remote_window"))
        menu.addSeparator()
        if self._status == "online":
            act_action = menu.addAction(Translations.tr("button.shutdown"))
        else:
            act_action = menu.addAction(Translations.tr("modern.devices.button.wake"))
        act_ping = menu.addAction(Translations.tr("button.ping"))
        menu.addSeparator()
        act_edit = menu.addAction(Translations.tr("device_manager.button.edit"))

        chosen = menu.exec(event.globalPos())
        if chosen is act_fs:
            self.remote_requested.emit(self.device_id, True)
        elif chosen is act_win:
            self.remote_requested.emit(self.device_id, False)
        elif chosen is act_action:
            self._action_clicked()
        elif chosen is act_ping:
            self.ping_requested.emit(self.device_id)
        elif chosen is act_edit:
            self.edit_requested.emit(self.device_id)

    def retranslate(self, local_ips: set[str]) -> None:
        self.title.setText(self._display_name(local_ips))
        self.remote_fs_btn.setToolTip(Translations.tr("button.remote_fullscreen"))
        self.remote_win_btn.setToolTip(Translations.tr("button.remote_window"))
        self.set_status(self._status)  # refresh wake/shutdown button text


class DevicesView(QWidget):
    """The modern "Geräte" screen (status card grid)."""

    devices_changed = pyqtSignal()

    def __init__(self, config_manager: Any, parent=None) -> None:
        super().__init__(parent)
        self.config: Any = config_manager
        self.engine: WOLEngine = WOLEngine(config_manager)
        self._status_thread: QThread | None = None
        self._status_worker: StatusWorker | None = None
        self._statuses: dict[str, str] = {}  # device id -> last known status
        self._cards: dict[str, DeviceCard] = {}
        self._grid_cols = 0

        self._setup_ui()
        self.refresh_devices()

        # Autorefresh like the prototype footer ("Autorefresh alle 30 s")
        self._timer = QTimer(self)
        self._timer.setInterval(AUTO_REFRESH_MS)
        self._timer.timeout.connect(self._auto_refresh)
        self._timer.start()

    # ── UI construction ──────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)
        self._scroll = scroll

        content = QWidget()
        content.setObjectName("pageContent")
        content.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        scroll.setWidget(content)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(32, 26, 32, 26)
        layout.setSpacing(14)

        # ── Page header: title + summary (left), search (right) ──
        header = QHBoxLayout()
        header.setSpacing(14)
        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        self.title = QLabel(Translations.tr("modern.devices.title"))
        self.title.setObjectName("pageTitle")
        self.subtitle = QLabel()
        self.subtitle.setObjectName("pageSubtitle")
        title_col.addWidget(self.title)
        title_col.addWidget(self.subtitle)
        header.addLayout(title_col)
        header.addStretch()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(Translations.tr("ui.search_devices_placeholder"))
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setFixedWidth(260)
        self.search_input.textChanged.connect(self.refresh_devices)
        header.addWidget(self.search_input, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(header)
        layout.addSpacing(4)

        # ── Toolbar: refresh · wake all ──
        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)
        self.refresh_btn = QPushButton("⟳")
        self.refresh_btn.setObjectName("iconBtn")
        self.refresh_btn.setFixedSize(36, 36)
        self.refresh_btn.setToolTip(Translations.tr("button.refresh"))
        self.refresh_btn.clicked.connect(self.refresh_statuses)
        toolbar.addWidget(self.refresh_btn)

        self.wake_all_btn = QPushButton(Translations.tr("button.wake_all"))
        self.wake_all_btn.setObjectName("primaryButton")
        self.wake_all_btn.clicked.connect(self._wake_all)
        toolbar.addWidget(self.wake_all_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)
        layout.addSpacing(6)

        # ── Card grid ──
        grid_host = QWidget()
        grid_host.setObjectName("deviceGrid")
        self.grid = QGridLayout(grid_host)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(GRID_SPACING)
        layout.addWidget(grid_host)

        # Empty state
        self.empty_label = QLabel(Translations.tr("modern.devices.empty"))
        self.empty_label.setObjectName("placeholderText")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setWordWrap(True)
        self.empty_label.hide()
        layout.addWidget(self.empty_label)

        layout.addStretch()

    # ── Device list ──────────────────────────────────────────────────────

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

    def refresh_devices(self) -> None:
        """Rebuild the card grid (device list or search filter changed)."""
        while self.grid.count():
            item = self.grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._cards.clear()

        local_ips = get_local_ips()
        devices = self._filtered_devices()
        for device in devices:
            status = self._statuses.get(device["id"], "unknown")
            card = DeviceCard(device, status, local_ips)
            card.wake_requested.connect(self._wake_device)
            card.shutdown_requested.connect(self._shutdown_device)
            card.remote_requested.connect(self._remote_device)
            card.edit_requested.connect(self._edit_device)
            card.ping_requested.connect(self._ping_device)
            self._cards[device["id"]] = card

        self._relayout_grid()
        self._update_summary()
        self.empty_label.setVisible(not devices)

    def _relayout_grid(self) -> None:
        """Place the cards into the grid, computing the column count from width."""
        # Viewport width minus the page margins (32 + 32)
        avail = max(self._scroll.viewport().width() - 64, CARD_MIN_WIDTH)
        cols = max(1, (avail + GRID_SPACING) // (CARD_MIN_WIDTH + GRID_SPACING))
        self._grid_cols = cols

        while self.grid.count():
            self.grid.takeAt(0)
        for i, card in enumerate(self._cards.values()):
            self.grid.addWidget(card, i // cols, i % cols)
        # Stretch columns so cards fill the row like the prototype grid
        for c in range(cols):
            self.grid.setColumnStretch(c, 1)

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        super().resizeEvent(event)
        # Reflow the grid when the column count changes
        avail = max(self._scroll.viewport().width() - 64, CARD_MIN_WIDTH)
        cols = max(1, (avail + GRID_SPACING) // (CARD_MIN_WIDTH + GRID_SPACING))
        if cols != self._grid_cols:
            self._relayout_grid()

    def _update_summary(self) -> None:
        devices = self._filtered_devices()
        online = sum(
            1 for d in devices
            if self._statuses.get(d["id"]) == "online"
        )
        self.subtitle.setText(
            Translations.tr("modern.devices.summary", total=len(devices), online=online)
        )

    # ── Device actions ───────────────────────────────────────────────────

    def _device_by_id(self, device_id: str) -> dict | None:
        return self.config.get_device_by_id(device_id)

    def _wake_device(self, device_id: str) -> None:
        device = self._device_by_id(device_id)
        if device is None:
            return
        if not device.get("enabled", True):
            QMessageBox.warning(
                self,
                Translations.tr("dialog.device_disabled.title"),
                Translations.tr("dialog.device_disabled.message", name=device["name"]),
            )
            return
        success, msg = self.engine.send_wake_packet(device_id)
        if not success:
            QMessageBox.warning(
                self, Translations.tr("dialog.wake_failed.title"), msg)

    def _shutdown_device(self, device_id: str) -> None:
        device = self._device_by_id(device_id)
        if device is None:
            return
        confirm_shutdown(self, self.config, device)
        # Status will update on the next refresh cycle

    def _remote_device(self, device_id: str, fullscreen: bool) -> None:
        device = self._device_by_id(device_id)
        if device is None:
            return
        start_remote_desktop(self, self.config, device, fullscreen)

    def _ping_device(self, device_id: str) -> None:
        device = self._device_by_id(device_id)
        if device is None:
            return
        status, msg = self.engine.check_device_status(device_id)
        self._statuses[device_id] = status
        card = self._cards.get(device_id)
        if card is not None:
            card.set_status(status)
        self._update_summary()
        QMessageBox.information(
            self,
            Translations.tr("dialog.status_result.title", status=self._translated_status(status)),
            msg,
        )

    def _translated_status(self, status: str) -> str:
        return Translations.tr(f"status.{status}")

    def _edit_device(self, device_id: str) -> None:
        device = self._device_by_id(device_id)
        if device is None:
            return
        dialog = ModernDeviceDialog(self.config, device=device, parent=self)
        dialog.device_saved.connect(lambda _d: self._on_devices_changed())
        dialog.exec()

    def _wake_all(self) -> None:
        """Wake all enabled devices (confirmation like the classic layout)."""
        devices = [d for d in self.config.get_devices() if d.get("enabled", True)]
        if not devices:
            QMessageBox.information(
                self,
                Translations.tr("dialog.no_devices.title"),
                Translations.tr("dialog.no_devices.message"),
            )
            return

        reply: QMessageBox.StandardButton = QMessageBox.question(
            self,
            Translations.tr("dialog.wake_all.title"),
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
        self.refresh_statuses()

    def _on_devices_changed(self) -> None:
        self.refresh_devices()
        self.refresh_statuses()
        self.devices_changed.emit()

    # ── Status checks ────────────────────────────────────────────────────

    def refresh_statuses(self) -> None:
        """Ping all devices in the background and update the cards in-place."""
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
        """Update the status dots / action buttons of the visible cards."""
        for device_id, _name, status, _msg in results:
            self._statuses[device_id] = status
            card = self._cards.get(device_id)
            if card is not None:
                card.set_status(status)
        self._update_summary()

    def _auto_refresh(self) -> None:
        if self.isVisible():
            self.refresh_statuses()

    def showEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        super().showEvent(event)
        self.refresh_statuses()

    # ── Language / lifecycle ─────────────────────────────────────────────

    def retranslate(self) -> None:
        """Re-apply all texts after a language switch."""
        self.title.setText(Translations.tr("modern.devices.title"))
        self.search_input.setPlaceholderText(Translations.tr("ui.search_devices_placeholder"))
        self.refresh_btn.setToolTip(Translations.tr("button.refresh"))
        self.wake_all_btn.setText(Translations.tr("button.wake_all"))
        self.empty_label.setText(Translations.tr("modern.devices.empty"))
        local_ips = get_local_ips()
        for card in self._cards.values():
            card.retranslate(local_ips)
        self._update_summary()

    def cancel_workers(self) -> None:
        """Cancel background work on window close (mirrors ManageView)."""
        self._timer.stop()
        if self._status_worker is not None:
            self._status_worker.cancel()
        if self._status_thread is not None and self._status_thread.isRunning():
            self._status_thread.quit()
            self._status_thread.wait(2000)
