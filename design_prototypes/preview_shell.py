"""Preview launcher for Phase 2: the application shell (sidebar + screens).

Shows the full ``MainShell`` with the sidebar navigation and all (placeholder)
screens. Toggle the display mode with D/L keys.

Usage:
    python design_prototypes/preview_shell.py
"""

import os
import sys

os.environ.setdefault("WOL_HEADLESS", "1")
# Make the project root importable when run from design_prototypes/.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QMainWindow

from wol_app.config import ConfigManager
from wol_app.main_shell import MainShell
from wol_app.theme import apply_display_mode
from wol_app.translations import Translations


class PreviewWindow(QMainWindow):
    def __init__(self, config, engine) -> None:
        super().__init__()
        self.setWindowTitle("Phase 2 Preview – Dark Control Center")
        self.resize(1024, 700)
        self.setCentralWidget(MainShell(config, engine))

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_D:
            apply_display_mode(QApplication.instance(), "dark")
        elif event.key() == Qt.Key.Key_L:
            apply_display_mode(QApplication.instance(), "light")
        else:
            super().keyPressEvent(event)


def main() -> None:
    config = ConfigManager()
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
