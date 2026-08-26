"""Application shell for the new "Dark Control Center" UI.

Replaces the classic menu bar with a left sidebar navigation and a
``QStackedWidget`` on the right that switches between the application
screens. Each screen is a widget under :mod:`wol_app.screens`.
"""

from PyQt6.QtWidgets import QHBoxLayout, QStackedWidget, QVBoxLayout, QWidget

from wol_app.screens.about_screen import AboutScreen
from wol_app.screens.devices_screen import DevicesScreen
from wol_app.screens.logs_screen import LogsScreen
from wol_app.screens.manage_screen import ManageScreen
from wol_app.screens.schedule_screen import ScheduleScreen
from wol_app.screens.settings_screen import SettingsScreen
from wol_app.translations import Translations
from wol_app.widgets import Sidebar

# Navigation keys used by the sidebar items.
KEY_DEVICES = "devices"
KEY_MANAGE = "manage"
KEY_SCHEDULE = "schedule"
KEY_LOGS = "logs"
KEY_SETTINGS = "settings"
KEY_ABOUT = "about"


class MainShell(QWidget):
    """The application frame: sidebar navigation + stacked screens."""

    def __init__(self, config, engine, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.config = config
        self.engine = engine

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Left navigation rail
        self.sidebar = Sidebar(parent=self)
        self.sidebar.add_item(KEY_DEVICES, Translations.tr("sidebar.devices"))
        self.sidebar.add_item(KEY_MANAGE, Translations.tr("sidebar.manage"))
        self.sidebar.add_item(KEY_SCHEDULE, Translations.tr("sidebar.schedule"))
        self.sidebar.add_item(KEY_LOGS, Translations.tr("sidebar.logs"))
        self.sidebar.add_footer_item(KEY_SETTINGS, Translations.tr("sidebar.settings"))
        self.sidebar.add_footer_item(KEY_ABOUT, Translations.tr("sidebar.about"))
        self.sidebar.navigated.connect(self._on_navigate)
        root.addWidget(self.sidebar)

        # Right content area (with inner padding so content does not touch the
        # window edges).
        self.content_host = QWidget()
        content_layout = QVBoxLayout(self.content_host)
        content_layout.setContentsMargins(24, 20, 24, 20)
        content_layout.setSpacing(0)

        self.stack = QStackedWidget()
        self._screens: dict[str, QWidget] = {}
        self._register_screen(KEY_DEVICES, DevicesScreen(config, engine))
        self._register_screen(KEY_MANAGE, ManageScreen(config))
        self._register_screen(KEY_SCHEDULE, ScheduleScreen(config))
        self._register_screen(KEY_LOGS, LogsScreen(config))
        self._register_screen(KEY_SETTINGS, SettingsScreen(config))
        self._register_screen(KEY_ABOUT, AboutScreen(config))
        content_layout.addWidget(self.stack)
        root.addWidget(self.content_host, 1)

        self.sidebar.set_current(KEY_DEVICES)

    def _register_screen(self, key: str, widget: QWidget) -> None:
        self._screens[key] = widget
        self.stack.addWidget(widget)

    def _on_navigate(self, key: str) -> None:
        if key in self._screens:
            self.stack.setCurrentWidget(self._screens[key])

    # Convenience accessor for the devices screen (used by previews/tests).
    def devices_screen(self) -> DevicesScreen:
        return self._screens[KEY_DEVICES]  # type: ignore[return-value]
