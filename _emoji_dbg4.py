# Temporary diagnostic: native-platform standalone emoji render vs. in-button.
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QImage, QPainter
from PyQt6.QtWidgets import QApplication

app = QApplication(sys.argv)
here = os.path.dirname(os.path.abspath(__file__))

for size in (14, 16):
    ff = QFont("Segoe UI")
    ff.setPixelSize(size)
    image = QImage(64, 48, QImage.Format.Format_ARGB32)
    image.fill(QColor(36, 41, 46))
    p = QPainter(image)
    p.setFont(ff)
    p.drawText(QRectF(0, 0, 64, 48),
               Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
               "\U0001F552")
    p.end()
    image.save(os.path.join(here, f"_nclock_{size}.png"))

# Also measure the ink width of the full string (no clipping canvas).
ff = QFont("Segoe UI")
ff.setPixelSize(14)
image = QImage(400, 48, QImage.Format.Format_ARGB32)
image.fill(QColor(36, 41, 46))
p = QPainter(image)
p.setFont(ff)
p.drawText(QRectF(0, 0, 400, 48),
           Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
           "\U0001F552  Zeitplan")
p.end()
image.save(os.path.join(here, "_nfull.png"))


def col_runs(img, bg):
    w_, h_ = img.width(), img.height()
    xs = []
    for x in range(w_):
        n = 0
        for y in range(h_):
            c = img.pixelColor(x, y)
            if (abs(c.red() - bg[0]) > 40 or abs(c.green() - bg[1]) > 40
                    or abs(c.blue() - bg[2]) > 40):
                n += 1
        if n > 0:
            xs.append(x)
    runs = []
    if not xs:
        return runs
    start = prev = xs[0]
    for x in xs[1:]:
        if x == prev + 1:
            prev = x
        else:
            runs.append((start, prev))
            start = prev = x
    runs.append((start, prev))
    return runs


out = []
for size in (14, 16):
    img = QImage(os.path.join(here, f"_nclock_{size}.png"))
    out.append(f"native standalone {size}: runs={col_runs(img, (36, 41, 46))}")
img = QImage(os.path.join(here, "_nfull.png"))
out.append(f"native full string: runs={col_runs(img, (36, 41, 46))}")
with open(os.path.join(here, "_dbg_out.txt"), "w", encoding="utf-8") as fh:
    fh.write("\n".join(out))
print("done")
