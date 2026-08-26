"""Schedule screen: time-based wake/shutdown schedules.

Lists schedules as cards with an enable toggle. Creating/editing reuses the
existing :class:`~wol_app.schedule_dialog.ScheduleEditDialog`.
"""

from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from wol_app.schedule_dialog import ScheduleEditDialog
from wol_app.translations import Translations
from wol_app.widgets import Toggle


class ScheduleScreen(QWidget):
    """Screen listing wake/shutdown schedules."""

    _DAY_ORDER = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    def __init__(self, config, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.config = config
        self._build_ui()
        self.refresh()

    # ---- UI ---------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(18)

        # Header: title + search
        header = QHBoxLayout()
        title = QLabel(Translations.tr("screen.schedule.title"))
        header.addWidget(title)
        header.addStretch()
        self.search_input = QLineEdit()
        self.search_input.setObjectName("SearchBox")
        self.search_input.setPlaceholderText(Translations.tr("schedule_dialog.search_placeholder"))
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self.refresh)
        header.addWidget(self.search_input, 1)
        root.addLayout(header)

        # Toolbar
        toolbar = QHBoxLayout()
        self.add_btn = QPushButton(Translations.tr("schedule_dialog.button.add_schedule"))
        self.add_btn.setObjectName("primaryButton")
        self.add_btn.clicked.connect(self._add_schedule)
        toolbar.addWidget(self.add_btn)
        toolbar.addStretch()
        root.addLayout(toolbar)

        # Schedule list
        self.list_host = QVBoxLayout()
        self.list_host.setContentsMargins(0, 0, 0, 0)
        self.list_host.setSpacing(12)
        root.addLayout(self.list_host)
        root.addStretch()

    # ---- Data / refresh ---------------------------------------------------

    def _device_name(self, device_id: str) -> str:
        dev = self.config.get_device_by_id(device_id)
        return dev.get("name", "") if dev else Translations.tr("schedule_dialog.unknown_device")

    def _filtered_schedules(self) -> list:
        query = self.search_input.text().strip().lower()
        schedules = self.config.get_schedules()
        if not query:
            return schedules
        result = []
        for s in schedules:
            text = " ".join([
                self._device_name(s.get("device_id", "")),
                s.get("action", "wake"),
                " ".join(s.get("days", [])),
            ]).lower()
            if query in text:
                result.append(s)
        return result

    def refresh(self) -> None:
        while (item := self.list_host.takeAt(0)) is not None:
            w = item.widget()
            if w is not None:
                w.deleteLater()

        for schedule in self._filtered_schedules():
            row = QWidget()
            layout = QHBoxLayout(row)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(16)

            # Enable toggle
            toggle = Toggle(checked=schedule.get("enabled", True))
            toggle.toggled.connect(
                lambda on, sid=schedule["id"]: self._toggle_enabled(sid, on)
            )
            layout.addWidget(toggle)

            # Info
            device = self._device_name(schedule.get("device_id", ""))
            action = Translations.tr(
                "schedule_edit.action.shutdown"
                if schedule.get("action", "wake") == "shutdown"
                else "schedule_edit.action.wake"
            )
            days = " · ".join(Translations.day_short(d) for d in schedule.get("days", [])) or Translations.tr("schedule_edit.no_days")
            time_str = f"{schedule.get('hour', 0):02d}:{schedule.get('minute', 0):02d}"

            info = QVBoxLayout()
            name_label = QLabel(device)
            meta = QLabel(f"{action} · {time_str} · {days}")
            meta.setObjectName("DeviceCardMeta")
            info.addWidget(name_label)
            info.addWidget(meta)
            layout.addLayout(info, 1)

            # Actions
            edit_btn = QPushButton(Translations.tr("schedule_dialog.button.edit"))
            edit_btn.clicked.connect(lambda checked=False, s=schedule: self._edit_schedule(s))
            delete_btn = QPushButton(Translations.tr("schedule_dialog.button.delete"))
            delete_btn.clicked.connect(lambda checked=False, s=schedule: self._delete_schedule(s))
            layout.addWidget(edit_btn)
            layout.addWidget(delete_btn)

            self.list_host.addWidget(row)

        if not self._filtered_schedules():
            empty = QLabel(Translations.tr("schedule_dialog.no_schedules"))
            empty.setObjectName("DeviceCardMeta")
            self.list_host.addWidget(empty)

    # ---- Actions ----------------------------------------------------------

    def _toggle_enabled(self, schedule_id: str, enabled: bool) -> None:
        self.config.update_schedule(schedule_id, enabled=enabled)

    def _add_schedule(self) -> None:
        devices = self.config.get_devices()
        if not devices:
            QMessageBox.warning(
                self, Translations.tr("schedule_dialog.no_devices"),
                Translations.tr("schedule_dialog.no_devices_msg"),
            )
            return
        dialog = ScheduleEditDialog(self.config, devices, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _edit_schedule(self, schedule: dict) -> None:
        devices = self.config.get_devices()
        dialog = ScheduleEditDialog(self.config, devices, schedule=schedule, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _delete_schedule(self, schedule: dict) -> None:
        reply = QMessageBox.question(
            self,
            Translations.tr("schedule_dialog.confirm_delete"),
            Translations.tr("schedule_dialog.confirm_delete_msg"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.config.remove_schedule(schedule["id"])
            self.refresh()
