"""Modern "Dark Control Center" main window for the Wake-on-LAN application.

Sidebar-based layout mirroring design_prototype/dark_control_center_full.html:
Geräte / Verwalten / Zeitplan / Protokolle + application footer (settings,
about, quit). Feature-identical to the classic ``MainWindow``; in this
iteration "Verwalten", "Zeitplan", "Protokolle", "Einstellungen" and
"Über" (incl. the update check) are native screens — the remaining areas
reuse the existing dialogs or show placeholders.

The window is selected at startup via ``ui.layout_mode`` (installer choice /
settings dialog); see :func:`wol_app.main_window.main`.
"""

import os
from typing import Any, NoReturn

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QApplication,
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

from wol_app.config import ConfigManager
from wol_app.main_window import HEADLESS_MODE
from wol_app.modern_theme import DARK, LIGHT, app_icon_pixmap, apply_modern_theme
from wol_app.schedule_runner import dispatch_schedule_action
from wol_app.translations import Translations
from wol_app.utils import get_resource_path
from wol_app.views.dashboard_view import DeviceDashboardView
from wol_app.views.devices_view import DevicesView
from wol_app.views.logs_view import LogsView
from wol_app.views.manage_view import ManageView
from wol_app.views.schedule_view import ScheduleView
from wol_app.views.settings_view import SettingsView
from wol_app.views.update_view import UpdateView
from wol_app.wol_engine import WOLEngine


def nav_text(icon: str, key: str) -> str:
    """Sidebar button label: emoji + translated text without menu mnemonics."""
    return f"{icon}  {Translations.tr(key).replace('&', '')}"


# Stack index of the native settings screen (after devices/manage/schedule/logs).
SETTINGS_NAV_INDEX = 4

# Stack index of the native "Über" screen (about + update check).
UPDATE_NAV_INDEX = 5

# Stack index of the per-device dashboard (opened via the 📊 tile on the
# devices screen — intentionally NOT a sidebar entry).
DASHBOARD_NAV_INDEX = 6





class ModernMainWindow(QMainWindow):
    """Sidebar control-center window (modern layout)."""

    def __init__(self, config_manager: ConfigManager, dark_mode: bool = True) -> None:
        super().__init__()
        self.config: Any = config_manager
        self.dark_mode = dark_mode
        self._tokens = DARK if dark_mode else LIGHT

        self.setWindowTitle(Translations.tr("app.name"))
        # Use the modern logo in the taskbar (WM_SETICON uses the window icon,
        # not the app icon, so this must be set on the window itself).
        icon_path = get_resource_path("icon_modern.ico")
        if not os.path.exists(icon_path):
            icon_path = get_resource_path("icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self.resize(1180, 740)

        # Scheduler engine (wake/shutdown for fired schedule entries)
        self.engine: WOLEngine = WOLEngine(self.config)

        self._setup_ui()
        self._select_nav(0)

        # Start the schedule engine (skip in headless mode)
        if not HEADLESS_MODE:
            self.engine.schedule_fired.connect(self._on_schedule_fired)
            self.engine.start_scheduler()

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

        self.devices_view = DevicesView(self.config)
        self.manage_view = ManageView(self.config)
        self.schedule_view = ScheduleView(self.config)
        self.logs_view = LogsView(self.config)
        self.settings_view = SettingsView(self.config)
        self.settings_view.settings_saved.connect(self._on_settings_saved)
        self.update_view = UpdateView(self.config)
        self.dashboard_view = DeviceDashboardView(self.config)
        self.stack.addWidget(self.devices_view)   # index 0
        self.stack.addWidget(self.manage_view)    # index 1
        self.stack.addWidget(self.schedule_view)  # index 2
        self.stack.addWidget(self.logs_view)      # index 3
        self.stack.addWidget(self.settings_view)  # index 4
        self.stack.addWidget(self.update_view)    # index 5
        self.stack.addWidget(self.dashboard_view)  # index 6 (no sidebar entry)

        # Keep the device lists of both areas in sync
        self.manage_view.devices_changed.connect(self._on_devices_changed)
        self.devices_view.devices_changed.connect(self._on_devices_changed)

        # Dashboard: opened from the 📊 tile, returns to the devices screen
        self.devices_view.dashboard_requested.connect(self.open_device_dashboard)
        self.dashboard_view.back_requested.connect(lambda: self._select_nav(0))

    def _on_devices_changed(self) -> None:
        """A device was added/edited/removed in either area — refresh both."""
        self.devices_view.refresh_devices()
        self.devices_view.refresh_statuses()
        self.manage_view._refresh_device_list()
        # Keep an open dashboard's header in sync with edits
        self.dashboard_view.refresh_device_header()

    def open_device_dashboard(self, device_id: str) -> None:
        """Show the per-device dashboard (stack switch, no sidebar entry)."""
        self.dashboard_view.set_device(device_id)
        self.stack.setCurrentIndex(DASHBOARD_NAV_INDEX)
        self._clear_nav_check()

    def _clear_nav_check(self) -> None:
        """Uncheck every nav button (dashboard screen has no nav entry)."""
        for btn in self.nav_buttons:
            btn.setChecked(False)
        self.settings_btn.setChecked(False)
        self.about_btn.setChecked(False)

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
        mark = QLabel()
        mark.setObjectName("logoMark")
        mark.setFixedSize(40, 40)
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        _pix = app_icon_pixmap(40)
        if _pix is not None:
            mark.setPixmap(_pix)
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

        self.settings_btn = self._nav_action(
            "⚙", "menu.tools.settings",
            lambda: self._select_nav(SETTINGS_NAV_INDEX, self.settings_btn))
        self.settings_btn.setCheckable(True)
        # The native update/about screen is opened via "Über"; the update
        # check itself is the primary button on that screen.
        self.about_btn = self._nav_action(
            "\u2139\ufe0f", "menu.help.about",
            lambda: self._select_nav(UPDATE_NAV_INDEX, self.about_btn))
        self.about_btn.setCheckable(True)
        self.quit_btn = self._nav_action("⏻", "menu.file.exit", self.close)
        layout.addWidget(self.settings_btn)
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

    def _select_nav(self, index: int, trigger: QPushButton | None = None) -> None:
        self.stack.setCurrentIndex(index)
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == index)
        # The footer entries (settings / about) participate in the same
        # exclusive checked state as the area buttons.
        self.settings_btn.setChecked(trigger is self.settings_btn)
        self.about_btn.setChecked(trigger is self.about_btn)

    # ── Application actions (reuse classic dialogs) ──────────────────────

    def _on_settings_saved(self) -> None:
        """React to a save/reset on the native settings screen.

        Re-apply the modern theme (the display mode may have changed) and
        refresh every screen (the language may have changed).
        """
        from wol_app.theme import _system_uses_dark

        display_mode = self.config.config.get("ui", {}).get("display_mode", "auto")
        self.dark_mode = display_mode == "dark" or (
            display_mode == "auto" and _system_uses_dark()
        )
        self._tokens = DARK if self.dark_mode else LIGHT
        app = QApplication.instance()
        if app is not None:
            apply_modern_theme(app, self.dark_mode)
        if self.settings_view.restart_required:
            QMessageBox.information(
                self,
                Translations.tr("app.name"),
                Translations.tr("settings.restart_required"),
            )
        self._retranslate()

    def _on_schedule_fired(self, device_id: str, action: str) -> None:
        """Dispatch a fired schedule entry (wake / shutdown).

        Shares the logic with the classic layout via schedule_runner.
        """
        dispatch_schedule_action(
            self.config, self.engine, device_id, action,
            lambda msg, _ms: None,  # no status bar in the modern layout
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
        self.about_btn.setText(nav_text("\u2139\ufe0f", "menu.help.about"))
        self.quit_btn.setText(nav_text("⏻", "menu.file.exit"))

        self.devices_view.retranslate()
        self.manage_view.retranslate()
        self.schedule_view.retranslate()
        self.logs_view.retranslate()
        self.settings_view.retranslate()
        self.update_view.retranslate()
        self.dashboard_view.retranslate()

    # ── Lifecycle ────────────────────────────────────────────────────────

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        self.devices_view.cancel_workers()
        self.manage_view.cancel_workers()
        self.dashboard_view.cancel_workers()
        self.update_view.cancel_checks()
        self.engine.stop_scheduler()
        event.accept()


def run_modern_window(config: ConfigManager, dark_mode: bool) -> NoReturn:
    """Show the modern window on an existing QApplication and enter the loop."""
    import sys

    from PyQt6.QtWidgets import QApplication

    apply_modern_theme(QApplication.instance(), dark_mode)
    icon_path: str = get_resource_path("icon_modern.ico")
    if not os.path.exists(icon_path):
        icon_path = get_resource_path("icon.ico")
    if os.path.exists(icon_path):
        QApplication.instance().setWindowIcon(QIcon(icon_path))
    window = ModernMainWindow(config, dark_mode=dark_mode)
    window.show()
    sys.exit(QApplication.instance().exec())
