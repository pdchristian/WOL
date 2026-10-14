#!/usr/bin/env python3
"""Erzeugt das iOS-App-Icon (iOS 10+ Single-Size 1024x1024) vollflächig.

Vorbild ist das Android-Adaptive-Icon: Der Hintergrund ist der durchgehende
Teal-Verlauf aus `ic_launcher_background.png` (kein Kreis auf dunklem Grund),
darüber das weiße Symbol aus `ic_launcher_foreground.png`. Damit ist das
iOS-Icon farblich identisch mit dem Android-Icon.

iOS skaliert/maskiert die 1024px-Vorlage selbst (Squircle ohne Randzone), die
Datei muss opak sein (kein Alpha-Kanal). Größe und Position des Symbols folgen
der Android-Launcher-Darstellung: Der Adaptive-Layer liegt auf einem
108-dp-Canvas, von dem die Launcher nur die mittleren 72 dp zeigen. Dieses
Sichtzonen-Fenster wird auf das iOS-Canvas gelegt, dadurch wirken beide Icons
identisch. Die Kulisse nutzt weiterhin den kompletten Verlauf (iOS füllt die
ganze Fläche aus).

Aufruf:  python generate_ios_icon.py [--preview]
Optionen:
  --preview   schreibt Vorschauen (Android-Referenz, iOS, Gegenüberstellung)
              nach build/icon_preview/ statt das Asset zu überschreiben
Benötigt: Pillow (requirements-dev.txt)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image

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

# Android-Adaptive-Ebene: 108-dp-Canvas, von dem die Launcher nur die mittleren
# 72 dp zeigen. iOS maskiert die komplette Vorlage, also überträgt genau dieser
# Ausschnitt die Symbolgröße und -position auf das iOS-Icon.
ANDROID_CANVAS_DP = 108
ANDROID_VISIBLE_DP = 72
# Helligkeitsschwelle für das weiße Symbol (Teal-Kulisse liegt bei L ≈ 112).
SYMBOL_LUMINANCE = 200


def visible_zone(img: Image.Image) -> Image.Image:
    """Mittleres 72/108-Fenster eines Android-Adaptive-Canvases."""
    margin_x = img.width * (ANDROID_CANVAS_DP - ANDROID_VISIBLE_DP) / (2 * ANDROID_CANVAS_DP)
    margin_y = img.height * (ANDROID_CANVAS_DP - ANDROID_VISIBLE_DP) / (2 * ANDROID_CANVAS_DP)
    return img.crop(
        (
            round(margin_x),
            round(margin_y),
            round(img.width - margin_x),
            round(img.height - margin_y),
        )
    )


def render() -> Image.Image:
    """Volles 1024x1024-Icon: Android-Verlauf als Kulisse + weißes Symbol."""
    bg = Image.open(BG_SRC).convert("RGB").resize((SIZE, SIZE), Image.LANCZOS)

    fg = Image.open(FG_SRC).convert("RGBA")
    layer = visible_zone(fg).resize((SIZE, SIZE), Image.LANCZOS)
    return Image.alpha_composite(bg.convert("RGBA"), layer).convert("RGB")


def symbol_fill(icon: Image.Image) -> tuple[float, float]:
    """Anteil des Symbols an der Canvas-Kantenlänge (Breite, Höhe)."""
    bbox = icon.convert("L").point(lambda v: 255 if v > SYMBOL_LUMINANCE else 0).getbbox()
    if not bbox:
        return (0.0, 0.0)
    return ((bbox[2] - bbox[0]) / SIZE, (bbox[3] - bbox[1]) / SIZE)


def android_reference() -> Image.Image:
    """So baut der Launcher das Android-Icon: beide Ebenen, mittlere 72 dp sichtbar."""
    bg = Image.open(BG_SRC).convert("RGBA").resize((SIZE, SIZE), Image.LANCZOS)
    fg = Image.open(FG_SRC).convert("RGBA").resize((SIZE, SIZE), Image.LANCZOS)
    return visible_zone(Image.alpha_composite(bg, fg)).resize((SIZE, SIZE), Image.LANCZOS)


def write_asset(icon: Image.Image) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "AppIcon1024.png"
    icon.save(out, "PNG")
    aw, ah = symbol_fill(android_reference())
    w, h = symbol_fill(icon)
    print(f"Geschrieben: {out.relative_to(ROOT)} ({SIZE}x{SIZE}, opak)")
    print(
        f"Symbol-Füllgrad iOS: {w * 100:.1f} % Breite / {h * 100:.1f} % Höhe | "
        f"Android-Referenz: {aw * 100:.1f} % / {ah * 100:.1f} %"
    )

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
    """Android-Launcher-Referenz und iOS-Icon nebeneinander als Kontrolle."""
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)

    android = android_reference()
    ios = render()
    android.save(PREVIEW_DIR / "android_reference.png")
    ios.save(PREVIEW_DIR / "ios.png")

    thumb = 256
    sheet = Image.new("RGB", (thumb * 2, thumb), (255, 255, 255))
    sheet.paste(android.resize((thumb, thumb), Image.LANCZOS), (0, 0))
    sheet.paste(ios.resize((thumb, thumb), Image.LANCZOS), (thumb, 0))
    sheet.save(PREVIEW_DIR / "compare.png")
    print(
        f"Vorschau: {(PREVIEW_DIR / 'compare.png').relative_to(ROOT)} (links Android, rechts iOS)"
    )


def main() -> None:
    if "--preview" in sys.argv:
        write_previews()
        return
    write_asset(render())


if __name__ == "__main__":
    main()
