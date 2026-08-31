"""Modern UI: dialog for creating/editing a schedule entry.

Visually aligned with the Dark Control Center design (panel sections,
modern buttons); functionally equivalent to the classic
``ScheduleEditDialog`` in ``wol_app.schedule_dialog`` and writes through
the same ``ConfigManager`` API.
"""

from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from wol_app.translations import Translations
from wol_app.widgets.toggle_switch import ToggleSwitch

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


class ModernScheduleEditDialog(QDialog):
    """Add or edit one schedule entry (modern layout)."""

    def __init__(
        self,
        config_manager: Any,
        devices: list,
        schedule: dict | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.config: Any = config_manager
        self.devices = devices
        self.editing_schedule = schedule
        self.setWindowTitle(
            Translations.tr("schedule_edit.title.edit")
            if schedule else Translations.tr("schedule_edit.title.add")
        )
        self.setMinimumWidth(440)
        self._setup_ui()
        if schedule:
            self._fill_form(schedule)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # Header
        header = QLabel(
            Translations.tr("schedule_edit.title.edit")
            if self.editing_schedule else Translations.tr("schedule_edit.title.add")
        )
        header.setObjectName("pageTitle")
        layout.addWidget(header)

        # Form panel
        panel = QWidget()
        panel.setObjectName("panel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(18, 16, 18, 16)

        form = QFormLayout()
        form.setSpacing(12)

        self.device_combo = QComboBox()
        for dev in self.devices:
            self.device_combo.addItem(dev["name"], dev["id"])
        form.addRow(Translations.tr("schedule_edit.device"), self.device_combo)

        self.action_combo = QComboBox()
        self.action_combo.addItem(Translations.tr("schedule_edit.action.wake"), "wake")
        self.action_combo.addItem(Translations.tr("schedule_edit.action.shutdown"), "shutdown")
        form.addRow(Translations.tr("schedule_edit.action_label"), self.action_combo)

        time_row = QHBoxLayout()
        time_row.setSpacing(8)
        self.hour_spin = QSpinBox()
        self.hour_spin.setRange(0, 23)
        self.hour_spin.setSuffix(" h")
        self.minute_spin = QSpinBox()
        self.minute_spin.setRange(0, 59)
        self.minute_spin.setSuffix(" m")
        time_row.addWidget(self.hour_spin)
        time_row.addWidget(self.minute_spin)
        time_row.addStretch()
        form.addRow(Translations.tr("schedule_edit.wake_time"), time_row)

        panel_layout.addLayout(form)

        # Days of week
        days_label = QLabel(Translations.tr("schedule_edit.days_of_week"))
        days_label.setObjectName("sectionHeading")
        panel_layout.addWidget(days_label)

        days_grid = QGridLayout()
        days_grid.setSpacing(8)
        self.day_checks: dict[str, QCheckBox] = {}
        for i, day in enumerate(DAYS):
            # DAY keys stay English (config data); the label is translated
            cb = QCheckBox(Translations.tr(f"day.{day}"))
            cb.setChecked(True)
            self.day_checks[day] = cb
            days_grid.addWidget(cb, 0, i)
        panel_layout.addLayout(days_grid)

        layout.addWidget(panel)

        # Enabled toggle row
        enabled_row = QHBoxLayout()
        enabled_label = QLabel(Translations.tr("schedule_edit.enabled"))
        enabled_label.setObjectName("rowTitle")
        self.enabled_toggle = ToggleSwitch(checked=True)
        enabled_row.addWidget(enabled_label)
        enabled_row.addStretch()
        enabled_row.addWidget(self.enabled_toggle)
        layout.addLayout(enabled_row)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.save_btn = QPushButton(
            Translations.tr("schedule_edit.button.update")
            if self.editing_schedule else Translations.tr("schedule_edit.button.save")
        )
        self.save_btn.setObjectName("primaryButton")
        self.save_btn.clicked.connect(self._save)
        self.cancel_btn = QPushButton(Translations.tr("schedule_edit.button.cancel"))
        self.cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.save_btn)
        btn_row.addWidget(self.cancel_btn)
        layout.addLayout(btn_row)

    def _fill_form(self, schedule: dict) -> None:
        for i in range(self.device_combo.count()):
            if self.device_combo.itemData(i) == schedule.get("device_id", ""):
                self.device_combo.setCurrentIndex(i)
                break
        if schedule.get("action", "wake") == "shutdown":
            self.action_combo.setCurrentIndex(1)
        self.hour_spin.setValue(schedule.get("hour", 0))
        self.minute_spin.setValue(schedule.get("minute", 0))
        selected_days = schedule.get("days", [])
        for day, cb in self.day_checks.items():
            cb.setChecked(day in selected_days)
        self.enabled_toggle.setChecked(schedule.get("enabled", True))

    def _save(self) -> None:
        device_id = self.device_combo.currentData()
        action: Any | str = self.action_combo.currentData() or "wake"
        hour: int = self.hour_spin.value()
        minute: int = self.minute_spin.value()
        days = [day for day, cb in self.day_checks.items() if cb.isChecked()]
        enabled: bool = self.enabled_toggle.isChecked()

        if not days:
            QMessageBox.warning(
                self,
                Translations.tr("schedule_edit.no_days"),
                Translations.tr("schedule_edit.no_days_msg"),
            )
            return

        if self.editing_schedule:
            self.config.update_schedule(
                self.editing_schedule["id"],
                device_id=device_id, hour=hour, minute=minute,
                days=days, enabled=enabled, action=action,
            )
        else:
            self.config.add_schedule(device_id, hour, minute, days, enabled, action=action)

        self.accept()
