"""Preview launcher for Phase 1 of the "Dark Control Center" UI.

Runs a minimal QMainWindow containing the new DevicesScreen (cards/list
toggle) with the new theme, so the design can be reviewed without the full
app. Toggle the display mode by pressing D/L keys.

Usage:
    python design_prototypes/preview_phase1.py
"""

import os
import sys

os.environ.setdefault("WOL_HEADLESS", "1")

# Make the project root importable when run as a script from design_prototypes/.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QHBoxLayout, QMainWindow, QWidget

from wol_app.config import ConfigManager
from wol_app.screens.devices_screen import DevicesScreen
from wol_app.theme import apply_display_mode
from wol_app.translations import Translations


class PreviewWindow(QMainWindow):
    def __init__(self, config, engine) -> None:
        super().__init__()
        self.setWindowTitle("Phase 1 Preview – Dark Control Center")
        self.resize(980, 640)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(20, 20, 20, 20)

        self.screen = DevicesScreen(config, engine)
        layout.addWidget(self.screen)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_D:
            apply_display_mode(QApplication.instance(), "dark")
        elif event.key() == Qt.Key.Key_L:
            apply_display_mode(QApplication.instance(), "light")
        else:
            super().keyPressEvent(event)


def main() -> None:
    config = ConfigManager()
    # Ensure some demo devices exist so the view is not empty on first run.
    if not config.get_devices():
        for name, mac in [
            ("Workstation", "AA:BB:CC:00:11:22"),
            ("Media-Server", "AA:BB:CC:33:44:55"),
            ("Gaming-PC", "AA:BB:CC:66:77:88"),
            ("NAS - Synology", "AA:BB:CC:99:00:11"),
        ]:
            config.add_device(name=name, mac=mac)

    Translations()  # init singleton
    Translations.set_language(config.config.get("ui", {}).get("language", "en"))

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    mode = config.config.get("ui", {}).get("display_mode", "auto")
    apply_display_mode(app, mode)

    from wol_app.wol_engine import WOLEngine
    engine = WOLEngine(config)
    window = PreviewWindow(config, engine)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
