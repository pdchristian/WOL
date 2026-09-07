# Temporary diagnostic: where exactly are the emoji and text drawn inside a
# themed nav button? Pixel-column analysis + per-glyph layout info.
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtGui import QImage, QTextLayout, QFont, QTextOption
from PyQt6.QtWidgets import QApplication

from wol_app.config import ConfigManager
from wol_app.modern_theme import apply_modern_theme
from wol_app.translations import Translations

Translations().load("de")
app = QApplication(sys.argv)
apply_modern_theme(app, True)

from wol_app.modern_main_window import ModernMainWindow

cfg = ConfigManager(os.path.join(tempfile.mkdtemp(), "devices.json"))
w = ModernMainWindow(cfg, dark_mode=True)
w.resize(1200, 800)
w.show()
app.processEvents()
app.processEvents()

here = os.path.dirname(os.path.abspath(__file__))
out = []

btn = w.nav_buttons[2]  # Zeitplan
pix = btn.grab()
img = pix.toImage()
out.append(f"button size: {img.width()}x{img.height()} dpr={pix.devicePixelRatio()}")

# Column occupancy: count "bright" pixels (text/emoji) per column.
w_, h_ = img.width(), img.height()
cols = []
for x in range(w_):
    n = 0
    for y in range(h_):
        c = img.pixelColor(x, y)
        if c.red() > 120 or c.green() > 120 or c.blue() > 120:
            n += 1
    cols.append(n)
runs = []
in_run = False
for x, n in enumerate(cols):
    if n > 0 and not in_run:
        start = x
        in_run = True
    elif n == 0 and in_run:
        runs.append((start, x - 1))
        in_run = False
if in_run:
    runs.append((start, w_ - 1))
out.append("bright column runs (x0-x1): " + ", ".join(f"{a}-{b}" for a, b in runs))

# Per-glyph layout with the button's effective font.
f = btn.font()
out.append(f"button font: {f.family()!r} pixelSize={f.pixelSize()} pointSize={f.pointSize()}")

# Standalone emoji renders at several sizes, wide canvas (no clipping):
from PyQt6.QtGui import QPainter, QColor
from PyQt6.QtCore import QRectF, Qt as QtC
for size in (14, 16, 20):
    ff = QFont("Segoe UI")
    ff.setPixelSize(size)
    image = QImage(64, 48, QImage.Format.Format_ARGB32)
    image.fill(QColor(36, 41, 46))
    p = QPainter(image)
    p.setFont(ff)
    p.drawText(QRectF(0, 0, 64, 48), QtC.AlignmentFlag.AlignLeft | QtC.AlignmentFlag.AlignVCenter, "\U0001F552")
    p.end()
    image.save(os.path.join(here, f"_clock_{size}.png"))

with open(os.path.join(here, "_dbg_out.txt"), "w", encoding="utf-8") as fh:
    fh.write("\n".join(out))
print("done")
