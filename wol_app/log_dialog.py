"""Log Viewer Dialog for Wake-on-LAN Application."""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox,
)
from PyQt6.QtCore import Qt


class LogDialog(QDialog):
    """Dialog to view wake attempt logs/history."""

    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.config = config_manager
        self.setWindowTitle("Wake Log History")
        self.setMinimumSize(700, 450)
        self._setup_ui()
        self._refresh_table()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Log Table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Timestamp", "Device", "Action", "Status", "Message"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(0, 180)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(2, 100)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(3, 90)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        # Buttons
        btn_layout = QHBoxLayout()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh_table)
        clear_btn = QPushButton("Clear Logs")
        clear_btn.clicked.connect(self._clear_logs)

        btn_layout.addWidget(refresh_btn)
        btn_layout.addWidget(clear_btn)
        btn_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        layout.addWidget(self.table)
        layout.addLayout(btn_layout)

    def _refresh_table(self):
        from datetime import datetime
        self.table.setRowCount(0)
        logs = self.config.get_logs()

        for log in reversed(logs):  # Show newest first
            row = self.table.rowCount()
            self.table.insertRow(row)

            # Parse timestamp
            try:
                ts = datetime.fromisoformat(log["timestamp"])
                ts_str = ts.strftime("%Y-%m-%d %H:%M:%S")
            except (ValueError, KeyError):
                ts_str = log.get("timestamp", "Unknown")

            self.table.setItem(row, 0, QTableWidgetItem(ts_str))
            self.table.setItem(row, 1, QTableWidgetItem(log.get("device_name", "")))
            self.table.setItem(row, 2, QTableWidgetItem(log.get("action", "")))

            status_item = QTableWidgetItem(log.get("status", ""))
            status = log.get("status", "").upper()
            if status in ("SUCCESS", "ONLINE", "TRIGGERED"):
                status_item.setForeground(Qt.GlobalColor.darkGreen)
            elif status in ("ERROR", "OFFLINE"):
                status_item.setForeground(Qt.GlobalColor.darkRed)
            else:
                status_item.setForeground(Qt.GlobalColor.darkYellow)
            self.table.setItem(row, 3, status_item)

            self.table.setItem(row, 4, QTableWidgetItem(log.get("message", "")))

    def _clear_logs(self):
        reply = QMessageBox.question(
            self, "Clear Logs",
            "Are you sure you want to clear all logs?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.config.clear_logs()
            self._refresh_table()
