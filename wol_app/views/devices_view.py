"""Modern UI: "Geräte" screen (device status cards).

Layout mirrors the prototype's devices screen
(design_prototype/dark_control_center_full.html, ``#devices``):

1. Page header (title + live summary "N Geräte · M online") and a search field.
2. Toolbar: refresh icon button and the primary "Alle aufwecken" button.
3. A responsive grid of device cards. Each card shows the device name with
   a status/platform pill (top right: online dot + detected OS), a mono
   IP/MAC block and, in the bottom row, two Remote-Desktop icon tiles
   (fullscreen / window) plus the primary action button: "Aufwecken" while
   offline/unknown, "Herunterfahren" while online.

All persistence goes through the shared ``ConfigManager``; the wake/ping
engine and the status worker are reused from the classic UI, the remote
desktop and shutdown flows from :mod:`wol_app.remote_desktop` /
:mod:`wol_app.shutdown_flow`.
"""

from typing import Any

from PyQt6.QtCore import Qt, QSize, QThread, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from wol_app.config import (
    DEFAULT_INFERENCE_INTERVAL_MS,
    DEVICES_VIEW_GRID,
    DEVICES_VIEW_LIST,
    REMOTE_PROTOCOL_RDP,
    REMOTE_PROTOCOL_VNC,
    ConfigManager,
)
from wol_app.app_core import HEADLESS_MODE, OsDetectWorker, StatusWorker
from wol_app.metrics_worker import InferenceSweepWorker
from wol_app.network_scanner import get_local_ips
from wol_app.remote_desktop import resolve_remote_protocol, start_remote_desktop
from wol_app.shutdown_flow import execute_shutdown
from wol_app.translations import Translations
from wol_app.utils import ip_sort_key
from wol_app.views.device_edit_dialog import ModernDeviceDialog
from wol_app.views.shutdown_confirm_dialog import ModernShutdownConfirmDialog
from wol_app.widgets.status_pill import StatusPill
from wol_app.wol_engine import WOLEngine

# Grid geometry mirrors the prototype (.grid in dark_control_center_full.html):
# repeat(auto-fill, minmax(MIN, 1fr)) with 16px gap, inside .main padding 36px.
# The column formula below reproduces that behaviour for the Qt grid.
# MIN is 300 (not the prototype's 230): at 230 the action button
# "Herunterfahren" no longer fits next to the three remote tiles and gets
# elided; 3 tiles (108) + gaps + button (~130) + card margins (36) ≈ 290.
CARD_MIN_WIDTH = 300
GRID_SPACING = 16

# Horizontal page margins inside the scroll content — matches the prototype's
# .main padding (28px 36px) so the column formula sees the same available width.
PAGE_MARGIN_H = 36

# Auto-refresh interval for the status dots (prototype footer: 30 s)
AUTO_REFRESH_MS = 30_000

# Poll interval choices for the inference badge (host protocol v9,
# "requests_active") — persisted via config as ui.inference_interval_ms.
INFERENCE_INTERVAL_CHOICES_MS = (5_000, 10_000, 15_000, 30_000)

# Fixed height of one device row in the list view (px)
LIST_ROW_HEIGHT = 64

# Sort order of the "Status" sort key: Online, offline, unbekannt
STATUS_SORT_RANK = {"online": 0, "offline": 1, "unknown": 2}


def derive_inference_state(response: "dict | None") -> "str | None":
    """Badge state for one metrics response (host protocol v9).

    Returns "active" / "idle" / "warn" / "hidden", or None when the response
    carries no verdict at all (unreachable host, pre-v9, or no port-watched
    entry) — callers then keep the previous state instead of flickering.
    "hidden" is a *verdict*: the badge is cleared on purpose. Precedence:
    active > warn > idle > hidden.

    * any watched entry with ``requests_active > 0``  -> "active"
    * any port-watched entry reporting ``requests_active == 0`` -> "idle"
    * port open but unmeasurable (a v9 host that could not read /metrics)
      -> "warn" (surfaces even when other entries idle)
    * every port-watched entry has its API port closed -> "hidden" — the
      inference server is simply off, so there is nothing to report
    * name-only watch entries are not measurable and ignored; if no entry
      watches a port there is no verdict.
    """
    if not isinstance(response, dict):
        return None
    protocol = response.get("protocol")
    if not isinstance(protocol, int) or protocol < 9:
        return None
    processes = response.get("processes")
    if not isinstance(processes, dict):
        return None

    active = idle = warn = off = False
    for entry in processes.values():
        if not isinstance(entry, dict) or "api_port" not in entry:
            continue  # name-only watch entry — activity not measurable
        requests_active = entry.get("requests_active")
        if isinstance(requests_active, int) and requests_active > 0:
            active = True
        elif isinstance(requests_active, int):
            idle = True
        elif entry.get("api_port_open") or entry.get("api_up"):
            warn = True  # v9 host, API up — but /metrics unreadable
        else:
            off = True  # watched API port closed — server off, nothing to show
    if active:
        return "active"
    if warn:
        # an open-but-unmeasurable port outranks idle/off entries — the
        # measurement problem must stay visible
        return "warn"
    if idle:
        return "idle"
    if off:
        return "hidden"
    return None


def remote_tooltip(action_key: str, protocol: str) -> str:
    """Tooltip for a Remote tile: the action plus the client it will start.

    The platform of the device decides whether the tile opens the RDP client
    or TurboVNC, so the tooltip names the client before the user clicks.
    """
    client_key = (
        "modern.devices.client_vnc"
        if protocol == REMOTE_PROTOCOL_VNC
        else "modern.devices.client_rdp"
    )
    return f"{Translations.tr(action_key)} · {Translations.tr(client_key)}"


def compute_columns(avail: int) -> int:
    """CSS ``repeat(auto-fill, minmax(MIN, 1fr))``: max Spalten mit MIN-Breite.

    Eine weitere Spalte passt, sobald die gleichmäßige Kachelbreite noch
    >= CARD_MIN_WIDTH wäre: ``cols = (avail + GAP) // (MIN + GAP)``.
    """
    if avail <= 0:
        return 1
    return max(1, (avail + GRID_SPACING) // (CARD_MIN_WIDTH + GRID_SPACING))


class WidthPinnedScrollArea(QScrollArea):
    """ScrollArea whose content width is ALWAYS exactly the viewport width.

    Fixes the "ratchet" bug of the plain QScrollArea: normally the content
    is never narrower than its layout's minimum (fixed toolbar widths, card
    content hints). Shrinking the window then clamps the content width — no
    resizeEvent with a smaller width ever arrives, the grid formula sees a
    stale too-large width and a dead margin (or overflow) appears on the
    right. CSS block elements behave the other way (width == containing
    block, period); setFixedWidth in resizeEvent enforces exactly that here.
    """

    def __init__(self, content: QWidget, parent=None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setWidget(content)
        self._content = content

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        super().resizeEvent(event)
        vw = self.viewport().width()
        if vw > 0 and self._content.width() != vw:
            self._content.setFixedWidth(vw)


class FlexToolbar(QWidget):
    """Toolbar laid out like CSS ``display:flex; justify-content:space-between``.

    A QBoxLayout distributes a width deficit over ALL items — the search
    field slides left and is no longer flush with the right edge of the
    card grid. Here everything is positioned manually instead:

    - right group (sort combo + search): ALWAYS right-aligned at the
      container edge; the search field shrinks first (260 → 160 px),
      then the combo (150 → 100 px);
    - left group (view toggle · refresh · wake all): starts at the left
      edge, the last button compresses first when space gets tight.

    Invariant: right edge of the search field == right edge of the grid
    == content width (both share the same PAGE_MARGIN_H margins).
    """

    # CSS parity: the right group shrinks the search field first, then the
    # combo; the left group gives way without limit.
    SEARCH_MIN = 160
    SEARCH_MAX = 260
    COMBO_MIN = 100
    COMBO_W = 150
    INTERVAL_MIN = 72
    INTERVAL_W = 90

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._left: list[QWidget] = []
        # (widget, preferred width, minimum width) — right group, left to right
        self._right: list[tuple[QWidget, int, int]] = []
        self._gap = 10

    def add_left(self, widget: QWidget) -> None:
        widget.setParent(self)
        self._left.append(widget)

    def add_right(self, widget: QWidget,
                  width: int = COMBO_W, min_width: int = COMBO_MIN) -> None:
        widget.setParent(self)
        self._right.append((widget, width, min_width))

    def _widths_right(self, avail: int) -> list[int]:
        """Widths of the right group (list end == search field).

        Shrinks from the right edge inwards (search first, then the combos),
        each widget down to its own minimum — mirrors the CSS flex order.
        """
        widths = [pref for (_w, pref, _m) in self._right]
        mins = [min_w for (_w, _pref, min_w) in self._right]
        need = sum(widths) + self._gap * max(0, len(widths) - 1)
        deficit = need - avail
        if deficit <= 0:
            return widths
        for i in range(len(widths) - 1, -1, -1):
            take = min(deficit, widths[i] - mins[i])
            widths[i] -= take
            deficit -= take
            if deficit <= 0:
                break
        return widths

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        super().resizeEvent(event)
        w, h = self.width(), self.height()

        def place(widget: QWidget, x: int, width: int) -> None:
            # Center on the height ACTUALLY given (>= 36), not the smaller
            # sizeHint height — centering on sizeHint (≈20) inside a 36px
            # toolbar pushed widgets ~8px below the toolbar's bottom edge.
            height = max(widget.sizeHint().height(), h)
            y = (h - height) // 2
            widget.setGeometry(x, y, width, height)

        # Right group: build from the right edge leftwards.
        widths = self._widths_right(w)
        x = w
        for (widget, _pref, _min_w), width in zip(
                reversed(self._right), reversed(widths)):
            x -= width
            place(widget, x, width)
            x -= self._gap
        right_block_left = x + self._gap
        # Left group: from the left; the last button compresses first.
        x = 0
        for i, widget in enumerate(self._left):
            pref = widget.sizeHint().width()
            remaining = right_block_left - self._gap - x
            if i == len(self._left) - 1:
                width = max(0, min(pref, remaining))
            else:
                width = min(pref, max(0, remaining))
            place(widget, x, width)
            x += width + self._gap

    def sizeHint(self) -> QSize:  # noqa: N802 (Qt naming)
        right_widgets = [w for (w, _p, _m) in self._right]
        lh = max((w.sizeHint().height() for w in self._left + right_widgets),
                 default=36)
        return QSize(400, max(lh, 36))

    def minimumSizeHint(self) -> QSize:  # noqa: N802 (Qt naming)
        return QSize(0, self.sizeHint().height())


class DeviceListRow(QWidget):
    """One device in the list view: dot · name / mono IP · MAC · pill · tiles.

    Mirrors the layout proposal: status dot and the two-line info block on
    the left, then the platform pill, the action tiles on the right (remote
    fullscreen, remote window, dashboard, edit) followed by the power icon
    button (wake ↔ shutdown, same color logic as the card action button).
    """

    remote_requested = pyqtSignal(str, bool)  # device id, fullscreen
    edit_requested = pyqtSignal(str)
    dashboard_requested = pyqtSignal(str)
    wake_requested = pyqtSignal(str)
    shutdown_requested = pyqtSignal(str)

    def __init__(
        self,
        device: dict,
        status: str,
        local_ips: set[str],
        remote_protocol: str = REMOTE_PROTOCOL_RDP,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.device_id: str = device["id"]
        self.device_name: str = device.get("name", "")
        self._device_ip: str = device.get("ip", "")
        self.enabled: bool = device.get("enabled", True)
        self._status = status
        self._remote_protocol = remote_protocol

        self.setObjectName("deviceRow")
        self.setFixedHeight(LIST_ROW_HEIGHT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 10, 18, 10)
        layout.setSpacing(14)

        self.dot = QLabel()
        self.dot.setFixedSize(10, 10)
        layout.addWidget(self.dot, 0, Qt.AlignmentFlag.AlignVCenter)

        info = QVBoxLayout()
        info.setSpacing(2)
        self.title = QLabel(self._display_name(local_ips))
        self.title.setObjectName(
            "rowTitle" if self.enabled else "rowTitleDisabled")
        ip = device.get("ip", "")
        mac = device.get("mac", "")
        self.mono = QLabel(f"{ip} · {mac}" if ip else mac)
        self.mono.setObjectName("rowMono")
        info.addWidget(self.title)
        info.addWidget(self.mono)
        layout.addLayout(info)

        layout.addStretch()

        # Platform chip: the detected OS doubles as the hint of which client
        # the remote tiles open (Windows → RDP, macOS/Linux → TurboVNC).
        self.pill = StatusPill(
            device.get("os", ""), device.get("os_confidence", ""))
        layout.addWidget(self.pill, 0, Qt.AlignmentFlag.AlignVCenter)

        self.remote_fs_btn = QPushButton("🖥️")
        self.remote_fs_btn.setObjectName("tileButton")
        self.remote_fs_btn.setFixedSize(36, 36)
        self.remote_fs_btn.setToolTip(
            remote_tooltip("button.remote_fullscreen", remote_protocol))
        self.remote_fs_btn.clicked.connect(
            lambda: self.remote_requested.emit(self.device_id, True))
        layout.addWidget(self.remote_fs_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        self.remote_win_btn = QPushButton("🪟")
        self.remote_win_btn.setObjectName("tileButton")
        self.remote_win_btn.setFixedSize(36, 36)
        self.remote_win_btn.setToolTip(
            remote_tooltip("button.remote_window", remote_protocol))
        self.remote_win_btn.clicked.connect(
            lambda: self.remote_requested.emit(self.device_id, False))
        layout.addWidget(self.remote_win_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        self.dashboard_btn = QPushButton("📊")
        self.dashboard_btn.setObjectName("tileButton")
        self.dashboard_btn.setFixedSize(36, 36)
        self.dashboard_btn.setToolTip(Translations.tr("button.dashboard"))
        self.dashboard_btn.clicked.connect(
            lambda: self.dashboard_requested.emit(self.device_id))
        layout.addWidget(self.dashboard_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        self.edit_btn = QPushButton("✏️")
        self.edit_btn.setObjectName("tileButton")
        self.edit_btn.setFixedSize(36, 36)
        self.edit_btn.setToolTip(Translations.tr("device_manager.button.edit"))
        self.edit_btn.clicked.connect(
            lambda: self.edit_requested.emit(self.device_id))
        layout.addWidget(self.edit_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        # Power icon button (far right): wake (accent) ↔ shutdown (danger),
        # objectName swap in set_status() — same logic as DeviceCard.
        self.action_btn = QPushButton()
        self.action_btn.setObjectName("wakeIconButton")
        self.action_btn.setFixedSize(36, 36)
        self.action_btn.clicked.connect(self._action_clicked)
        layout.addWidget(self.action_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        self.set_status(status)
        if not self.enabled:
            # Disabled devices cannot be reached remotely or woken
            self.remote_fs_btn.setEnabled(False)
            self.remote_win_btn.setEnabled(False)
            self.dashboard_btn.setEnabled(False)
            self.action_btn.setEnabled(False)

    # ── Status ────────────────────────────────────────────────────

    def _display_name(self, local_ips: set[str]) -> str:
        """Device name with the classic "(ich)" marker for the local machine."""
        name = self.device_name
        if self._device_ip in local_ips:
            name = f"{name} {Translations.tr('device.me')}"
        if not self.enabled:
            name = f"{name} {Translations.tr('device.disabled')}"
        return name

    def set_status(self, status: str) -> None:
        """Update the status dot and swap the power button (wake ↔ shutdown)."""
        self._status = status
        self.dot.setToolTip(Translations.tr(f"status.{status}"))
        dot_name = {
            "online": "dotOnline",
            "offline": "dotOffline",
        }.get(status, "dotUnknown")
        if self.dot.objectName() != dot_name:
            self.dot.setObjectName(dot_name)
            self._repolish(self.dot)
        self.pill.set_status(status)

        online = status == "online"
        action_name = "shutdownIconButton" if online else "wakeIconButton"
        tip_key = "button.shutdown" if online else "modern.devices.button.wake"
        if self.action_btn.objectName() != action_name:
            self.action_btn.setObjectName(action_name)
            self._repolish(self.action_btn)
        self.action_btn.setToolTip(Translations.tr(tip_key))

    def set_inference(self, state: str) -> None:
        """Show/hide the inference bolt inside the pill (v9 requests_active)."""
        self.pill.set_inference(state)

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

    # ── Mouse interaction ────────────────────────────────────────

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        self.edit_requested.emit(self.device_id)

    def retranslate(self, local_ips: set[str]) -> None:
        self.title.setText(self._display_name(local_ips))
        self.remote_fs_btn.setToolTip(
            remote_tooltip("button.remote_fullscreen", self._remote_protocol))
        self.remote_win_btn.setToolTip(
            remote_tooltip("button.remote_window", self._remote_protocol))
        self.dashboard_btn.setToolTip(Translations.tr("button.dashboard"))
        self.edit_btn.setToolTip(Translations.tr("device_manager.button.edit"))
        self.pill.retranslate()
        self.set_status(self._status)  # refresh power button tooltip


class DeviceCard(QWidget):
    """One device card: name + status/platform pill / IP · MAC / tiles + action."""

    wake_requested = pyqtSignal(str)
    shutdown_requested = pyqtSignal(str)
    remote_requested = pyqtSignal(str, bool)  # device id, fullscreen
    edit_requested = pyqtSignal(str)
    ping_requested = pyqtSignal(str)
    dashboard_requested = pyqtSignal(str)

    def __init__(
        self,
        device: dict,
        status: str,
        local_ips: set[str],
        remote_protocol: str = REMOTE_PROTOCOL_RDP,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.device_id: str = device["id"]
        self.device_name: str = device.get("name", "")
        self._device_ip: str = device.get("ip", "")
        self.enabled: bool = device.get("enabled", True)
        self._status = status
        self._remote_protocol = remote_protocol

        self.setObjectName("deviceCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        # Plain QWidget subclasses only paint QSS background/border with this
        # attribute set (same as #pageContent in ManageView).
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        # No minimum-width ratchet: Qt clamps a widget at its minimumSizeHint
        # (tiles + action button ≈ 290 px here), so a shrinking window could
        # never make the card narrower — the grid formula would keep seeing
        # the stale wide width and leave a dead margin on the right. With
        # Ignored, qSmartMinSize uses only the explicit minimumSize (0) and
        # the card follows its grid column exactly. (setMinimumWidth(0) alone
        # does NOT work: Preferred policy ignores it.)
        size_policy = self.sizePolicy()
        size_policy.setHorizontalPolicy(QSizePolicy.Policy.Ignored)
        size_policy.setVerticalPolicy(QSizePolicy.Policy.Preferred)
        self.setSizePolicy(size_policy)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(10)

        # ── Row 1: name … status/platform pill ──
        top = QHBoxLayout()
        top.setSpacing(10)
        self.title = QLabel(self._display_name(local_ips))
        self.title.setObjectName(
            "rowTitle" if self.enabled else "rowTitleDisabled")
        self.title.setWordWrap(True)
        self.pill = StatusPill(
            device.get("os", ""), device.get("os_confidence", ""))
        top.addWidget(self.title, 1)
        top.addWidget(self.pill, 0, Qt.AlignmentFlag.AlignVCenter)
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
        self.remote_fs_btn.setToolTip(
            remote_tooltip("button.remote_fullscreen", remote_protocol))
        self.remote_fs_btn.clicked.connect(
            lambda: self.remote_requested.emit(self.device_id, True))
        bottom.addWidget(self.remote_fs_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        self.remote_win_btn = QPushButton("🪟")
        self.remote_win_btn.setObjectName("tileButton")
        self.remote_win_btn.setFixedSize(36, 36)
        self.remote_win_btn.setToolTip(
            remote_tooltip("button.remote_window", remote_protocol))
        self.remote_win_btn.clicked.connect(
            lambda: self.remote_requested.emit(self.device_id, False))
        bottom.addWidget(self.remote_win_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        self.dashboard_btn = QPushButton("📊")
        self.dashboard_btn.setObjectName("tileButton")
        self.dashboard_btn.setFixedSize(36, 36)
        self.dashboard_btn.setToolTip(Translations.tr("button.dashboard"))
        self.dashboard_btn.clicked.connect(
            lambda: self.dashboard_requested.emit(self.device_id))
        bottom.addWidget(self.dashboard_btn, 0, Qt.AlignmentFlag.AlignVCenter)

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
            self.dashboard_btn.setEnabled(False)

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
        """Update the pill and swap the action button (wake ↔ shutdown)."""
        self._status = status
        self.pill.set_status(status)

        online = status == "online"
        action_name = "shutdownButton" if online else "wakeButton"
        action_key = "button.shutdown" if online else "modern.devices.button.wake"
        if self.action_btn.objectName() != action_name:
            self.action_btn.setObjectName(action_name)
            self._repolish(self.action_btn)
        self.action_btn.setText(Translations.tr(action_key))

    def set_inference(self, state: str) -> None:
        """Show/hide the inference bolt inside the pill (v9 requests_active)."""
        self.pill.set_inference(state)

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
        act_fs = menu.addAction(
            remote_tooltip("button.remote_fullscreen", self._remote_protocol))
        act_win = menu.addAction(
            remote_tooltip("button.remote_window", self._remote_protocol))
        act_dashboard = menu.addAction(Translations.tr("button.dashboard"))
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
        elif chosen is act_dashboard:
            self.dashboard_requested.emit(self.device_id)
        elif chosen is act_action:
            self._action_clicked()
        elif chosen is act_ping:
            self.ping_requested.emit(self.device_id)
        elif chosen is act_edit:
            self.edit_requested.emit(self.device_id)

    def retranslate(self, local_ips: set[str]) -> None:
        self.title.setText(self._display_name(local_ips))
        self.remote_fs_btn.setToolTip(
            remote_tooltip("button.remote_fullscreen", self._remote_protocol))
        self.remote_win_btn.setToolTip(
            remote_tooltip("button.remote_window", self._remote_protocol))
        self.dashboard_btn.setToolTip(Translations.tr("button.dashboard"))
        self.pill.retranslate()
        self.set_status(self._status)  # refresh wake/shutdown button text


class DevicesView(QWidget):
    """The modern "Geräte" screen (card grid or device list).

    The toolbar toggles between the two views (icon top-left) and offers a
    sort drop-down (name / IP / MAC / status) next to the search field.
    Both the view mode and the sort key are persisted via ConfigManager.
    """

    devices_changed = pyqtSignal()
    dashboard_requested = pyqtSignal(str)  # device id — open the dashboard view
    statuses_refreshed = pyqtSignal(dict)  # device id -> status (dashboard nav)

    def __init__(self, config_manager: Any, parent=None) -> None:
        super().__init__(parent)
        self.config: Any = config_manager
        self.engine: WOLEngine = WOLEngine(config_manager)
        self._status_thread: QThread | None = None
        self._status_worker: StatusWorker | None = None
        self._statuses: dict[str, str] = {}  # device id -> last known status
        # Platform detection (only for devices without a stored platform):
        # _os_probed remembers what was already fingerprinted this session so
        # silent hosts are not probed again on every screen change.
        self._os_thread: QThread | None = None
        self._os_worker: OsDetectWorker | None = None
        self._os_probed: set[str] = set()
        self._cards: dict[str, DeviceCard] = {}
        self._rows: dict[str, DeviceListRow] = {}
        # Inference badge (host protocol v9): device id ->
        # "active" | "idle" | "warn" | "hidden" (absent = hidden too).
        # Cached so a card rebuild (sort/filter/edit) re-applies the last
        # known state.
        self._inference_states: dict[str, str] = {}
        self._inference_thread: QThread | None = None
        self._inference_worker: InferenceSweepWorker | None = None
        self._grid_cols = 0
        # Highest column count ever used: QGridLayout keeps per-column
        # properties (stretch, min width) PERMANENTLY, so a column left over
        # from a wider layout would keep stretch=1 and split the row into a
        # phantom extra column — cards too narrow with a dead margin on the
        # right. Every reflow resets all columns up to this high-water mark.
        self._grid_max_cols = 0
        self._view_mode: str = self.config.get_devices_view_mode()
        self._sort_key: str = self.config.get_devices_sort_key()

        self._setup_ui()
        self.refresh_devices()
        # Devices added by hand — or before the scanner stored a platform —
        # have no "os" value, so their pill would stay at "unknown" and the
        # Remote buttons could not route. Fingerprint them once per session.
        self.detect_missing_platforms()

        # Autorefresh like the prototype footer ("Autorefresh alle 30 s")
        self._timer = QTimer(self)
        self._timer.setInterval(AUTO_REFRESH_MS)
        self._timer.timeout.connect(self._auto_refresh)
        self._timer.start()

        # Inference badge poll (design_prototype/Inferenz_Kachel.html): its
        # own interval — the status ping stays at 30 s while "is a job
        # running" wants 5-30 s. Config: ui.inference_interval_ms.
        self._inference_timer = QTimer(self)
        self._inference_timer.setInterval(self._inference_interval_ms())
        self._inference_timer.timeout.connect(self._auto_inference_poll)
        self._inference_timer.start()

    # ── UI construction ──────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        content = QWidget()
        content.setObjectName("pageContent")
        content.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        # Content width is pinned to the viewport (see WidthPinnedScrollArea):
        # the grid formula below always measures the REAL visible width.
        scroll = WidthPinnedScrollArea(content)
        outer.addWidget(scroll)
        self._scroll = scroll

        layout = QVBoxLayout(content)
        # Horizontal margins match PAGE_MARGIN_H (prototype .main padding 36px)
        layout.setContentsMargins(PAGE_MARGIN_H, 26, PAGE_MARGIN_H, 26)
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
        layout.addLayout(header)
        layout.addSpacing(4)

        # ── Toolbar: view toggle · refresh · wake all … sort · search ──
        # FlexToolbar (manual CSS space-between): the right group (sort +
        # search) is ALWAYS right-aligned at the content edge, so the
        # search field's right edge coincides with the last card's right
        # edge at every window width. A QBoxLayout would spread width
        # deficits over all items and slide the search field left instead.
        toolbar = FlexToolbar()
        # View-mode toggle (icon top left): three lines while the card grid
        # is active, four tiles while the list is active. Glyphs come from
        # the #viewListButton / #viewGridButton QSS images (SVG).
        self.view_btn = QPushButton()
        self.view_btn.setFixedSize(36, 36)
        self.view_btn.clicked.connect(self._toggle_view_mode)
        toolbar.add_left(self.view_btn)

        # No text: the glyph comes from the #refreshButton QSS image (SVG),
        # a font glyph like "⟳" renders small and font-dependent.
        self.refresh_btn = QPushButton()
        self.refresh_btn.setObjectName("refreshButton")
        self.refresh_btn.setFixedSize(36, 36)
        self.refresh_btn.setToolTip(Translations.tr("button.refresh"))
        self.refresh_btn.clicked.connect(self._on_refresh_clicked)
        toolbar.add_left(self.refresh_btn)

        self.wake_all_btn = QPushButton(Translations.tr("button.wake_all"))
        self.wake_all_btn.setObjectName("primaryButton")
        self.wake_all_btn.clicked.connect(self._wake_all)
        toolbar.add_left(self.wake_all_btn)

        # Inference poll interval (left of the sort combo) — persisted
        # setting; only meaningful for devices with watched processes.
        self.inference_combo = QComboBox()
        self.inference_combo.setObjectName("devicesIntervalCombo")
        for ms in INFERENCE_INTERVAL_CHOICES_MS:
            self.inference_combo.addItem(Translations.tr("modern.devices.interval.seconds", seconds=ms // 1000), ms)
        current = self._inference_interval_ms()
        idx = self.inference_combo.findData(current)
        if idx < 0:
            self.inference_combo.addItem(Translations.tr("modern.devices.interval.seconds", seconds=current // 1000), current)
            idx = self.inference_combo.count() - 1
        self.inference_combo.setCurrentIndex(idx)
        self.inference_combo.setToolTip(
            Translations.tr("modern.devices.infer.interval_tip"))
        self.inference_combo.currentIndexChanged.connect(
            self._on_inference_interval_changed)
        toolbar.add_right(
            self.inference_combo,
            width=FlexToolbar.INTERVAL_W, min_width=FlexToolbar.INTERVAL_MIN)

        # Sort drop-down (left of the search field) — persisted setting.
        self.sort_combo = QComboBox()
        self.sort_combo.setObjectName("devicesSortCombo")
        self._sort_keys: list[str] = []
        for key in ("name", "ip", "mac", "status"):
            self.sort_combo.addItem(
                Translations.tr(f"modern.devices.sort.{key}"), key)
            self._sort_keys.append(key)
        idx = self.sort_combo.findData(self._sort_key)
        self.sort_combo.setCurrentIndex(max(0, idx))
        self.sort_combo.currentIndexChanged.connect(self._on_sort_changed)
        toolbar.add_right(self.sort_combo)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(Translations.tr("ui.search_devices_placeholder"))
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self.refresh_devices)
        toolbar.add_right(self.search_input)
        layout.addWidget(toolbar)
        layout.addSpacing(6)

        # ── Card grid (Kachelansicht) ──
        grid_host = QWidget()
        grid_host.setObjectName("deviceGrid")
        # Same no-ratchet rule as the cards: the host must always follow the
        # content width, never hold it open at its layout minimum.
        host_policy = grid_host.sizePolicy()
        host_policy.setHorizontalPolicy(QSizePolicy.Policy.Ignored)
        grid_host.setSizePolicy(host_policy)
        self.grid = QGridLayout(grid_host)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(GRID_SPACING)
        self._grid_host = grid_host
        layout.addWidget(grid_host)

        # ── Device list (Listenansicht): panel with rows + separators ──
        list_panel = QWidget()
        list_panel.setObjectName("panel")
        list_panel.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.list_layout = QVBoxLayout(list_panel)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(0)
        self._list_panel = list_panel
        layout.addWidget(list_panel)

        # Empty state
        self.empty_label = QLabel(Translations.tr("modern.devices.empty"))
        self.empty_label.setObjectName("placeholderText")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setWordWrap(True)
        self.empty_label.hide()
        layout.addWidget(self.empty_label)

        layout.addStretch()

        self._apply_view_mode()

    # ── View mode / sorting ──────────────────────────────────────────────

    def _apply_view_mode(self) -> None:
        """Show grid or list and set the toggle icon (three lines ↔ tiles)."""
        is_list = self._view_mode == DEVICES_VIEW_LIST
        self._grid_host.setVisible(not is_list)
        self._list_panel.setVisible(is_list)
        name = "viewGridButton" if is_list else "viewListButton"
        tip_key = (
            "modern.devices.view.grid" if is_list
            else "modern.devices.view.list")
        if self.view_btn.objectName() != name:
            self.view_btn.setObjectName(name)
            style = self.view_btn.style()
            style.unpolish(self.view_btn)
            style.polish(self.view_btn)
        self.view_btn.setToolTip(Translations.tr(tip_key))

    def _toggle_view_mode(self) -> None:
        self._view_mode = (
            DEVICES_VIEW_GRID if self._view_mode == DEVICES_VIEW_LIST
            else DEVICES_VIEW_LIST)
        try:
            self.config.set_devices_view_mode(self._view_mode)
        except Exception:  # pragma: no cover - persistence must not break UI
            pass
        self._apply_view_mode()

    def _on_sort_changed(self, index: int) -> None:
        if 0 <= index < len(self._sort_keys):
            self._sort_key = self._sort_keys[index]
            try:
                self.config.set_devices_sort_key(self._sort_key)
            except Exception:  # pragma: no cover - persistence must not break UI
                pass
            self.refresh_devices()

    def _sort_devices(self, devices: list[dict]) -> list[dict]:
        """Sort by the active key; name/IP/MAC ascending, status by rank."""
        key = self._sort_key
        if key == "ip":
            return sorted(devices, key=lambda d: ip_sort_key(str(d.get("ip", ""))))
        if key == "mac":
            return sorted(devices, key=lambda d: str(d.get("mac", "")).upper())
        if key == "status":
            return sorted(
                devices,
                key=lambda d: (
                    STATUS_SORT_RANK.get(self._statuses.get(d.get("id"), "unknown"), 2),
                    str(d.get("name", "")).lower(),
                ),
            )
        return sorted(devices, key=lambda d: str(d.get("name", "")).lower())

    # ── Device list ──────────────────────────────────────────────────────

    def _filtered_devices(self) -> list[dict]:
        query = self.search_input.text().strip().lower()
        devices = self._sort_devices(self.config.get_devices())
        if not query:
            return devices
        fields = ("name", "mac", "ip", "username")
        return [
            d for d in devices
            if any(query in str(d.get(f, "")).lower() for f in fields)
        ]

    def refresh_devices(self) -> None:
        """Rebuild cards and list rows (device list, sort or filter changed)."""
        while self.grid.count():
            item = self.grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._cards.clear()
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._rows.clear()

        local_ips = get_local_ips()
        devices = self._filtered_devices()
        for idx, device in enumerate(devices):
            status = self._statuses.get(device["id"], "unknown")
            protocol = resolve_remote_protocol(self.config, device)
            card = DeviceCard(device, status, local_ips, protocol)
            card.wake_requested.connect(self._wake_device)
            card.shutdown_requested.connect(self._shutdown_device)
            card.remote_requested.connect(self._remote_device)
            card.edit_requested.connect(self._edit_device)
            card.ping_requested.connect(self._ping_device)
            card.dashboard_requested.connect(self._open_dashboard)
            self._cards[device["id"]] = card

            row = DeviceListRow(device, status, local_ips, protocol)
            row.remote_requested.connect(self._remote_device)
            row.edit_requested.connect(self._edit_device)
            row.dashboard_requested.connect(self._open_dashboard)
            row.wake_requested.connect(self._wake_device)
            row.shutdown_requested.connect(self._shutdown_device)
            self._rows[device["id"]] = row
            self.list_layout.addWidget(row)
            if idx < len(devices) - 1:
                sep = QWidget()
                sep.setObjectName("rowSeparator")
                sep.setFixedHeight(1)
                self.list_layout.addWidget(sep)
            # Re-apply the cached inference badge (cards/rows are rebuilt on
            # every sort/filter/edit — the poll result must survive that).
            state = self._inference_states.get(device["id"])
            if state:
                card.set_inference(state)
                row.set_inference(state)

        self._relayout_grid()
        self._update_summary()
        self.empty_label.setVisible(not devices)

    def _grid_columns(self) -> int:
        """Column count from the current viewport width (0 = not measured yet).

        Before the first real layout the view is hidden and its viewport only
        has a placeholder size; measuring then would produce a bogus column
        count that visibly "jumps" on the first resize. Return 0 as a sentinel
        so the first visible layout (resizeEvent or the deferred showEvent
        pass) always establishes the real column count.
        """
        if not self.isVisible():
            return 0
        vw = self._scroll.viewport().width()
        if vw <= 0:
            return 0
        # The content is pinned to the viewport width (WidthPinnedScrollArea)
        # and the grid host fills it minus the page margins — so this is the
        # REAL width the cards get, never a stale clamped one.
        avail = max(vw - 2 * PAGE_MARGIN_H, CARD_MIN_WIDTH)
        return compute_columns(avail)

    def _relayout_grid(self) -> None:
        """Place the cards into the grid, computing the column count from width."""
        cols = self._grid_columns()
        # Not measured (hidden view or no width yet): stack in one column and
        # RESET the sentinel to 0, so the next showEvent/resize reflows with
        # the real width. Without the reset, a rebuild while the view is
        # hidden (e.g. device edited on "Verwalten" -> refresh_devices) would
        # leave a 1-column placeholder that showEvent skips, because
        # _grid_cols still holds the old (correct-looking) column count.
        if cols == 0:
            self._grid_cols = 0
            cols = 1
        else:
            self._grid_cols = cols

        while self.grid.count():
            self.grid.takeAt(0)
        for i, card in enumerate(self._cards.values()):
            self.grid.addWidget(card, i // cols, i % cols)
        # Reset EVERY column ever used before stretching the active ones:
        # QGridLayout keeps columnStretch permanently, so a leftover column
        # from a wider layout would act as a phantom stretch column — cards
        # too narrow with a dead margin on the right (takeAt does NOT clear
        # column properties).
        for c in range(cols, self._grid_max_cols + 1):
            self.grid.setColumnStretch(c, 0)
        # Stretch columns so cards fill the row like the prototype grid
        for c in range(cols):
            self.grid.setColumnStretch(c, 1)
        self._grid_max_cols = max(self._grid_max_cols, cols)

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        super().resizeEvent(event)
        if self._view_mode == DEVICES_VIEW_LIST:
            return
        # Reflow the grid when the column count changes (0 sentinel: the
        # constructor measured before layout — first resize always reflows)
        cols = self._grid_columns()
        if cols and cols != self._grid_cols:
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
        dialog = ModernShutdownConfirmDialog(device.get("name", ""), self)
        if dialog.exec():
            execute_shutdown(self, self.config, device, None)
        # Status will update on the next refresh cycle

    def _remote_device(self, device_id: str, fullscreen: bool) -> None:
        device = self._device_by_id(device_id)
        if device is None:
            return
        start_remote_desktop(self, self.config, device, fullscreen)

    def _open_dashboard(self, device_id: str) -> None:
        """Forward the dashboard request to the main window (stack switch)."""
        if self._device_by_id(device_id) is not None:
            self.dashboard_requested.emit(device_id)

    def _ping_device(self, device_id: str) -> None:
        device = self._device_by_id(device_id)
        if device is None:
            return
        status, msg = self.engine.check_device_status(device_id)
        self._statuses[device_id] = status
        card = self._cards.get(device_id)
        if card is not None:
            card.set_status(status)
        row = self._rows.get(device_id)
        if row is not None:
            row.set_status(status)
        # The "status" sort order depends on the new status
        if self._sort_key == "status":
            self.refresh_devices()
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
        # A hand-added device has no platform yet — fingerprint it too.
        self.detect_missing_platforms()
        self.devices_changed.emit()

    # ── Status checks ────────────────────────────────────────────────────

    def device_statuses(self) -> dict[str, str]:
        """Last known ping status per device id (dashboard prev/next nav)."""
        return dict(self._statuses)

    def _on_refresh_clicked(self) -> None:
        """Manual refresh: statuses now, and a second try for missing platforms.

        The automatic pass fingerprints every device only once per session, so
        a device that was asleep during the first sweep would stay without a
        platform until the next start. The refresh button deliberately forgets
        that memory for the devices which still have no platform.
        """
        getter = getattr(self.config, "get_device_os", None)
        for device in self.config.get_devices():
            if not (callable(getter) and getter(device)):
                self._os_probed.discard(device.get("id"))
        self.refresh_statuses()
        self.detect_missing_platforms()

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
            row = self._rows.get(device_id)
            if row is not None:
                row.set_status(status)
        # Keep the list order correct when sorting by status
        if self._sort_key == "status":
            self.refresh_devices()
        self._update_summary()
        # Dashboard prev/next navigation skips offline devices.
        self.statuses_refreshed.emit(dict(self._statuses))

    # ── Platform detection ───────────────────────────────────────────────

    def detect_missing_platforms(self) -> None:
        """Fingerprint every device that has no stored platform yet.

        Devices added by hand (or before the scanner stored a platform) lack
        the ``os`` key, which leaves the platform pill at "unknown" and forces
        the Remote buttons onto the RDP fallback. The already-implemented
        fingerprint of :mod:`wol_app.os_detect` runs in a background thread
        (:class:`wol_app.app_core.OsDetectWorker`) and the result is persisted
        via ``config.set_device_os()``, so it survives restarts. Each device
        is probed at most once per session — a silent host is not re-probed on
        every refresh.
        """
        if HEADLESS_MODE:
            return
        if self._os_thread is not None and self._os_thread.isRunning():
            return

        getter = getattr(self.config, "get_device_os", None)

        def has_platform(device: dict) -> bool:
            return bool(callable(getter) and getter(device))

        pending = [
            d for d in self.config.get_devices()
            if d.get("enabled", True)
            and (d.get("ip") or "").strip()
            and not has_platform(d)
            and d.get("id") not in self._os_probed
        ]
        if not pending:
            return

        self._os_worker = OsDetectWorker(self.config)
        self._os_thread = QThread()
        self._os_worker.moveToThread(self._os_thread)
        self._os_thread.started.connect(self._os_worker.run)
        self._os_worker.finished.connect(self._on_platforms_finished)
        self._os_worker.finished.connect(self._os_thread.quit)
        self._os_worker.finished.connect(self._os_worker.deleteLater)

        def on_thread_finished() -> None:
            self._os_thread.deleteLater()
            self._os_thread = None

        self._os_thread.finished.connect(on_thread_finished)
        self._os_thread.start()

    def _on_platforms_finished(self, results: list) -> None:
        """Persist the detected platforms and rebuild cards/rows."""
        changed = False
        for entry in results:
            device_id, os_id, confidence = entry[0], entry[1], entry[2]
            self._os_probed.add(device_id)
            if not os_id:
                continue
            setter = getattr(self.config, "set_device_os", None)
            if callable(setter) and setter(device_id, os_id, confidence):
                changed = True
        if changed:
            # Rebuild so pill text, remote tooltips and the RDP/VNC routing
            # pick up the newly stored platform.
            self.refresh_devices()

    def _auto_refresh(self) -> None:
        if self.isVisible():
            self.refresh_statuses()

    # ── Inference badge (host protocol v9 "requests_active") ───────────

    def _inference_interval_ms(self) -> int:
        getter = getattr(self.config, "get_inference_interval_ms", None)
        if not callable(getter):
            return DEFAULT_INFERENCE_INTERVAL_MS
        try:
            value = int(getter())
        except (TypeError, ValueError):
            return DEFAULT_INFERENCE_INTERVAL_MS
        return value if value > 0 else DEFAULT_INFERENCE_INTERVAL_MS

    def _on_inference_interval_changed(self) -> None:
        ms = self.inference_combo.currentData()
        if not isinstance(ms, int):
            return
        setter = getattr(self.config, "set_inference_interval_ms", None)
        if callable(setter):
            setter(ms)
        self._inference_timer.setInterval(self._inference_interval_ms())
        # Immediate feedback for the new cadence (mirrors the dashboard).
        self.refresh_inference()

    def _inference_targets(self) -> list:
        """Devices worth polling: watched processes + host credentials.

        Without username/password every metrics request is rejected, and
        without a watch list the host never reports ``processes`` — both
        cases skip the network round-trip. Offline devices are skipped too
        (the TCP connect would burn the full timeout); they re-enter the
        sweep as soon as the status ping calls them online again.
        """
        targets = []
        for device in self.config.get_devices():
            if not device.get("enabled", True):
                continue
            if not (device.get("username", "") and device.get("password", "")):
                continue
            watch = ConfigManager.get_device_watch_processes(device)
            if not watch:
                continue
            if self._statuses.get(device["id"]) == "offline":
                continue
            targets.append({
                "id": device["id"],
                "ip": device.get("ip", ""),
                "username": device.get("username", ""),
                "password": device.get("password", ""),
                "watch": watch,
            })
        return [t for t in targets if t["ip"]]

    def refresh_inference(self) -> None:
        """Poll the inference badge state for every watch-configured device."""
        if HEADLESS_MODE:
            return
        if self._inference_thread is not None and self._inference_thread.isRunning():
            return  # single-flight: never stack sweeps
        targets = self._inference_targets()
        if not targets:
            return

        self._inference_worker = InferenceSweepWorker(targets)
        self._inference_thread = QThread()
        self._inference_worker.moveToThread(self._inference_thread)
        self._inference_thread.started.connect(self._inference_worker.run)
        self._inference_worker.finished.connect(self._on_inference_finished)
        self._inference_worker.finished.connect(self._inference_thread.quit)
        self._inference_worker.finished.connect(self._inference_worker.deleteLater)

        def on_thread_finished() -> None:
            self._inference_thread.deleteLater()
            self._inference_thread = None

        self._inference_thread.finished.connect(on_thread_finished)
        self._inference_thread.start()

    def _on_inference_finished(self, results: list) -> None:
        """Apply the badge state derived from each device's metrics reply."""
        for device_id, response in results:
            state = derive_inference_state(response)
            if state is None:
                continue  # no verdict (pre-v9 host / unreachable) — keep last
            self._inference_states[device_id] = state
            card = self._cards.get(device_id)
            if card is not None:
                card.set_inference(state)
            row = self._rows.get(device_id)
            if row is not None:
                row.set_inference(state)

    def _auto_inference_poll(self) -> None:
        if self.isVisible():
            self.refresh_inference()

    def showEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        super().showEvent(event)
        self.refresh_statuses()
        self.refresh_inference()
        # Safety net: if the grid was built before the first real layout
        # (sentinel _grid_cols == 0), reflow once the viewport has a width —
        # even when showing never triggers a resizeEvent.
        if self._grid_cols == 0:
            QTimer.singleShot(0, self._relayout_grid)

    # ── Language / lifecycle ─────────────────────────────────────────────

    def retranslate(self) -> None:
        """Re-apply all texts after a language switch."""
        self.title.setText(Translations.tr("modern.devices.title"))
        self.search_input.setPlaceholderText(Translations.tr("ui.search_devices_placeholder"))
        self.refresh_btn.setToolTip(Translations.tr("button.refresh"))
        self.wake_all_btn.setText(Translations.tr("button.wake_all"))
        self.empty_label.setText(Translations.tr("modern.devices.empty"))
        # Re-label the sort drop-down, keeping the selected key
        for i, key in enumerate(self._sort_keys):
            self.sort_combo.setItemText(i, Translations.tr(f"modern.devices.sort.{key}"))
        # Re-label the inference interval drop-down, keeping the selected ms
        for i in range(self.inference_combo.count()):
            ms = self.inference_combo.itemData(i)
            if isinstance(ms, int):
                self.inference_combo.setItemText(i, Translations.tr("modern.devices.interval.seconds", seconds=ms // 1000))
        self.inference_combo.setToolTip(
            Translations.tr("modern.devices.infer.interval_tip"))
        self._apply_view_mode()  # refresh the toggle tooltip
        local_ips = get_local_ips()
        for card in self._cards.values():
            card.retranslate(local_ips)
        for row in self._rows.values():
            row.retranslate(local_ips)
        self._update_summary()

    def cancel_workers(self) -> None:
        """Cancel background work on window close (mirrors ManageView)."""
        self._timer.stop()
        self._inference_timer.stop()
        if self._status_worker is not None:
            self._status_worker.cancel()
        if self._status_thread is not None and self._status_thread.isRunning():
            self._status_thread.quit()
            self._status_thread.wait(2000)
        if self._inference_worker is not None:
            self._inference_worker.cancel()
        if self._inference_thread is not None and self._inference_thread.isRunning():
            self._inference_thread.quit()
            self._inference_thread.wait(2000)
