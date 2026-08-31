"""Modern UI: "Zeitplan" screen (scheduled wake-up / shutdown entries).

Layout mirrors the prototype's schedule screen
(Design_Prototpye/dark_control_center_full.html):

1. Page header (title + subtitle).
2. Toolbar: primary "Zeitplan erstellen" button and a live search field.
3. A panel of fixed-height schedule rows: pill toggle (enabled), info
   block (bold title, mono "days · HH:MM · action" subtitle) and
   edit/delete tile buttons.

All persistence goes through the shared ``ConfigManager`` schedule API;
the edit dialog is the modern ``ModernScheduleEditDialog``.
"""

from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
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
from wol_app.views.schedule_edit_dialog import DAYS, ModernScheduleEditDialog
from wol_app.widgets.toggle_switch import ToggleSwitch

# Fixed height of one schedule row (px) — matches DeviceRow in manage_view
ROW_HEIGHT = 64


def format_days(days: list) -> str:
    """Human-readable day summary like the prototype ("Sa · So", "Wochentags").

    Empty list means "every day" (mirrors the classic dialog).
    """
    if not days or len(days) >= 7:
        return Translations.tr("modern.schedule.days.every")
    if set(days) == {"Mon", "Tue", "Wed", "Thu", "Fri"}:
        return Translations.tr("modern.schedule.days.weekdays")
    ordered = [d for d in DAYS if d in days]
    return " · ".join(Translations.tr(f"day.{d}") for d in ordered)


class ScheduleRow(QWidget):
    """One schedule entry: toggle · title / mono subtitle · edit · delete."""

    edit_requested = pyqtSignal(str)   # schedule id
    delete_requested = pyqtSignal(str)  # schedule id
    enabled_toggled = pyqtSignal(str, bool)  # schedule id, enabled

    def __init__(self, schedule: dict, device_name: str, parent=None) -> None:
        super().__init__(parent)
        self.schedule_id: str = schedule.get("id", "")
        self.setObjectName("scheduleRow")
        self.setFixedHeight(ROW_HEIGHT)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 10, 18, 10)
        layout.setSpacing(16)

        # Enable toggle (prototype: pill toggle leftmost)
        self.toggle = ToggleSwitch(checked=schedule.get("enabled", True))
        self.toggle.toggled.connect(
            lambda checked: self.enabled_toggled.emit(self.schedule_id, checked)
        )
        layout.addWidget(self.toggle, 0, Qt.AlignmentFlag.AlignVCenter)

        # Info block: bold title + dim mono subtitle
        info = QVBoxLayout()
        info.setSpacing(2)
        self.title = QLabel(device_name)
        self.title.setObjectName(
            "rowTitle" if schedule.get("enabled", True) else "rowTitleDisabled")
        time_str = f"{schedule.get('hour', 0):02d}:{schedule.get('minute', 0):02d}"
        action_key = (
            "modern.schedule.action.wake"
            if schedule.get("action", "wake") == "wake"
            else "modern.schedule.action.shutdown"
        )
        days_str = format_days(schedule.get("days", []))
        self.mono = QLabel(f"{days_str} · {time_str} · {Translations.tr(action_key)}")
        self.mono.setObjectName("rowMono")
        info.addWidget(self.title)
        info.addWidget(self.mono)
        layout.addLayout(info)

        layout.addStretch()

        # Action tiles — identical to the device rows (36x36 px, vertically centered)
        self.edit_btn = QPushButton("✏️")
        self.edit_btn.setObjectName("tileButton")
        self.edit_btn.setFixedSize(36, 36)
        self.edit_btn.setToolTip(Translations.tr("device_manager.button.edit"))
        self.edit_btn.clicked.connect(lambda: self.edit_requested.emit(self.schedule_id))
        layout.addWidget(self.edit_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        self.delete_btn = QPushButton("🗑️")
        self.delete_btn.setObjectName("tileDanger")
        self.delete_btn.setFixedSize(36, 36)
        self.delete_btn.setToolTip(Translations.tr("device_manager.button.delete"))
        self.delete_btn.clicked.connect(lambda: self.delete_requested.emit(self.schedule_id))
        layout.addWidget(self.delete_btn, 0, Qt.AlignmentFlag.AlignVCenter)

    def set_enabled_style(self, enabled: bool) -> None:
        """Dim the title when the schedule is disabled."""
        self.title.setObjectName("rowTitle" if enabled else "rowTitleDisabled")
        style = self.title.style()
        style.unpolish(self.title)
        style.polish(self.title)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        self.edit_requested.emit(self.schedule_id)

    def retranslate(self, device_name: str, schedule: dict) -> None:
        self.title.setText(device_name)
        time_str = f"{schedule.get('hour', 0):02d}:{schedule.get('minute', 0):02d}"
        action_key = (
            "modern.schedule.action.wake"
            if schedule.get("action", "wake") == "wake"
            else "modern.schedule.action.shutdown"
        )
        days_str = format_days(schedule.get("days", []))
        self.mono.setText(f"{days_str} · {time_str} · {Translations.tr(action_key)}")
        self.edit_btn.setToolTip(Translations.tr("device_manager.button.edit"))
        self.delete_btn.setToolTip(Translations.tr("device_manager.button.delete"))


class ScheduleView(QWidget):
    """The modern "Zeitplan" screen."""

    schedules_changed = pyqtSignal()

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
        self.title = QLabel(Translations.tr("modern.schedule.title"))
        self.title.setObjectName("pageTitle")
        self.subtitle = QLabel(Translations.tr("modern.schedule.subtitle"))
        self.subtitle.setObjectName("pageSubtitle")
        layout.addWidget(self.title)
        layout.addWidget(self.subtitle)
        layout.addSpacing(10)

        # ── Toolbar ──
        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)
        self.add_btn = QPushButton(Translations.tr("modern.schedule.button.add"))
        self.add_btn.setObjectName("primaryButton")
        self.add_btn.clicked.connect(self._add_schedule)
        toolbar.addWidget(self.add_btn)
        toolbar.addStretch()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(
            Translations.tr("modern.schedule.search_placeholder"))
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._refresh_list)
        self.search_input.setFixedWidth(260)
        toolbar.addWidget(self.search_input)
        layout.addLayout(toolbar)

        # ── Schedule list panel ──
        self.panel = QWidget()
        self.panel.setObjectName("panel")
        self.list_layout = QVBoxLayout(self.panel)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(0)
        layout.addWidget(self.panel)

        # Empty-state hint (visible when no schedules match)
        self.empty_label = QLabel(Translations.tr("modern.schedule.empty"))
        self.empty_label.setObjectName("placeholderText")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setMargin(24)
        self.empty_label.hide()
        layout.addWidget(self.empty_label)
        layout.addStretch()

    def retranslate(self) -> None:
        """Re-apply all texts after a language switch."""
        self.title.setText(Translations.tr("modern.schedule.title"))
        self.subtitle.setText(Translations.tr("modern.schedule.subtitle"))
        self.add_btn.setText(Translations.tr("modern.schedule.button.add"))
        self.search_input.setPlaceholderText(
            Translations.tr("modern.schedule.search_placeholder"))
        self.empty_label.setText(Translations.tr("modern.schedule.empty"))
        self._refresh_list()

    # ── List handling ────────────────────────────────────────────────────

    def _device_name(self, schedule: dict) -> str:
        device = self.config.get_device_by_id(schedule.get("device_id", ""))
        return (device["name"] if device
                else Translations.tr("schedule_dialog.unknown_device"))

    def _filtered_schedules(self) -> list[dict]:
        """All schedules (sorted by time), filtered by the search query."""
        query = self.search_input.text().strip().lower()
        schedules = sorted(
            self.config.get_schedules(),
            key=lambda s: (s.get("hour", 0), s.get("minute", 0)),
        )
        if not query:
            return schedules

        enabled_term = Translations.tr("schedule_dialog.col.enabled").lower()
        disabled_term = Translations.tr("device.disabled").lower()
        filtered = []
        for schedule in schedules:
            action_key = (
                "modern.schedule.action.wake"
                if schedule.get("action", "wake") == "wake"
                else "modern.schedule.action.shutdown"
            )
            values = [
                self._device_name(schedule),
                f"{schedule.get('hour', 0):02d}:{schedule.get('minute', 0):02d}",
                Translations.tr(action_key),
                format_days(schedule.get("days", [])),
                enabled_term if schedule.get("enabled", True) else disabled_term,
            ]
            if any(query in v.lower() for v in values):
                filtered.append(schedule)
        return filtered

    def _refresh_list(self) -> None:
        """Rebuild the schedule rows, honouring the search filter."""
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        schedules = self._filtered_schedules()
        for idx, schedule in enumerate(schedules):
            row = ScheduleRow(schedule, self._device_name(schedule))
            row.edit_requested.connect(self._edit_schedule)
            row.delete_requested.connect(self._delete_schedule)
            row.enabled_toggled.connect(self._on_toggle_enabled)
            self.list_layout.addWidget(row)
            if idx < len(schedules) - 1:
                sep = QWidget()
                sep.setObjectName("rowSeparator")
                sep.setFixedHeight(1)
                self.list_layout.addWidget(sep)

        self.empty_label.setVisible(not schedules)
        self.panel.setVisible(bool(schedules))

    def _schedule_rows(self) -> list[ScheduleRow]:
        return [
            self.list_layout.itemAt(i).widget()
            for i in range(self.list_layout.count())
            if isinstance(self.list_layout.itemAt(i).widget(), ScheduleRow)
        ]

    # ── Actions ──────────────────────────────────────────────────────────

    def _add_schedule(self) -> None:
        devices = self.config.get_devices()
        if not devices:
            QMessageBox.warning(
                self,
                Translations.tr("modern.schedule.no_devices.title"),
                Translations.tr("modern.schedule.no_devices.message"),
            )
            return
        dialog = ModernScheduleEditDialog(self.config, devices, parent=self)
        dialog.accepted.connect(self._on_schedules_changed)
        dialog.exec()

    def _edit_schedule(self, schedule_id: str) -> None:
        schedule = self._find_schedule(schedule_id)
        if schedule is None:
            return
        devices = self.config.get_devices()
        dialog = ModernScheduleEditDialog(
            self.config, devices, schedule=schedule, parent=self)
        dialog.accepted.connect(self._on_schedules_changed)
        dialog.exec()

    def _delete_schedule(self, schedule_id: str) -> None:
        schedule = self._find_schedule(schedule_id)
        if schedule is None:
            return
        reply: QMessageBox.StandardButton = QMessageBox.question(
            self,
            Translations.tr("modern.schedule.delete.title"),
            Translations.tr(
                "modern.schedule.delete.message",
                name=self._device_name(schedule),
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.config.remove_schedule(schedule_id)
            self._on_schedules_changed()

    def _on_toggle_enabled(self, schedule_id: str, enabled: bool) -> None:
        self.config.update_schedule(schedule_id, enabled=enabled)
        # Dim/undim the row title without a full rebuild
        for row in self._schedule_rows():
            if row.schedule_id == schedule_id:
                row.set_enabled_style(enabled)
                break

    def _find_schedule(self, schedule_id: str) -> dict | None:
        for schedule in self.config.get_schedules():
            if schedule.get("id") == schedule_id:
                return schedule
        return None

    def _on_schedules_changed(self) -> None:
        self._refresh_list()
        self.schedules_changed.emit()

    def showEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        super().showEvent(event)
        # Devices may have changed in the manage view while away
        self._refresh_list()
