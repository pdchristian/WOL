"""Schedule Management Dialog for Wake-on-LAN Application."""

from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from .translations import Translations
from .utils import sort_rows


class ScheduleDialog(QDialog):
    """Dialog for managing scheduled wake-ups."""

    def __init__(self, config_manager, parent=None) -> None:
        super().__init__(parent)
        self.config: Any = config_manager
        self.setWindowTitle(Translations.tr("schedule_dialog.title"))
        self.setMinimumSize(650, 450)
        # Column header sort state (None = no sort, else column index)
        self._sort_column: int | None = None
        self._sort_descending: bool = False
        self._setup_ui()
        self._refresh_table()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Schedule Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            Translations.tr("schedule_dialog.col.device"),
            Translations.tr("schedule_dialog.col.time"),
            Translations.tr("schedule_dialog.col.action"),
            Translations.tr("schedule_dialog.col.days"),
            Translations.tr("schedule_dialog.col.enabled"),
            ""
        ])
        header: QHeaderView | None = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        # Clicking a column header sorts the table (1st A-Z, 2nd Z-A)
        header.setSortIndicatorShown(True)
        header.setSectionsClickable(True)
        header.sectionClicked.connect(self._on_header_clicked)
        for col in range(self.table.columnCount()):
            item = self.table.horizontalHeaderItem(col)
            if item is not None:
                item.setToolTip(Translations.tr("table.sort.tooltip"))
        self.table.itemDoubleClicked.connect(lambda item: self._edit_schedule())
        # Right-click context menu on the schedule table
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_schedule_context_menu)

        # Buttons
        btn_layout = QHBoxLayout()
        add_btn = QPushButton(Translations.tr("schedule_dialog.button.add_schedule"))
        add_btn.clicked.connect(self._add_schedule)
        edit_btn = QPushButton(Translations.tr("schedule_dialog.button.edit"))
        edit_btn.clicked.connect(self._edit_schedule)
        delete_btn = QPushButton(Translations.tr("schedule_dialog.button.delete"))
        delete_btn.clicked.connect(self._delete_schedule)

        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(edit_btn)
        btn_layout.addWidget(delete_btn)
        btn_layout.addStretch()

        close_btn = QPushButton(Translations.tr("schedule_dialog.button.close"))
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        layout.addWidget(self.table)
        layout.addLayout(btn_layout)

    def _days_to_string(self, days: list) -> str:
        day_names: dict[str, str] = {
            "Mon": "Mon", "Tue": "Tue", "Wed": "Wed",
            "Thu": "Thu", "Fri": "Fri", "Sat": "Sat", "Sun": "Sun"
        }
        return ", ".join(day_names.get(d, d) for d in days) if days else "Every day"

    def _on_header_clicked(self, column: int) -> None:
        """Sort by the clicked column: 1st click A-Z, 2nd click Z-A.

        The Enabled column (4) and the empty actions column (5) are not sortable.
        """
        if column in (4, 5):
            return
        if self._sort_column == column:
            self._sort_descending = not self._sort_descending
        else:
            self._sort_column = column
            self._sort_descending = False
        self._refresh_table()

    def _refresh_table(self) -> None:
        self.table.setRowCount(0)
        schedules = self.config.get_schedules()

        # Build sortable rows: (key, device_name, time_str, action_str, days_str, enabled)
        rows: list[tuple] = []
        for schedule in schedules:
            device = self.config.get_device_by_id(schedule.get("device_id", ""))
            device_name = device["name"] if device else Translations.tr("schedule_dialog.unknown_device")

            time_str: str = f"{schedule.get('hour', 0):02d}:{schedule.get('minute', 0):02d}"
            action_str: str = Translations.tr("schedule_dialog.action.wake") if schedule.get("action", "wake") == "wake" else Translations.tr("schedule_dialog.action.shutdown")
            days_str: str = self._days_to_string(schedule.get("days", []))
            enabled = schedule.get("enabled", True)

            values = [device_name, time_str, action_str, days_str]
            if self._sort_column is None:
                key = device_name
            elif self._sort_column == 1:  # Time HH:MM -> numeric sort
                key = schedule.get("hour", 0) * 60 + schedule.get("minute", 0)
            else:
                key = values[self._sort_column]
            rows.append((key, device_name, time_str, action_str, days_str,
                         enabled, schedule.get("id", "")))

        if self._sort_column is None:
            rows.sort(key=lambda r: r[0])
        else:
            rows = sort_rows(rows, 0, reverse=self._sort_descending)

        for _key, device_name, time_str, action_str, days_str, enabled, s_id in rows:
            row: int = self.table.rowCount()
            self.table.insertRow(row)

            self.table.setItem(row, 0, QTableWidgetItem(device_name))
            self.table.setItem(row, 1, QTableWidgetItem(time_str))
            self.table.setItem(row, 2, QTableWidgetItem(action_str))
            self.table.setItem(row, 3, QTableWidgetItem(days_str))

            enabled_check = QCheckBox()
            enabled_check.setChecked(enabled)
            enabled_check.toggled.connect(
                lambda checked, s_id=s_id: self.config.update_schedule(s_id, enabled=checked)
            )
            self.table.setCellWidget(row, 4, enabled_check)

        # Show the active sort indicator on the header
        header: QHeaderView | None = self.table.horizontalHeader()
        if self._sort_column is not None:
            order = Qt.SortOrder.DescendingOrder if self._sort_descending else Qt.SortOrder.AscendingOrder
            header.setSortIndicator(self._sort_column, order)
        else:
            header.setSortIndicator(-1, Qt.SortOrder.AscendingOrder)

    def _show_schedule_context_menu(self, pos) -> None:
        """Show the right-click context menu for the schedule table.

        Offers Add/Edit/Delete. Edit and Delete act on the row under the
        cursor (selected automatically); Add is always available.
        """
        row: int = self.table.rowAt(pos.y())

        menu = QMenu(self)
        menu.addAction(
            Translations.tr("schedule_dialog.button.add_schedule"),
            self._add_schedule,
        )
        if row >= 0:
            # Select the row under the cursor so Edit/Delete apply to it
            self.table.selectRow(row)
            self.table.setCurrentCell(row, 0)
            menu.addAction(
                Translations.tr("schedule_dialog.button.edit"),
                self._edit_schedule,
            )
            menu.addAction(
                Translations.tr("schedule_dialog.button.delete"),
                self._delete_schedule,
            )
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _add_schedule(self) -> None:
        devices = self.config.get_devices()
        if not devices:
            QMessageBox.warning(self, Translations.tr("schedule_dialog.no_devices"), Translations.tr("schedule_dialog.no_devices_msg"))
            return

        dialog = ScheduleEditDialog(self.config, devices, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._refresh_table()

    def _edit_schedule(self) -> None:
        current_row: int = self.table.currentRow()
        if current_row < 0:
            QMessageBox.information(self, Translations.tr("schedule_dialog.select_schedule"), Translations.tr("schedule_dialog.select_schedule_edit_msg"))
            return

        schedules = self.config.get_schedules()
        if current_row >= len(schedules):
            return
        schedule = schedules[current_row]

        devices = self.config.get_devices()
        dialog = ScheduleEditDialog(self.config, devices, schedule=schedule, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._refresh_table()

    def _delete_schedule(self) -> None:
        current_row: int = self.table.currentRow()
        if current_row < 0:
            QMessageBox.information(self, Translations.tr("schedule_dialog.select_schedule"), Translations.tr("schedule_dialog.select_schedule_delete_msg"))
            return

        schedules = self.config.get_schedules()
        if not schedules or current_row >= len(schedules):
            return
        schedule = schedules[current_row]

        reply: QMessageBox.StandardButton = QMessageBox.question(
            self, Translations.tr("schedule_dialog.confirm_delete"),
            Translations.tr("schedule_dialog.confirm_delete_msg"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.config.remove_schedule(schedule["id"])
            self.table.clearSelection()
            self._refresh_table()


class ScheduleEditDialog(QDialog):
    """Dialog for adding/editing a single schedule."""

    def __init__(self, config_manager, devices: list, schedule: dict = None, parent=None) -> None:
        super().__init__(parent)
        self.config = config_manager
        self.devices = devices
        self.editing_schedule = schedule
        self.setWindowTitle(Translations.tr("schedule_edit.title.edit") if schedule else Translations.tr("schedule_edit.title.add"))
        self.setMinimumWidth(400)
        self._setup_ui()
        if schedule:
            self._fill_form(schedule)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        form = QFormLayout()

        # Device selector
        self.device_combo = QComboBox()
        for dev in self.devices:
            self.device_combo.addItem(dev["name"], dev["id"])
        form.addRow(Translations.tr("schedule_edit.device"), self.device_combo)

        # Action selector
        self.action_combo = QComboBox()
        self.action_combo.addItem(Translations.tr("schedule_edit.action.wake"), "wake")
        self.action_combo.addItem(Translations.tr("schedule_edit.action.shutdown"), "shutdown")
        form.addRow(Translations.tr("schedule_edit.action_label"), self.action_combo)

        # Time
        time_layout = QHBoxLayout()
        self.hour_spin = QSpinBox()
        self.hour_spin.setRange(0, 23)
        self.hour_spin.setSuffix(" h")
        self.minute_spin = QSpinBox()
        self.minute_spin.setRange(0, 59)
        self.minute_spin.setSuffix(" m")
        time_layout.addWidget(self.hour_spin)
        time_layout.addWidget(self.minute_spin)
        form.addRow(Translations.tr("schedule_edit.wake_time"), time_layout)

        # Days of week
        days_layout = QHBoxLayout()
        self.day_checks = {}
        for day in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]:
            cb = QCheckBox(day)
            cb.setChecked(True)
            self.day_checks[day] = cb
            days_layout.addWidget(cb)
        form.addRow("Days:", QLabel())  # Placeholder - we'll add checks manually

        # Insert day checkboxes properly
        days_group = QGroupBox(Translations.tr("schedule_edit.days_of_week"))
        days_grid = QGridLayout()
        for i, day in enumerate(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]):
            cb = QCheckBox(day)
            cb.setChecked(True)
            self.day_checks[day] = cb
            days_grid.addWidget(cb, 0, i)
        days_group.setLayout(days_grid)

        # Enabled
        self.enabled_check = QCheckBox(Translations.tr("schedule_edit.enabled"))
        self.enabled_check.setChecked(True)

        # Buttons
        btn_layout = QHBoxLayout()
        save_btn = QPushButton(Translations.tr("schedule_edit.button.save") if not self.editing_schedule else Translations.tr("schedule_edit.button.update"))
        save_btn.clicked.connect(self._save)
        cancel_btn = QPushButton(Translations.tr("schedule_edit.button.cancel"))
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(form)
        layout.addWidget(days_group)
        layout.addWidget(self.enabled_check)
        layout.addLayout(btn_layout)

    def _fill_form(self, schedule: dict) -> None:
        for i in range(self.device_combo.count()):
            if self.device_combo.itemData(i) == schedule.get("device_id", ""):
                self.device_combo.setCurrentIndex(i)
                break
        action = schedule.get("action", "wake")
        if action == "shutdown":
            self.action_combo.setCurrentIndex(1)
        self.hour_spin.setValue(schedule.get("hour", 0))
        self.minute_spin.setValue(schedule.get("minute", 0))
        selected_days = schedule.get("days", [])
        for day, cb in self.day_checks.items():
            cb.setChecked(day in selected_days)
        self.enabled_check.setChecked(schedule.get("enabled", True))

    def _save(self) -> None:
        device_id = self.device_combo.currentData()
        action: Any | str = self.action_combo.currentData() or "wake"
        hour: int = self.hour_spin.value()
        minute: int = self.minute_spin.value()
        days = [day for day, cb in self.day_checks.items() if cb.isChecked()]
        enabled: bool = self.enabled_check.isChecked()

        if not days:
            QMessageBox.warning(self, Translations.tr("schedule_edit.no_days"), Translations.tr("schedule_edit.no_days_msg"))
            return

        if self.editing_schedule:
            self.config.update_schedule(
                self.editing_schedule["id"],
                device_id=device_id, hour=hour, minute=minute, days=days, enabled=enabled, action=action
            )
        else:
            self.config.add_schedule(device_id, hour, minute, days, enabled, action=action)

        self.accept()
