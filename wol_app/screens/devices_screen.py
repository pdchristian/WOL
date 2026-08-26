"""Devices screen: main view with a card/list view toggle.

Implements the primary "Geräte" screen of the new design. It offers two
representations of the configured devices:

* **Cards** – a responsive-style grid of :class:`~wol_app.widgets.DeviceCard`.
* **List**  – a compact table, better suited for many devices.

The user can switch between both; the choice is persisted via
:meth:`ConfigManager.set_device_view_mode`.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from wol_app.translations import Translations
from wol_app.widgets import DeviceCard, StatusText


class DevicesScreen(QWidget):
    """Main devices view with a card/list toggle."""

    # Minimum card width (px) used to derive the responsive column count.
    _CARD_MIN_WIDTH = 230
    _GRID_SPACING = 16

    def __init__(self, config, engine, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.config = config
        self.engine = engine

        self._build_ui()
        self._apply_view_mode(self.config.get_device_view_mode())
        self.refresh()

    # ---- UI construction -------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(18)

        # Header row: title + search
        header = QHBoxLayout()
        self.title_label = QLabel(Translations.tr("ui.devices_group"))
        self.title_label.setObjectName("ScreenTitle")
        self.search_input = QLineEdit()
        self.search_input.setObjectName("SearchBox")
        self.search_input.setPlaceholderText(
            Translations.tr("ui.search_devices_placeholder")
        )
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self.refresh)
        header.addWidget(self.title_label)
        header.addStretch()
        header.addWidget(self.search_input, 1)
        root.addLayout(header)

        # Toolbar: actions + view toggle
        toolbar = QHBoxLayout()
        self.refresh_btn = QPushButton(Translations.tr("button.refresh"))
        self.refresh_btn.clicked.connect(self.refresh)
        self.wake_all_btn = QPushButton(Translations.tr("button.wake_all"))
        self.wake_all_btn.setObjectName("primaryButton")
        self.wake_all_btn.clicked.connect(self._wake_all)
        toolbar.addWidget(self.refresh_btn)
        toolbar.addWidget(self.wake_all_btn)
        toolbar.addStretch()

        self.view_toggle = QHBoxLayout()
        self.cards_btn = QPushButton(Translations.tr("ui.view.cards"))
        self.cards_btn.setCheckable(True)
        self.list_btn = QPushButton(Translations.tr("ui.view.list"))
        self.list_btn.setCheckable(True)
        self.cards_btn.clicked.connect(lambda: self._set_view_mode("cards"))
        self.list_btn.clicked.connect(lambda: self._set_view_mode("list"))
        self.view_toggle.addWidget(self.cards_btn)
        self.view_toggle.addWidget(self.list_btn)
        toolbar.addLayout(self.view_toggle)
        root.addLayout(toolbar)

        # Content stack: responsive cards grid + list table
        self.cards_scroll = QScrollArea()
        self.cards_scroll.setWidgetResizable(True)
        self.cards_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.cards_container = QWidget()
        self.cards_layout = QGridLayout(self.cards_container)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(self._GRID_SPACING)
        self.cards_scroll.setWidget(self.cards_container)
        self._cards: list[DeviceCard] = []

        self.table = QTableWidget()
        self.table.setObjectName("DeviceTable")
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels([
            Translations.tr("table.header.name"),
            Translations.tr("table.header.mac"),
            Translations.tr("table.header.ip"),
            Translations.tr("table.header.status"),
        ])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        header_view = self.table.horizontalHeader()
        header_view.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header_view.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)

        root.addWidget(self.cards_scroll)
        root.addWidget(self.table)

    # ---- View mode -------------------------------------------------------

    def _apply_view_mode(self, mode: str) -> None:
        """Show the cards grid or the list table based on *mode*."""
        if mode == "list":
            self.cards_scroll.hide()
            self.table.show()
            self.cards_btn.setChecked(False)
            self.list_btn.setChecked(True)
        else:
            self.table.hide()
            self.cards_scroll.show()
            self.cards_btn.setChecked(True)
            self.list_btn.setChecked(False)

    def _set_view_mode(self, mode: str) -> None:
        self._apply_view_mode(mode)
        self.config.set_device_view_mode(mode)

    def showEvent(self, event) -> None:
        """Re-flow the grid once the widget has its real size."""
        super().showEvent(event)
        self._reflow_cards()

    def resizeEvent(self, event) -> None:
        """Re-flow the card grid when the window is resized."""
        super().resizeEvent(event)
        self._reflow_cards()

    def _reflow_cards(self) -> None:
        """Arrange the current cards into a grid matching the available width."""
        columns = self._column_count()
        # Reset any previous column stretches so unused columns collapse.
        for col in range(self.cards_layout.columnCount()):
            self.cards_layout.setColumnStretch(col, 0)
        for index, card in enumerate(self._cards):
            row, col = index // columns, index % columns
            self.cards_layout.addWidget(card, row, col)
            self.cards_layout.setColumnStretch(col, 1)

    def _column_count(self) -> int:
        """Return how many cards fit side-by-side in the current viewport."""
        width = self.cards_scroll.viewport().width()
        if width <= 0:
            return 1
        return max(1, width // (self._CARD_MIN_WIDTH + self._GRID_SPACING))

    # ---- Data / refresh --------------------------------------------------

    def _filtered_devices(self) -> list:
        query = self.search_input.text().strip().lower()
        devices = self.config.get_devices()
        if not query:
            return devices
        fields = ("name", "mac", "ip", "username")
        return [
            d for d in devices
            if any(query in str(d.get(f, "")).lower() for f in fields)
        ]

    def refresh(self) -> None:
        """Rebuild both views from the current config."""
        devices = self._filtered_devices()

        # Cards: drop all existing cards (and their widgets)
        for card in self._cards:
            self.cards_layout.removeWidget(card)
            card.deleteLater()
        self._cards = []

        for dev in devices:
            card = DeviceCard(
                device_id=dev.get("id", ""),
                name=dev.get("name", ""),
                ip=dev.get("ip", ""),
                mac=dev.get("mac", ""),
                status=self.engine.get_device_status(dev.get("id", "")),
                enabled=dev.get("enabled", True),
                parent=self.cards_container,
            )
            card.wake_requested.connect(self._wake_device)
            self._cards.append(card)
        self._reflow_cards()

        # Table
        self.table.setRowCount(0)
        for dev in devices:
            row = self.table.rowCount()
            self.table.insertRow(row)
            name_item = QTableWidgetItem(dev.get("name", ""))
            name_item.setData(Qt.ItemDataRole.UserRole, dev.get("id", ""))
            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, QTableWidgetItem(dev.get("mac", "")))
            self.table.setItem(row, 2, QTableWidgetItem(dev.get("ip", "")))
            status = self.engine.get_device_status(dev.get("id", ""))
            status_widget = StatusText(status)
            self.table.setCellWidget(row, 3, status_widget)

    # ---- Actions ---------------------------------------------------------

    def _wake_device(self, device_id: str) -> None:
        device = self.config.get_device_by_id(device_id)
        if device is None:
            return
        self.engine.send_wake_packet(device_id)

    def _wake_all(self) -> None:
        for dev in self.config.get_devices():
            if dev.get("enabled", True):
                self.engine.send_wake_packet(dev.get("id", ""))
