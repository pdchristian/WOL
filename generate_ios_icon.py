#!/usr/bin/env python3
"""Erzeugt das iOS-App-Icon (1024x1024, opak) aus den Android-Icon-Layern.

Übernimmt das Icon der Android-App: den full-bleed Teal-Verlauf
(ic_launcher_background.png) plus das weiße Steckersymbol
(ic_launcher_foreground.png) in denselben Proportionen.

Aufruf:  python generate_ios_icon.py
Benötigt: Pillow (requirements-dev.txt)
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent
ANDROID_RES = ROOT / "android_html" / "app" / "src" / "main" / "res" / "drawable-nodpi"
BG_SRC = ANDROID_RES / "ic_launcher_background.png"
FG_SRC = ANDROID_RES / "ic_launcher_foreground.png"
OUT_DIR = ROOT / "ios" / "WolManager" / "Assets.xcassets" / "AppIcon.appiconset"
SIZE = 1024


def main() -> None:
    for src in (BG_SRC, FG_SRC):
        if not src.exists():
            raise SystemExit(f"Android-Icon fehlt: {src}")

    # Hintergrund: full-bleed Verlauf, auf iOS-Größe skaliert.
    bg = Image.open(BG_SRC).convert("RGBA").resize((SIZE, SIZE), Image.LANCZOS)

    # Vordergrund: weißes Symbol auf transparentem Grund — gleiche relative
    # Proportionen wie in Androids Adaptive Icon (Symbol ~56 % der Kantenlänge).
    fg = Image.open(FG_SRC).convert("RGBA").resize((SIZE, SIZE), Image.LANCZOS)

    canvas = Image.alpha_composite(bg, fg).convert("RGB")  # iOS verlangt opak

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "AppIcon1024.png"
    canvas.save(out, "PNG")
    print(f"Geschrieben: {out.relative_to(ROOT)} ({SIZE}x{SIZE}, opak)")


if __name__ == "__main__":
    main()
