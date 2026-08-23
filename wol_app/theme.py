"""Display mode (theme) handling for the Wake-on-LAN application.

Provides the light/dark palettes, the application-wide stylesheet (design
system), a bundled SVG icon loader, and status-badge color helpers.
"""

import os
import sys

from PyQt6.QtCore import QByteArray, Qt
from PyQt6.QtGui import QColor, QIcon, QPalette, QPixmap
from PyQt6.QtWidgets import QApplication


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
    palette.setColor(QPalette.ColorRole.Window, QColor(30, 31, 36))        # #1e1f24
    palette.setColor(QPalette.ColorRole.WindowText, QColor(229, 231, 235))  # #e5e7eb
    palette.setColor(QPalette.ColorRole.Base, QColor(38, 39, 46))           # #26272e
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(30, 31, 36))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(229, 231, 235))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(30, 31, 36))
    palette.setColor(QPalette.ColorRole.Text, QColor(229, 231, 235))
    palette.setColor(QPalette.ColorRole.Button, QColor(38, 39, 46))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(229, 231, 235))
    palette.setColor(QPalette.ColorRole.BrightText, QColor(239, 68, 68))
    palette.setColor(QPalette.ColorRole.Link, QColor(59, 130, 246))         # #3b82f6
    palette.setColor(QPalette.ColorRole.Highlight, QColor(59, 130, 246))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    return palette


def _light_palette() -> QPalette:
    """Return an explicit light palette (independent of the OS scheme)."""
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(245, 246, 248))      # #f5f6f8
    palette.setColor(QPalette.ColorRole.WindowText, QColor(31, 41, 55))     # #1f2937
    palette.setColor(QPalette.ColorRole.Base, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(245, 246, 248))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(31, 41, 55))
    palette.setColor(QPalette.ColorRole.Text, QColor(31, 41, 55))
    palette.setColor(QPalette.ColorRole.Button, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(31, 41, 55))
    palette.setColor(QPalette.ColorRole.BrightText, QColor(220, 38, 38))
    palette.setColor(QPalette.ColorRole.Link, QColor(37, 99, 235))          # #2563eb
    palette.setColor(QPalette.ColorRole.Highlight, QColor(37, 99, 235))
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

    if dark:
        app.setPalette(_dark_palette())
        app.setStyleSheet(_DARK_STYLESHEET)
    else:
        app.setPalette(_light_palette())
        app.setStyleSheet(_LIGHT_STYLESHEET)


# ── Design-system color tokens ──────────────────────────────────────────────

_LIGHT_COLORS = {
    "bg": "#f5f6f8",
    "card": "#ffffff",
    "text": "#1f2937",
    "text_muted": "#6b7280",
    "accent": "#2563eb",
    "accent_hover": "#1d4ed8",
    "accent_pressed": "#1e40af",
    "success": "#16a34a",
    "danger": "#dc2626",
    "danger_hover": "#b91c1c",
    "warning": "#d97706",
    "border": "#e5e7eb",
    "row_alt": "#f9fafb",
    "row_hover": "#eff6ff",
    "sidebar_bg": "#ffffff",
    "sidebar_hover": "#f3f4f6",
    "sidebar_active": "#dbeafe",
    "input_bg": "#ffffff",
    "badge_success_bg": "#dcfce7",
    "badge_success_fg": "#166534",
    "badge_danger_bg": "#fee2e2",
    "badge_danger_fg": "#991b1b",
    "badge_warning_bg": "#fef3c7",
    "badge_warning_fg": "#92400e",
}

_DARK_COLORS = {
    "bg": "#1e1f24",
    "card": "#26272e",
    "text": "#e5e7eb",
    "text_muted": "#9ca3af",
    "accent": "#3b82f6",
    "accent_hover": "#2563eb",
    "accent_pressed": "#1d4ed8",
    "success": "#22c55e",
    "danger": "#ef4444",
    "danger_hover": "#dc2626",
    "warning": "#f59e0b",
    "border": "#3a3b41",
    "row_alt": "#232429",
    "row_hover": "#1e3a5f",
    "sidebar_bg": "#1a1b1f",
    "sidebar_hover": "#2a2b31",
    "sidebar_active": "#1e3a5f",
    "input_bg": "#1e1f24",
    "badge_success_bg": "#14532d",
    "badge_success_fg": "#86efac",
    "badge_danger_bg": "#7f1d1d",
    "badge_danger_fg": "#fecaca",
    "badge_warning_bg": "#78350f",
    "badge_warning_fg": "#fde68a",
}


def _build_stylesheet(c: dict) -> str:
    """Build the application stylesheet from a color-token dict."""
    return f"""
QMainWindow, QDialog {{
    background-color: {c['bg']};
    color: {c['text']};
}}
QWidget#Sidebar {{
    background-color: {c['sidebar_bg']};
    border-right: 1px solid {c['border']};
}}
QLabel {{
    color: {c['text']};
    background: transparent;
}}
QLabel#SidebarTitle {{
    font-size: 15px;
    font-weight: 600;
    color: {c['text']};
    padding: 4px;
}}
QLabel#SidebarSubtitle {{
    font-size: 11px;
    color: {c['text_muted']};
    padding: 0 4px 12px 4px;
}}
QToolButton#sidebarButton {{
    text-align: left;
    padding: 9px 12px;
    margin: 2px 6px;
    border: none;
    border-radius: 6px;
    background: transparent;
    color: {c['text']};
    font-size: 13px;
}}
QToolButton#sidebarButton:hover {{
    background-color: {c['sidebar_hover']};
}}
QToolButton#sidebarButton:checked {{
    background-color: {c['sidebar_active']};
    color: {c['accent']};
    font-weight: 600;
}}
QGroupBox {{
    background-color: {c['card']};
    border: 1px solid {c['border']};
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 14px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 4px;
    color: {c['text_muted']};
    font-size: 12px;
}}
QPushButton {{
    background-color: {c['card']};
    color: {c['text']};
    border: 1px solid {c['border']};
    border-radius: 6px;
    padding: 7px 14px;
    min-height: 18px;
}}
QPushButton:hover {{
    background-color: {c['sidebar_hover']};
    border-color: {c['text_muted']};
}}
QPushButton:pressed {{
    background-color: {c['row_alt']};
}}
QPushButton:disabled {{
    color: {c['text_muted']};
    border-color: {c['border']};
    background-color: {c['bg']};
}}
QPushButton#primaryButton {{
    background-color: {c['accent']};
    color: #ffffff;
    border: none;
    font-weight: 600;
}}
QPushButton#primaryButton:hover {{
    background-color: {c['accent_hover']};
}}
QPushButton#primaryButton:pressed {{
    background-color: {c['accent_pressed']};
}}
QPushButton#primaryButton:disabled {{
    background-color: {c['border']};
    color: {c['text_muted']};
}}
QPushButton#dangerButton {{
    background-color: {c['danger']};
    color: #ffffff;
    border: none;
    font-weight: 600;
}}
QPushButton#dangerButton:hover {{
    background-color: {c['danger_hover']};
}}
QTableWidget, QTableView {{
    background-color: {c['card']};
    alternate-background-color: {c['row_alt']};
    gridline-color: {c['border']};
    border: 1px solid {c['border']};
    border-radius: 8px;
    color: {c['text']};
    selection-background-color: {c['accent']};
    selection-color: #ffffff;
}}
QTableWidget::item {{
    padding: 4px;
    border: none;
}}
QTableWidget::item:selected {{
    background-color: {c['accent']};
    color: #ffffff;
}}
QHeaderView::section {{
    background-color: {c['card']};
    color: {c['text_muted']};
    border: none;
    border-bottom: 1px solid {c['border']};
    padding: 6px 8px;
    font-weight: 600;
    font-size: 12px;
}}
QLineEdit, QComboBox, QSpinBox, QPlainTextEdit, QTextEdit {{
    background-color: {c['input_bg']};
    color: {c['text']};
    border: 1px solid {c['border']};
    border-radius: 6px;
    padding: 5px 8px;
    selection-background-color: {c['accent']};
    selection-color: #ffffff;
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{
    border: 1px solid {c['accent']};
}}
QComboBox::drop-down {{
    border: none;
    width: 22px;
}}
QComboBox QAbstractItemView {{
    background-color: {c['card']};
    color: {c['text']};
    selection-background-color: {c['accent']};
    selection-color: #ffffff;
    border: 1px solid {c['border']};
}}
QCheckBox {{
    color: {c['text']};
    spacing: 8px;
    background: transparent;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {c['border']};
    border-radius: 4px;
    background-color: {c['input_bg']};
}}
QCheckBox::indicator:checked {{
    background-color: {c['accent']};
    border-color: {c['accent']};
}}
QStatusBar {{
    background-color: {c['bg']};
    color: {c['text_muted']};
    border-top: 1px solid {c['border']};
}}
QMenu {{
    background-color: {c['card']};
    color: {c['text']};
    border: 1px solid {c['border']};
    border-radius: 6px;
    padding: 4px;
}}
QMenu::item {{
    padding: 6px 24px 6px 12px;
    border-radius: 4px;
}}
QMenu::item:selected {{
    background-color: {c['row_hover']};
    color: {c['accent']};
}}
QMenu::separator {{
    height: 1px;
    background: {c['border']};
    margin: 4px 8px;
}}
QScrollBar:vertical {{
    background: {c['bg']};
    width: 12px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {c['border']};
    border-radius: 6px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{
    background: {c['text_muted']};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background: {c['bg']};
    height: 12px;
    margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: {c['border']};
    border-radius: 6px;
    min-width: 24px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {c['text_muted']};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}
QProgressBar {{
    background-color: {c['input_bg']};
    border: 1px solid {c['border']};
    border-radius: 6px;
    text-align: center;
    color: {c['text']};
}}
QProgressBar::chunk {{
    background-color: {c['accent']};
    border-radius: 5px;
}}
QToolTip {{
    background-color: {c['card']};
    color: {c['text']};
    border: 1px solid {c['border']};
    padding: 4px;
}}
"""


_DARK_STYLESHEET = _build_stylesheet(_DARK_COLORS)
_LIGHT_STYLESHEET = _build_stylesheet(_LIGHT_COLORS)


# ── Icon loading ────────────────────────────────────────────────────────────

# Stroke color used for the bundled monochrome SVG icons, per theme.
_ICON_COLOR = {
    "light": "#4b5563",
    "dark": "#d1d5db",
}


def _icons_dir() -> str:
    """Return the directory containing the bundled SVG icons."""
    if getattr(__import__("sys"), "frozen", False):
        base = __import__("sys")._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "assets", "icons")


def get_icon(name: str, dark: bool = False, size: int = 20) -> QIcon:
    """Load a bundled SVG icon, tinted for the active theme.

    The SVG files use an ``ICON_COLOR`` stroke placeholder which is replaced
    with a theme-appropriate color before rendering, so a single icon set
    works in both light and dark mode. Returns a null icon if the file is
    missing or fails to render.
    """
    path = os.path.join(_icons_dir(), f"{name}.svg")
    try:
        with open(path, "r", encoding="utf-8") as f:
            svg = f.read()
    except OSError:
        return QIcon()

    svg = svg.replace("ICON_COLOR", _ICON_COLOR["dark" if dark else "light"])
    pixmap = QPixmap()
    if not pixmap.loadFromData(QByteArray(svg.encode("utf-8")), "SVG"):
        return QIcon()
    pixmap = pixmap.scaled(
        size, size,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    return QIcon(pixmap)


# ── Status badge colors ─────────────────────────────────────────────────────

def status_badge_colors(status: str, dark: bool = False) -> tuple[str, str]:
    """Return ``(background, foreground)`` hex colors for a status badge.

    ``status`` is one of ``online`` / ``offline`` / ``unknown``.
    """
    c = _DARK_COLORS if dark else _LIGHT_COLORS
    mapping = {
        "online": (c["badge_success_bg"], c["badge_success_fg"]),
        "offline": (c["badge_danger_bg"], c["badge_danger_fg"]),
    }
    return mapping.get(status, (c["badge_warning_bg"], c["badge_warning_fg"]))
