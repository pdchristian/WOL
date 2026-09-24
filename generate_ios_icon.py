#!/usr/bin/env python3
"""Erzeugt das iOS-App-Icon (1024x1024, opak) aus dem Watch-Icon.

Quelle ist das Watch-App-Icon (ios/WolManagerWatch/.../AppIcon1024.png,
generiert von generate_watch_icon.py aus icon_modern.png): Teal-Kreis mit
großem weißem Steckersymbol. Da iOS die Ecken der App-Icon-Form abschneidet,
wirkt der Kreis wie ein full-bleed Teal-Hintergrund.

Aufruf:  python generate_ios_icon.py   (setzt das Watch-Icon voraus; sonst
zuerst  python generate_watch_icon.py  laufen lassen)
Benötigt: Pillow (requirements-dev.txt)
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent
SRC = (
    ROOT / "ios" / "WolManagerWatch" / "Assets.xcassets" / "AppIcon.appiconset" / "AppIcon1024.png"
)
OUT_DIR = ROOT / "ios" / "WolManager" / "Assets.xcassets" / "AppIcon.appiconset"
SIZE = 1024


def main() -> None:
    if not SRC.exists():
        raise SystemExit(
            f"Watch-Icon fehlt: {SRC}\nBitte zuerst erzeugen:  python generate_watch_icon.py"
        )

    icon = Image.open(SRC).convert("RGBA")
    if icon.size != (SIZE, SIZE):
        icon = icon.resize((SIZE, SIZE), Image.LANCZOS)

    canvas = icon.convert("RGB")  # iOS verlangt opak; Quelle ist ohnehin opak

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "AppIcon1024.png"
    canvas.save(out, "PNG")
    print(f"Geschrieben: {out.relative_to(ROOT)} ({SIZE}x{SIZE}, opak) — Quelle: {SRC.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
