"""About screen: version and update actions (placeholder)."""

from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from wol_app.translations import Translations


class AboutScreen(QWidget):
    """Screen with version info and update button."""

    def __init__(self, config, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.config = config
        layout = QVBoxLayout(self)
        label = QLabel(Translations.tr("screen.about.placeholder"))
        label.setWordWrap(True)
        layout.addWidget(label)
        layout.addStretch()
