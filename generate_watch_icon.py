#!/usr/bin/env python3
"""Erzeugt das Apple-Watch-App-Icon (watchOS 10+ Single-Size 1024x1024) aus icon_modern.png.

watchOS-Icons müssen opak sein (kein Alpha-Kanal); das System maskiert auf die
runde Form. icon_modern.png ist ein Kreis auf transparentem Grund — die
transparenten Ecken werden daher mit einer diagonalen Teal-Kulisse gefüllt,
deren Farben direkt aus dem Icon sampelt werden (passt zum Farbverlauf).

Aufruf:  python generate_watch_icon.py
Benötigt: Pillow (requirements-dev.txt)
"""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "icon_modern.png"
OUT_DIR = ROOT / "ios" / "WolManagerWatch" / "Assets.xcassets" / "AppIcon.appiconset"
SIZE = 1024


def sample_corner_colors(img: Image.Image) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    """Mittlere RGB-Farbe nahe dem Kreisrand oben-links und unten-rechts."""
    w, h = img.size
    r = w * 0.42  # sicher innerhalb des Kreises (Radius ~0.5*w)
    cx, cy = w / 2, h / 2

    def avg_at(px: int, py: int) -> tuple[int, int, int]:
        acc = [0, 0, 0]
        n = 0
        for dx in range(-6, 7, 2):
            for dy in range(-6, 7, 2):
                x, y = min(max(px + dx, 0), w - 1), min(max(py + dy, 0), h - 1)
                # Distanz zum Zentrum: nur innerhalb des Kreises sampeln
                if (x - cx) ** 2 + (y - cy) ** 2 > (w * 0.47) ** 2:
                    continue
                p = img.getpixel((x, y))
                if p[3] < 250:  # nur opake Pixel
                    continue
                acc[0] += p[0]
                acc[1] += p[1]
                acc[2] += p[2]
                n += 1
        return tuple(c // max(n, 1) for c in acc)  # type: ignore[return-value]

    import math

    off = r / math.sqrt(2)
    return avg_at(int(cx - off), int(cy - off)), avg_at(int(cx + off), int(cy + off))


def main() -> None:
    src = Image.open(SRC).convert("RGBA")
    icon = src.resize((SIZE, SIZE), Image.LANCZOS)

    c_tl, c_br = sample_corner_colors(src)
    print(f"Kulisse: oben-links {c_tl}, unten-rechts {c_br}")

    # Diagonaler Verlauf als Kulisse (entspricht dem Farbverlauf im Kreis).
    bg = Image.new("RGB", (SIZE, SIZE))
    draw = ImageDraw.Draw(bg)
    for y in range(SIZE):
        for_x = y / SIZE  # diagonale Mischung: x- und y-Anteil
        # einfache diagonale Interpolation über (x + y) / (2 * SIZE)
        row_a, row_b = c_tl, c_br
        # in 4er-Schritten Spalten mischen (schnell genug für 1024)
        strip = Image.new("RGB", (SIZE, 1))
        sdraw = ImageDraw.Draw(strip)
        for x0 in range(0, SIZE, 4):
            t = ((x0 + y) / (2 * SIZE)) ** 1.0
            col = tuple(round(a + (b - a) * t) for a, b in zip(row_a, row_b, strict=True))
            sdraw.rectangle([x0, 0, min(x0 + 3, SIZE - 1), 0], fill=col)  # type: ignore[arg-type]
        bg.paste(strip, (0, y))
    del draw

    canvas = Image.alpha_composite(bg.convert("RGBA"), icon).convert("RGB")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "AppIcon1024.png"
    canvas.save(out, "PNG")
    print(f"Geschrieben: {out.relative_to(ROOT)} ({SIZE}x{SIZE}, opak)")

    contents = {
        "images": [
            {
                "filename": "AppIcon1024.png",
                "idiom": "universal",
                "platform": "watchos",
                "size": "1024x1024",
            }
        ],
        "info": {"author": "xcode", "version": 1},
    }
    (OUT_DIR / "Contents.json").write_text(json.dumps(contents, indent=2) + "\n", encoding="utf-8")
    assets_root = OUT_DIR.parent  # Assets.xcassets
    (assets_root / "Contents.json").write_text(
        json.dumps({"info": {"author": "xcode", "version": 1}}, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Contents.json: {OUT_DIR.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
