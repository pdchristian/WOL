#!/usr/bin/env python3
"""Erzeugt das iOS-App-Icon (iOS 10+ Single-Size 1024x1024) vollflächig.

Vorbild ist das Android-Adaptive-Icon: Der Hintergrund ist der durchgehende
Teal-Verlauf aus `ic_launcher_background.png` (kein Kreis auf dunklem Grund),
darüber das weiße Symbol aus `ic_launcher_foreground.png`. Damit ist das
iOS-Icon farblich identisch mit dem Android-Icon.

iOS skaliert/maskiert die 1024px-Vorlage selbst (Squircle ohne Randzone), die
Datei muss opak sein (kein Alpha-Kanal). Die Android-Adaptive-Ebene liegt auf
einem 108-dp-Canvas mit 72-dp-Sichtzone; das Symbol wird daher auf die
iOS-typische Füllgröße gebracht, damit es nicht an den Rand gedrängt wirkt.

Aufruf:  python generate_ios_icon.py [--preview]
Optionen:
  --preview   schreibt zusätzlich Vorschauen (verschiedene Füllgrade) nach
              build/icon_preview/ statt das Asset zu überschreiben
Benötigt: Pillow (requirements-dev.txt)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent
BG_SRC = (
    ROOT
    / "android_html"
    / "app"
    / "src"
    / "main"
    / "res"
    / "drawable-nodpi"
    / "ic_launcher_background.png"
)
FG_SRC = (
    ROOT
    / "android_html"
    / "app"
    / "src"
    / "main"
    / "res"
    / "drawable-nodpi"
    / "ic_launcher_foreground.png"
)
OUT_DIR = ROOT / "ios" / "WolManager" / "Assets.xcassets" / "AppIcon.appiconset"
PREVIEW_DIR = ROOT / "build" / "icon_preview"
SIZE = 1024
# Symbolbreite als Anteil der Canvas-Kantenlänge (iOS-Standard: ~0.60).
SYMBOL_FILL = 0.61


def symbol_bbox(fg: Image.Image) -> tuple[int, int, int, int]:
    """Begrenzungsrahmen der deckenden Symbol-Pixel der Android-Vordergrundebene."""
    alpha = fg.getchannel("A")
    return alpha.getbbox() or (0, 0, fg.width, fg.height)


def render(fill: float = SYMBOL_FILL) -> Image.Image:
    """Volles 1024x1024-Icon: Android-Verlauf als Kulisse + weißes Symbol."""
    bg = Image.open(BG_SRC).convert("RGB").resize((SIZE, SIZE), Image.LANCZOS)

    fg = Image.open(FG_SRC).convert("RGBA")
    x0, _, x1, _ = symbol_bbox(fg)
    scale = (SIZE * fill) / (x1 - x0 + 1)
    layer = fg.resize(
        (max(1, round(fg.width * scale)), max(1, round(fg.height * scale))), Image.LANCZOS
    )

    # Symbolmittelpunkt exzentrisch auf Canvasmitte setzen.
    lx0, ly0, lx1, ly1 = symbol_bbox(layer)
    cx = (lx0 + lx1) / 2
    cy = (ly0 + ly1) / 2
    dx = round(SIZE / 2 - cx)
    dy = round(SIZE / 2 - cy)

    canvas = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    canvas.paste(layer, (dx, dy), layer)
    return Image.alpha_composite(bg.convert("RGBA"), canvas).convert("RGB")


def write_asset(icon: Image.Image) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "AppIcon1024.png"
    icon.save(out, "PNG")
    print(f"Geschrieben: {out.relative_to(ROOT)} ({SIZE}x{SIZE}, opak)")

    ensure_contents(
        OUT_DIR / "Contents.json",
        {
            "images": [
                {
                    "filename": "AppIcon1024.png",
                    "idiom": "universal",
                    "platform": "ios",
                    "size": "1024x1024",
                }
            ],
            "info": {"author": "xcode", "version": 1},
        },
    )
    ensure_contents(OUT_DIR.parent / "Contents.json", {"info": {"author": "xcode", "version": 1}})


def ensure_contents(path: Path, data: dict) -> None:
    """Schreibt Contents.json nur, wenn er inhaltlich abweicht (Xcode-Formatierung erhalten)."""
    if path.exists():
        try:
            if json.loads(path.read_text(encoding="utf-8")) == data:
                return
        except json.JSONDecodeError:
            pass
    path.write_text(json.dumps(data, indent=2, separators=(",", " : ")) + "\n", encoding="utf-8")
    print(f"Contents.json: {path.relative_to(ROOT)}")


def write_previews() -> None:
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    for fill in (0.55, 0.61, 0.72):
        icon = render(fill)
        out = PREVIEW_DIR / f"ios_icon_fill{int(fill * 100):02d}.png"
        icon.save(out, "PNG")
        thumb = ImageOps.fit(icon, (256, 256), Image.LANCZOS)
        thumb.save(PREVIEW_DIR / f"ios_icon_fill{int(fill * 100):02d}_256.png")
        print(f"Vorschau: {out.relative_to(ROOT)}")


def main() -> None:
    if "--preview" in sys.argv:
        write_previews()
        return
    write_asset(render())


if __name__ == "__main__":
    main()
