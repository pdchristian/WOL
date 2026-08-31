"""Modern UI: dialog for adding/editing a device.

Visually aligned with the Dark Control Center design (dialog background =
window bg, form inside a surface panel, labels above inputs, 2-column
field pairs, toggle row with the switch on the right); functionally
equivalent to the classic ``DeviceDialog`` in ``wol_app.device_dialog``
and writes through the same ``ConfigManager`` API.
"""

from typing import Any

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from wol_app.translations import Translations
from wol_app.widgets.toggle_switch import ToggleSwitch
from wol_app.utils import (
    validate_device_name,
    validate_mac,
    validate_password,
    validate_username,
)


class ModernDeviceDialog(QDialog):
    """Add or edit one device (modern layout)."""

    device_saved = pyqtSignal(dict)  # Emits device dict on save

    def __init__(
        self,
        config_manager: Any,
        device: dict | None = None,
        parent: QWidget | None = None,
        preset: dict | None = None,
    ) -> None:
        super().__init__(parent)
        self.config: Any = config_manager
        self.editing_device = device
        self.setWindowTitle(
            Translations.tr("device_dialog.title.edit")
            if device else Translations.tr("device_dialog.title.add")
        )
        self.setMinimumWidth(460)
        self._setup_ui()
        if device:
            self._fill_form(device)
        elif preset:
            # Pre-fill from a scan result (name/mac/ip) without editing mode
            self.name_input.setText(preset.get("name", ""))
            self.mac_input.setText(preset.get("mac", ""))
            self.ip_input.setText(preset.get("ip", ""))
        if not device:
            # Pre-select the default shutdown method from settings
            default_method = self.config.get_default_shutdown_method()
            for idx in range(self.method_combo.count()):
                if self.method_combo.itemData(idx) == default_method:
                    self.method_combo.setCurrentIndex(idx)
                    break

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # Header
        header = QLabel(
            Translations.tr("device_dialog.title.edit")
            if self.editing_device else Translations.tr("device_dialog.title.add")
        )
        header.setObjectName("pageTitle")
        layout.addWidget(header)

        # Form panel (surface card on the dialog bg)
        panel = QWidget()
        panel.setObjectName("panel")
        grid = QGridLayout(panel)
        grid.setContentsMargins(18, 16, 18, 16)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText(
            Translations.tr("device_dialog.placeholder.name")
        )
        self._add_field(grid, 0, 0, "device_dialog.label.name", self.name_input,
                        col_span=2)

        self.mac_input = QLineEdit()
        self.mac_input.setPlaceholderText(
            Translations.tr("device_dialog.placeholder.mac")
        )
        self._add_field(grid, 1, 0, "device_dialog.label.mac", self.mac_input)

        self.ip_input = QLineEdit()
        self.ip_input.setPlaceholderText(
            Translations.tr("device_dialog.placeholder.ip")
        )
        self._add_field(grid, 1, 1, "device_dialog.label.ip", self.ip_input)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText(
            Translations.tr("device_dialog.placeholder.user")
        )
        self._add_field(grid, 2, 0, "device_dialog.label.user",
                        self.username_input)

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText(
            Translations.tr("device_dialog.placeholder.password")
        )
        self._add_field(grid, 2, 1, "device_dialog.label.password",
                        self.password_input)

        self.method_combo = QComboBox()
        self.method_combo.addItem(
            Translations.tr("device_dialog.method.host_service"), "host_service",
        )
        self.method_combo.addItem(
            Translations.tr("device_dialog.method.smb"), "smb",
        )
        self._add_field(grid, 3, 0, "device_dialog.label.shutdown_method",
                        self.method_combo, col_span=2)

        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        layout.addWidget(panel)

        # Enabled toggle row (label left, switch right — like the schedule dialog)
        enabled_row = QHBoxLayout()
        enabled_label = QLabel(Translations.tr("device_dialog.enabled"))
        enabled_label.setObjectName("rowTitle")
        self.enabled_toggle = ToggleSwitch(checked=True)
        enabled_row.addWidget(enabled_label)
        enabled_row.addStretch()
        enabled_row.addWidget(self.enabled_toggle)
        layout.addLayout(enabled_row)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.save_btn = QPushButton(
            Translations.tr("device_dialog.button.update")
            if self.editing_device else Translations.tr("device_dialog.button.save")
        )
        self.save_btn.setObjectName("primaryButton")
        self.save_btn.clicked.connect(self._save)
        self.cancel_btn = QPushButton(Translations.tr("device_dialog.button.cancel"))
        self.cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.save_btn)
        btn_row.addWidget(self.cancel_btn)
        layout.addLayout(btn_row)

    def _add_field(
        self,
        grid: QGridLayout,
        row: int,
        col: int,
        label_key: str,
        field: QWidget,
        col_span: int = 1,
    ) -> None:
        """Place a ``fieldLabel`` above its input in the grid."""
        label = QLabel(Translations.tr(label_key))
        label.setObjectName("fieldLabel")
        grid.addWidget(label, row * 2, col, 1, col_span)
        grid.addWidget(field, row * 2 + 1, col, 1, col_span)

    def _fill_form(self, device: dict) -> None:
        self.name_input.setText(device.get("name", ""))
        self.mac_input.setText(device.get("mac", ""))
        self.ip_input.setText(device.get("ip", ""))
        self.username_input.setText(device.get("username", ""))
        self.password_input.setText(device.get("password", ""))
        self.enabled_toggle.setChecked(device.get("enabled", True))
        # Set shutdown method (legacy devices default to "smb")
        method = self.config.get_device_shutdown_method(device)
        for idx in range(self.method_combo.count()):
            if self.method_combo.itemData(idx) == method:
                self.method_combo.setCurrentIndex(idx)
                break

    def _save(self) -> None:
        name: str = self.name_input.text().strip()
        mac: str = self.mac_input.text().strip()
        ip: str = self.ip_input.text().strip()

        if not name:
            QMessageBox.warning(self, Translations.tr("dialog.error.title"), Translations.tr("device_dialog.error.missing_name"))
            return
        if not validate_device_name(name):
            QMessageBox.warning(self, Translations.tr("dialog.error.title"), Translations.tr("device_dialog.error.invalid_name"))
            return
        if not mac:
            QMessageBox.warning(self, Translations.tr("dialog.error.title"), Translations.tr("device_dialog.error.missing_mac"))
            return
        if not validate_mac(mac):
            QMessageBox.warning(self, Translations.tr("dialog.error.title"), Translations.tr("device_dialog.error.invalid_mac"))
            return

        username: str = self.username_input.text().strip()
        password: str = self.password_input.text().strip()

        # Validate username and password
        if username and not validate_username(username):
            QMessageBox.warning(self, Translations.tr("dialog.error.title"), Translations.tr("device_dialog.error.invalid_username"))
            return
        if password and not validate_password(password):
            QMessageBox.warning(self, Translations.tr("dialog.error.title"), Translations.tr("device_dialog.error.invalid_password"))
            return

        shutdown_method = self.method_combo.currentData()

        if self.editing_device:
            updates = {
                "name": name,
                "mac": mac,
                "enabled": self.enabled_toggle.isChecked(),
                "shutdown_method": shutdown_method,
            }
            if ip:
                updates["ip"] = ip
            if username:
                updates["username"] = username
            if password:
                updates["password"] = password
            self.config.update_device(self.editing_device["id"], **updates)
            # Re-fetch updated device
            updated = self.config.get_device_by_id(self.editing_device["id"])
            self.device_saved.emit(updated)
        else:
            device = self.config.add_device(
                name, mac, enabled=self.enabled_toggle.isChecked()
            )
            if device:
                if ip:
                    self.config.update_device(device["id"], ip=ip)
                if username:
                    self.config.update_device(device["id"], username=username)
                if password:
                    self.config.update_device(device["id"], password=password)
                # add_device already applied the default method; honour the
                # user's explicit selection (may differ from the default)
                if shutdown_method != device.get("shutdown_method"):
                    self.config.update_device(device["id"], shutdown_method=shutdown_method)
                self.device_saved.emit(self.config.get_device_by_id(device["id"]))
            else:
                QMessageBox.warning(self, Translations.tr("dialog.error.title"), Translations.tr("device_dialog.error.save_failed"))
                return

        # Clear password from input field for security
        self.password_input.clear()
        self.accept()
