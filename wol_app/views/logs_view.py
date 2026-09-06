"""Modern UI: "Protokolle" screen (application event log).

Layout mirrors the prototype's logs screen
(design_prototype/dark_control_center_full.html):

1. Page header (title + subtitle).
2. Toolbar: search field, level filter combo and a CSV export button.
3. A panel of log rows: level badge (INFO / WARN / FEHLER), mono
   timestamp, dim device name and the message text.

All entries come from the shared ``ConfigManager`` log API
(``get_logs``); rows are shown newest-first. The status values written
by the engines (SUCCESS / ERROR / FAILED / WARN / …) are mapped onto the
three prototype levels.
"""

import csv
from datetime import datetime
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from wol_app.translations import Translations

# Fixed height of one log row (px) — single-line rows, a bit lower than
# the two-line device rows of the other screens.
ROW_HEIGHT = 48

# Status values (written by wol_engine / main_window / schedule_runner)
# that map onto the red FEHLER badge; everything unknown stays WARN.
_ERROR_STATUSES = {"ERROR", "FAILED", "OFFLINE"}
_INFO_STATUSES = {"SUCCESS", "ONLINE", "TRIGGERED", "WAKE", "SHUTDOWN"}

# Representative output of format_timestamp() used to size the time column.
# The width is MEASURED, not hardcoded: #logTime requests Consolas, which only
# exists on Windows — Linux falls back to a wider mono font (DejaVu Sans Mono),
# so a pixel constant tuned on one OS clips the timestamp on the other.
_TIME_SAMPLE = "08.09. 17:25"
_TIME_PAD = 4


def log_level(status: str) -> str:
    """Map a log status onto a prototype level: info | warn | error."""
    status = (status or "").upper()
    if status in _ERROR_STATUSES:
        return "error"
    if status in _INFO_STATUSES:
        return "info"
    return "warn"


def format_timestamp(raw: str) -> str:
    """Format an ISO timestamp like the prototype ("26.08. 20:00")."""
    try:
        return datetime.fromisoformat(raw).strftime("%d.%m. %H:%M")
    except (ValueError, TypeError):
        return raw or ""


def measure_time_width(text: str = _TIME_SAMPLE) -> int:
    """Pixel width the ``#logTime`` column needs for ``text``.

    Polishes a throw-away label so the measurement uses the real stylesheet
    font (size and family), then returns the advance width plus a little
    padding. Called once per list rebuild and passed to every :class:`LogRow`.
    """
    probe = QLabel()
    probe.setObjectName("logTime")
    probe.ensurePolished()
    fm = probe.fontMetrics()
    width = max(fm.horizontalAdvance(text), fm.horizontalAdvance(_TIME_SAMPLE))
    probe.setParent(None)
    return width + _TIME_PAD


class LogRow(QWidget):
    """One log entry: level badge · time · device · message."""

    def __init__(self, entry: dict, parent=None, time_width: int | None = None) -> None:
        super().__init__(parent)
        self.entry = entry
        self.setObjectName("logRow")
        self.setFixedHeight(ROW_HEIGHT)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 10, 18, 10)
        layout.setSpacing(14)

        # Level badge (prototype .level: radius 6, tinted background)
        level = log_level(entry.get("status", ""))
        self.badge = QLabel(Translations.tr(f"modern.logs.level.{level}"))
        self.badge.setObjectName(
            {"info": "badgeInfo", "warn": "badgeWarn", "error": "badgeError"}[level])
        self.badge.setFixedHeight(18)
        # Uniform badge width ("FEHLER" is the longest label) so the
        # timestamps and messages align vertically across rows.
        self.badge.setFixedWidth(64)
        self.badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.badge, 0, Qt.AlignmentFlag.AlignVCenter)

        # Mono timestamp, fixed width so messages align vertically
        self.time_label = QLabel(format_timestamp(entry.get("timestamp", "")))
        self.time_label.setObjectName("logTime")
        # Never a hardcoded pixel width: the mono font differs per OS (see
        # measure_time_width), so a fixed 84 px clipped the time on Linux.
        self.time_label.setFixedWidth(
            time_width if time_width is not None
            else measure_time_width(self.time_label.text()))
        layout.addWidget(self.time_label, 0, Qt.AlignmentFlag.AlignVCenter)

        # Dim device prefix (only when a device name is present)
        device_name = entry.get("device_name", "")
        if device_name and device_name != Translations.tr("log_dialog.unknown"):
            device_label = QLabel(f"{device_name} ·")
            device_label.setObjectName("logDevice")
            layout.addWidget(device_label, 0, Qt.AlignmentFlag.AlignVCenter)

        self.msg_label = QLabel(
            entry.get("message") or Translations.tr("log_dialog.unknown"))
        self.msg_label.setObjectName("logMsg")
        self.msg_label.setWordWrap(False)
        layout.addWidget(self.msg_label, 1)


class LogsView(QWidget):
    """The modern "Protokolle" screen."""

    def __init__(self, config_manager: Any, parent=None) -> None:
        super().__init__(parent)
        self.config: Any = config_manager
        self._setup_ui()
        self._refresh_list()

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
        self.title = QLabel(Translations.tr("modern.logs.title"))
        self.title.setObjectName("pageTitle")
        self.subtitle = QLabel(Translations.tr("modern.logs.subtitle"))
        self.subtitle.setObjectName("pageSubtitle")
        layout.addWidget(self.title)
        layout.addWidget(self.subtitle)
        layout.addSpacing(10)

        # ── Toolbar ──
        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(
            Translations.tr("modern.logs.search_placeholder"))
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setFixedWidth(260)
        self.search_input.textChanged.connect(self._refresh_list)
        toolbar.addWidget(self.search_input)

        self.level_filter = QComboBox()
        for level in ("all", "info", "warn", "error"):
            self.level_filter.addItem(
                Translations.tr(f"modern.logs.filter.{level}"), level)
        self.level_filter.currentIndexChanged.connect(self._refresh_list)
        toolbar.addWidget(self.level_filter)

        toolbar.addStretch()

        self.export_btn = QPushButton(Translations.tr("modern.logs.button.export"))
        self.export_btn.clicked.connect(self._export_logs)
        toolbar.addWidget(self.export_btn)
        layout.addLayout(toolbar)

        # ── Log list panel ──
        self.panel = QWidget()
        self.panel.setObjectName("panel")
        self.list_layout = QVBoxLayout(self.panel)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(0)
        layout.addWidget(self.panel)

        # Empty-state hint (visible when no entries match)
        self.empty_label = QLabel(Translations.tr("modern.logs.empty"))
        self.empty_label.setObjectName("placeholderText")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setMargin(24)
        self.empty_label.hide()
        layout.addWidget(self.empty_label)
        layout.addStretch()

    def retranslate(self) -> None:
        """Re-apply all texts after a language switch."""
        self.title.setText(Translations.tr("modern.logs.title"))
        self.subtitle.setText(Translations.tr("modern.logs.subtitle"))
        self.search_input.setPlaceholderText(
            Translations.tr("modern.logs.search_placeholder"))
        current = self.level_filter.currentData()
        for i, level in enumerate(("all", "info", "warn", "error")):
            self.level_filter.setItemText(
                i, Translations.tr(f"modern.logs.filter.{level}"))
        self.level_filter.setCurrentIndex(
            ("all", "info", "warn", "error").index(current))
        self.export_btn.setText(Translations.tr("modern.logs.button.export"))
        self.empty_label.setText(Translations.tr("modern.logs.empty"))
        self._refresh_list()

    # ── List handling ────────────────────────────────────────────────────

    def showEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        """Reload entries whenever the page becomes visible."""
        super().showEvent(event)
        self._refresh_list()

    def _filtered_logs(self) -> list[dict]:
        """All log entries (newest first), filtered by query and level."""
        query = self.search_input.text().strip().lower()
        level = self.level_filter.currentData() or "all"

        logs = sorted(
            self.config.get_logs(),
            key=lambda e: e.get("timestamp", ""),
            reverse=True,
        )
        filtered = []
        for entry in logs:
            if level != "all" and log_level(entry.get("status", "")) != level:
                continue
            if query and query not in entry.get("message", "").lower() \
                    and query not in entry.get("device_name", "").lower():
                continue
            filtered.append(entry)
        return filtered

    def _refresh_list(self) -> None:
        """Rebuild the log rows, honouring search and level filter."""
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        entries = self._filtered_logs()
        # Measure the time column once, then give every row the same width so
        # timestamps and messages stay aligned down the list.
        time_width = measure_time_width() if entries else 0
        for idx, entry in enumerate(entries):
            self.list_layout.addWidget(LogRow(entry, time_width=time_width))
            if idx < len(entries) - 1:
                sep = QWidget()
                sep.setObjectName("rowSeparator")
                sep.setFixedHeight(1)
                self.list_layout.addWidget(sep)

        self.empty_label.setVisible(not entries)
        self.panel.setVisible(bool(entries))

    # ── Actions ──────────────────────────────────────────────────────────

    def _export_logs(self) -> None:
        """Export the current log entries to a CSV file (like LogDialog)."""
        logs = self.config.get_logs()
        if not logs:
            QMessageBox.information(self, Translations.tr("modern.logs.title"),
                                    Translations.tr("log_dialog.unknown"))
            return

        path, _ = QFileDialog.getSaveFileName(
            self, Translations.tr("log_dialog.button.export"),
            "wol_logs.csv", "CSV Files (*.csv)"
        )
        if not path:
            return

        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["timestamp", "device_name", "action", "status", "message"])
                for log in logs:
                    writer.writerow([
                        log.get("timestamp", ""),
                        log.get("device_name", ""),
                        log.get("action", ""),
                        log.get("status", ""),
                        log.get("message", ""),
                    ])
            QMessageBox.information(
                self, Translations.tr("modern.logs.title"),
                Translations.tr("log_dialog.export.success", path=path),
            )
        except Exception as e:
            QMessageBox.critical(
                self, Translations.tr("modern.logs.title"),
                Translations.tr("log_dialog.export.error", error=str(e)),
            )
