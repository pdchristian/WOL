"""Log Viewer Dialog for Wake-on-LAN Application."""

import csv
from datetime import datetime
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from wol_app.translations import Translations
from wol_app.utils import sort_rows


class LogPage(QWidget):
    """Page to view wake attempt logs/history."""

    def __init__(self, config_manager, parent=None) -> None:
        super().__init__(parent)
        self.config: Any = config_manager
        self.setMinimumSize(700, 450)
        # Column header sort state (None = no sort, else column index)
        self._sort_column: int | None = None
        self._sort_descending: bool = False
        self._setup_ui()
        self._refresh_table()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Log Table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            Translations.tr("log_dialog.col.timestamp"),
            Translations.tr("log_dialog.col.device"),
            Translations.tr("log_dialog.col.action"),
            Translations.tr("log_dialog.col.status"),
            Translations.tr("log_dialog.col.message"),
        ])
        header: QHeaderView | None = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(0, 180)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(2, 100)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(3, 90)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
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

        # Buttons
        btn_layout = QHBoxLayout()
        refresh_btn = QPushButton(Translations.tr("log_dialog.button.refresh"))
        refresh_btn.clicked.connect(self._refresh_table)
        export_btn = QPushButton(Translations.tr("log_dialog.button.export"))
        export_btn.clicked.connect(self._export_logs)
        clear_btn = QPushButton(Translations.tr("log_dialog.button.clear_logs"))
        clear_btn.clicked.connect(self._clear_logs)

        btn_layout.addWidget(refresh_btn)
        btn_layout.addWidget(export_btn)
        btn_layout.addWidget(clear_btn)
        btn_layout.addStretch()

        layout.addWidget(self.table)
        layout.addLayout(btn_layout)

    def _on_header_clicked(self, column: int) -> None:
        """Sort by the clicked column: 1st click A-Z, 2nd click Z-A."""
        if self._sort_column == column:
            self._sort_descending = not self._sort_descending
        else:
            self._sort_column = column
            self._sort_descending = False
        self._refresh_table()

    def _refresh_table(self) -> None:
        self.table.setRowCount(0)
        logs = self.config.get_logs()

        # Build rows with a sortable key for the active sort column
        rows: list[tuple] = []
        for log in logs:
            # Parse timestamp
            try:
                ts: datetime = datetime.fromisoformat(log["timestamp"])
                ts_str: str = ts.strftime("%Y-%m-%d %H:%M:%S")
            except (ValueError, KeyError):
                ts_str = log.get("timestamp", "Unknown")
                ts = None

            status_item = QTableWidgetItem(log.get("status", ""))
            status = log.get("status", "").upper()
            if status in ("SUCCESS", "ONLINE", "TRIGGERED"):
                status_item.setForeground(Qt.GlobalColor.darkGreen)
            elif status in ("ERROR", "OFFLINE"):
                status_item.setForeground(Qt.GlobalColor.darkRed)
            else:
                status_item.setForeground(Qt.GlobalColor.darkYellow)

            message = log.get("message", Translations.tr("log_dialog.unknown"))
            # Column 0 (and the default order) sorts chronologically by the
            # string timestamp; the other columns sort by their string value.
            if self._sort_column is None or self._sort_column == 0:
                sort_value = ts_str
            else:
                sort_value = [
                    ts_str,
                    log.get("device_name", ""),
                    log.get("action", ""),
                    log.get("status", ""),
                    message,
                ][self._sort_column]
            rows.append((sort_value, ts_str, log.get("device_name", ""),
                         log.get("action", ""), status_item, message))

        # Default order: newest first (timestamp descending)
        if self._sort_column is None:
            rows.sort(key=lambda r: r[0], reverse=True)
        else:
            rows = sort_rows(rows, 0, reverse=self._sort_descending)

        for sort_value, ts_str, device_name, action, status_item, message in rows:
            row: int = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(ts_str))
            self.table.setItem(row, 1, QTableWidgetItem(device_name))
            self.table.setItem(row, 2, QTableWidgetItem(action))
            self.table.setItem(row, 3, status_item)
            self.table.setItem(row, 4, QTableWidgetItem(message))

        # Show the active sort indicator on the header
        header: QHeaderView | None = self.table.horizontalHeader()
        if self._sort_column is not None:
            order = Qt.SortOrder.DescendingOrder if self._sort_descending else Qt.SortOrder.AscendingOrder
            header.setSortIndicator(self._sort_column, order)
        else:
            header.setSortIndicator(-1, Qt.SortOrder.AscendingOrder)

    def _export_logs(self) -> None:
        """Export the current log entries to a CSV file."""
        logs = self.config.get_logs()
        if not logs:
            QMessageBox.information(self, Translations.tr("log_dialog.title"),
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
                self, Translations.tr("log_dialog.title"),
                Translations.tr("log_dialog.export.success", path=path),
            )
        except Exception as e:
            QMessageBox.critical(
                self, Translations.tr("log_dialog.title"),
                Translations.tr("log_dialog.export.error", error=str(e)),
            )

    def _clear_logs(self) -> None:
        reply: QMessageBox.StandardButton = QMessageBox.question(
            self, Translations.tr("log_dialog.confirm_clear.title"),
            Translations.tr("log_dialog.confirm_clear.message"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.config.clear_logs()
            self._refresh_table()
