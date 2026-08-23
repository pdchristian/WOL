"""Main Window for Wake-on-LAN Application."""

import os
import subprocess
import sys
from typing import Any, Literal, NoReturn

from PyQt6.QtCore import QThread, QTimer, pyqtSlot
from PyQt6.QtGui import QIcon, QKeySequence
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from wol_app import __version__
from wol_app.config import ConfigManager
from wol_app.device_dialog import DeviceManagerPage
from wol_app.host_service_client import send_host_command
from wol_app.log_dialog import LogPage
from wol_app.network_scan_dialog import NetworkScanPage
from wol_app.schedule_dialog import SchedulePage
from wol_app.settings_dialog import SettingsPage
from wol_app.theme import apply_display_mode, get_icon
from wol_app.translations import Translations
from wol_app.update_dialog import (
    UpdateAvailableDialog,
    UpdateErrorDialog,
    UpdateInfoDialog,
)
from wol_app.updater import UpdateChecker, check_for_updates_sync
from wol_app.utils import get_resource_path
from wol_app.wol_engine import WOLEngine

# Module-level registry to hold thread references until native threads truly finish
# Prevents premature GC of QThread wrapper objects while C-level I/O is blocked
_active_threads = []


def _track_thread(thread: "QThread") -> None:
    """Keep a strong reference to *thread* until it finishes, then auto-remove.

    This guarantees the registry never grows unbounded even if a worker's
    dedicated cleanup callback is missed or disconnected.
    """
    _active_threads.append(thread)

    def _on_finished() -> None:
        try:
            if thread in _active_threads:
                _active_threads.remove(thread)
        except Exception:
            pass

    thread.finished.connect(_on_finished)


# Headless/test mode: disables all background threads to avoid QThread shutdown warnings
# Set WOL_HEADLESS=1 in test/headless environments (CI, automated tests, no display)
HEADLESS_MODE: bool = os.environ.get("WOL_HEADLESS", "").lower() in ("1", "true", "yes")


class MainWindow(QMainWindow):
    """Main application window with a sidebar and stacked content pages."""

    # Page indices in the QStackedWidget
    PAGE_DEVICES = 0
    PAGE_SCHEDULES = 1
    PAGE_SCAN = 2
    PAGE_LOG = 3
    PAGE_SETTINGS = 4

    # Sidebar navigation items: (key, locale_key, icon, page_index)
    _SIDEBAR_ITEMS = [
        ("devices", "sidebar.devices", "devices", PAGE_DEVICES),
        ("schedules", "sidebar.schedules", "schedules", PAGE_SCHEDULES),
        ("scan", "sidebar.scan", "scan", PAGE_SCAN),
        ("log", "sidebar.log", "log", PAGE_LOG),
        ("settings", "sidebar.settings", "settings", PAGE_SETTINGS),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.config = ConfigManager()

        # Load language from config and initialize translations BEFORE any UI setup
        saved_language = self.config.config.get("ui", {}).get("language", "en")
        Translations.set_language(saved_language)

        self.engine: WOLEngine[ConfigManager] = WOLEngine(self.config)

        self.setWindowTitle(Translations.tr("app.name"))
        self.setMinimumSize(900, 600)

        # Update checker references
        self._update_thread = None
        self._update_worker = None
        self._update_check_running = False

        # Page references
        self.devices_page: DeviceManagerPage | None = None
        self.schedules_page: SchedulePage | None = None
        self.scan_page: NetworkScanPage | None = None
        self.log_page: LogPage | None = None
        self.settings_page: SettingsPage | None = None

        # Sidebar references
        self._sidebar_buttons: dict[str, QToolButton] = {}
        self._sidebar_button_group: QButtonGroup | None = None
        self._sidebar_title: QLabel | None = None
        self._sidebar_subtitle: QLabel | None = None
        self._stacked: QStackedWidget | None = None
        self._current_page = self.PAGE_DEVICES

        self._setup_ui()

        # Initial status check on startup (skip in headless mode)
        if not HEADLESS_MODE:
            try:
                if self.screen() is not None:
                    self.devices_page._refresh_statuses()
            except Exception:
                pass  # Skip status check if display unavailable

        # Start scheduler (skip in headless mode)
        if not HEADLESS_MODE:
            self.engine.schedule_fired.connect(self._on_schedule_fired)
            self.engine.start_scheduler()

        # Auto-check for updates on startup (skip if no display/headless mode)
        if not HEADLESS_MODE:
            try:
                if self.screen() is not None and self.config.should_check_for_updates():
                    QTimer.singleShot(5000, self._check_for_updates_async)
            except Exception:
                pass  # Skip update check if display unavailable

        # Auto-refresh device status every 30 seconds (skip in headless mode)
        if not HEADLESS_MODE:
            self.devices_page.start_auto_refresh()

    # ---- UI Setup -----------------------------------------------------------

    def _setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_sidebar())

        # Stacked content pages
        self._stacked = QStackedWidget()
        root.addWidget(self._stacked, 1)

        self._rebuild_pages()

        # Status bar
        self.statusBar().showMessage(Translations.tr("status.ready"))

    def _build_sidebar(self) -> QWidget:
        """Build the left navigation sidebar."""
        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(210)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(8, 14, 8, 14)
        layout.setSpacing(2)

        # App title + version
        self._sidebar_title = QLabel(Translations.tr("app.name"))
        self._sidebar_title.setObjectName("SidebarTitle")
        self._sidebar_title.setWordWrap(True)
        layout.addWidget(self._sidebar_title)

        self._sidebar_subtitle = QLabel(f"v{__version__}")
        self._sidebar_subtitle.setObjectName("SidebarSubtitle")
        layout.addWidget(self._sidebar_subtitle)

        layout.addSpacing(10)

        # Navigation buttons (one per page)
        self._sidebar_button_group = QButtonGroup(self)
        self._sidebar_button_group.setExclusive(True)

        for key, locale_key, icon, page_index in self._SIDEBAR_ITEMS:
            btn = QToolButton()
            btn.setText(Translations.tr(locale_key))
            btn.setIcon(get_icon(icon))
            btn.setCheckable(True)
            btn.setToolTip(Translations.tr(locale_key))
            btn.clicked.connect(lambda _=False, p=page_index, k=key: self._switch_page(p, k))
            self._sidebar_button_group.addButton(btn)
            self._sidebar_buttons[key] = btn
            layout.addWidget(btn)

        # Mark the initial page as checked
        initial = self._sidebar_buttons["devices"]
        if initial is not None:
            initial.setChecked(True)

        layout.addStretch(1)

        # Action buttons (do not switch pages)
        updates_btn = QToolButton()
        updates_btn.setText(Translations.tr("sidebar.check_updates"))
        updates_btn.setIcon(get_icon("update"))
        updates_btn.setToolTip(Translations.tr("sidebar.check_updates"))
        updates_btn.setShortcut(QKeySequence("Ctrl+U"))
        updates_btn.clicked.connect(self._manual_update_check)
        self._sidebar_buttons["updates"] = updates_btn
        layout.addWidget(updates_btn)

        about_btn = QToolButton()
        about_btn.setText(Translations.tr("sidebar.about"))
        about_btn.setIcon(get_icon("about"))
        about_btn.setToolTip(Translations.tr("sidebar.about"))
        about_btn.clicked.connect(self._show_about)
        self._sidebar_buttons["about"] = about_btn
        layout.addWidget(about_btn)

        return sidebar

    def _rebuild_pages(self) -> None:
        """(Re)create the stacked content pages and wire up their signals.

        Called on startup and after a language change so every page reflects
        the active locale.
        """
        prev_page = self._current_page

        # Stop the auto-refresh timer before tearing down the old device page
        if self.devices_page is not None:
            self.devices_page.stop_auto_refresh()

        # Clear the stacked widget
        while self._stacked.count() > 0:
            w = self._stacked.widget(0)
            self._stacked.removeWidget(w)
            w.deleteLater()

        # Create pages
        self.devices_page = DeviceManagerPage(self.config, self.engine, parent=self)
        self.schedules_page = SchedulePage(self.config, parent=self)
        self.scan_page = NetworkScanPage(self.config, parent=self)
        self.log_page = LogPage(self.config, parent=self)
        self.settings_page = SettingsPage(self.config, parent=self)

        for page in (
            self.devices_page,
            self.schedules_page,
            self.scan_page,
            self.log_page,
            self.settings_page,
        ):
            self._stacked.addWidget(page)

        # Wire cross-page signals
        self.devices_page.request_scan.connect(lambda: self._switch_page(self.PAGE_SCAN, "scan"))
        self.scan_page.device_added.connect(self._on_device_added)
        self.settings_page.settings_saved.connect(self._apply_language)

        # Restore the previously visible page
        self._switch_page(prev_page, self._page_key_for_index(prev_page))

        # Restart the auto-refresh timer on the new device page
        if not HEADLESS_MODE:
            self.devices_page.start_auto_refresh()

    def _page_key_for_index(self, index: int) -> str:
        for key, _locale, _icon, page_index in self._SIDEBAR_ITEMS:
            if page_index == index:
                return key
        return "devices"

    def _switch_page(self, page_index: int, key: str | None = None) -> None:
        """Switch the stacked widget to *page_index* and update the sidebar."""
        self._current_page = page_index
        self._stacked.setCurrentIndex(page_index)
        if key is not None:
            btn = self._sidebar_buttons.get(key)
            if btn is not None and btn.isCheckable():
                btn.setChecked(True)

    def _on_device_added(self) -> None:
        """Refresh the device table after a device is added from a scan."""
        if self.devices_page is not None:
            self.devices_page._refresh_table()
            if not HEADLESS_MODE:
                self.devices_page._refresh_statuses()

    # ---- Update Checker Methods ---------------------------------------------

    def _check_for_updates_async(self) -> None:
        """Check for updates in a background thread (follows StatusWorker pattern)."""
        if self._update_check_running:
            return
        self._update_check_running = True

        self._update_worker = UpdateChecker(current_version=__version__)
        self._update_thread = QThread()
        self._update_worker.moveToThread(self._update_thread)

        self._update_thread.started.connect(self._update_worker.run)
        self._update_worker.finished.connect(self._on_update_check_finished)
        self._update_worker.finished.connect(self._update_thread.quit)
        self._update_thread.finished.connect(self._update_thread.deleteLater)

        def on_async_done() -> None:
            self._update_check_running = False
            if self._update_worker is not None:
                self._update_worker.deleteLater()
            self._update_worker = None
            self._update_thread = None
        self._update_thread.finished.connect(on_async_done)

        # Track in module-level registry (auto-removes on finish) to prevent GC
        _track_thread(self._update_thread)
        self._update_thread.start()

    def _on_update_check_finished(self, release_info, has_update) -> None:
        """Handle result of background update check."""
        if has_update and release_info:
            # Show update available dialog for the auto-check
            dlg = UpdateAvailableDialog(release_info, __version__, self)
            dlg.exec()

    def _manual_update_check(self) -> None:
        """Manually check for updates via the sidebar."""
        if self._update_check_running:
            QMessageBox.information(
                self, "Update Check Running",
                "An update check is already in progress. Please wait.",
            )
            return

        result: tuple[Any, bool] | tuple[None, Literal[False]] = check_for_updates_sync(current_version=__version__)

        if result is None:
            # No internet / network error
            dlg = UpdateErrorDialog(self)
            dlg.exec()
            return

        release_info, has_update = result
        if has_update and release_info:
            dlg = UpdateAvailableDialog(release_info, __version__, self)
            dlg.exec()
        else:
            # Current version is up to date
            dlg = UpdateInfoDialog(self)
            dlg.exec()

    # ---- Scheduler Handlers -------------------------------------------------

    @pyqtSlot(str, str)
    def _on_schedule_fired(self, device_id: str, action: str) -> None:
        """Handle scheduled action trigger - dispatch to wake or shutdown."""
        if action == "shutdown":
            self._scheduled_shutdown(device_id)
        else:
            self.engine.send_wake_packet(device_id)

    def _scheduled_host_service_shutdown(self, device_name: str, ip: str, device: dict) -> None:
        """Execute a scheduled shutdown via the WOL Host Service (no dialog)."""
        username = device.get("username", "")
        password = device.get("password", "")

        if not username or not password:
            msg = Translations.tr("status.scheduled_shutdown_fail", name=device_name, error=Translations.tr("status.scheduled_shutdown_missing_creds"))
            self.statusBar().showMessage(msg, 5000)
            self.config.add_log(device_name, "SHUTDOWN", "FAILED", msg)
            QApplication.processEvents()
            return

        try:
            success, message = send_host_command(ip, "shutdown", username, password)
            if success:
                msg = Translations.tr("status.scheduled_shutdown_success", name=device_name)
                self.statusBar().showMessage(msg, 5000)
                self.config.add_log(device_name, "SHUTDOWN", "SUCCESS", f"Host service: {message}")
            else:
                msg = Translations.tr("status.scheduled_shutdown_fail", name=device_name, error=message)
                self.statusBar().showMessage(msg, 5000)
                self.config.add_log(device_name, "SHUTDOWN", "FAILED", f"Host service: {message}")
        except Exception as e:
            msg = Translations.tr("status.scheduled_shutdown_error", name=device_name, error=str(e))
            self.statusBar().showMessage(msg, 5000)
            self.config.add_log(device_name, "SHUTDOWN", "FAILED", msg)

        QApplication.processEvents()

    def _scheduled_shutdown(self, device_id: str) -> None:
        """Execute remote shutdown for a scheduled entry (no confirmation dialog)."""
        device = self.config.get_device_by_id(device_id)
        if not device:
            msg: str = Translations.tr("status.device_not_found", device_id=device_id)
            self.statusBar().showMessage(msg, 5000)
            return

        device_name = device.get("name", Translations.tr("device.unknown"))
        ip = device.get("ip", "")

        self.statusBar().showMessage(Translations.tr("status.scheduled_shutdown_starting", name=device_name, ip=ip), 0)
        self.config.add_log(device_name, "SHUTDOWN", "IN_PROGRESS", Translations.tr("status.scheduled_shutdown_progress", name=device_name))

        # Dispatch on the device's shutdown method
        if self.config.get_device_shutdown_method(device) == "host_service":
            self._scheduled_host_service_shutdown(device_name, ip, device)
            return

        try:
            # Step 1: Establish IPC$ connection
            username = device.get("username", "")
            password = device.get("password", "")

            if username:
                cmd: str = rf'net use \\{ip}\IPC$ "{password}" /user:"{username}"'
            else:
                cmd: str = rf'net use \\{ip}\IPC$'

            result: subprocess.CompletedProcess[str] = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=15
            )

            if result.returncode != 0:
                msg: str = Translations.tr("status.scheduled_shutdown_conn_fail", name=device_name, error=result.stderr.strip())
                self.statusBar().showMessage(msg, 5000)
                self.config.add_log(device_name, "SHUTDOWN", "FAILED", msg)
                QApplication.processEvents()
                return

            # Step 2: Execute remote shutdown
            cmd: str = rf'shutdown /m \\{ip} /s /t 0 /f'
            result: subprocess.CompletedProcess[str] = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30
            )

            if result.returncode == 0:
                msg: str = Translations.tr("status.scheduled_shutdown_success", name=device_name)
                self.statusBar().showMessage(msg, 5000)
                self.config.add_log(device_name, "SHUTDOWN", "SUCCESS", msg)
            else:
                msg: str = Translations.tr("status.scheduled_shutdown_fail", name=device_name, error=result.stderr.strip())
                self.statusBar().showMessage(msg, 5000)
                self.config.add_log(device_name, "SHUTDOWN", "FAILED", msg)

        except subprocess.TimeoutExpired:
            msg: str = Translations.tr("status.scheduled_shutdown_timeout", name=device_name)
            self.statusBar().showMessage(msg, 5000)
            self.config.add_log(device_name, "SHUTDOWN", "TIMEOUT", msg)
        except Exception as e:
            msg: str = Translations.tr("status.scheduled_shutdown_error", name=device_name, error=str(e))
            self.statusBar().showMessage(msg, 5000)
            self.config.add_log(device_name, "SHUTDOWN", "FAILED", msg)

        QApplication.processEvents()

    # ---- Language / About ---------------------------------------------------

    def _apply_language(self) -> None:
        """Refresh all UI text after a language change.

        Rebuilds the stacked pages (they bake translations at construction)
        and updates the sidebar labels in place.
        """
        self.setWindowTitle(Translations.tr("app.name"))

        # Update sidebar labels
        for key, locale_key, _icon, _idx in self._SIDEBAR_ITEMS:
            btn = self._sidebar_buttons.get(key)
            if btn is not None:
                btn.setText(Translations.tr(locale_key))
                btn.setToolTip(Translations.tr(locale_key))
        for key, locale_key in (("updates", "sidebar.check_updates"), ("about", "sidebar.about")):
            btn = self._sidebar_buttons.get(key)
            if btn is not None:
                btn.setText(Translations.tr(locale_key))
                btn.setToolTip(Translations.tr(locale_key))

        # Rebuild pages so they reflect the new locale
        self._rebuild_pages()

    def _show_about(self) -> None:
        QMessageBox.about(
            self, Translations.tr("dialog.about.title"),
            "<h3>Wake-on-LAN Manager</h3>"
            f"<p>{Translations.tr('dialog.about.version')} {__version__}</p>"
            f"<p>{Translations.tr('dialog.about.description')}</p>"
            f"<p>{Translations.tr('dialog.about.supports')}</p>"
        )

    def closeEvent(self, event) -> None:
        """Wait for all background threads to finish before closing."""
        # Stop device-page timers and cancel in-flight status checks
        if self.devices_page is not None:
            self.devices_page.cleanup()

        # Cancel the update worker
        if self._update_worker is not None:
            self._update_worker.cancel()

        self.engine.stop_scheduler()

        # Wait for the update thread to actually finish
        if self._update_thread is not None and self._update_thread.isRunning():
            self._update_thread.quit()
            self._update_thread.wait(5000)

        # Clear worker references
        self._update_worker = None
        self._update_thread = None

        # Clear module-level registry — threads will be GC'd when MainWindow is destroyed
        _active_threads.clear()

        event.accept()


def main() -> NoReturn:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # Clean modern look on Windows

    # Initialize config and translations
    config = ConfigManager()
    trans = Translations()
    language = config.config.get("ui", {}).get("language", "en")
    trans.load(language)

    # Apply display mode (auto / light / dark)
    display_mode = config.config.get("ui", {}).get("display_mode", "auto")
    apply_display_mode(app, display_mode)

    icon_path: str = get_resource_path("icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
