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

from PyQt6.QtCore import QEvent, QSize, Qt, QTimer
from PyQt6.QtGui import QIcon, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from wol_app.config import (
    ConfigManager,
    SIDEBAR_COLLAPSED_WIDTH,
    SIDEBAR_SNAP_WIDTH,
    SIDEBAR_WIDTH_MAX,
    SIDEBAR_WIDTH_MIN,
)
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
from wol_app.views.shutdown_confirm_dialog import ModernShutdownConfirmDialog
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

# Sidebar area entries (icon, translation key) in stack order 0..3. Single
# source of truth for _build_sidebar, _retranslate and the collapsed
# icon-only rendering.
NAV_DEFS = [
    ("💻", "modern.nav.devices"),
    ("🔧", "modern.nav.manage"),
    ("🕒", "modern.nav.schedule"),
    ("📋", "modern.nav.logs"),
]





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

        # Sidebar collapse/resize state (persisted under ui.sidebar_*).
        self._sidebar_collapsed: bool = self.config.get_sidebar_collapsed()
        self._sidebar_last_width: int = self.config.get_sidebar_width()
        self._sidebar_save_timer: QTimer | None = None
        self._sidebar_applying: bool = False
        self._active_nav_btn: QPushButton | None = None

        self._setup_ui()
        self._apply_sidebar_mode()
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

        # Sidebar and content live in a splitter so the sidebar width is
        # drag-resizable (design_prototype/Sidebar.html).
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setObjectName("modernSplitter")
        self.splitter.setHandleWidth(5)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        root.addWidget(self.splitter)

        self.sidebar = self._build_sidebar()
        self.splitter.addWidget(self.sidebar)

        # Stacked screens
        self.stack = QStackedWidget()
        self.splitter.addWidget(self.stack)
        self.splitter.setCollapsible(0, False)
        self.splitter.setCollapsible(1, False)

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

        # Sidebar resize/collapse wiring (after the widgets exist).
        self._sidebar_save_timer = QTimer(self)
        self._sidebar_save_timer.setSingleShot(True)
        self._sidebar_save_timer.timeout.connect(self._save_sidebar_state)
        self.splitter.splitterMoved.connect(self._on_splitter_moved)
        # Double-click the drag handle toggles the sidebar (like the
        # prototype's resizer dblclick).
        self.splitter.handle(1).installEventFilter(self)
        shortcut = QShortcut(QKeySequence("Ctrl+B"), self)
        shortcut.activated.connect(self._toggle_sidebar)

    def eventFilter(self, obj, event) -> bool:
        # Toggle on double-click of the splitter handle.
        if (obj is self.splitter.handle(1)
                and event.type() == QEvent.Type.MouseButtonDblClick):
            self._toggle_sidebar()
            return True
        return super().eventFilter(obj, event)

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
        # No active entry → the next icon click navigates, never toggles.
        self._active_nav_btn = None

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(12, 20, 12, 16)
        layout.setSpacing(4)

        # Logo — the app icon doubles as the collapse toggle (v4: no arrow).
        logo_row = QHBoxLayout()
        logo_row.setSpacing(12)
        self.logo_mark = QToolButton()
        self.logo_mark.setObjectName("logoMark")
        self.logo_mark.setFixedSize(40, 40)
        self.logo_mark.setCursor(Qt.CursorShape.PointingHandCursor)
        self.logo_mark.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        _pix = app_icon_pixmap(40)
        if _pix is not None:
            self.logo_mark.setIcon(QIcon(_pix))
            self.logo_mark.setIconSize(QSize(40, 40))
        self.logo_mark.clicked.connect(self._toggle_sidebar)
        self.logo_text = QLabel(Translations.tr("app.name.short"))
        self.logo_text.setObjectName("logoText")
        logo_row.addWidget(self.logo_mark)
        logo_row.addWidget(self.logo_text)
        logo_row.addStretch()
        layout.addLayout(logo_row)
        layout.addSpacing(18)

        # Area section
        self.lbl_areas = QLabel(Translations.tr("modern.nav.areas").upper())
        self.lbl_areas.setObjectName("sectionLabel")
        layout.addWidget(self.lbl_areas)

        self.nav_buttons: list[QPushButton] = []
        for idx, (icon, key) in enumerate(NAV_DEFS):
            btn = QPushButton(nav_text(icon, key))
            btn.setObjectName("navItem")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(Translations.tr(key).replace("&", ""))
            btn.clicked.connect(lambda _c=False, i=idx, b=btn: self._select_nav(i, b))
            self.nav_buttons.append(btn)
            layout.addWidget(btn)

        layout.addStretch()

        # Application section
        sep = QFrame()
        sep.setObjectName("navSeparator")
        sep.setFixedHeight(1)
        layout.addWidget(sep)
        self.lbl_app = QLabel(Translations.tr("modern.nav.application").upper())
        self.lbl_app.setObjectName("sectionLabel")
        layout.addWidget(self.lbl_app)

        self.settings_btn = self._nav_action(
            "⚙", "menu.tools.settings", lambda: None)
        self.settings_btn.setCheckable(True)
        self.settings_btn.clicked.connect(
            lambda _c=False, b=self.settings_btn: self._select_nav(SETTINGS_NAV_INDEX, b))
        # The native update/about screen is opened via "Über"; the update
        # check itself is the primary button on that screen.
        self.about_btn = self._nav_action(
            "\u2139\ufe0f", "menu.help.about", lambda: None)
        self.about_btn.setCheckable(True)
        self.about_btn.clicked.connect(
            lambda _c=False, b=self.about_btn: self._select_nav(UPDATE_NAV_INDEX, b))
        self.quit_btn = self._nav_action("⏻", "menu.file.exit", self._confirm_quit)
        layout.addWidget(self.settings_btn)
        layout.addWidget(self.about_btn)
        layout.addWidget(self.quit_btn)
        return sidebar

    def _nav_action(self, icon: str, text_key: str, handler) -> QPushButton:
        btn = QPushButton(nav_text(icon, text_key))
        btn.setObjectName("navItem")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setToolTip(Translations.tr(text_key).replace("&", ""))
        btn.clicked.connect(handler)
        return btn

    # ── Sidebar collapse / resize ────────────────────────────────────────

    def _toggle_sidebar(self) -> None:
        """Switch between expanded (icon + label) and icon-only sidebar."""
        if not self._sidebar_collapsed:
            # Remember the intentional width before collapsing.
            current = self.splitter.sizes()[0] if len(self.splitter.sizes()) else 0
            if current >= SIDEBAR_WIDTH_MIN:
                self._sidebar_last_width = min(current, SIDEBAR_WIDTH_MAX)
        self._sidebar_collapsed = not self._sidebar_collapsed
        self._apply_sidebar_mode()
        self._save_sidebar_state()

    def _apply_sidebar_mode(self) -> None:
        """Push the collapsed state onto splitter, widgets and QSS."""
        collapsed = self._sidebar_collapsed
        if collapsed:
            self.sidebar.setMinimumWidth(SIDEBAR_COLLAPSED_WIDTH)
            self.sidebar.setMaximumWidth(SIDEBAR_COLLAPSED_WIDTH)
        else:
            # The minimum is the snap threshold so the user can drag into
            # the collapse zone; widths below SIDEBAR_WIDTH_MIN bounce back
            # (see _on_splitter_moved, mirrors the prototype).
            self.sidebar.setMinimumWidth(SIDEBAR_SNAP_WIDTH)
            self.sidebar.setMaximumWidth(SIDEBAR_WIDTH_MAX)

        # Labels vanish in icon-only mode (hide() instead of QSS width:0 —
        # hidden widgets with QSS padding keep stale layout gaps).
        self.logo_text.setVisible(not collapsed)
        self.lbl_areas.setVisible(not collapsed)
        self.lbl_app.setVisible(not collapsed)

        footer_defs = [
            (self.settings_btn, "⚙", "menu.tools.settings"),
            (self.about_btn, "\u2139\ufe0f", "menu.help.about"),
            (self.quit_btn, "⏻", "menu.file.exit"),
        ]
        for btn, (icon, key) in zip(
                self.nav_buttons, NAV_DEFS, strict=True):
            self._set_nav_button_text(btn, icon, key)
        for btn, icon, key in footer_defs:
            self._set_nav_button_text(btn, icon, key)

        total = sum(self.splitter.sizes()) or self.width()
        width = (SIDEBAR_COLLAPSED_WIDTH if collapsed
                 else min(max(self._sidebar_last_width, SIDEBAR_WIDTH_MIN),
                          SIDEBAR_WIDTH_MAX))
        self._sidebar_applying = True
        self.splitter.setSizes([width, max(total - width, 100)])
        self._sidebar_applying = False
        self.logo_mark.setToolTip(Translations.tr(
            "modern.nav.expand" if collapsed else "modern.nav.collapse"))

    def _set_nav_button_text(self, btn: QPushButton, icon: str, key: str) -> None:
        """Icon-only while collapsed, icon + label while expanded."""
        btn.setText(icon if self._sidebar_collapsed else nav_text(icon, key))
        btn.setProperty("collapsed", "true" if self._sidebar_collapsed else None)
        style = btn.style()
        style.unpolish(btn)
        style.polish(btn)

    def _on_splitter_moved(self, pos: int, index: int) -> None:
        """Track drag width, snap shut below the threshold, persist width."""
        if self._sidebar_save_timer is None or self._sidebar_applying:
            return  # signal fired during __init__ or a programmatic resize
        if self._sidebar_collapsed:
            return  # fixed-width while collapsed; re-expand via click
        width = self.splitter.sizes()[0]
        if width <= SIDEBAR_SNAP_WIDTH:
            # Snap: collapse instead of letting the sidebar shrink further.
            self._sidebar_collapsed = True
            self._apply_sidebar_mode()
            self._save_sidebar_state()
            return
        if width < SIDEBAR_WIDTH_MIN:
            # Between snap threshold and minimum: bounce back to the minimum
            # (the prototype clamps the same way).
            self._sidebar_applying = True
            total = sum(self.splitter.sizes()) or self.width()
            self.splitter.setSizes([SIDEBAR_WIDTH_MIN, max(total - SIDEBAR_WIDTH_MIN, 100)])
            self._sidebar_applying = False
            return
        self._sidebar_last_width = min(width, SIDEBAR_WIDTH_MAX)
        self._sidebar_save_timer.start(400)

    def _save_sidebar_state(self) -> None:
        """Persist sidebar width + collapsed flag (debounced via the timer)."""
        try:
            self.config.set_sidebar_width(self._sidebar_last_width)
            self.config.set_sidebar_collapsed(self._sidebar_collapsed)
        except OSError:
            pass  # non-fatal: sidebar cosmetics only

    # ── Navigation ───────────────────────────────────────────────────────

    def _select_nav(self, index: int, trigger: QPushButton | None = None) -> None:
        # v4 UX: clicking the already-active entry toggles the sidebar
        # instead of re-selecting the screen (footer entries included;
        # "Beenden" is not checkable and never routes here). Qt flips
        # isChecked() before emitting clicked, so restore the highlight.
        if trigger is not None and trigger is self._active_nav_btn:
            trigger.setChecked(True)
            self._toggle_sidebar()
            return
        self.stack.setCurrentIndex(index)
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == index)
        # The footer entries (settings / about) participate in the same
        # exclusive checked state as the area buttons.
        self.settings_btn.setChecked(trigger is self.settings_btn)
        self.about_btn.setChecked(trigger is self.about_btn)
        if trigger is not None:
            self._active_nav_btn = trigger
        elif index < len(self.nav_buttons):
            self._active_nav_btn = self.nav_buttons[index]

    # ── Application actions (reuse classic dialogs) ──────────────────────

    def _confirm_quit(self) -> None:
        """Ask for confirmation before closing the window (modern layout).

        Reuses the modern shutdown-confirm dialog with quit-specific texts;
        the application name is substituted into the ``{app}`` placeholder.
        Always shown — even with WOL_HEADLESS set — because a stray
        environment variable in the user's shell must not silently disable
        the confirmation (automated tests call ``close()`` directly and
        never route through here).
        """
        dialog = ModernShutdownConfirmDialog(
            "",
            self,
            title_key="modern.quit_confirm.title",
            message_key="modern.quit_confirm.message",
            yes_key="modern.quit_confirm.yes",
            no_key="modern.quit_confirm.no",
            message_kwargs={"app": Translations.tr("app.name")},
        )
        if dialog.exec():
            self.close()

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
        # Section labels (hidden while collapsed — text still refreshed).
        self.lbl_areas.setText(Translations.tr("modern.nav.areas").upper())
        self.lbl_app.setText(Translations.tr("modern.nav.application").upper())
        # Navigation labels: collapse-aware (icon-only must stay icon-only).
        for btn, (icon, key) in zip(self.nav_buttons, NAV_DEFS, strict=True):
            self._set_nav_button_text(btn, icon, key)
            btn.setToolTip(Translations.tr(key).replace("&", ""))
        footer_defs = [
            (self.settings_btn, "⚙", "menu.tools.settings"),
            (self.about_btn, "\u2139\ufe0f", "menu.help.about"),
            (self.quit_btn, "⏻", "menu.file.exit"),
        ]
        for btn, icon, key in footer_defs:
            self._set_nav_button_text(btn, icon, key)
            btn.setToolTip(Translations.tr(key).replace("&", ""))
        self.logo_mark.setToolTip(Translations.tr(
            "modern.nav.expand" if self._sidebar_collapsed
            else "modern.nav.collapse"))

        self.devices_view.retranslate()
        self.manage_view.retranslate()
        self.schedule_view.retranslate()
        self.logs_view.retranslate()
        self.settings_view.retranslate()
        self.update_view.retranslate()
        self.dashboard_view.retranslate()

    # ── Lifecycle ────────────────────────────────────────────────────────

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        # Flush any pending debounced sidebar width save.
        if self._sidebar_save_timer is not None:
            self._sidebar_save_timer.stop()
        self._save_sidebar_state()
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
