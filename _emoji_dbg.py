# Temporary diagnostic: measure emoji glyph overflow vs. advance width.
import os
import sys

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QImage, QPainter, QTextOption
from PyQt6.QtWidgets import QApplication, QPushButton

app = QApplication([])
out = []

STACK = ('"Segoe UI", "Noto Sans", "Ubuntu", '
         '"Noto Color Emoji", "Apple Color Emoji", "Segoe UI Emoji", '
         "sans-serif")

# 1) boundingRect overflow for each nav emoji (button font: 14px)
for name, ch in [("devices", "\U0001F4BB"), ("manage", "\U0001F527"),
                 ("schedule", "\U0001F552"), ("logs", "\U0001F4CB")]:
    f = QFont("Segoe UI")
    f.setPixelSize(14)
    engine_font = QFont("Segoe UI Emoji")
    engine_font.setPixelSize(14)
    lay = QTextOption()
    doc_rect = QRectF(0, 0, 1000, 100)
    br = lay.boundingRect(QRectF(0, 0, 1000, 100), ch, f)
    from PyQt6.QtGui import QFontMetricsF
    adv = QFontMetricsF(f).horizontalAdvance(ch)
    # real glyph bbox via the emoji engine
    fe = engine_font
    br_emoji = QTextOption().boundingRect(doc_rect, ch, fe)
    adv_emoji = QFontMetricsF(fe).horizontalAdvance(ch)
    out.append(f"{name}: advance={adv:.1f} bbox={br.width():.1f} "
               f"| emoji-font advance={adv_emoji:.1f} bbox={br_emoji.width():.1f}")

# 2) render "🕒  Zeitplan" clipped to the layout width, big, on light bg
f = QFont("Segoe UI")
f.setPixelSize(40)
img = QImage(400, 80, QImage.Format.Format_ARGB32)
img.fill(QColor("white"))
p = QPainter(img)
opt = QTextOption()
opt.setFlags(QTextOption.Flags(0))
# layout width = advance of the string (what a left-aligned button reserves)
fm = None
from PyQt6.QtGui import QFontMetrics
fm = QFontMetrics(f)
w_needed = fm.horizontalAdvance("\U0001F552  Zeitplan")
p.setClipRect(0, 0, w_needed, 80)
p.drawText(QRectF(0, 0, w_needed, 80), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "\U0001F552  Zeitplan")
p.setClipping(False)
p.setPen(QColor("red"))
p.drawLine(w_needed, 0, w_needed, 80)
p.end()
img.save(os.path.join(os.path.dirname(__file__), "_emoji_clip.png"))
out.append(f"clip x = {w_needed}")

with open(os.path.join(os.path.dirname(__file__), "_dbg_out.txt"), "w",
          encoding="utf-8") as fh:
    fh.write("\n".join(out))
print("ok")
