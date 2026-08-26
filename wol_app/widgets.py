"""Reusable UI widgets for the Wake-on-LAN application.

Implements the "Dark Control Center" design building blocks (device cards,
status dots, badges, toggles) that are shared across the new screens. Widgets
rely on stable ``objectName`` values that the theme stylesheets target.
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from wol_app.translations import Translations


_STATUS_KEY = {
    "online": "status.online",
    "offline": "status.offline",
    "unknown": "status.unknown",
}


def _set_status_property(widget: QWidget, status: str) -> None:
    """Set the QSS dynamic property ``status`` and refresh the style."""
    widget.setProperty("status", status)
    # Re-polish so the stylesheet selector [#StatusDot[status=...]] applies
    widget.style().unpolish(widget)
    widget.style().polish(widget)


class StatusDot(QWidget):
    """A small round dot reflecting a device's online status."""

    def __init__(self, status: str = "unknown", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("StatusDot")
        self.setFixedSize(10, 10)
        self.set_status(status)

    def set_status(self, status: str) -> None:
        """Update the dot colour for the given status."""
        _set_status_property(self, status)


class StatusText(QLabel):
    """A label that colours itself according to a device's status."""

    def __init__(self, status: str = "unknown", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("StatusText")
        self.set_status(status)

    def set_status(self, status: str) -> None:
        """Update the text colour for the given status."""
        _set_status_property(self, status)
        self.setText(Translations.tr(_STATUS_KEY.get(status, "status.unknown")))


class DeviceCard(QFrame):
    """A card showing one device with its status and a wake action.

    Signals:
        wake_requested: emitted when the user clicks the wake button.
    """

    wake_requested = pyqtSignal(str)  # device_id

    def __init__(
        self,
        device_id: str,
        name: str,
        ip: str,
        mac: str,
        status: str = "unknown",
        enabled: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("DeviceCard")
        self.device_id = device_id

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(0)

        # Header row: name + status dot
        header = QHBoxLayout()
        self.title_label = QLabel(name)
        self.title_label.setObjectName("DeviceCardTitle")
        header.addWidget(self.title_label)
        header.addStretch()
        self.dot = StatusDot(status)
        header.addWidget(self.dot)
        root.addLayout(header)

        # Meta block: IP + MAC
        self.meta_label = QLabel(f"{ip}\n{mac}" if ip else mac)
        self.meta_label.setObjectName("DeviceCardMeta")
        self.meta_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        root.addSpacing(14)
        root.addWidget(self.meta_label)

        # Bottom row: status text + wake button
        bottom = QHBoxLayout()
        self.status_text = StatusText(status)
        bottom.addWidget(self.status_text)
        bottom.addStretch()

        self.wake_btn = QPushButton(Translations.tr("button.wake"))
        self.wake_btn.setObjectName("wakeButton")
        self.wake_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.wake_btn.clicked.connect(lambda: self.wake_requested.emit(self.device_id))
        bottom.addWidget(self.wake_btn)
        root.addSpacing(16)
        root.addLayout(bottom)

        if not enabled:
            self.setEnabled(False)
            self.setToolTip(Translations.tr("device.disabled"))

    def set_status(self, status: str) -> None:
        """Update the status dot and text."""
        self.dot.set_status(status)
        self.status_text.set_status(status)


class Toggle(QWidget):
    """A simple animated on/off switch."""

    toggled = pyqtSignal(bool)

    def __init__(self, checked: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(40, 22)
        self._checked = checked

        self._knob = QLabel(self)
        self._knob.setObjectName("ToggleKnob")
        self._knob.setFixedSize(16, 16)
        self._knob.move(3, 3)

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.set_checked(checked)

    def is_checked(self) -> bool:
        return self._checked

    def set_checked(self, checked: bool) -> None:
        self._checked = checked
        self.setProperty("state", "on" if checked else "off")
        self.style().unpolish(self)
        self.style().polish(self)
        self._knob.move(21 if checked else 3, 3)

    def mousePressEvent(self, event) -> None:
        self.set_checked(not self._checked)
        self.toggled.emit(self._checked)
        super().mousePressEvent(event)


class Sidebar(QWidget):
    """The left navigation rail of the "Dark Control Center" design.

    Holds a logo, a set of primary navigation items, and a footer group
    (application items such as Settings / About / Beenden). Navigation is
    modelled as checkable buttons styled through the ``#NavItem`` selector;
    switching selection emits :attr:`navigated` with the item's key.
    """

    navigated = pyqtSignal(str)

    def __init__(self, width: int = 230, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(width)
        self._items: dict[str, QPushButton] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 20, 12, 12)
        root.setSpacing(2)

        # Logo row
        logo_row = QHBoxLayout()
        logo_label = QLabel("W")
        logo_label.setObjectName("SidebarLogo")
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_label.setFixedSize(40, 40)
        self.app_name = QLabel(Translations.tr("app.name"))
        logo_row.addWidget(logo_label)
        logo_row.addSpacing(10)
        logo_row.addWidget(self.app_name)
        root.addLayout(logo_row)
        root.addSpacing(24)

        # Section label + primary items
        self.section_label = QLabel(Translations.tr("sidebar.section.areas"))
        self.section_label.setObjectName("SidebarLabel")
        root.addWidget(self.section_label)
        root.addSpacing(4)
        root.addWidget(self._make_separator())

        self._primary_host = QVBoxLayout()
        self._primary_host.setSpacing(2)
        root.addLayout(self._primary_host)

        root.addStretch()

        # Application footer
        self.footer_label = QLabel(Translations.tr("sidebar.section.application"))
        self.footer_label.setObjectName("SidebarLabel")
        root.addWidget(self.footer_label)
        root.addSpacing(4)
        self._footer_host = QVBoxLayout()
        self._footer_host.setSpacing(2)
        root.addLayout(self._footer_host)

    def _make_separator(self) -> QWidget:
        sep = QWidget()
        sep.setObjectName("NavSeparator")
        sep.setFixedHeight(1)
        return sep

    def _make_item(self, key: str, label: str) -> QPushButton:
        btn = QPushButton(label)
        btn.setObjectName("NavItem")
        btn.setCheckable(True)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(lambda: self.set_current(key))
        return btn

    def add_item(self, key: str, label: str) -> None:
        """Add a primary navigation item."""
        btn = self._make_item(key, label)
        self._items[key] = btn
        self._primary_host.addWidget(btn)

    def add_footer_item(self, key: str, label: str) -> None:
        """Add an item in the application footer group."""
        btn = self._make_item(key, label)
        self._items[key] = btn
        self._footer_host.addWidget(btn)

    def set_current(self, key: str) -> None:
        """Set the selected item and emit :attr:`navigated`."""
        if key not in self._items:
            return
        for k, btn in self._items.items():
            btn.setChecked(k == key)
        self.navigated.emit(key)
