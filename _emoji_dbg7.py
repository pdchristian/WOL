# Temporary diagnostic: REAL screen capture (DirectWrite path, not grab()).
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from wol_app.config import ConfigManager
from wol_app.modern_theme import apply_modern_theme
from wol_app.translations import Translations

Translations().load("de")
app = QApplication(sys.argv)
apply_modern_theme(app, True)

from wol_app.modern_main_window import ModernMainWindow

cfg = ConfigManager(os.path.join(os.environ.get("TEMP", "."), "wol_dbg_devices.json"))
w = ModernMainWindow(cfg, dark_mode=True)
w.setWindowTitle("WOLDBG")
w.resize(900, 600)
w.move(50, 50)
w.show()
here = os.path.dirname(os.path.abspath(__file__))


def capture():
    app.processEvents()
    screen = w.screen()
    pm = screen.grabWindow(0)
    img = pm.toImage()
    # Crop the window area (device pixels: logical * dpr).
    dpr = pm.devicePixelRatio()
    g = w.geometry()
    print("window geometry:", g, "dpr:", dpr, "screen:", screen.name())
    crop = img.copy(int(g.x() * dpr), int(g.y() * dpr),
                    int(g.width() * dpr), int(g.height() * dpr))
    crop.save(os.path.join(here, "_realscreen.png"))
    # Also a tight crop of just the sidebar nav area, scaled up 3x.
    sb = w.sidebar.geometry()
    sbg = w.mapToGlobal(sb.topLeft())
    crop2 = img.copy(int(sbg.x() * dpr), int(sbg.y() * dpr),
                     int(sb.width() * dpr), int(sb.height() * dpr))
    crop2 = crop2.scaled(crop2.width() * 3, crop2.height() * 3)
    crop2.save(os.path.join(here, "_realscreen_sb3x.png"))
    app.quit()


QTimer.singleShot(1200, capture)
sys.exit(app.exec())
