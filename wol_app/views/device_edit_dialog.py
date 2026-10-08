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

from wol_app.shared_password import (
    apply_api_key,
    apply_password,
    collect_api_key_share_targets,
    collect_share_targets,
)
from wol_app.translations import Translations
from wol_app.utils import (
    validate_api_key,
    validate_device_name,
    validate_ip_or_hostname,
    validate_mac,
    validate_password,
    validate_rustdesk_id,
    validate_username,
)
from wol_app.views.shutdown_confirm_dialog import ModernShutdownConfirmDialog
from wol_app.widgets.toggle_switch import ToggleSwitch


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

        # RDP certificate validation (mstsc "authentication level") used when
        # this device is opened with Remote Desktop. Default 1 = warn on an
        # unexpected certificate; 0 = connect without verifying (legacy),
        # 2 = connect only on an exact certificate match.
        self.rdp_auth_combo = QComboBox()
        for level in (1, 2, 0):
            self.rdp_auth_combo.addItem(
                Translations.tr(f"device_dialog.rdp_auth.{level}"), level)
        self.rdp_auth_combo.setToolTip(
            Translations.tr("device_dialog.rdp_auth.tooltip"))
        self._add_field(grid, 4, 0, "device_dialog.label.rdp_auth",
                        self.rdp_auth_combo, col_span=2)

        # RustDesk peer id (optional). A device routed to RustDesk is reached by
        # Direct IP Access (ip:21118) when this is empty; the id cannot be
        # discovered by a network scan, so it has to be entered once by hand.
        self.rustdesk_id_input = QLineEdit()
        self.rustdesk_id_input.setPlaceholderText(
            Translations.tr("device_dialog.placeholder.rustdesk_id"))
        self.rustdesk_id_input.setToolTip(
            Translations.tr("device_dialog.tooltip.rustdesk_id"))
        self._add_field(grid, 5, 0, "device_dialog.label.rustdesk_id",
                        self.rustdesk_id_input, col_span=2)

        # Watched processes (dashboard service chips, host service v3) -
        # comma separated, entries may carry ":port" for the API check.
        self.watch_input = QLineEdit()
        self.watch_input.setPlaceholderText(
            Translations.tr("device_dialog.placeholder.watch"))
        self.watch_input.setToolTip(
            Translations.tr("device_dialog.tooltip.watch"))
        self._add_field(grid, 6, 0, "device_dialog.label.watch",
                        self.watch_input, col_span=2)

        # Dashboard API key (host service protocol v10): sent along with the
        # metrics request so the host can present it as
        # "Authorization: Bearer <key>" when probing the inference API.
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setPlaceholderText(
            Translations.tr("device_dialog.placeholder.api_key"))
        self.api_key_input.setToolTip(
            Translations.tr("device_dialog.tooltip.api_key"))
        self._add_field(grid, 7, 0, "device_dialog.label.api_key",
                        self.api_key_input, col_span=2)

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
        self.watch_input.setText(", ".join(
            self.config.get_device_watch_processes(device)))
        self.api_key_input.setText(self.config.get_device_api_key(device))
        self.enabled_toggle.setChecked(device.get("enabled", True))
        # Set shutdown method (legacy devices default to "smb")
        method = self.config.get_device_shutdown_method(device)
        for idx in range(self.method_combo.count()):
            if self.method_combo.itemData(idx) == method:
                self.method_combo.setCurrentIndex(idx)
                break
        # Set RDP certificate-validation level (default 1)
        rdp_level = self.config.get_device_rdp_auth_level(device)
        for idx in range(self.rdp_auth_combo.count()):
            if self.rdp_auth_combo.itemData(idx) == rdp_level:
                self.rdp_auth_combo.setCurrentIndex(idx)
                break
        # RustDesk peer id ("" = the device is reached by Direct IP Access)
        self.rustdesk_id_input.setText(
            self.config.get_device_rustdesk_id(device))

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
        # The address is optional but must be a valid IPv4 or host name when set
        # (xrdp/Linux hosts are typically reached by name, e.g. ubuntu-mercury).
        if ip and not validate_ip_or_hostname(ip):
            QMessageBox.warning(self, Translations.tr("dialog.error.title"), Translations.tr("device_dialog.error.invalid_ip_or_host"))
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

        # Dashboard API key (optional) — goes into the Authorization header
        # of the host-side inference probes.
        api_key: str = self.api_key_input.text().strip()
        if api_key and not validate_api_key(api_key):
            QMessageBox.warning(self, Translations.tr("dialog.error.title"), Translations.tr("device_dialog.error.invalid_api_key"))
            return

        # RustDesk peer id (optional) — empty means "reach it by IP".
        rustdesk_id: str = self.rustdesk_id_input.text().strip()
        if rustdesk_id and not validate_rustdesk_id(rustdesk_id):
            QMessageBox.warning(self, Translations.tr("dialog.error.title"), Translations.tr("device_dialog.error.invalid_rustdesk_id"))
            return

        shutdown_method = self.method_combo.currentData()
        rdp_auth_level = self.rdp_auth_combo.currentData()
        watch_entries = self.config.get_device_watch_processes(
            {"watch_processes": self.watch_input.text().replace(";", ",").split(",")})

        if self.editing_device:
            updates = {
                "name": name,
                "mac": mac,
                "enabled": self.enabled_toggle.isChecked(),
                "shutdown_method": shutdown_method,
                "rdp_auth_level": rdp_auth_level,
                # Always written: an empty id removes the key again, which is
                # how the user switches a device back to Direct IP Access.
                "rustdesk_id": rustdesk_id,
            }
            if ip:
                updates["ip"] = ip
            if username:
                updates["username"] = username
            if password:
                updates["password"] = password
            self.config.update_device(self.editing_device["id"], **updates)
            # Only touch watch_processes on an actual change (avoids writing
            # an empty list into every edited device).
            if watch_entries != self.config.get_device_watch_processes(
                    self.editing_device):
                self.config.set_device_watch_processes(
                    self.editing_device["id"], watch_entries)
            # Same rule for the API key: only write on an actual change, so
            # editing a device never clears a key that is not shown here.
            previous_api_key = self.config.get_device_api_key(
                self.editing_device)
            api_key_changed = api_key != previous_api_key
            if api_key_changed:
                self.config.set_device_api_key(
                    self.editing_device["id"], api_key)
            # Re-fetch updated device
            saved = self.config.get_device_by_id(self.editing_device["id"])
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
                # Persist a non-default RDP certificate-validation level.
                if rdp_auth_level != 1:
                    self.config.update_device(device["id"], rdp_auth_level=rdp_auth_level)
                # RustDesk peer id (only when entered).
                if rustdesk_id:
                    self.config.update_device(
                        device["id"], rustdesk_id=rustdesk_id)
                if watch_entries:
                    self.config.set_device_watch_processes(
                        device["id"], watch_entries)
                if api_key:
                    self.config.set_device_api_key(device["id"], api_key)
                api_key_changed = bool(api_key)
                saved = self.config.get_device_by_id(device["id"])
            else:
                QMessageBox.warning(self, Translations.tr("dialog.error.title"), Translations.tr("device_dialog.error.save_failed"))
                return

        # Offer to apply the password to all other devices that share this
        # username (modern look, Ja/Nein like the shutdown confirmation).
        self._offer_shared_password(username, password,
                                    saved.get("id") if saved else None)
        # Same offer for the dashboard API key: it belongs to the inference
        # server rather than to a login, so it covers every other device.
        # Only asked when the key was actually (re-)entered, so saving an
        # unchanged device doesn't nag.
        if api_key_changed:
            self._offer_shared_api_key(api_key, saved.get("id") if saved else None)

        # Clear secrets from the input fields for security
        self.password_input.clear()
        self.api_key_input.clear()
        self.device_saved.emit(saved)
        self.accept()

    def _offer_shared_password(self, username: str, password: str,
                               current_id: str | None) -> None:
        """Ask whether to copy the password to devices with the same username."""
        targets = collect_share_targets(self.config, username, password,
                                        exclude_id=current_id)
        if not targets:
            return
        dialog = ModernShutdownConfirmDialog(
            "", self,
            title_key="device_dialog.apply_shared.title",
            message_key="device_dialog.apply_shared.message",
            yes_key="device_dialog.apply_shared.yes",
            no_key="device_dialog.apply_shared.no",
            message_kwargs={"username": username.strip(),
                            "count": len(targets)},
            yes_object_name="primaryButton",
            show_icon=False,
        )
        if dialog.exec():
            apply_password(self.config, targets, password)

    def _offer_shared_api_key(self, api_key: str,
                              current_id: str | None) -> None:
        """Ask whether to copy the API key to every other device."""
        targets = collect_api_key_share_targets(self.config, api_key,
                                                exclude_id=current_id)
        if not targets:
            return
        dialog = ModernShutdownConfirmDialog(
            "", self,
            title_key="device_dialog.apply_shared_key.title",
            message_key="device_dialog.apply_shared_key.message",
            yes_key="device_dialog.apply_shared_key.yes",
            no_key="device_dialog.apply_shared_key.no",
            message_kwargs={"count": len(targets)},
            yes_object_name="primaryButton",
            show_icon=False,
        )
        if dialog.exec():
            apply_api_key(self.config, targets, api_key)
