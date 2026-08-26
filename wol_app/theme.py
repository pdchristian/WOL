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
    palette.setColor(QPalette.ColorRole.Window, QColor(15, 17, 21))       # bg
    palette.setColor(QPalette.ColorRole.WindowText, QColor(230, 232, 238))
    palette.setColor(QPalette.ColorRole.Base, QColor(26, 29, 36))         # surface
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(17, 20, 26))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(35, 39, 51))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(230, 232, 238))
    palette.setColor(QPalette.ColorRole.Text, QColor(230, 232, 238))
    palette.setColor(QPalette.ColorRole.Button, QColor(26, 29, 36))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(230, 232, 238))
    palette.setColor(QPalette.ColorRole.BrightText, QColor(224, 72, 90))
    palette.setColor(QPalette.ColorRole.Link, QColor(0, 184, 169))         # accent
    palette.setColor(QPalette.ColorRole.Highlight, QColor(0, 184, 169))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(3, 32, 25))
    return palette


def _light_palette() -> QPalette:
    """Return an explicit light palette (independent of the OS scheme)."""
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(244, 246, 249))    # bg
    palette.setColor(QPalette.ColorRole.WindowText, QColor(30, 36, 48))
    palette.setColor(QPalette.ColorRole.Base, QColor(255, 255, 255))      # surface
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(247, 249, 252))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(30, 36, 48))
    palette.setColor(QPalette.ColorRole.Text, QColor(30, 36, 48))
    palette.setColor(QPalette.ColorRole.Button, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(30, 36, 48))
    palette.setColor(QPalette.ColorRole.BrightText, QColor(220, 38, 38))
    palette.setColor(QPalette.ColorRole.Link, QColor(0, 143, 132))         # accent
    palette.setColor(QPalette.ColorRole.Highlight, QColor(0, 143, 132))
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


# ---------------------------------------------------------------------------
# "Dark Control Center" theme.
#
# Two complete stylesheets (DARK + LIGHT) implement the design language from
# the design_prototypes/*.html mockups. New UI widgets (cards, sidebar, badges,
# toggles, list view, modals) are targeted through stable objectName selectors,
# so each widget must be created with a matching objectName.
# ---------------------------------------------------------------------------

# Shared QSS fragment for both modes: layout helpers, scrollbars, selection.
_BASE_QSS = """
/* Global spacing and font */
* { font-family: "Segoe UI", sans-serif; }
QToolTip {
    border: 1px solid %(border)s;
    border-radius: 6px;
    padding: 4px 8px;
    background-color: %(surface_alt)s;
    color: %(text)s;
}

/* ---- Scrollbars ---- */
QScrollBar:vertical {
    background: transparent; width: 10px; margin: 0;
}
QScrollBar::handle:vertical {
    background: %(border)s; border-radius: 5px; min-height: 24px;
}
QScrollBar::handle:vertical:hover { background: %(text_dim)s; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal {
    background: transparent; height: 10px; margin: 0;
}
QScrollBar::handle:horizontal {
    background: %(border)s; border-radius: 5px; min-width: 24px;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical,
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: none; }

/* ---- Sidebar ---- */
#Sidebar { background-color: %(surface)s; border-right: 1px solid %(border)s; }
#SidebarLogo { background-color: %(accent)s; border-radius: 12px; color: %(on_accent)s; font-weight: 600; }
#SidebarLabel { color: %(text_dim)s; font-size: 11px; font-weight: 600; }
#NavItem {
    background-color: transparent; color: %(text_dim)s;
    border: none; border-radius: 10px; text-align: left;
    padding: 10px 12px; font-size: 14px;
}
#NavItem:hover { background-color: %(surface_hover)s; color: %(text)s; }
#NavItem:checked {
    background-color: %(accent_soft)s; color: %(accent)s; font-weight: 600;
}
#NavSeparator { background-color: %(border)s; border: none; }

/* ---- Buttons ---- */
QPushButton {
    background-color: %(surface)s; color: %(text)s;
    border: 1px solid %(border)s; border-radius: 10px;
    padding: 8px 14px; font-size: 13px; font-weight: 600;
}
QPushButton:hover { background-color: %(surface_hover)s; }
QPushButton:pressed { background-color: %(surface_alt)s; }
QPushButton:disabled { color: %(text_dim)s; background-color: %(surface)s; }
#primaryButton {
    background-color: %(accent)s; color: %(on_accent)s; border: none;
}
#primaryButton:hover { background-color: %(accent_hover)s; }
#dangerButton {
    background-color: %(danger_soft)s; color: %(danger)s; border: 1px solid %(danger_border)s;
}
#dangerButton:hover { background-color: %(danger_soft_hover)s; }
#iconButton { padding: 8px 10px; }
#wakeButton {
    background-color: transparent; color: %(accent)s;
    border: 1px solid %(accent)s; border-radius: 8px;
    padding: 5px 12px; font-size: 12px; font-weight: 600;
}
#wakeButton:hover { background-color: %(accent)s; color: %(on_accent)s; }

/* ---- Search / inputs ---- */
#SearchBox {
    background-color: %(surface)s; border: 1px solid %(border)s;
    border-radius: 10px; color: %(text)s; padding: 9px 14px; font-size: 14px;
}
#SearchBox:focus { border-color: %(accent)s; }
QLineEdit, QComboBox, QSpinBox, QTextEdit, QPlainTextEdit {
    background-color: %(surface)s; border: 1px solid %(border)s;
    border-radius: 10px; color: %(text)s; padding: 8px 12px; font-size: 14px;
    selection-background-color: %(accent)s; selection-color: %(on_accent)s;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QTextEdit:focus { border-color: %(accent)s; }

/* ---- Combo box drop-down arrow ---- */
QComboBox::drop-down { border: none; width: 28px; }
QComboBox::down-arrow {
    image: none; width: 0; height: 0;
    border-left: 4px solid transparent; border-right: 4px solid transparent;
    border-top: 5px solid %(text_dim)s; margin-right: 10px;
}
QComboBox QAbstractItemView {
    background-color: %(surface)s; border: 1px solid %(border)s; border-radius: 8px; color: %(text)s;
    selection-background-color: %(accent_soft)s; selection-color: %(accent)s;
}

/* ---- Spin box up/down buttons ---- */
QSpinBox::up-button, QDoubleSpinBox::up-button {
    background-color: %(surface_hover)s; border: none;
    border-radius: 0 10px 0 0; width: 20px; border-left: 1px solid %(border)s;
}
QSpinBox::down-button, QDoubleSpinBox::down-button {
    background-color: %(surface_hover)s; border: none;
    border-radius: 0 0 10px 0; width: 20px; border-left: 1px solid %(border)s;
}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
    background-color: %(accent_soft)s;
}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
    image: none; width: 0; height: 0;
    border-left: 4px solid transparent; border-right: 4px solid transparent;
    border-bottom: 5px solid %(text)s; margin: 4px;
}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
    image: none; width: 0; height: 0;
    border-left: 4px solid transparent; border-right: 4px solid transparent;
    border-top: 5px solid %(text)s; margin: 4px;
}
QSpinBox::up-button:disabled, QSpinBox::down-button:disabled {
    background-color: %(surface)s;
}

/* ---- Cards ---- */
#DeviceCard {
    background-color: %(surface)s; border: 1px solid %(border)s; border-radius: 14px;
}
#DeviceCard:hover { background-color: %(surface_hover)s; border-color: %(accent)s; }
#DeviceCardTitle { color: %(text)s; font-size: 15px; font-weight: 600; }
#DeviceCardMeta { color: %(text_dim)s; font-size: 12px; }

/* ---- Status dot / badges ---- */
#StatusDot { border-radius: 5px; }
#StatusDot[status="online"] { background-color: %(online)s; }
#StatusDot[status="offline"] { background-color: %(offline)s; }
#StatusDot[status="unknown"] { background-color: %(unknown)s; }
#StatusText { font-size: 12px; font-weight: 600; }
#StatusText[status="online"] { color: %(online)s; }
#StatusText[status="offline"] { color: %(offline)s; }
#StatusText[status="unknown"] { color: %(unknown)s; }

/* ---- List view (device table) ---- */
#DeviceTable {
    background-color: %(surface)s; border: 1px solid %(border)s; border-radius: 14px;
    gridline-color: %(border)s; alternate-background-color: %(surface_alt)s;
}
#DeviceTable::item { border: none; padding: 8px; }
#DeviceTable::item:selected { background-color: %(accent_soft)s; color: %(accent)s; }
QHeaderView::section {
    background-color: %(surface_hover)s; color: %(text_dim)s;
    border: none; border-bottom: 1px solid %(border)s;
    padding: 10px 12px; font-size: 12px; font-weight: 600;
}

/* ---- Toggle switch ---- */
#Toggle { background-color: %(border)s; border-radius: 11px; }
#Toggle[state="on"] { background-color: %(accent)s; }
#ToggleKnob { background-color: %(on_accent)s; border-radius: 8px; }

/* ---- Modal ---- */
#Modal { background-color: %(surface)s; border: 1px solid %(border)s; border-radius: 16px; }
#ModalTitle { font-size: 18px; font-weight: 600; }
#ModalSubtitle { color: %(text_dim)s; font-size: 13px; }
#ModalFooter { background-color: %(surface)s; border-top: 1px solid %(border)s; border-radius: 0 0 16px 16px; }

/* ---- Groups / panels ---- */
QGroupBox {
    background-color: %(surface)s; border: 1px solid %(border)s; border-radius: 12px;
    margin-top: 8px; padding-top: 8px; color: %(text)s;
    font-weight: 600;
}
QGroupBox::title {
    subcontrol-origin: margin; left: 14px; padding: 0 4px; color: %(text_dim)s;
}

/* ---- Dialogs / windows ---- */
QMainWindow, QDialog { background-color: %(bg)s; color: %(text)s; }
QMessageBox { background-color: %(surface)s; }

/* ---- Menu (context menus) ---- */
QMenu { background-color: %(surface)s; color: %(text)s; border: 1px solid %(border)s; border-radius: 8px; padding: 6px; }
QMenu::item { padding: 7px 24px; border-radius: 6px; }
QMenu::item:selected { background-color: %(accent_soft)s; color: %(accent)s; }
QMenu::separator { height: 1px; background-color: %(border)s; margin: 4px 8px; }

QStatusBar { background-color: %(surface)s; color: %(text_dim)s; border-top: 1px solid %(border)s; }
"""


def _dark_stylesheet() -> str:
    """Return the full dark-mode QSS stylesheet."""
    colors = {
        "bg": "#0f1115",
        "surface": "#1a1d24",
        "surface_hover": "#232733",
        "surface_alt": "#11141a",
        "border": "#2c303a",
        "text": "#e6e8ee",
        "text_dim": "#9aa0ab",
        "accent": "#00b8a9",
        "accent_hover": "#00d4c3",
        "accent_soft": "rgba(0, 184, 169, 0.14)",
        "on_accent": "#032019",
        "online": "#22c55e",
        "offline": "#ef4444",
        "unknown": "#f59e0b",
        "danger": "#e0485a",
        "danger_soft": "rgba(224, 72, 90, 0.12)",
        "danger_soft_hover": "rgba(224, 72, 90, 0.22)",
        "danger_border": "rgba(224, 72, 90, 0.4)",
    }
    return _render_qss(colors)


def _light_stylesheet() -> str:
    """Return the full light-mode QSS stylesheet."""
    colors = {
        "bg": "#f4f6f9",
        "surface": "#ffffff",
        "surface_hover": "#eef2f7",
        "surface_alt": "#f7f9fc",
        "border": "#dfe5ee",
        "text": "#1e2430",
        "text_dim": "#6b7280",
        "accent": "#008f84",
        "accent_hover": "#00a89b",
        "accent_soft": "rgba(0, 143, 132, 0.12)",
        "on_accent": "#ffffff",
        "online": "#16a34a",
        "offline": "#dc2626",
        "unknown": "#d97706",
        "danger": "#dc2626",
        "danger_soft": "rgba(220, 38, 38, 0.08)",
        "danger_soft_hover": "rgba(220, 38, 38, 0.16)",
        "danger_border": "rgba(220, 38, 38, 0.4)",
    }
    return _render_qss(colors)


def _render_qss(colors: dict) -> str:
    """Render the shared QSS template with the given color tokens."""
    return _BASE_QSS % colors


_DARK_STYLESHEET = _dark_stylesheet()
_LIGHT_STYLESHEET = _light_stylesheet()
