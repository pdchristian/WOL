"""Logs screen: event log viewer (placeholder)."""

from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from wol_app.translations import Translations


class LogsScreen(QWidget):
    """Screen showing application event logs."""

    def __init__(self, config, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.config = config
        layout = QVBoxLayout(self)
        label = QLabel(Translations.tr("screen.logs.placeholder"))
        label.setWordWrap(True)
        layout.addWidget(label)
        layout.addStretch()
