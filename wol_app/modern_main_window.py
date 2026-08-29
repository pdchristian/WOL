"""Modern "Dark Control Center" main window for the Wake-on-LAN application.

Sidebar-based layout mirroring Design_Prototpye/dark_control_center_full.html:
Geräte / Verwalten / Zeitplan / Protokolle + application footer (settings,
update check, about, quit). Feature-identical to the classic ``MainWindow``;
in this iteration only "Verwalten" is a native screen — the other areas
reuse the existing dialogs (schedule manager, logs) or show placeholders.

The window is selected at startup via ``ui.layout_mode`` (installer choice /
settings dialog); see :func:`wol_app.main_window.main`.
"""

from typing import Any, NoReturn

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from wol_app import __version__
from wol_app.config import ConfigManager
from wol_app.log_dialog import LogDialog
from wol_app.modern_theme import DARK, LIGHT, apply_modern_theme
from wol_app.schedule_dialog import ScheduleDialog
from wol_app.settings_dialog import SettingsDialog
from wol_app.translations import Translations
from wol_app.update_dialog import (
    UpdateAvailableDialog,
    UpdateErrorDialog,
    UpdateInfoDialog,
)
from wol_app.updater import check_for_updates_sync
from wol_app.utils import get_resource_path
from wol_app.views.manage_view import ManageView


def nav_text(icon: str, key: str) -> str:
    """Sidebar button label: emoji + translated text without menu mnemonics."""
    return f"{icon}  {Translations.tr(key).replace('&', '')}"


class PlaceholderPage(QWidget):
    """Simple centered placeholder screen for not-yet-modernized areas."""

    def __init__(self, icon: str, title_key: str, desc_key: str, parent=None) -> None:
        super().__init__(parent)
        self.icon = icon
        self.title_key = title_key
        self.desc_key = desc_key

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(10)

        self.icon_label = QLabel(icon)
        self.icon_label.setObjectName("placeholderIcon")
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label = QLabel()
        self.title_label.setObjectName("pageTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.desc_label = QLabel()
        self.desc_label.setObjectName("placeholderText")
        self.desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.desc_label.setWordWrap(True)
        self.hint_label = QLabel(Translations.tr("modern.placeholder.hint"))
        self.hint_label.setObjectName("placeholderText")
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        for w in (self.icon_label, self.title_label, self.desc_label, self.hint_label):
            layout.addWidget(w)
        self.retranslate()

    def retranslate(self) -> None:
        self.title_label.setText(Translations.tr(self.title_key))
        self.desc_label.setText(Translations.tr(self.desc_key))
        self.hint_label.setText(Translations.tr("modern.placeholder.hint"))


class ModernMainWindow(QMainWindow):
    """Sidebar control-center window (modern layout)."""

    def __init__(self, config_manager: ConfigManager, dark_mode: bool = True) -> None:
        super().__init__()
        self.config: Any = config_manager
        self.dark_mode = dark_mode
        self._tokens = DARK if dark_mode else LIGHT
        self._update_check_running = False

        self.setWindowTitle(Translations.tr("app.name"))
        self.resize(1180, 740)

        self._setup_ui()
        self._select_nav(0)

    # ── UI construction ──────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        central = QWidget()
        central.setObjectName("modernCentral")
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_sidebar())

        # Stacked screens
        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)

        self.manage_view = ManageView(self.config)
        self.devices_page = PlaceholderPage(
            "💻", "modern.nav.devices", "modern.placeholder.devices")
        self.schedule_page = PlaceholderPage(
            "🕒", "modern.nav.schedule", "modern.placeholder.schedule")
        self.logs_page = PlaceholderPage(
            "📋", "modern.nav.logs", "modern.placeholder.logs")
        self.placeholder_pages = [self.devices_page, self.schedule_page, self.logs_page]
        self.stack.addWidget(self.devices_page)   # index 0
        self.stack.addWidget(self.manage_view)    # index 1
        self.stack.addWidget(self.schedule_page)  # index 2
        self.stack.addWidget(self.logs_page)      # index 3

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(230)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(12, 20, 12, 16)
        layout.setSpacing(4)

        # Logo
        logo_row = QHBoxLayout()
        logo_row.setSpacing(12)
        mark = QLabel("W")
        mark.setObjectName("logoMark")
        mark.setFixedSize(40, 40)
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_text = QLabel(Translations.tr("app.name.short"))
        logo_text.setObjectName("logoText")
        logo_row.addWidget(mark)
        logo_row.addWidget(logo_text)
        logo_row.addStretch()
        layout.addLayout(logo_row)
        layout.addSpacing(18)

        # Area section
        lbl_areas = QLabel(Translations.tr("modern.nav.areas").upper())
        lbl_areas.setObjectName("sectionLabel")
        layout.addWidget(lbl_areas)

        self.nav_buttons: list[QPushButton] = []
        nav_defs = [
            ("💻", "modern.nav.devices"),
            ("🔧", "modern.nav.manage"),
            ("🕒", "modern.nav.schedule"),
            ("📋", "modern.nav.logs"),
        ]
        for idx, (icon, key) in enumerate(nav_defs):
            btn = QPushButton(nav_text(icon, key))
            btn.setObjectName("navItem")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _c=False, i=idx: self._select_nav(i))
            self.nav_buttons.append(btn)
            layout.addWidget(btn)

        layout.addStretch()

        # Application section
        sep = QFrame()
        sep.setObjectName("navSeparator")
        sep.setFixedHeight(1)
        layout.addWidget(sep)
        lbl_app = QLabel(Translations.tr("modern.nav.application").upper())
        lbl_app.setObjectName("sectionLabel")
        layout.addWidget(lbl_app)

        self.settings_btn = self._nav_action("⚙", "menu.tools.settings", self._open_settings)
        self.update_btn = self._nav_action("🔄", "menu.tools.update", self._manual_update_check)
        self.about_btn = self._nav_action("ℹ", "menu.help.about", self._show_about)
        self.quit_btn = self._nav_action("⏻", "menu.file.exit", self.close)
        layout.addWidget(self.settings_btn)
        layout.addWidget(self.update_btn)
        layout.addWidget(self.about_btn)
        layout.addWidget(self.quit_btn)
        return sidebar

    def _nav_action(self, icon: str, text_key: str, handler) -> QPushButton:
        btn = QPushButton(nav_text(icon, text_key))
        btn.setObjectName("navItem")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(handler)
        return btn

    # ── Navigation ───────────────────────────────────────────────────────

    def _select_nav(self, index: int) -> None:
        # Zeitplan/Protokolle sind in dieser Iteration Dialoge (Platzhalter-Seiten bleiben wählbar)
        self.stack.setCurrentIndex(index)
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == index)
        if index == 2:
            self._open_schedule_manager()
        elif index == 3:
            self._open_logs()

    # ── Application actions (reuse classic dialogs) ──────────────────────

    def _open_settings(self) -> None:
        dialog: SettingsDialog[ConfigManager] = SettingsDialog(self.config, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # The settings dialog applies the classic stylesheet; restore the
            # modern theme (respecting a possibly changed display mode).
            from wol_app.theme import _system_uses_dark

            display_mode = self.config.config.get("ui", {}).get("display_mode", "auto")
            self.dark_mode = display_mode == "dark" or (
                display_mode == "auto" and _system_uses_dark()
            )
            self._tokens = DARK if self.dark_mode else LIGHT
            app = QApplication.instance()
            if app is not None:
                apply_modern_theme(app, self.dark_mode)
            if dialog.restart_required:
                QMessageBox.information(
                    self,
                    Translations.tr("app.name"),
                    Translations.tr("settings.restart_required"),
                )
            self._retranslate()

    def _open_schedule_manager(self) -> None:
        dialog: ScheduleDialog[ConfigManager] = ScheduleDialog(self.config, parent=self)
        dialog.exec()

    def _open_logs(self) -> None:
        dialog: LogDialog[ConfigManager] = LogDialog(self.config, parent=self)
        dialog.exec()

    def _manual_update_check(self) -> None:
        if self._update_check_running:
            return
        self._update_check_running = True
        try:
            result = check_for_updates_sync(current_version=__version__)
        finally:
            self._update_check_running = False

        if result is None:
            UpdateErrorDialog(self).exec()
            return
        release_info, has_update = result
        if has_update and release_info:
            UpdateAvailableDialog(release_info, __version__, self).exec()
        else:
            UpdateInfoDialog(self).exec()

    def _show_about(self) -> None:
        QMessageBox.about(
            self, Translations.tr("dialog.about.title"),
            "<h3>Wake-on-LAN Manager</h3>"
            f"<p>{Translations.tr('dialog.about.version')} {__version__}</p>"
            f"<p>{Translations.tr('dialog.about.description')}</p>"
            f"<p>{Translations.tr('dialog.about.supports')}</p>",
        )

    # ── Language / theme ─────────────────────────────────────────────────

    def _retranslate(self) -> None:
        """Refresh all UI text after a language change in the settings dialog."""
        self.setWindowTitle(Translations.tr("app.name"))
        # Navigation labels (nav_buttons: devices, manage, schedule, logs)
        nav_defs = [
            ("💻", "modern.nav.devices"),
            ("🔧", "modern.nav.manage"),
            ("🕒", "modern.nav.schedule"),
            ("📋", "modern.nav.logs"),
        ]
        for btn, (icon, key) in zip(self.nav_buttons, nav_defs, strict=True):
            btn.setText(nav_text(icon, key))
        self.settings_btn.setText(nav_text("⚙", "menu.tools.settings"))
        self.update_btn.setText(nav_text("🔄", "menu.tools.update"))
        self.about_btn.setText(nav_text("ℹ", "menu.help.about"))
        self.quit_btn.setText(nav_text("⏻", "menu.file.exit"))

        self.manage_view.retranslate()
        for page in self.placeholder_pages:
            page.retranslate()

    # ── Lifecycle ────────────────────────────────────────────────────────

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        self.manage_view.cancel_workers()
        event.accept()


def run_modern_window(config: ConfigManager, dark_mode: bool) -> NoReturn:
    """Show the modern window on an existing QApplication and enter the loop."""
    import sys

    from PyQt6.QtWidgets import QApplication

    apply_modern_theme(QApplication.instance(), dark_mode)
    icon_path: str = get_resource_path("icon.ico")
    if icon_path:
        QApplication.instance().setWindowIcon(QIcon(icon_path))
    window = ModernMainWindow(config, dark_mode=dark_mode)
    window.show()
    sys.exit(QApplication.instance().exec())
