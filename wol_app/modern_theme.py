"""Stylesheet for the modern "Dark Control Center" UI.

Color tokens mirror the design prototype
(Design_Prototpye/dark_control_center_full.html). A light variant is
provided for ``ui.display_mode == "light"`` so the modern layout respects
the existing display-mode setting.

All rules are objectName-based (``#sidebar``, ``#navItem``, ``#panel`` …)
so they only affect widgets of the modern window and never leak into the
classic UI or the shared dialogs.
"""

import os
import tempfile

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QApplication

from wol_app.utils import get_resource_path

_ARROW_DIR = os.path.join(tempfile.gettempdir(), "wol_modern_arrows")


def app_icon_pixmap(size: int) -> QPixmap | None:
    """Load the app logo scaled to ``size``×``size`` (or None).

    Used for the in-app logo tiles (sidebar + about screen). Prefers the
    high-resolution ``icon_modern.png`` and falls back to the ``.ico``
    variants when the PNG is not bundled.
    """
    for name in ("icon_modern.png", "icon_modern.ico", "icon.ico"):
        path = get_resource_path(name)
        if os.path.exists(path):
            pix = QPixmap(path)
            if not pix.isNull():
                return pix.scaled(
                    size, size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
    return None


def _svg_url(name: str, svg: str) -> str:
    """Write an SVG once to the shared temp dir and return its file URL.

    Forward slashes: backslashes are escape characters inside QSS url()
    strings, while Qt on Windows accepts '/' in file paths.
    """
    os.makedirs(_ARROW_DIR, exist_ok=True)
    path = os.path.join(_ARROW_DIR, name)
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            f.write(svg)
    return path.replace("\\", "/")


def _arrow_url(direction: str, color: str) -> str:
    """Return a file URL of a chevron SVG for spinbox/combobox arrows.

    Qt6 does not render the CSS border-triangle trick for
    ``QSpinBox::up-arrow`` / ``QComboBox::down-arrow`` (it shows a
    filled rectangle instead), so the arrows are drawn as small SVG
    chevrons that the QSS references via ``image: url(...)``.
    The PyQt6 venv ships qsvg.dll, so SVG images work in QSS.
    """
    if direction == "up":
        d = "M2 6.5 L5 3.5 L8 6.5"
    else:
        d = "M2 3.5 L5 6.5 L8 3.5"
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">'
        f'<path d="{d}" fill="none" stroke="{color}" stroke-width="1.6" '
        'stroke-linecap="round" stroke-linejoin="round"/></svg>'
    )
    return _svg_url(f"chevron_{direction}_{color.lstrip('#')}.svg", svg)


def _checkmark_url(color: str) -> str:
    """Return a file URL of a checkmark SVG for checked checkbox indicators."""
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" '
        'viewBox="0 0 12 12">'
        f'<path d="M2.5 6.5 L5 9 L9.5 3.5" fill="none" stroke="{color}" '
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        "</svg>"
    )
    return _svg_url(f"checkmark_{color.lstrip('#')}.svg", svg)


# ── Dark tokens (prototype) ──────────────────────────────────────────────
DARK = {
    "bg": "#0f1115",
    "surface": "#1a1d24",
    "surface_hover": "#232733",
    "border": "#2c303a",
    "text": "#e6e8ee",
    "text_dim": "#9aa0ab",
    "accent": "#00b8a9",
    "accent_dark": "#006b63",
    "accent_text": "#032019",
    "online": "#22c55e",
    "offline": "#ef4444",
    "unknown": "#f59e0b",
    "danger": "#e0485a",
    "blue": "#60a5fa",
}

# ── Light variant (same structure, light surfaces) ───────────────────────
LIGHT = {
    "bg": "#f3f4f7",
    "surface": "#ffffff",
    "surface_hover": "#eef0f4",
    "border": "#d8dbe2",
    "text": "#1b1e24",
    "text_dim": "#5b6270",
    "accent": "#009688",
    "accent_dark": "#00695f",
    "accent_text": "#ffffff",
    "online": "#16a34a",
    "offline": "#dc2626",
    "unknown": "#d97706",
    "danger": "#dc2637",
    "blue": "#2563eb",
}


def modern_stylesheet(t: dict) -> str:
    """Build the QSS for the modern UI from a token dict."""
    return f"""
/* ── Window base ─────────────────────────────────────────────────────── */
QMainWindow, #modernCentral {{ background: {t['bg']}; }}
QWidget {{ color: {t['text']}; font-family: "Segoe UI", sans-serif; font-size: 13px; }}
/* ── Sidebar ─────────────────────────────────────────────────────────── */
#sidebar {{
    background: {t['surface']};
    border-right: 1px solid {t['border']};
}}
#logoMark {{
    background: transparent;
}}
#logoText {{ color: {t['text']}; font-weight: 600; font-size: 15px; }}
#sectionLabel {{
    color: {t['text_dim']}; font-size: 10px; font-weight: 600;
    letter-spacing: 1px; padding: 8px 12px 4px 12px;
}}
#navItem {{
    background: transparent; border: none; text-align: left;
    padding: 10px 12px; border-radius: 10px;
    color: {t['text_dim']}; font-size: 14px;
}}
#navItem:hover {{ background: {t['surface_hover']}; color: {t['text']}; }}
#navItem:checked {{
    background: rgba(0, 184, 169, 0.14); color: {t['accent']}; font-weight: 600;
}}
#navSeparator {{ background: {t['border']}; max-height: 1px; border: none; }}

/* ── Page header ─────────────────────────────────────────────────────── */
#pageTitle {{ font-size: 21px; font-weight: 600; color: {t['text']}; }}
#pageSubtitle {{ color: {t['text_dim']}; font-size: 12px; }}
#sectionHeading {{
    color: {t['text_dim']}; font-size: 14px; font-weight: 600;
    margin-top: 8px;
}}

/* ── Buttons ─────────────────────────────────────────────────────────── */
QPushButton {{
    background: {t['surface']}; color: {t['text']};
    border: 1px solid {t['border']}; border-radius: 9px;
    padding: 8px 14px; font-size: 13px; font-weight: 600;
}}
QPushButton:hover {{ background: {t['surface_hover']}; }}
QPushButton:disabled {{ color: {t['text_dim']}; }}
QPushButton#primaryButton {{
    background: {t['accent']}; color: {t['accent_text']}; border: none;
}}
QPushButton#primaryButton:hover {{ background: {t['accent_dark']}; color: #ffffff; }}
QPushButton#primaryButton:disabled {{ background: {t['border']}; color: {t['text_dim']}; }}
QPushButton#dangerButton {{
    background: transparent; color: {t['danger']};
    border: 1px solid {t['danger']};
}}
QPushButton#dangerButton:hover {{ background: {t['danger']}; color: #ffffff; }}
QPushButton#wakeButton {{
    background: transparent; color: {t['accent']};
    border: 1px solid {t['accent']}; border-radius: 8px;
    padding: 5px 12px; font-size: 12px;
}}
QPushButton#wakeButton:hover {{ background: {t['accent']}; color: {t['accent_text']}; }}
/* Card action button while the device is online (prototype .btn.danger) */
QPushButton#shutdownButton {{
    background: transparent; color: {t['danger']};
    border: 1px solid {t['danger']}; border-radius: 8px;
    padding: 5px 12px; font-size: 12px;
}}
QPushButton#shutdownButton:hover {{ background: {t['danger']}; color: #ffffff; }}
QPushButton#shutdownButton:disabled {{ color: {t['text_dim']}; border-color: {t['border']}; }}
QPushButton#iconBtn {{
    background: transparent; border: none; padding: 4px 8px;
    font-size: 14px; border-radius: 8px;
}}
QPushButton#iconBtn:hover {{ background: {t['surface_hover']}; }}

/* ── Dialogs (QDialog / QMessageBox) ─────────────────────────────────── */
/* Without these rules every QDialog falls back to the native gray system
   palette, which clashes with the control-center look. Dialogs use the
   window background (bg) so they read as a continuation of the main
   window; inputs (surface) stand out against it. */
QDialog {{ background: {t['bg']}; }}
QMessageBox {{ background: {t['bg']}; }}
QMessageBox QLabel {{ color: {t['text']}; background: transparent; }}

/* ── Panels / cards ──────────────────────────────────────────────────── */
#panel {{
    background: {t['surface']};
    border: 1px solid {t['border']}; border-radius: 14px;
}}
#deviceGrid {{ background: transparent; }}
/* Device status cards (prototype .card): surface tile, accent hover border */
#deviceCard {{
    background: {t['surface']};
    border: 1px solid {t['border']}; border-radius: 14px;
}}
#deviceCard:hover {{
    background: {t['surface_hover']}; border-color: {t['accent']};
}}
#scanRow, #deviceRow, #scheduleRow, #logRow {{ background: transparent; }}
#scanRow:hover, #deviceRow:hover, #scheduleRow:hover, #logRow:hover {{ background: {t['surface_hover']}; }}
#rowSeparator {{ background: {t['border']}; max-height: 1px; border: none; }}
#rowTitle {{ color: {t['text']}; font-size: 14px; font-weight: 600; }}
#rowTitleDisabled {{ color: {t['text_dim']}; font-size: 14px; font-weight: 600; }}
#rowMono {{
    color: {t['text_dim']}; font-family: Consolas, monospace; font-size: 12px;
}}

/* ── Status tiles (badges) ───────────────────────────────────────────── */
#badgeOnline, #badgeOffline, #badgeUnknown {{
    border-radius: 10px; padding: 0 10px;
    font-size: 12px; font-weight: 600;
}}
#badgeOnline {{ background: rgba(34, 197, 94, 0.15); color: {t['online']}; }}
#badgeOffline {{ background: rgba(239, 68, 68, 0.15); color: {t['offline']}; }}
#badgeUnknown {{ background: rgba(245, 158, 11, 0.15); color: {t['unknown']}; }}

/* ── Log level badges (prototype .level) ─────────────────────────────── */
#badgeInfo, #badgeWarn, #badgeError {{
    border-radius: 6px; padding: 0 8px;
    font-size: 11px; font-weight: 700;
}}
#badgeInfo {{ background: rgba(59, 130, 246, 0.15); color: {t['blue']}; }}
#badgeWarn {{ background: rgba(245, 158, 11, 0.15); color: {t['unknown']}; }}
#badgeError {{ background: rgba(239, 68, 68, 0.15); color: {t['offline']}; }}
#logTime {{
    color: {t['text_dim']}; font-family: Consolas, monospace; font-size: 12px;
}}
#logDevice {{ color: {t['text_dim']}; font-size: 13px; }}
#logMsg {{ color: {t['text']}; font-size: 13px; }}

/* ── Action tiles (edit / delete) ────────────────────────────────────── */
QPushButton#tileButton, QPushButton#tileDanger {{
    background: {t['surface_hover']}; color: {t['text_dim']};
    border: 1px solid {t['border']}; border-radius: 10px;
    padding: 0px; font-size: 14px;
}}
QPushButton#tileButton:hover {{
    background: {t['accent']}; color: {t['accent_text']};
    border: 1px solid {t['accent']};
}}
QPushButton#tileDanger:hover {{
    background: {t['danger']}; color: #ffffff;
    border: 1px solid {t['danger']};
}}

/* ── Status dots ─────────────────────────────────────────────────────── */
#dotOnline {{ background: {t['online']}; border-radius: 5px; max-width: 10px; max-height: 10px; }}
#dotOffline {{ background: {t['offline']}; border-radius: 5px; max-width: 10px; max-height: 10px; }}
#dotUnknown {{ background: {t['unknown']}; border-radius: 5px; max-width: 10px; max-height: 10px; }}

/* ── Inputs ──────────────────────────────────────────────────────────── */
#fieldLabel {{
    color: {t['text_dim']}; font-size: 12px;
}}
#fieldHint {{ color: {t['text_dim']}; font-size: 12px; }}
QLineEdit, QComboBox, QSpinBox {{
    background: {t['surface']}; color: {t['text']};
    border: 1px solid {t['border']}; border-radius: 10px;
    padding: 8px 12px; selection-background-color: {t['accent']};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{ border-color: {t['accent']}; }}
QLineEdit{{ placeholder-text-color: {t['text_dim']}; }}
/* ComboBox: no visible border around the drop-down zone, chevron on the
   right (Qt6 needs an image for ::down-arrow — border-triangles render as
   rectangles). */
QComboBox::drop-down {{
    subcontrol-origin: padding; subcontrol-position: top right;
    border: none; width: 24px;
}}
QComboBox::down-arrow {{
    width: 10px; height: 10px;
    image: url("{_arrow_url('down', t['text_dim'])}");
}}
QComboBox:focus {{
    border-color: {t['accent']};
}}

/* SpinBox up/down buttons (custom QSS hides the native arrows otherwise).
   Arrows are chevron SVGs referenced via image — the border-triangle trick
   renders as a rectangle under Qt6. */
QSpinBox::up-button {{
    subcontrol-origin: border; subcontrol-position: top right;
    width: 20px; border-left: 1px solid {t['border']};
    border-top-right-radius: 9px; background: transparent;
}}
QSpinBox::down-button {{
    subcontrol-origin: border; subcontrol-position: bottom right;
    width: 20px; border-left: 1px solid {t['border']};
    border-bottom-right-radius: 9px; background: transparent;
}}
QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
    background: {t['surface_hover']};
}}
QSpinBox::up-arrow {{
    width: 10px; height: 10px;
    image: url("{_arrow_url('up', t['text_dim'])}");
}}
QSpinBox::down-arrow {{
    width: 10px; height: 10px;
    image: url("{_arrow_url('down', t['text_dim'])}");
}}
QComboBox QAbstractItemView {{
    background: {t['surface']}; border: 1px solid {t['border']};
    selection-background-color: {t['surface_hover']};
}}
QCheckBox {{ color: {t['text']}; spacing: 8px; background: transparent; }}
QCheckBox::indicator {{
    width: 16px; height: 16px; border-radius: 4px;
    border: 1px solid {t['border']}; background: {t['surface']};
}}
QCheckBox::indicator:checked {{
    background: {t['accent']}; border-color: {t['accent']};
    image: url("{_checkmark_url(t['accent_text'])}");
}}

/* ── Progress bar ────────────────────────────────────────────────────── */
QProgressBar {{
    background: {t['surface']}; border: 1px solid {t['border']};
    border-radius: 8px; height: 10px; text-align: center;
    color: {t['text_dim']};
}}
QProgressBar::chunk {{ background: {t['accent']}; border-radius: 8px; }}

/* ── Scrollbars / scroll areas ───────────────────────────────────────── */
QStackedWidget {{ background: {t['bg']}; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget {{ background: {t['bg']}; }}
QScrollArea > QWidget > QWidget {{ background: {t['bg']}; }}
#pageContent {{ background: {t['bg']}; }}
QScrollBar:vertical {{
    background: transparent; width: 10px; margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {t['border']}; border-radius: 4px; min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: {t['text_dim']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{
    background: {t['border']}; border-radius: 4px; min-width: 30px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* ── Tooltip / menu ──────────────────────────────────────────────────── */
QToolTip {{
    background: {t['surface_hover']}; color: {t['text']};
    border: 1px solid {t['border']}; border-radius: 6px; padding: 4px 8px;
}}
QMenu {{
    background: {t['surface']}; border: 1px solid {t['border']}; border-radius: 10px;
    padding: 6px;
}}
QMenu::item {{ padding: 8px 24px; border-radius: 8px; }}
QMenu::item:selected {{ background: {t['surface_hover']}; color: {t['accent']}; }}

/* ── Placeholder screens ─────────────────────────────────────────────── */
#placeholderIcon {{ font-size: 42px; }}
#placeholderText {{ color: {t['text_dim']}; font-size: 14px; }}

/* ── About / update screen (prototype .about) ────────────────────────── */
#aboutLogo {{
    background: transparent;
}}
#aboutTitle {{ color: {t['text']}; font-size: 24px; font-weight: 600; }}
#aboutVersion {{ color: {t['text_dim']}; font-size: 14px; }}
#aboutText {{ color: {t['text_dim']}; font-size: 13px; }}
#updateStatus {{ color: {t['text_dim']}; font-size: 13px; }}
"""


def apply_modern_theme(app: QApplication, dark: bool) -> None:
    """Apply the modern control-center stylesheet to the application."""
    global _current_tokens
    _current_tokens = DARK if dark else LIGHT
    app.setStyleSheet(modern_stylesheet(_current_tokens))


# Token set of the most recently applied modern theme; custom-painted
# widgets (e.g. ToggleSwitch) read their colors from here.
_current_tokens: dict = DARK


def current_tokens() -> dict:
    """Return the color tokens of the currently applied modern theme."""
    return _current_tokens
