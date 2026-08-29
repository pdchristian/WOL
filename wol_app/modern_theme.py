"""Stylesheet for the modern "Dark Control Center" UI.

Color tokens mirror the design prototype
(Design_Prototpye/dark_control_center_full.html). A light variant is
provided for ``ui.display_mode == "light"`` so the modern layout respects
the existing display-mode setting.

All rules are objectName-based (``#sidebar``, ``#navItem``, ``#panel`` …)
so they only affect widgets of the modern window and never leak into the
classic UI or the shared dialogs.
"""

from PyQt6.QtWidgets import QApplication

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
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {t['accent']}, stop:1 {t['accent_dark']});
    color: #ffffff; font-weight: 700; font-size: 16px;
    border-radius: 12px;
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
QPushButton#iconBtn {{
    background: transparent; border: none; padding: 4px 8px;
    font-size: 14px; border-radius: 8px;
}}
QPushButton#iconBtn:hover {{ background: {t['surface_hover']}; }}

/* ── Panels / cards ──────────────────────────────────────────────────── */
#panel {{
    background: {t['surface']};
    border: 1px solid {t['border']}; border-radius: 14px;
}}
#scanRow, #deviceRow {{ background: transparent; }}
#scanRow:hover, #deviceRow:hover {{ background: {t['surface_hover']}; }}
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
QLineEdit, QComboBox, QSpinBox {{
    background: {t['surface']}; color: {t['text']};
    border: 1px solid {t['border']}; border-radius: 10px;
    padding: 8px 12px; selection-background-color: {t['accent']};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{ border-color: {t['accent']}; }}
QLineEdit{{ placeholder-text-color: {t['text_dim']}; }}
QComboBox::drop-down {{ border: none; width: 24px; }}

/* SpinBox up/down buttons (custom QSS hides the native arrows otherwise) */
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
    width: 0; height: 0;
    border-left: 5px solid transparent; border-right: 5px solid transparent;
    border-bottom: 6px solid {t['text_dim']};
}}
QSpinBox::down-arrow {{
    width: 0; height: 0;
    border-left: 5px solid transparent; border-right: 5px solid transparent;
    border-top: 6px solid {t['text_dim']};
}}
QSpinBox::up-arrow:hover, QSpinBox::down-arrow:hover {{
    border-bottom-color: {t['accent']}; border-top-color: {t['accent']};
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
QCheckBox::indicator:checked {{ background: {t['accent']}; border-color: {t['accent']}; }}

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
"""


def apply_modern_theme(app: QApplication, dark: bool) -> None:
    """Apply the modern control-center stylesheet to the application."""
    app.setStyleSheet(modern_stylesheet(DARK if dark else LIGHT))
