"""Display mode (theme) handling and design system for the Wake-on-LAN application."""

import os
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon, QPalette
from PyQt6.QtWidgets import QApplication

from wol_app.utils import get_resource_path


# ---------------------------------------------------------------------------
# Design tokens (shared across light & dark so widget code uses one source)
# ---------------------------------------------------------------------------
ACCENT = "#0f8ff8"          # primary action colour (Wake, primary buttons)
ACCENT_DARK = "#0b74cc"
SUCCESS = "#2e9e5b"         # online / success
WARNING = "#e0a21c"         # unknown / pending
DANGER = "#d64545"          # offline / error
SIDEBAR_WIDTH = 200
BORDER_RADIUS = 6


def _tokens(dark: bool) -> dict[str, str]:
    """Return colour tokens for the given colour scheme."""
    if dark:
        return {
            "bg": "#1e1e24",
            "surface": "#2a2a32",
            "surface_alt": "#33333d",
            "border": "#3d3d49",
            "text": "#e6e6eb",
            "text_muted": "#9a9aa8",
            "sidebar": "#23232b",
            "sidebar_active": "#2f3550",
            "accent": ACCENT,
        }
    return {
        "bg": "#f4f5f7",
        "surface": "#ffffff",
        "surface_alt": "#f0f1f4",
        "border": "#dcdfe6",
        "text": "#23262e",
        "text_muted": "#6b7180",
        "sidebar": "#eceef2",
        "sidebar_active": "#e1e9f5",
        "accent": "#0f6fd8",
    }


def _build_stylesheet(t: dict[str, str]) -> str:
    """Build a modern Fusion stylesheet from colour tokens."""
    return f"""
QMainWindow, QDialog {{
    background-color: {t['bg']};
    color: {t['text']};
}}
QWidget {{
    color: {t['text']};
}}
QLabel {{
    background: transparent;
}}

/* --- Sidebar --- */
QListWidget#sidebar {{
    background-color: {t['sidebar']};
    border: none;
    outline: none;
    padding: 8px 6px;
}}
QListWidget#sidebar::item {{
    color: {t['text']};
    border-radius: {BORDER_RADIUS}px;
    padding: 9px 12px;
    margin: 2px 2px;
}}
QListWidget#sidebar::item:selected {{
    background-color: {t['accent']};
    color: #ffffff;
}}
QListWidget#sidebar::item:hover:!selected {{
    background-color: {t['surface_alt']};
}}

/* --- Cards / groups --- */
QGroupBox {{
    background-color: {t['surface']};
    border: 1px solid {t['border']};
    border-radius: {BORDER_RADIUS}px;
    margin-top: 14px;
    padding: 10px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 4px;
    color: {t['text_muted']};
    font-weight: 600;
}}

/* --- Inputs --- */
QLineEdit, QComboBox, QSpinBox, QTextEdit, QPlainTextEdit {{
    background-color: {t['surface_alt']};
    border: 1px solid {t['border']};
    border-radius: {BORDER_RADIUS}px;
    padding: 5px 8px;
    color: {t['text']};
    selection-background-color: {t['accent']};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{
    border: 1px solid {t['accent']};
}}

/* --- Table --- */
QTableWidget, QTreeWidget, QTableView {{
    background-color: {t['surface']};
    alternate-background-color: {t['surface_alt']};
    border: 1px solid {t['border']};
    border-radius: {BORDER_RADIUS}px;
    gridline-color: {t['border']};
    selection-background-color: {t['accent']};
    selection-color: #ffffff;
}}
QHeaderView::section {{
    background-color: {t['surface_alt']};
    color: {t['text_muted']};
    border: none;
    border-bottom: 1px solid {t['border']};
    padding: 6px;
    font-weight: 600;
}}

/* --- Buttons --- */
QPushButton {{
    background-color: {t['surface_alt']};
    border: 1px solid {t['border']};
    border-radius: {BORDER_RADIUS}px;
    padding: 6px 14px;
    color: {t['text']};
}}
QPushButton:hover {{
    background-color: {t['border']};
}}
QPushButton:pressed {{
    background-color: {t['surface_alt']};
}}
QPushButton:disabled {{
    color: {t['text_muted']};
}}
QPushButton#primaryButton {{
    background-color: {t['accent']};
    border: none;
    color: #ffffff;
    font-weight: 600;
}}
QPushButton#primaryButton:hover {{
    background-color: {ACCENT_DARK};
}}
QPushButton#dangerButton {{
    background-color: transparent;
    border: 1px solid {DANGER};
    color: {DANGER};
}}
QPushButton#dangerButton:hover {{
    background-color: {DANGER};
    color: #ffffff;
}}

/* --- Scrollbars --- */
QScrollBar:vertical {{
    background: {t['surface']};
    width: 10px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {t['border']};
    border-radius: 5px;
    min-height: 30px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: transparent;
}}

QMenuBar {{
    background-color: {t['sidebar']};
    color: {t['text']};
}}
QMenuBar::item:selected {{
    background-color: {t['surface_alt']};
}}
QMenu {{
    background-color: {t['surface']};
    color: {t['text']};
    border: 1px solid {t['border']};
}}
QMenu::item:selected {{
    background-color: {t['accent']};
    color: #ffffff;
}}
QStatusBar {{
    background-color: {t['sidebar']};
    color: {t['text_muted']};
}}
"""


def _system_uses_dark() -> bool:
    """Detect the OS color scheme.

    On Windows the registry value ``AppsUseLightTheme`` is authoritative.
    Falls back to Qt's default palette hint on other platforms.
    """
    if sys.platform == "win32":
        try:
            import winreg

            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            )
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return value == 0
        except OSError:
            pass

    app = QApplication.instance()
    if app is not None:
        return app.palette().color(QPalette.ColorRole.Window).lightness() < 128
    return False


def _dark_palette() -> QPalette:
    """Return a fully dark palette with readable text."""
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.Base, QColor(35, 35, 35))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.Text, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 0, 0))
    palette.setColor(QPalette.ColorRole.Link, QColor(0, 188, 212))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(0, 188, 212))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(0, 0, 0))
    return palette


def _light_palette() -> QPalette:
    """Return an explicit light palette (independent of the OS scheme)."""
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(240, 240, 240))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(0, 0, 0))
    palette.setColor(QPalette.ColorRole.Base, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(248, 248, 248))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(0, 0, 0))
    palette.setColor(QPalette.ColorRole.Text, QColor(0, 0, 0))
    palette.setColor(QPalette.ColorRole.Button, QColor(240, 240, 240))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(0, 0, 0))
    palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 0, 0))
    palette.setColor(QPalette.ColorRole.Link, QColor(0, 120, 215))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(0, 120, 215))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    return palette


def apply_display_mode(app: QApplication, mode: str) -> None:
    """Apply the selected display mode via a Fusion palette.

    ``auto`` follows the OS color scheme, ``light`` forces a light palette,
    and ``dark`` forces a dark palette.
    """
    if mode == "dark":
        dark = True
    elif mode == "light":
        dark = False
    else:  # auto
        dark = _system_uses_dark()

    tokens = _tokens(dark)
    if dark:
        app.setPalette(_dark_palette())
    else:
        app.setPalette(_light_palette())
    app.setStyleSheet(_build_stylesheet(tokens))


# Base stylesheet that overrides OS-default colors for the most common widgets.
# Kept minimal so it does not interfere with widget-specific stylesheets.
_DARK_STYLESHEET = ""
_LIGHT_STYLESHEET = ""


def get_icon(name: str, dark: bool | None = None, size: int = 18) -> QIcon:
    """Load an SVG icon from the bundled assets and tint it for the theme.

    Icons are stored as SVG with the literal placeholder ``ICON_COLOR`` where
    the stroke/fill colour should be theme-dependent. The current scheme
    (or the caller-supplied ``dark`` flag) decides the final colour.

    Returns an empty QIcon if the icon file is missing.
    """
    if dark is None:
        app = QApplication.instance()
        dark = False
        if app is not None:
            dark = app.palette().color(QPalette.ColorRole.Window).lightness() < 128
    color = _tokens(dark)["text"]
    if dark:
        # muted icons look better on dark surfaces
        color = "#c9c9d1"

    path = get_resource_path(os.path.join("assets", "icons", f"{name}.svg"))
    if not os.path.exists(path):
        return QIcon()
    try:
        with open(path, "r", encoding="utf-8") as fh:
            svg = fh.read()
    except OSError:
        return QIcon()
    svg = svg.replace("ICON_COLOR", color)
    return QIcon(svg)


def status_badge_colors(status: str) -> tuple[str, str]:
    """Return (foreground, background) CSS colours for a status badge.

    *status* is one of ``online``, ``offline``, ``unknown`` (or anything
    else, which is treated as ``unknown``).
    """
    if status == "online":
        return "#ffffff", SUCCESS
    if status == "offline":
        return "#ffffff", DANGER
    return "#23262e", WARNING
