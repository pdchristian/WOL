# Temporary diagnostic: render the real sidebar on the native platform and
# capture each nav button (and the emoji alone) to PNG.
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication

from wol_app.config import ConfigManager
from wol_app.modern_theme import apply_modern_theme
from wol_app.translations import Translations

Translations().load("de")
app = QApplication(sys.argv)

# Use the REAL user config (sidebar_width, display mode) like the running app.
cfg = ConfigManager()
display_mode = cfg.config.get("ui", {}).get("display_mode", "dark")
dark = display_mode != "light"
apply_modern_theme(app, dark)

from wol_app.modern_main_window import ModernMainWindow

w = ModernMainWindow(cfg, dark_mode=dark)
w.resize(1246, 623)
w.show()
app.processEvents()
app.processEvents()

here = os.path.dirname(os.path.abspath(__file__))
w.sidebar.grab().save(os.path.join(here, "_sidebar_native.png"))
for i, b in enumerate(w.nav_buttons):
    b.grab().save(os.path.join(here, f"_navbtn_{i}.png"))
info = []
for b in w.nav_buttons:
    fe = b.font()
    info.append(f"{b.text()!r} family={fe.family()!r} pixelSize={fe.pixelSize()} "
                f"pointSize={fe.pointSize()} adv={b.fontMetrics().horizontalAdvance(b.text())}")
with open(os.path.join(here, "_dbg_out.txt"), "w", encoding="utf-8") as fh:
    fh.write("\n".join(info))
print("captured")
