# Decisive test: is the color-emoji bitmap clipped to its advance cell?
import os
import sys

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QImage, QPainter
from PyQt6.QtWidgets import QApplication, QPushButton

app = QApplication(sys.argv)
here = os.path.dirname(os.path.abspath(__file__))
BG = (30, 34, 38)
out = []


def ink(img, transparent=False):
    w_, h_ = img.width(), img.height()
    xs = []
    for x in range(w_):
        for y in range(h_):
            c = img.pixelColor(x, y)
            hit = (c.alpha() > 20) if transparent else (
                abs(c.red() - BG[0]) > 25 or abs(c.green() - BG[1]) > 25
                or abs(c.blue() - BG[2]) > 25)
            if hit:
                xs.append(x)
                break
    return (min(xs), max(xs), max(xs) - min(xs) + 1) if xs else None


# 1) huge standalone render — natural ink vs advance
for size in (96, 48):
    f = QFont("Segoe UI")
    f.setPixelSize(size)
    img = QImage(size * 3, size * 2, QImage.Format.Format_ARGB32)
    img.fill(QColor(*BG))
    p = QPainter(img)
    p.setFont(f)
    p.drawText(QRectF(0, 0, size * 3, size * 2),
               Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
               "\U0001F552")
    p.end()
    img.save(os.path.join(here, f"_big_{size}.png"))
    out.append(f"standalone {size}px: ink={ink(img)}")

# 2) inside a QPushButton at huge font size
btn = QPushButton("\U0001F552  Zeitplan")
f = QFont("Segoe UI")
f.setPixelSize(48)
btn.setFont(f)
btn.setStyleSheet(f"background: rgb{BG}; color: white; padding: 20px;")
btn.resize(500, 120)
btn.show()
app.processEvents()
img = btn.grab().toImage()
img.save(os.path.join(here, "_big_btn.png"))
out.append(f"button 48px: ink={ink(img)}")

with open(os.path.join(here, "_dbg_out.txt"), "w", encoding="utf-8") as fh:
    fh.write("\n".join(str(o) for o in out))
print("done")
