"""Display mode (theme) handling for the Wake-on-LAN application."""

import sys

from PyQt6.QtGui import QColor, QPalette
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

    if dark:
        app.setPalette(_dark_palette())
        app.setStyleSheet(_DARK_STYLESHEET)
    else:
        app.setPalette(_light_palette())
        app.setStyleSheet(_LIGHT_STYLESHEET)


# Base stylesheet that overrides OS-default colors for the most common widgets.
# Kept minimal so it does not interfere with widget-specific stylesheets.
_DARK_STYLESHEET = """
QMainWindow, QDialog, QGroupBox {
    background-color: #353535;
    color: #ffffff;
}
QTableWidget, QTextEdit, QLineEdit, QComboBox, QSpinBox {
    background-color: #232323;
    color: #ffffff;
    alternate-background-color: #4b4b4b;
}
QHeaderView::section {
    background-color: #353535;
    color: #ffffff;
}
QPushButton {
    background-color: #353535;
    color: #ffffff;
}
"""

_LIGHT_STYLESHEET = """
QMainWindow, QDialog, QGroupBox {
    background-color: #f0f0f0;
    color: #000000;
}
QTableWidget, QTextEdit, QLineEdit, QComboBox, QSpinBox {
    background-color: #ffffff;
    color: #000000;
    alternate-background-color: #f8f8f8;
}
QHeaderView::section {
    background-color: #f0f0f0;
    color: #000000;
}
QPushButton {
    background-color: #f0f0f0;
    color: #000000;
}
"""
