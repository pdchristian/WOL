"""Settings screen: application configuration (placeholder)."""

from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from wol_app.translations import Translations


class SettingsScreen(QWidget):
    """Screen for application & network configuration."""

    def __init__(self, config, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.config = config
        layout = QVBoxLayout(self)
        label = QLabel(Translations.tr("screen.settings.placeholder"))
        label.setWordWrap(True)
        layout.addWidget(label)
        layout.addStretch()
