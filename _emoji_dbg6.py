# Temporary diagnostic (run with QT_SCALE_FACTOR=1.5): find a rendering
# variant where the color-emoji ink is NOT clipped.
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtCore import QPointF, QRectF, QSize, Qt
from PyQt6.QtGui import QColor, QFont, QIcon, QImage, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication, QLabel, QPushButton

app = QApplication(sys.argv)
here = os.path.dirname(os.path.abspath(__file__))
BG = (24, 28, 32)
out = []


def ink_runs(img):
    w_, h_ = img.width(), img.height()
    xs = []
    for x in range(w_):
        n = 0
        for y in range(h_):
            c = img.pixelColor(x, y)
            if (abs(c.red() - BG[0]) > 40 or abs(c.green() - BG[1]) > 40
                    or abs(c.blue() - BG[2]) > 40):
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


def grab(wid, name):
    wid.setStyleSheet(
        f"background: rgb{BG}; color: white; font-size: 14px; padding: 10px;")
    wid.resize(300, 44)
    wid.show()
    app.processEvents()
    img = wid.grab().toImage()
    img.save(os.path.join(here, f"_6{name}.png"))
    return ink_runs(img)


def emoji_pix(char, canvas, font_px, spacing=0):
    pm = QPixmap(canvas, canvas)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    f = QFont("Segoe UI")
    f.setPixelSize(font_px)
    if spacing:
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, spacing)
    p.setFont(f)
    p.drawText(QRectF(0, 0, canvas, canvas),
               Qt.AlignmentFlag.AlignCenter, char)
    p.end()
    return pm


CLOCK = "\U0001F552"

# S1: plain button string (current implementation)
out.append(f"S1 button 2sp:        {grab(QPushButton(CLOCK + '  Zeitplan'), 's1')}")
# S2: 3 spaces after emoji
out.append(f"S2 button 3sp:        {grab(QPushButton(CLOCK + '   Zeitplan'), 's2')}")
# S3: QLabel emoji alone
out.append(f"S3 label emoji:       {grab(QLabel(CLOCK), 's3')}")
# S4: button with pixmap icon (no letter spacing)
b4 = QPushButton("Zeitplan")
b4.setIcon(QIcon(emoji_pix(CLOCK, 32, 20)))
b4.setIconSize(QSize(20, 20))
out.append(f"S4 button pixmap:     {grab(b4, 's4')}")
# S5: button with pixmap icon rendered with letter spacing
b5 = QPushButton("Zeitplan")
b5.setIcon(QIcon(emoji_pix(CLOCK, 32, 20, spacing=8)))
b5.setIconSize(QSize(20, 20))
out.append(f"S5 button pixmap+sp:  {grab(b5, 's5')}")

# Raw pixmap ink (transparent canvas -> measure against alpha)
for tag, sp in (("plain", 0), ("sp8", 8)):
    pm = emoji_pix(CLOCK, 32, 20, sp)
    img = pm.toImage()
    xs = [x for x in range(img.width())
          if any(img.pixelColor(x, y).alpha() > 10
                 for y in range(img.height()))]
    out.append(f"P pixmap {tag} alpha cols: {min(xs)}..{max(xs)}")

# 4x zoomed crops of the two clock renderings for visual comparison.
for name, x0, x1 in (("cmp_s1", 130, 200), ("cmp_s3", 10, 50)):
    img = QImage(os.path.join(here, f"_6{name.split('_')[1].replace('s1','s1').replace('s3','s3')}.png"))
    pass
img1 = QImage(os.path.join(here, "_6s1.png"))
img1.copy(130, 0, 80, img1.height()).scaled(320, img1.height() * 4).save(
    os.path.join(here, "_cmp_button.png"))
img3 = QImage(os.path.join(here, "_6s3.png"))
img3.copy(0, 0, 80, img3.height()).scaled(320, img3.height() * 4).save(
    os.path.join(here, "_cmp_label.png"))


with open(os.path.join(here, "_dbg_out.txt"), "w", encoding="utf-8") as fh:
    fh.write("\n".join(out))
print("done")
