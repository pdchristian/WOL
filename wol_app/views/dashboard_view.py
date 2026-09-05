"""Modern UI: device dashboard (live metrics + remote batches).

Layout mirrors design_prototype/Dashboard_Prototyp_Flash.html:

1. Page header: back button, device name + status badge, mono IP · MAC and
   the metrics poll interval.
2. Four metric cards (CPU / RAM / GPU / VRAM), each with a ring gauge, a
   detail line and a 60-sample sparkline.
3. A batch section: the device's batch library on the left, an editor
   (name / script / timeout) with "Run" on the right, and an output console.

All data comes from the WOL Host Service on the target machine via
:mod:`wol_app.metrics_worker` (metrics polled on a timer, single-flight);
batches are persisted per device in ``config.json`` and require both the
per-device opt-in (``allow_batch``) and the host-side gate
(``--enable-batch``).

The view is opened from the 📊 tile on the devices screen (no sidebar
entry); ``ModernMainWindow`` switches the stack and calls
:meth:`set_device`.
"""

from collections import deque
from datetime import datetime
from typing import Any

from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from wol_app.config import (
    BATCH_TIMEOUT_MAX_S,
    BATCH_TIMEOUT_MIN_S,
    DEFAULT_BATCH_TIMEOUT_S,
    ConfigManager,
)
from wol_app.main_window import HEADLESS_MODE
from wol_app.metrics_worker import BatchWorker, MetricsWorker
from wol_app.modern_theme import current_tokens
from wol_app.translations import Translations

# Ring gauge geometry (prototype .gauge: 86 px, stroke 8)
GAUGE_SIZE = 86
GAUGE_STROKE = 8

# Sparkline history: 60 samples (≈ 3 minutes at the 3 s default interval)
SPARK_SAMPLES = 60

# Interval choices offered in the header (seconds)
INTERVAL_CHOICES = (2, 3, 5, 10)

_GAUGE_TOKENS = {"cpu": "gauge_cpu", "ram": "gauge_ram", "gpu": "gauge_gpu",
                 "vram": "gauge_vram"}

# "Inferenz aktiv" indicator: whole-machine GPU load at/above this percent
# for INFERENCE_GPU_POLLS consecutive polls while a watched service is
# ready. The host service only reports the machine's GPU utilization, so
# this is a heuristic that tells an idle llama-server apart from one
# answering requests (shown as a small badge next to the service name).
INFERENCE_GPU_PCT = 60.0
INFERENCE_GPU_POLLS = 2


def _watch_display_name(entry: str) -> str:
    """``"llama-server.exe:8080"`` -> ``"llama-server"`` (chip/row label)."""
    name = entry.rpartition(":")[0] or entry
    if name.lower().endswith(".exe"):
        name = name[:-4]
    return name


def _watch_icon(entry: str) -> str:
    return "🦙" if "llama" in entry.lower() else "⚙️"


def _model_names(info: dict) -> list[str]:
    """Loaded model names for one watched-process entry (dashboard order).

    Prefers the host's ``models`` list (llama-server API ``GET /v1/models``,
    host protocol v4: every model resident on the server, loaded or sleeping
    in a llama-swap setup). Falls back to the single argv-derived ``model``
    (``-m`` flag) that older hosts report. Names keep their internal dots
    (``Qwen3.8-Flash-256k-62``) - the host already strips only a real file
    extension. Never raises; may return an empty list.
    """
    models = info.get("models")
    if isinstance(models, list):
        names = [str(m).strip() for m in models if str(m or "").strip()]
        if names:
            return names
    legacy = str(info.get("model") or "").strip()
    return [legacy] if legacy else []


def _fmt_bytes_gb(value: int | float | None) -> str:
    """Bytes → "12.3" GB string (one decimal, German-agnostic dot)."""
    if value is None:
        return ""
    return f"{value / (1024 ** 3):.1f}"


def _fmt_uptime(seconds: int | None) -> str:
    """Seconds → "3 d 4 h" / "4 h 12 m" / "12 m"."""
    if not seconds or seconds < 0:
        return ""
    days, rem = divmod(int(seconds), 86400)
    hours, rem = divmod(rem, 3600)
    minutes = rem // 60
    if days:
        return f"{days} d {hours} h"
    if hours:
        return f"{hours} h {minutes} m"
    return f"{minutes} m"


class RingGauge(QWidget):
    """Circular progress ring (prototype .gauge) with a centered value."""

    def __init__(self, color_key: str, parent=None) -> None:
        super().__init__(parent)
        self.setFixedSize(GAUGE_SIZE, GAUGE_SIZE)
        self._color_key = color_key
        self._pct: float | None = None
        self._value = QLabel("–")
        self._value.setObjectName("gaugeValue")
        self._value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._value)

    def set_value(self, pct: float | None) -> None:
        self._pct = None if pct is None else max(0.0, min(100.0, float(pct)))
        self._value.setText("–" if self._pct is None else str(round(self._pct)))
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        t = current_tokens()
        radius = (GAUGE_SIZE - GAUGE_STROKE) / 2 - 1
        center = GAUGE_SIZE / 2

        track = QPen(QColor(t["border"]), GAUGE_STROKE)
        painter.setPen(track)
        painter.drawEllipse(
            int(center - radius), int(center - radius),
            int(radius * 2), int(radius * 2),
        )

        if self._pct is not None:
            arc = QPen(QColor(t[self._color_key]), GAUGE_STROKE)
            arc.setCapStyle(Qt.PenCapStyle.FlatCap)
            painter.setPen(arc)
            # Qt angles are 1/16 degree; negative span draws clockwise from 12 o'clock.
            painter.drawArc(
                int(center - radius), int(center - radius),
                int(radius * 2), int(radius * 2),
                90 * 16, -int(self._pct * 360 * 16 / 100),
            )
        painter.end()


class Sparkline(QWidget):
    """Rolling line chart of the last SPARK_SAMPLES values (prototype canvas)."""

    def __init__(self, color_key: str, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(34)
        self.setMinimumWidth(60)
        self._color_key = color_key
        self._values: deque[float | None] = deque(
            [None] * SPARK_SAMPLES, maxlen=SPARK_SAMPLES)

    def push(self, pct: float | None) -> None:
        self._values.append(pct)
        self.update()

    def reset(self) -> None:
        self._values = deque([None] * SPARK_SAMPLES, maxlen=SPARK_SAMPLES)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor(current_tokens()[self._color_key])
        pen = QPen(color, 1.5)
        painter.setPen(pen)
        w, h = self.width(), self.height()
        if w < 4 or h < 4:
            return
        # Connect the known samples; gaps (None) break the line.
        step = w / (SPARK_SAMPLES - 1)
        last_x: float | None = None
        last_y: float | None = None
        for i, value in enumerate(self._values):
            if value is None:
                last_x = last_y = None
                continue
            x = i * step
            y = h - 2 - (max(0.0, min(100.0, value)) / 100.0) * (h - 4)
            if last_x is not None:
                painter.drawLine(int(last_x), int(last_y), int(x), int(y))
            last_x, last_y = x, y
        painter.end()


class MetricCard(QWidget):
    """One metric: title + color dot, ring gauge, detail line, sparkline."""

    def __init__(self, key: str, title: str, parent=None) -> None:
        super().__init__(parent)
        self.key = key
        self.setObjectName("metricCard")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        color_key = _GAUGE_TOKENS[key]

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 12)
        layout.setSpacing(8)

        head = QHBoxLayout()
        head.setSpacing(8)
        self.title = QLabel(title.upper())
        self.title.setObjectName("metricTitle")
        dot = QLabel()
        dot.setObjectName("metricDot")
        dot.setFixedSize(8, 8)
        pix = QPixmap(8, 8)
        pix.fill(QColor(current_tokens()[color_key]))
        dot.setPixmap(pix)
        head.addWidget(self.title)
        head.addStretch()
        head.addWidget(dot, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(head)

        gauge_row = QHBoxLayout()
        gauge_row.setSpacing(14)
        self.gauge = RingGauge(color_key)
        self.detail = QLabel("")
        self.detail.setObjectName("rowMono")
        self.detail.setWordWrap(True)
        gauge_row.addWidget(self.gauge, 0, Qt.AlignmentFlag.AlignVCenter)
        gauge_row.addWidget(self.detail, 1, Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(gauge_row)

        self.spark = Sparkline(color_key)
        layout.addWidget(self.spark)

    def set_title(self, title: str) -> None:
        self.title.setText(title.upper())

    def set_value(self, pct: float | None, detail: str) -> None:
        self.gauge.set_value(pct)
        self.detail.setText(detail)
        self.spark.push(pct)

    def reset_display(self) -> None:
        self.gauge.set_value(None)
        self.detail.setText("")
        self.spark.reset()


class ServiceChip(QLabel):
    """Header chip for one watched process (prototype .svc-chip).

    Three visual states, matching the design prototype:
    running + API port open → green "aktiv", running but port closed →
    amber "startet…", not found → grey "inaktiv". The chip is hidden when
    the host is offline or the host service is too old (no ``processes``).
    """

    def __init__(self, entry: str, parent=None) -> None:
        super().__init__(parent)
        self.entry = entry
        self.setFixedHeight(20)
        # Chip padding comes from contentsMargins, NOT the QSS padding:
        # the initial set_state(None) hides the label, and a QLabel that was
        # hidden before its first style polish never picks up QSS box-model
        # properties (padding stays 0) - which made the chips render tight.
        self.setContentsMargins(22, 0, 22, 0)
        self.setAlignment(
            Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self._state = ""
        self.set_state(None)

    def set_state(self, info: dict | None) -> None:
        """*info* is the per-entry dict from the metrics ``processes`` map.

        ``None`` hides the chip (host offline / host service too old).
        """
        if info is None:
            self.setObjectName("")
            self.setText("")
            self.setToolTip("")
            self.setVisible(False)
            self._repolish("")
            return
        self.setVisible(True)
        running = bool(info.get("running"))
        # A port was only requested for "name.exe:port" entries; without one
        # "running" alone is enough for the green state.
        wants_port = info.get("api_port") is not None
        port_open = bool(info.get("api_port_open"))
        ready = running and (port_open or not wants_port)
        name = _watch_display_name(self.entry)
        icon = _watch_icon(self.entry)
        if ready:
            state, model = "svcChipRunning", ""
            names = _model_names(info)
            if names:
                # Chip stays compact: first model, "+N" for the rest.
                label = names[0]
                if len(names) > 1:
                    label = f"{label} +{len(names) - 1}"
                model = f" · {label}"
            self.setText(f"{icon} {name}{model}")
            tip = Translations.tr("modern.dashboard.svc.tip_running",
                                  pid=info.get("pid", "?"),
                                  uptime=_fmt_uptime(info.get("uptime")),
                                  cpu=info.get("cpu", 0.0),
                                  ram=_fmt_bytes_gb(info.get("ram")))
            if names:
                tip += "\n" + Translations.tr(
                    "modern.dashboard.svc.tip_models",
                    models=", ".join(names))
        elif running:
            state = "svcChipProbing"
            self.setText(f"{icon} {name} · {Translations.tr('modern.dashboard.svc.starting')}")
            tip = Translations.tr("modern.dashboard.svc.tip_no_port",
                                  pid=info.get("pid", "?"),
                                  port=info.get("api_port", ""))
        else:
            state = "svcChipInactive"
            self.setText(f"{icon} {name} · {Translations.tr('modern.dashboard.svc.inactive')}")
            tip = Translations.tr("modern.dashboard.svc.tip_stopped")
        self.setToolTip(tip)
        self._repolish(state)

    def _repolish(self, state: str) -> None:
        if self._state == state:
            return
        self._state = state
        self.setObjectName(state)
        style = self.style()
        style.unpolish(self)
        style.polish(self)


class ServiceRow(QWidget):
    """One row of the services panel: icon, status line, process metrics."""

    def __init__(self, entry: str, parent=None) -> None:
        super().__init__(parent)
        self.entry = entry
        self.setObjectName("svcRow")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(16)

        self.icon = QLabel(_watch_icon(entry))
        self.icon.setObjectName("svcIcon")
        self.icon.setFixedSize(42, 42)
        self.icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.icon, 0, Qt.AlignmentFlag.AlignVCenter)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        name_row = QHBoxLayout()
        name_row.setSpacing(8)
        self.name = QLabel(_watch_display_name(entry))
        self.name.setObjectName("svcName")
        self.live = QLabel("")
        self.live.setObjectName("svcStatusWarn")
        name_row.addWidget(self.name)
        name_row.addWidget(self.live, 0, Qt.AlignmentFlag.AlignVCenter)
        name_row.addStretch()
        text_col.addLayout(name_row)
        self.status = QLabel("")
        self.status.setObjectName("svcStatusOff")
        text_col.addWidget(self.status)
        # One mono line per loaded model (llama-server GET /v1/models, host
        # protocol v4); hidden until the metrics carry a model list.
        self._model_holder = QVBoxLayout()
        self._model_holder.setSpacing(1)
        self._model_labels: list[QLabel] = []
        text_col.addLayout(self._model_holder)
        layout.addLayout(text_col, 1)

        # Right-aligned metric columns (value over caption), like the
        # prototype's .svc-metrics.
        self._metric_labels: dict[str, tuple[QLabel, QLabel]] = {}
        metrics_row = QHBoxLayout()
        metrics_row.setSpacing(22)
        for key in ("uptime", "ram", "cpu"):
            col = QVBoxLayout()
            col.setSpacing(0)
            value = QLabel("")
            value.setObjectName("svcMetricValue")
            value.setAlignment(Qt.AlignmentFlag.AlignRight)
            caption = QLabel(Translations.tr(f"modern.dashboard.svc.{key}"))
            caption.setObjectName("svcMetricCaption")
            caption.setAlignment(Qt.AlignmentFlag.AlignRight)
            col.addWidget(value)
            col.addWidget(caption)
            self._metric_labels[key] = (value, caption)
            metrics_row.addLayout(col)
        # Nested layouts cannot carry an alignment; the columns are wrapped
        # in a widget so they sit vertically centered next to the text.
        metrics_wrap = QWidget()
        metrics_wrap.setLayout(metrics_row)
        layout.addWidget(metrics_wrap, 0, Qt.AlignmentFlag.AlignVCenter)

    def update_info(self, info: dict | None, inferring: bool = False) -> None:
        if info is None:
            self.setVisible(False)
            return
        self.setVisible(True)
        running = bool(info.get("running"))
        wants_port = info.get("api_port") is not None
        port_open = bool(info.get("api_port_open"))
        ready = running and (port_open or not wants_port)
        if ready:
            if wants_port:
                status_obj = "svcStatusRunning"
                status_txt = Translations.tr(
                    "modern.dashboard.svc.status_ready",
                    pid=info.get("pid", "?"), port=info.get("api_port", ""))
            else:
                status_obj = "svcStatusRunning"
                status_txt = Translations.tr(
                    "modern.dashboard.svc.status_running",
                    pid=info.get("pid", "?"))
        elif running:
            status_obj, status_txt = "svcStatusWarn", Translations.tr(
                "modern.dashboard.svc.status_no_port", pid=info.get("pid", "?"),
                port=info.get("api_port", ""))
        else:
            status_obj, status_txt = "svcStatusOff", Translations.tr(
                "modern.dashboard.svc.stopped")
        if self.status.objectName() != status_obj:
            self.status.setObjectName(status_obj)
            self.status.style().unpolish(self.status)
            self.status.style().polish(self.status)
        self.status.setText(status_txt)

        # Loaded models: one line per model (llama-server API list when the
        # host reports it, else the single argv-derived name).
        names = _model_names(info) if running else []
        while len(self._model_labels) < len(names):
            lbl = QLabel("")
            lbl.setObjectName("rowMono")
            self._model_holder.addWidget(lbl)
            self._model_labels.append(lbl)
        while len(self._model_labels) > len(names):
            lbl = self._model_labels.pop()
            lbl.setParent(None)
            lbl.deleteLater()
        for lbl, model_name in zip(self._model_labels, names):
            lbl.setText(f"🧠 {model_name}")
            lbl.setToolTip(model_name)
            lbl.setVisible(True)

        for key in ("uptime", "ram", "cpu"):
            value_lbl, caption_lbl = self._metric_labels[key]
            if not running:
                value_lbl.setText("–")
            elif key == "uptime":
                value_lbl.setText(_fmt_uptime(info.get("uptime")) or "–")
            elif key == "ram":
                value_lbl.setText(
                    f"{_fmt_bytes_gb(info.get('ram'))} GB")
            else:
                value_lbl.setText(f"{float(info.get('cpu') or 0.0):.1f} %")
            caption_lbl.setText(Translations.tr(f"modern.dashboard.svc.{key}"))

        # "Inferenz aktiv" badge next to the service name (heuristic, see
        # INFERENCE_GPU_PCT - only meaningful while the service is ready).
        if inferring and ready:
            self.live.setText(Translations.tr("modern.dashboard.svc.inferring"))
            self.live.setVisible(True)
        else:
            self.live.setText("")
            self.live.setVisible(False)


class DeviceDashboardView(QWidget):
    """Per-device dashboard: live metrics + remote batch execution."""

    back_requested = pyqtSignal()

    def __init__(self, config_manager: ConfigManager, parent=None) -> None:
        super().__init__(parent)
        self.config: Any = config_manager
        self._device_id: str | None = None
        self._device: dict | None = None
        self._metrics_ok = False
        self._metrics_busy = False
        self._metrics_thread: QThread | None = None
        self._metrics_worker: MetricsWorker | None = None
        self._batch_thread: QThread | None = None
        self._batch_worker: BatchWorker | None = None
        self._batch_active: int = -1
        self._batch_dirty = False
        # Popup about missing/incorrect credentials: once per opened device
        # (the host service rejects every request without them, so polling
        # would repeat the same error every interval).
        self._cred_warned = False
        # Watched processes (dashboard service chips). _watch_entries is the
        # per-device config; _gpu_high_counts consecutive GPU samples feeding
        # the "inference active" heuristic (see INFERENCE_GPU_PCT).
        self._watch_entries: list[str] = []
        self._gpu_high_count = 0
        self._chip_widgets: dict[str, ServiceChip] = {}
        self._svc_row_widgets: dict[str, ServiceRow] = {}
        # Last metrics "processes" map (re-painted on retranslate()).
        self._last_processes: dict | None = None
        # Host service protocol version from the last metrics response
        # (shown behind the MAC in the header); None until metrics arrive.
        self._host_protocol: int | None = None

        self._setup_ui()

        self._timer = QTimer(self)
        self._timer.setInterval(self.config.get_dashboard_interval_ms())
        self._timer.timeout.connect(self._poll_metrics)

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

        # ── Header: back · title/badge · mono … interval · refresh ──
        header = QHBoxLayout()
        header.setSpacing(14)
        self.back_btn = QPushButton(Translations.tr("modern.dashboard.back"))
        self.back_btn.setObjectName("backButton")
        self.back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.back_btn.clicked.connect(self.back_requested.emit)
        header.addWidget(self.back_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        name_row = QHBoxLayout()
        name_row.setSpacing(10)
        self.title = QLabel("—")
        self.title.setObjectName("pageTitle")
        self.badge = QLabel("")
        self.badge.setObjectName("badgeUnknown")
        self.badge.setFixedHeight(20)
        self.badge.setAlignment(
            Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
        name_row.addWidget(self.title)
        name_row.addWidget(self.badge, 0, Qt.AlignmentFlag.AlignVCenter)
        # Watched-process chips (e.g. llama-server) - hidden until the host
        # service reports a "processes" map (protocol v3 + watch config).
        self._chip_widgets: dict[str, ServiceChip] = {}
        self._chip_holder = QHBoxLayout()
        self._chip_holder.setSpacing(8)
        name_row.addLayout(self._chip_holder)
        name_row.addStretch()
        self.mono = QLabel("")
        self.mono.setObjectName("rowMono")
        title_col.addLayout(name_row)
        title_col.addWidget(self.mono)
        header.addLayout(title_col, 1)

        lbl_interval = QLabel(Translations.tr("modern.dashboard.interval"))
        lbl_interval.setObjectName("pageSubtitle")
        header.addWidget(lbl_interval, 0, Qt.AlignmentFlag.AlignVCenter)
        self.interval_combo = QComboBox()
        self.interval_combo.setFixedWidth(90)
        current_ms = self.config.get_dashboard_interval_ms()
        for seconds in INTERVAL_CHOICES:
            self.interval_combo.addItem(f"{seconds} s", seconds * 1000)
        idx = self.interval_combo.findData(current_ms)
        if idx >= 0:
            self.interval_combo.setCurrentIndex(idx)
        self.interval_combo.currentIndexChanged.connect(self._on_interval_changed)
        header.addWidget(self.interval_combo, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(header)
        layout.addSpacing(4)

        # ── Services panel (watched processes, hidden when none) ─────
        self.svc_panel = QFrame()
        self.svc_panel.setObjectName("panel")
        self.svc_panel.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        svc_layout = QVBoxLayout(self.svc_panel)
        svc_layout.setContentsMargins(0, 0, 0, 0)
        svc_layout.setSpacing(0)

        svc_head = QHBoxLayout()
        svc_head.setContentsMargins(14, 10, 10, 10)
        self.svc_title = QLabel(Translations.tr("modern.dashboard.svc.title"))
        self.svc_title.setObjectName("sectionHeading")
        svc_head.addWidget(self.svc_title)
        svc_head.addStretch()
        self.svc_subtitle = QLabel("")
        self.svc_subtitle.setObjectName("pageSubtitle")
        svc_head.addWidget(self.svc_subtitle)
        svc_layout.addLayout(svc_head)

        self._svc_row_holder = QVBoxLayout()
        self._svc_row_holder.setSpacing(0)
        svc_layout.addLayout(self._svc_row_holder)
        self.svc_panel.setVisible(False)
        layout.addWidget(self.svc_panel)

        # ── Metric cards ─────────────────────────────────────────────
        cards_row = QHBoxLayout()
        cards_row.setSpacing(16)
        self.cards: dict[str, MetricCard] = {}
        for key in ("cpu", "ram", "gpu", "vram"):
            card = MetricCard(key, Translations.tr(f"modern.dashboard.metric.{key}"))
            self.cards[key] = card
            cards_row.addWidget(card, 1)
        layout.addLayout(cards_row)
        layout.addSpacing(6)

        # ── Batch section ────────────────────────────────────────────
        batch_row = QHBoxLayout()
        batch_row.setSpacing(16)

        # Left: batch library panel
        lib_panel = QFrame()
        lib_panel.setObjectName("panel")
        lib_panel.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        lib_panel.setFixedWidth(250)
        lib_layout = QVBoxLayout(lib_panel)
        lib_layout.setContentsMargins(0, 0, 0, 0)
        lib_layout.setSpacing(0)

        lib_head = QHBoxLayout()
        lib_head.setContentsMargins(14, 10, 10, 10)
        lib_head.setSpacing(8)
        self.lib_title = QLabel(Translations.tr("modern.dashboard.batch.title"))
        self.lib_title.setObjectName("sectionHeading")
        lib_head.addWidget(self.lib_title)
        lib_head.addStretch()
        self.new_btn = QPushButton(Translations.tr("modern.dashboard.batch.new"))
        self.new_btn.setObjectName("smallButton")
        self.new_btn.clicked.connect(self._new_batch)
        lib_head.addWidget(self.new_btn)
        lib_layout.addLayout(lib_head)

        self.batch_list = QListWidget()
        self.batch_list.setObjectName("batchList")
        self.batch_list.currentRowChanged.connect(self._on_batch_selected)
        lib_layout.addWidget(self.batch_list, 1)

        lib_foot = QHBoxLayout()
        lib_foot.setContentsMargins(10, 6, 10, 10)
        lib_foot.setSpacing(6)
        self.dup_btn = QPushButton(Translations.tr("modern.dashboard.batch.duplicate"))
        self.dup_btn.setObjectName("smallButton")
        self.dup_btn.clicked.connect(self._duplicate_batch)
        self.delete_btn = QPushButton(Translations.tr("modern.dashboard.batch.delete"))
        self.delete_btn.setObjectName("smallDanger")
        self.delete_btn.clicked.connect(self._delete_batch)
        lib_foot.addWidget(self.dup_btn)
        lib_foot.addWidget(self.delete_btn)
        lib_layout.addLayout(lib_foot)
        batch_row.addWidget(lib_panel)

        # Right: editor + console
        right = QVBoxLayout()
        right.setSpacing(12)

        edit_panel = QFrame()
        edit_panel.setObjectName("panel")
        edit_panel.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        edit_layout = QVBoxLayout(edit_panel)
        edit_layout.setContentsMargins(0, 0, 0, 0)
        edit_layout.setSpacing(0)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText(
            Translations.tr("modern.dashboard.batch.untitled"))
        self.name_edit.setContentsMargins(14, 10, 14, 4)
        self.name_edit.textChanged.connect(self._mark_dirty)
        edit_layout.addWidget(self.name_edit)

        self.script_edit = QPlainTextEdit()
        self.script_edit.setObjectName("codeEdit")
        self.script_edit.setPlaceholderText("@echo off\r\n")
        self.script_edit.setMinimumHeight(130)
        f = QFont("Consolas")
        f.setStyleHint(QFont.StyleHint.Monospace)
        self.script_edit.setFont(f)
        self.script_edit.textChanged.connect(self._mark_dirty)
        edit_layout.addWidget(self.script_edit)

        tool = QHBoxLayout()
        tool.setContentsMargins(14, 8, 14, 12)
        tool.setSpacing(10)
        lbl_timeout = QLabel(Translations.tr("modern.dashboard.timeout"))
        lbl_timeout.setObjectName("pageSubtitle")
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(BATCH_TIMEOUT_MIN_S, BATCH_TIMEOUT_MAX_S)
        self.timeout_spin.setValue(DEFAULT_BATCH_TIMEOUT_S)
        self.timeout_spin.setSuffix(" s")
        self.timeout_spin.valueChanged.connect(self._mark_dirty)
        tool.addWidget(lbl_timeout, 0, Qt.AlignmentFlag.AlignVCenter)
        tool.addWidget(self.timeout_spin, 0, Qt.AlignmentFlag.AlignVCenter)
        tool.addStretch()
        self.allow_batch_check = QCheckBox(
            Translations.tr("modern.dashboard.allow_batch"))
        self.allow_batch_check.setToolTip(
            Translations.tr("modern.dashboard.allow_batch_tip"))
        self.allow_batch_check.toggled.connect(self._on_allow_batch_toggled)
        tool.addWidget(self.allow_batch_check, 0, Qt.AlignmentFlag.AlignVCenter)
        self.save_btn = QPushButton(Translations.tr("modern.dashboard.batch.save"))
        self.save_btn.setDisabled(True)
        self.save_btn.clicked.connect(self._save_batches)
        tool.addWidget(self.save_btn)
        self.run_btn = QPushButton(Translations.tr("modern.dashboard.batch.run"))
        self.run_btn.setObjectName("primaryButton")
        self.run_btn.clicked.connect(self._run_batch)
        tool.addWidget(self.run_btn)
        edit_layout.addLayout(tool)
        right.addWidget(edit_panel)

        console_panel = QFrame()
        console_panel.setObjectName("panel")
        console_panel.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        console_layout = QVBoxLayout(console_panel)
        console_layout.setContentsMargins(0, 0, 0, 0)
        console_layout.setSpacing(0)

        console_head = QHBoxLayout()
        console_head.setContentsMargins(14, 10, 10, 10)
        self.console_title = QLabel(Translations.tr("modern.dashboard.console"))
        self.console_title.setObjectName("sectionHeading")
        console_head.addWidget(self.console_title)
        console_head.addStretch()
        self.clear_btn = QPushButton(Translations.tr("modern.dashboard.batch.clear"))
        self.clear_btn.setObjectName("smallButton")
        self.clear_btn.clicked.connect(lambda: self.console_edit.clear())
        console_head.addWidget(self.clear_btn)
        console_layout.addLayout(console_head)

        self.console_edit = QPlainTextEdit()
        self.console_edit.setObjectName("consoleEdit")
        self.console_edit.setReadOnly(True)
        # Bound the buffer: an unbounded QPlainTextEdit slows down repaints
        # (notably after window activation) once batches ran often.
        self.console_edit.setMaximumBlockCount(5000)
        self.console_edit.setMinimumHeight(140)
        self.console_edit.setFont(f)
        console_layout.addWidget(self.console_edit)

        self.status_line = QLabel("")
        self.status_line.setObjectName("statusLine")
        self.status_line.setContentsMargins(14, 6, 14, 8)
        console_layout.addWidget(self.status_line)
        right.addWidget(console_panel)

        batch_row.addLayout(right, 1)
        layout.addLayout(batch_row)
        layout.addStretch()

    # ── Public API ───────────────────────────────────────────────────────

    def set_device(self, device_id: str) -> None:
        """Open the dashboard for *device_id* (reset state, start polling)."""
        # Drop any in-flight work for the previous device: its results would
        # otherwise paint the old host's metrics into the new dashboard (and
        # a finished old thread could clear the *new* thread's references).
        self._stop_metrics_worker()
        self._stop_batch_worker()
        device = self.config.get_device_by_id(device_id)
        self._device_id = device_id
        self._device = device
        self._metrics_ok = False
        self._cred_warned = False
        self._watch_entries = (
            ConfigManager.get_device_watch_processes(device)
            if device is not None else [])
        self._gpu_high_count = 0
        self._host_protocol = None
        self._rebuild_service_widgets()
        for card in self.cards.values():
            card.reset_display()
        self.console_edit.clear()
        self.status_line.setText("")
        self.refresh_device_header()
        self._load_batches()
        self._update_run_enabled()
        if self._device is not None:
            self._poll_metrics()
        self._timer.start()

    def refresh_device_header(self) -> None:
        """Refresh name/IP after an edit while the dashboard is open."""
        if self._device_id is None:
            return
        device = self.config.get_device_by_id(self._device_id)
        self._device = device
        if device is None:
            self.title.setText("—")
            self.mono.setText("")
            return
        self.title.setText(device.get("name", ""))
        self._update_mono_line()
        # Watch list may have changed in the device dialog while open.
        watch = ConfigManager.get_device_watch_processes(device)
        if watch != self._watch_entries:
            self._watch_entries = watch
            self._rebuild_service_widgets()

    def _update_mono_line(self) -> None:
        """Header line: ``IP · MAC · Host Service vN`` (version once known)."""
        if self._device is None:
            self.mono.setText("")
            return
        ip = self._device.get("ip", "")
        mac = self._device.get("mac", "")
        parts = [p for p in (ip, mac) if p]
        if self._host_protocol is not None:
            parts.append(Translations.tr(
                "modern.dashboard.svc.version", version=self._host_protocol))
        self.mono.setText(" · ".join(parts))

    def retranslate(self) -> None:
        self.back_btn.setText(Translations.tr("modern.dashboard.back"))
        self.lib_title.setText(Translations.tr("modern.dashboard.batch.title"))
        self.new_btn.setText(Translations.tr("modern.dashboard.batch.new"))
        self.dup_btn.setText(Translations.tr("modern.dashboard.batch.duplicate"))
        self.delete_btn.setText(Translations.tr("modern.dashboard.batch.delete"))
        self.save_btn.setText(Translations.tr("modern.dashboard.batch.save"))
        self.run_btn.setText(Translations.tr("modern.dashboard.batch.run"))
        self.clear_btn.setText(Translations.tr("modern.dashboard.batch.clear"))
        self.console_title.setText(Translations.tr("modern.dashboard.console"))
        self.allow_batch_check.setText(
            Translations.tr("modern.dashboard.allow_batch"))
        self.allow_batch_check.setToolTip(
            Translations.tr("modern.dashboard.allow_batch_tip"))
        self.name_edit.setPlaceholderText(
            Translations.tr("modern.dashboard.batch.untitled"))
        for key, card in self.cards.items():
            card.set_title(Translations.tr(f"modern.dashboard.metric.{key}"))
        # Watched-process widgets: rebuild (static labels) + repaint state
        if self._watch_entries:
            self._rebuild_service_widgets()
            if self._metrics_ok:
                self._update_services(self._last_processes)
        # Re-apply metric-dependent texts (detail lines, status line)
        if self._device is not None:
            self._update_mono_line()
            self._load_batches()

    def cancel_workers(self) -> None:
        self._timer.stop()
        self._stop_metrics_worker()
        self._stop_batch_worker()

    # ── Lifecycle: pause polling while hidden ────────────────────────────

    def hideEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        self._timer.stop()
        super().hideEvent(event)

    def showEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        super().showEvent(event)
        if self._device_id is not None:
            self._timer.start()

    # ── Metrics polling ──────────────────────────────────────────────────

    def _on_interval_changed(self, index: int) -> None:
        ms = self.interval_combo.itemData(index)
        if ms:
            self.config.set_dashboard_interval_ms(int(ms))
            self._timer.setInterval(int(ms))

    def _poll_metrics(self) -> None:
        if self._device is None or self._metrics_busy:
            return  # single-flight: skip while a request is still running
        if HEADLESS_MODE:
            # No network I/O in headless/test runs (mirrors DevicesView).
            return
        ip = self._device.get("ip", "")
        if not ip:
            self._show_offline(Translations.tr("dialog.no_ip.message",
                                               name=self._device.get("name", "")))
            return
        if not (self._device.get("username", "")
                and self._device.get("password", "")):
            # Without credentials every host-service request is rejected —
            # skip the network round-trip and tell the user once.
            self._show_offline(
                "", text=Translations.tr("modern.dashboard.creds.message"))
            self._warn_credentials()
            return
        self._metrics_busy = True
        worker = MetricsWorker(
            ip, self._device.get("username", ""), self._device.get("password", ""),
            watch=self._watch_entries or None)
        thread = QThread()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.metrics_ready.connect(self._on_metrics)
        worker.failed.connect(self._on_metrics_failed)
        worker.metrics_ready.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        # Capture the thread: a stale worker finishing late must not clear
        # the references of a newer poll (device switch / restart).
        thread.finished.connect(
            lambda t=thread: self._metrics_thread_done(t))
        self._metrics_worker = worker
        self._metrics_thread = thread
        thread.start()

    def _metrics_thread_done(self, thread: QThread | None = None) -> None:
        if thread is not None and self._metrics_thread is not thread:
            return  # stale worker — the current poll keeps its state
        self._metrics_busy = False
        self._metrics_thread = None
        self._metrics_worker = None

    def _stop_metrics_worker(self) -> None:
        # cancel() closes the in-flight socket so a blocked recv() aborts and
        # run() returns; then the thread's event loop can quit and be joined.
        if self._metrics_worker is not None:
            self._metrics_worker.cancel()
        if self._metrics_thread is not None:
            self._metrics_thread.quit()
            self._metrics_thread.wait(2000)
        self._metrics_busy = False

    def _on_metrics(self, data: dict) -> None:
        if not self._metrics_ok:
            self._metrics_ok = True
            self._set_badge("online")
        na = Translations.tr("modern.dashboard.metric.na")

        # Host service protocol version behind the MAC in the header.
        protocol = data.get("protocol")
        new_proto = protocol if isinstance(protocol, int) else None
        if new_proto != self._host_protocol:
            self._host_protocol = new_proto
            self._update_mono_line()

        cpu = data.get("cpu")
        cpu_count = data.get("cpu_count")
        cpu_detail = (
            Translations.tr("modern.dashboard.metric.cpu_detail", count=cpu_count)
            if cpu_count else "")
        uptime = _fmt_uptime(data.get("uptime"))
        if uptime:
            cpu_detail = f"{cpu_detail}\n{Translations.tr('modern.dashboard.uptime', value=uptime)}" if cpu_detail else Translations.tr("modern.dashboard.uptime", value=uptime)
        self.cards["cpu"].set_value(cpu, cpu_detail)

        ram_used, ram_total = data.get("ram_used"), data.get("ram_total")
        ram_detail = ""
        if ram_used is not None and ram_total:
            ram_detail = Translations.tr(
                "modern.dashboard.metric.mem_detail",
                used=_fmt_bytes_gb(ram_used), total=_fmt_bytes_gb(ram_total))
        ram_pct = data.get("ram_percent")
        if ram_pct is None and ram_used is not None and ram_total:
            ram_pct = ram_used / ram_total * 100.0
        self.cards["ram"].set_value(ram_pct, ram_detail)

        self.cards["gpu"].set_value(data.get("gpu"), str(data.get("gpu_name") or na))

        vram_used, vram_total = data.get("vram_used"), data.get("vram_total")
        vram_detail = na
        vram_pct = None
        if vram_used is not None and vram_total:
            vram_detail = Translations.tr(
                "modern.dashboard.metric.mem_detail",
                used=_fmt_bytes_gb(vram_used), total=_fmt_bytes_gb(vram_total))
            vram_pct = vram_used / vram_total * 100.0
        self.cards["vram"].set_value(vram_pct, vram_detail)

        # Watched processes (chips + services panel). The GPU-load counter
        # feeds the "inference active" heuristic and counts consecutive
        # high samples; a missing/None GPU sample resets it.
        gpu_pct = data.get("gpu")
        if gpu_pct is not None and gpu_pct >= INFERENCE_GPU_PCT:
            self._gpu_high_count += 1
        else:
            self._gpu_high_count = 0
        self._update_services(data.get("processes"))
        # The host just became reachable — "run_btn" may have been disabled
        # because metrics had not arrived yet when the opt-in was toggled.
        self._update_run_enabled()

    def _on_metrics_failed(self, message: str) -> None:
        if "authentication" in message.lower():
            # Stored credentials were rejected by the host service — the
            # generic "host unreachable" text would be misleading here.
            self._show_offline(
                message, text=Translations.tr("modern.dashboard.creds.message"))
            self._warn_credentials()
            return
        self._show_offline(message)

    def _show_offline(self, message: str,
                      text: "str | None" = None) -> None:
        self._metrics_ok = False
        self._gpu_high_count = 0
        # The version is only known while the host service answers.
        if self._host_protocol is not None:
            self._host_protocol = None
            self._update_mono_line()
        self._hide_services()
        self._set_badge("offline")
        for card in self.cards.values():
            card.gauge.set_value(None)
        self.status_line.setText(
            text or Translations.tr("modern.dashboard.offline", message=message))
        self._update_run_enabled()

    def _warn_credentials(self) -> None:
        """Popup about missing/incorrect credentials (once per device open)."""
        if self._cred_warned:
            return
        self._cred_warned = True
        QMessageBox.warning(
            self,
            Translations.tr("modern.dashboard.creds.title"),
            Translations.tr("modern.dashboard.creds.message"),
        )

    def _set_badge(self, status: str) -> None:
        name = {"online": "badgeOnline", "offline": "badgeOffline"}.get(
            status, "badgeUnknown")
        if self.badge.objectName() != name:
            self.badge.setObjectName(name)
            style = self.badge.style()
            style.unpolish(self.badge)
            style.polish(self.badge)
        self.badge.setText(Translations.tr(f"status.{status}"))

    # ── Watched processes (service chips + services panel) ───────────────

    def _rebuild_service_widgets(self) -> None:
        """(Re)create chips + panel rows for the current watch entries."""
        for chip in self._chip_widgets.values():
            chip.setParent(None)
            chip.deleteLater()
        self._chip_widgets.clear()
        for row in self._svc_row_widgets.values():
            row.setParent(None)
            row.deleteLater()
        self._svc_row_widgets.clear()
        for entry in self._watch_entries:
            chip = ServiceChip(entry)
            self._chip_holder.addWidget(chip)
            self._chip_widgets[entry] = chip
            row = ServiceRow(entry)
            row.setObjectName("svcRow")
            if self._svc_row_holder.count():
                sep = QFrame()
                sep.setObjectName("rowSeparator")
                sep.setFrameShape(QFrame.Shape.HLine)
                self._svc_row_holder.addWidget(sep)
            self._svc_row_holder.addWidget(row)
            self._svc_row_widgets[entry] = row
        has_watch = bool(self._watch_entries)
        self.svc_panel.setVisible(False)  # hidden until processes data arrives
        self.svc_title.setText(Translations.tr("modern.dashboard.svc.title"))
        self.svc_subtitle.setText("")

    def _update_services(self, processes: dict | None) -> None:
        """Paint chips + panel from the metrics ``processes`` map.

        *processes* is None while the host is unreachable or its service is
        too old (no watch support) - then everything service-related hides.
        """
        if not self._watch_entries:
            return
        supported = isinstance(processes, dict)
        self._last_processes = processes if supported else None
        self.svc_panel.setVisible(supported)
        inferring = self._gpu_high_count >= INFERENCE_GPU_POLLS
        for entry, chip in self._chip_widgets.items():
            info = processes.get(entry) if supported else None
            chip.set_state(info)
        for entry, row in self._svc_row_widgets.items():
            info = processes.get(entry) if supported else None
            row.update_info(info, inferring=inferring)
        if supported:
            self.svc_subtitle.setText(
                Translations.tr("modern.dashboard.svc.subtitle"))

    def _hide_services(self) -> None:
        """Host offline / no watch config: hide chips and panel."""
        for chip in self._chip_widgets.values():
            chip.set_state(None)
        self.svc_panel.setVisible(False)

    # ── Batch library ────────────────────────────────────────────────────

    def _batches(self) -> list[dict]:
        if self._device is None:
            return []
        return self.config.get_device_batches(self._device)

    def _load_batches(self) -> None:
        self.batch_list.blockSignals(True)
        self.batch_list.clear()
        for batch in self._batches():
            item = QListWidgetItem(batch.get("name") or
                                   Translations.tr("modern.dashboard.batch.untitled"))
            self.batch_list.addItem(item)
        self.batch_list.blockSignals(False)
        if self._batch_active >= len(self._batches()):
            self._batch_active = -1
        if self._batches() and self._batch_active < 0:
            self.batch_list.setCurrentRow(0)
        elif self._batch_active >= 0:
            self.batch_list.setCurrentRow(self._batch_active)
        else:
            self._show_batch(None)

    def _on_batch_selected(self, row: int) -> None:
        # Store pending edits of the previous batch before switching
        self._commit_editor()
        self._batch_active = row
        batches = self._batches()
        self._show_batch(batches[row] if 0 <= row < len(batches) else None)

    def _show_batch(self, batch: dict | None) -> None:
        self._batch_dirty = False
        self.save_btn.setDisabled(True)
        if batch is None:
            self.name_edit.blockSignals(True)
            self.script_edit.blockSignals(True)
            self.timeout_spin.blockSignals(True)
            self.name_edit.setText("")
            self.script_edit.setPlainText("")
            self.timeout_spin.setValue(DEFAULT_BATCH_TIMEOUT_S)
            self.name_edit.blockSignals(False)
            self.script_edit.blockSignals(False)
            self.timeout_spin.blockSignals(False)
            return
        self.name_edit.blockSignals(True)
        self.script_edit.blockSignals(True)
        self.timeout_spin.blockSignals(True)
        self.name_edit.setText(batch.get("name", ""))
        self.script_edit.setPlainText(batch.get("script", ""))
        self.timeout_spin.setValue(int(batch.get("timeout", DEFAULT_BATCH_TIMEOUT_S)))
        self.name_edit.blockSignals(False)
        self.script_edit.blockSignals(False)
        self.timeout_spin.blockSignals(False)

    def _commit_editor(self) -> None:
        """Write the editor content back into the active batch (in memory)."""
        if not self._batch_dirty or self._batch_active < 0 or self._device is None:
            return
        batches = self._batches()
        if self._batch_active >= len(batches):
            return
        batches[self._batch_active].update({
            "name": self.name_edit.text().strip(),
            "script": self.script_edit.toPlainText(),
            "timeout": self.timeout_spin.value(),
        })
        try:
            self.config.set_device_batches(self._device_id, batches)
        except (ValueError, RuntimeError):
            pass  # keep the editor state; user can retry with Save
        self._batch_dirty = False
        self.save_btn.setDisabled(True)
        item = self.batch_list.item(self._batch_active)
        if item is not None:
            item.setText(batches[self._batch_active]["name"] or
                         Translations.tr("modern.dashboard.batch.untitled"))

    def _mark_dirty(self) -> None:
        self._batch_dirty = True
        self.save_btn.setEnabled(True)

    def _new_batch(self) -> None:
        self._commit_editor()
        batches = self._batches()
        batches.append({
            "id": f"b{len(batches) + 1}-{datetime.now().strftime('%H%M%S')}",
            "name": Translations.tr("modern.dashboard.batch.untitled"),
            "script": "@echo off\r\n",
            "timeout": DEFAULT_BATCH_TIMEOUT_S,
        })
        self.config.set_device_batches(self._device_id, batches)
        self._batch_active = len(batches) - 1
        self._load_batches()
        self.batch_list.setCurrentRow(self._batch_active)

    def _duplicate_batch(self) -> None:
        self._commit_editor()
        batches = self._batches()
        if not (0 <= self._batch_active < len(batches)):
            return
        clone = dict(batches[self._batch_active])
        clone["id"] = f"b{len(batches) + 1}-{datetime.now().strftime('%H%M%S')}"
        clone["name"] = f"{clone['name']} (2)"[:64]
        batches.insert(self._batch_active + 1, clone)
        self.config.set_device_batches(self._device_id, batches)
        self._batch_active += 1
        self._load_batches()
        self.batch_list.setCurrentRow(self._batch_active)

    def _delete_batch(self) -> None:
        batches = self._batches()
        if not (0 <= self._batch_active < len(batches)):
            return
        name = batches[self._batch_active].get("name", "")
        answer = QMessageBox.question(
            self,
            Translations.tr("modern.dashboard.batch.delete"),
            Translations.tr("modern.dashboard.batch.confirm_delete", name=name),
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        batches.pop(self._batch_active)
        self.config.set_device_batches(self._device_id, batches)
        self._batch_active = min(self._batch_active, len(batches) - 1)
        self._load_batches()

    def _save_batches(self) -> None:
        self._commit_editor()

    def _on_allow_batch_toggled(self, allowed: bool) -> None:
        if self._device_id is None:
            return
        self.config.set_device_allow_batch(self._device_id, allowed)
        self._update_run_enabled()

    # ── Batch execution ──────────────────────────────────────────────────

    def _update_run_enabled(self) -> None:
        device = self._device or {}
        enabled = bool(
            self._metrics_ok
            and device.get("allow_batch", False)
            and device.get("username")
            and not (self._batch_thread is not None)
        )
        self.run_btn.setEnabled(enabled)
        self.allow_batch_check.blockSignals(True)
        self.allow_batch_check.setChecked(bool(device.get("allow_batch", False)))
        self.allow_batch_check.blockSignals(False)

    def _log(self, text: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        self.console_edit.appendPlainText(f"[{stamp}] {text}")

    def _run_batch(self) -> None:
        device = self._device
        if device is None or self._batch_thread is not None:
            return
        # Run the editor content (even unsaved), after committing to the library
        self._commit_editor()
        script = self.script_edit.toPlainText()
        if not script.strip():
            return
        name = self.name_edit.text().strip() or \
            Translations.tr("modern.dashboard.batch.untitled")
        self._log(Translations.tr("modern.dashboard.batch.started", name=name))
        self.status_line.setText(Translations.tr("modern.dashboard.batch.running"))
        self.run_btn.setEnabled(False)

        worker = BatchWorker(
            device.get("ip", ""), script,
            device.get("username", ""), device.get("password", ""),
            timeout=float(self.timeout_spin.value()))
        thread = QThread()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.batch_finished.connect(self._on_batch_finished)
        worker.failed.connect(self._on_batch_failed)
        worker.batch_finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(
            lambda t=thread: self._batch_thread_done(t))
        self._batch_worker = worker
        self._batch_thread = thread
        thread.start()

    def _batch_thread_done(self, thread: QThread | None = None) -> None:
        if thread is not None and self._batch_thread is not thread:
            return  # stale worker — the current batch keeps its state
        self._batch_thread = None
        self._batch_worker = None
        self._update_run_enabled()

    def _stop_batch_worker(self) -> None:
        # cancel() closes the in-flight socket so the batch request aborts and
        # the thread can be joined (see _stop_metrics_worker).
        if self._batch_worker is not None:
            self._batch_worker.cancel()
        if self._batch_thread is not None:
            self._batch_thread.quit()
            self._batch_thread.wait(2000)

    def _on_batch_finished(self, result: dict) -> None:
        stdout = str(result.get("stdout", ""))
        stderr = str(result.get("stderr", ""))
        if stdout.strip():
            self.console_edit.appendPlainText(stdout.rstrip())
        if stderr.strip():
            self.console_edit.appendPlainText(stderr.rstrip())
        if result.get("truncated"):
            self._log(Translations.tr("modern.dashboard.batch.truncated"))
        exit_code = result.get("exit_code")
        duration = result.get("duration_ms", 0)
        self._log(Translations.tr("modern.dashboard.batch.exit", code=exit_code))
        self.status_line.setText(Translations.tr(
            "modern.dashboard.batch.duration",
            seconds=f"{duration / 1000:.1f}"))

    def _on_batch_failed(self, message: str) -> None:
        self._log(f"✗ {message}")
        self.status_line.setText("")
