# Temporary diagnostic: confirm the emoji-clip mechanism and validate the fix.
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

app = QApplication(sys.argv)
here = os.path.dirname(os.path.abspath(__file__))
BG = (36, 41, 46)


def col_runs(img):
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


def grab_row(widget, name):
    widget.setStyleSheet(f"background: rgb{BG}; color: white; font-size: 14px;")
    widget.resize(300, 40)
    widget.show()
    app.processEvents()
    img = widget.grab().toImage()
    img.save(os.path.join(here, f"_{name}.png"))
    return col_runs(img)


out = []
# A) button "🕒  Zeitplan" (current impl)
b = QPushButton("\U0001F552  Zeitplan")
out.append(f"A button emoji+text: {grab_row(b, 't_a')}")

# B) button "🕒   Zeitplan" (extra space)
b2 = QPushButton("\U0001F552   Zeitplan")
out.append(f"B button +3 spaces:  {grab_row(b2, 't_b')}")

# C) standalone emoji QLabel (tight)
c = QLabel("\U0001F552")
out.append(f"C QLabel emoji only:  {grab_row(c, 't_c')}")

# D) emoji QLabel 24px wide + text QLabel  (proposed fix)
row = QWidget()
lay = QHBoxLayout(row)
lay.setContentsMargins(12, 0, 12, 0)
lay.setSpacing(12)
icon_lbl = QLabel("\U0001F552")
icon_lbl.setFixedWidth(20)
icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
text_lbl = QLabel("Zeitplan")
lay.addWidget(icon_lbl)
lay.addWidget(text_lbl)
lay.addStretch()
out.append(f"D icon-label fix:     {grab_row(row, 't_d')}")

with open(os.path.join(here, "_dbg_out.txt"), "w", encoding="utf-8") as fh:
    fh.write("\n".join(out))
print("done")
