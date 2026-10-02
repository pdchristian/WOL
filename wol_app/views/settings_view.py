"""Modern UI: "Einstellungen" screen (application & network configuration).

Layout mirrors the prototype's settings screen
(design_prototype/Geräte_Plattform_Einstellungen_v2.html):

1. Page header (title + subtitle).
2. One card per section — Netzwerk, Darstellung, Remote-Zugang, Sonstiges —
   each holding a two-column form grid: dim field label above each input
   (QLineEdit / QComboBox / QSpinBox) with an optional hint below, and the
   switches stacked full width.
3. An info label and a toolbar with "Zurücksetzen" and "Speichern"
   (primary) aligned to the right.

Feature-identical to the classic ``SettingsDialog`` — all persistence goes
through the shared ``ConfigManager`` using the same setters and the same
input validation (``_validate_broadcast_ip`` / ``_validate_port`` are
imported from ``wol_app.settings_dialog``) — plus the ``remote`` section
that maps each platform to RDP or TurboVNC. The prototype's
"Auto-Refresh" and "Host-Service Port" fields have no backend and are
intentionally omitted.

"Remote-Einstellungen" is *not* a separate screen: the remote fields live in
the "Remote-Zugang" group here, and the "Automatisch nach Updates suchen"
switch moved down next to the other switches.

The "Zurücksetzen" button restores factory defaults for the settings
sections only (network, updates, log limit, shutdown method, language,
display mode, remote routing); devices, schedules and logs are kept. The
layout mode is deliberately *not* reset — doing so would eject the user from
the modern layout mid-session.

After a successful save the view emits ``settings_saved`` so the main
window can re-apply the modern theme and retranslate every screen.
"""

import copy
import sys
from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from wol_app.config import (
    DEFAULT_CONFIG,
    DEFAULT_VNC_PORT,
    REMOTE_DESKTOP_RESOLUTION_AUTO,
    REMOTE_DESKTOP_RESOLUTIONS,
    REMOTE_PROTOCOL_RDP,
    REMOTE_PROTOCOL_VNC,
    VNC_PORT_MAX,
    VNC_PORT_MIN,
)
from wol_app.settings_dialog import _validate_broadcast_ip, _validate_port
from wol_app.translations import Translations
from wol_app.utils import OS_LINUX, OS_MACOS, OS_WINDOWS
from wol_app.widgets.toggle_switch import ToggleWithLabel


def _label(key: str) -> str:
    """Field label from an existing ``settings.label.*`` key.

    The classic dialog uses form labels with a trailing colon; the
    prototype's field labels have none — strip it.
    """
    return Translations.tr(key).rstrip(":").strip()


class Field(QWidget):
    """Prototype ``.field``: dim label above the input, optional hint below."""

    def __init__(
        self,
        label_key: str,
        widget: QWidget,
        hint_key: str = "",
        parent=None,
    ) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._label_key = label_key
        self._hint_key = hint_key

        self.label = QLabel(_label(label_key))
        self.label.setObjectName("fieldLabel")
        layout.addWidget(self.label)
        layout.addWidget(widget)

        self.hint: QLabel | None = None
        if hint_key:
            self.hint = QLabel(Translations.tr(hint_key))
            self.hint.setObjectName("fieldHint")
            self.hint.setWordWrap(True)
            layout.addWidget(self.hint)

    def retranslate(self, label_key: str = "") -> None:
        """Re-pick the label (and hint) texts; *label_key* may override the key."""
        if label_key:
            self._label_key = label_key
        self.label.setText(_label(self._label_key))
        if self.hint is not None:
            self.hint.setText(Translations.tr(self._hint_key))


class Group(QWidget):
    """Prototype ``.group``: card with an uppercase heading and a 2-column form.

    The settings screen used to be one flat grid; grouping it lets the new
    "Remote-Zugang" section sit alongside the existing fields instead of
    forming its own menu entry.
    """

    def __init__(self, title_key: str, parent=None) -> None:
        super().__init__(parent)
        self._title_key = title_key
        self.setObjectName("settingsGroup")
        # Plain QWidgets only paint their QSS background with this attribute.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 16, 20, 18)
        outer.setSpacing(14)

        self.title = QLabel(self._title_text())
        self.title.setObjectName("settingsGroupTitle")
        outer.addWidget(self.title)

        self.form = QGridLayout()
        self.form.setHorizontalSpacing(14)
        self.form.setVerticalSpacing(16)
        self.form.setColumnStretch(0, 1)
        self.form.setColumnStretch(1, 1)
        outer.addLayout(self.form)

    def add(self, widget: QWidget, row: int, col: int, span: int = 1) -> None:
        """Place *widget* in the group's form grid."""
        self.form.addWidget(widget, row, col, 1, span)

    def _title_text(self) -> str:
        # The prototype renders group headings with CSS text-transform.
        return Translations.tr(self._title_key).upper()

    def retranslate(self) -> None:
        self.title.setText(self._title_text())


class SettingsView(QWidget):
    """The modern "Einstellungen" screen."""

    settings_saved = pyqtSignal()

    def __init__(self, config_manager: Any, parent=None) -> None:
        super().__init__(parent)
        self.config: Any = config_manager
        self.restart_required: bool = False
        self._setup_ui()
        self._load_settings()

    # ── UI construction ──────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)

        content = QWidget()
        content.setObjectName("pageContent")
        content.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        scroll.setWidget(content)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(32, 26, 32, 26)
        layout.setSpacing(14)

        # ── Page header ──
        self.title = QLabel(Translations.tr("modern.settings.title"))
        self.title.setObjectName("pageTitle")
        self.subtitle = QLabel(Translations.tr("modern.settings.subtitle"))
        self.subtitle.setObjectName("pageSubtitle")
        layout.addWidget(self.title)
        layout.addWidget(self.subtitle)
        layout.addSpacing(10)

        # ── Grouped form: one card per section (prototype .group) ──
        self.group_network = Group("settings.group.network")
        self.group_appearance = Group("settings.group.appearance")
        self.group_remote = Group("settings.group.remote")
        self.group_misc = Group("settings.group.misc")
        for group in (
            self.group_network, self.group_appearance,
            self.group_remote, self.group_misc,
        ):
            layout.addWidget(group)

        # ── Netzwerk ──
        self.broadcast_ip_input = QLineEdit()
        self.broadcast_ip_input.setPlaceholderText("255.255.255.255")
        self.field_broadcast_ip = Field(
            "settings.label.broadcast_ip", self.broadcast_ip_input)
        self.group_network.add(self.field_broadcast_ip, 0, 0)

        self.broadcast_port_input = QSpinBox()
        self.broadcast_port_input.setRange(1, 65535)
        self.broadcast_port_input.setValue(9)
        self.field_broadcast_port = Field(
            "settings.label.broadcast_port", self.broadcast_port_input)
        self.group_network.add(self.field_broadcast_port, 0, 1)

        # ── Darstellung ──
        self.language_combo = QComboBox()
        for code, name in Translations.available_languages().items():
            self.language_combo.addItem(name, code)
        self.field_language = Field("settings.label.language", self.language_combo)
        self.group_appearance.add(self.field_language, 0, 0)

        self.display_mode_combo = QComboBox()
        self.display_mode_combo.addItem(
            Translations.tr("settings.display_mode.auto"), "auto")
        self.display_mode_combo.addItem(
            Translations.tr("settings.display_mode.light"), "light")
        self.display_mode_combo.addItem(
            Translations.tr("settings.display_mode.dark"), "dark")
        self.field_display_mode = Field(
            "settings.label.display_mode", self.display_mode_combo)
        self.group_appearance.add(self.field_display_mode, 0, 1)

        self.layout_mode_combo = QComboBox()
        self.layout_mode_combo.addItem(
            Translations.tr("settings.layout.classic"), "classic")
        self.layout_mode_combo.addItem(
            Translations.tr("settings.layout.modern"), "modern")
        self.field_layout_mode = Field(
            "settings.group.layout", self.layout_mode_combo)
        self.group_appearance.add(self.field_layout_mode, 1, 0)

        layout_hint = QLabel(Translations.tr("settings.layout.restart_hint"))
        layout_hint.setObjectName("fieldHint")
        layout_hint.setWordWrap(True)
        self.group_appearance.add(layout_hint, 2, 0)
        self.layout_hint = layout_hint

        # ── Remote-Zugang (the former "Remote Einstellungen" menu entry) ──
        self.remote_desktop_resolution_combo = QComboBox()
        # "Optimized 16:9" first (sentinel "auto"), then the fixed resolutions.
        self.remote_desktop_resolution_combo.addItem(
            Translations.tr("settings.label.remote_desktop_resolution_auto"),
            REMOTE_DESKTOP_RESOLUTION_AUTO,
        )
        for resolution in REMOTE_DESKTOP_RESOLUTIONS:
            w, h = resolution.split("x")
            self.remote_desktop_resolution_combo.addItem(f"{w} × {h}", resolution)
        self.field_rdp = Field(
            "settings.label.remote_desktop_resolution",
            self.remote_desktop_resolution_combo,
            hint_key="settings.hint.remote_resolution")
        self.group_remote.add(self.field_rdp, 0, 0)

        # Empty path = auto-detect (wol_app.utils.find_vnc_viewer).
        self.vnc_viewer_input = QLineEdit()
        self.field_vnc_viewer = Field(
            "settings.label.vnc_viewer_path", self.vnc_viewer_input,
            hint_key="settings.hint.vnc_path")
        self.group_remote.add(self.field_vnc_viewer, 0, 1)

        self.vnc_port_input = QSpinBox()
        self.vnc_port_input.setRange(VNC_PORT_MIN, VNC_PORT_MAX)
        self.vnc_port_input.setValue(DEFAULT_VNC_PORT)
        self.field_vnc_port = Field(
            "settings.label.vnc_port", self.vnc_port_input,
            hint_key="settings.hint.vnc_port")
        self.group_remote.add(self.field_vnc_port, 1, 0)

        # Which client the Remote buttons open, per detected platform.
        self.protocol_heading = QLabel(_label("settings.label.protocol_by_os"))
        self.protocol_heading.setObjectName("fieldLabel")
        self.group_remote.add(self.protocol_heading, 2, 0, 2)

        protocol_row = QHBoxLayout()
        protocol_row.setSpacing(12)
        protocol_holder = QWidget()
        protocol_holder.setLayout(protocol_row)
        self.protocol_combos: dict[str, QComboBox] = {}
        self.field_protocol: dict[str, Field] = {}
        for os_id in (OS_WINDOWS, OS_MACOS, OS_LINUX):
            combo = QComboBox()
            combo.addItem(
                Translations.tr("modern.devices.client_rdp"), REMOTE_PROTOCOL_RDP)
            combo.addItem(
                Translations.tr("modern.devices.client_vnc"), REMOTE_PROTOCOL_VNC)
            field = Field(f"scan_dialog.os.{os_id}", combo)
            self.protocol_combos[os_id] = combo
            self.field_protocol[os_id] = field
            protocol_row.addWidget(field, 1)
        self.group_remote.add(protocol_holder, 3, 0, 2)

        protocol_hint = QLabel(Translations.tr("settings.hint.protocol_by_os"))
        protocol_hint.setObjectName("fieldHint")
        protocol_hint.setWordWrap(True)
        self.group_remote.add(protocol_hint, 4, 0, 2)
        self.protocol_hint = protocol_hint

        # ── Sonstiges ──
        self.max_logs_input = QSpinBox()
        self.max_logs_input.setRange(10, 10000)
        self.max_logs_input.setSingleStep(50)
        self.max_logs_input.setValue(100)
        self.field_max_logs = Field(
            "settings.label.max_logs", self.max_logs_input)
        self.group_misc.add(self.field_max_logs, 0, 0)

        self.default_method_combo = QComboBox()
        self.default_method_combo.addItem(
            Translations.tr("device_dialog.method.host_service"), "host_service")
        self.default_method_combo.addItem(
            Translations.tr("device_dialog.method.smb"), "smb")
        self.field_shutdown_method = Field(
            "settings.label.default_shutdown_method", self.default_method_combo)
        self.group_misc.add(self.field_shutdown_method, 0, 1)

        # Relocated on purpose: the auto-update switch used to be the first
        # widget of the right column, now it sits with the other switches.
        self.auto_update_toggle = ToggleWithLabel(
            Translations.tr("settings.check.auto_update"))
        self.group_misc.add(self.auto_update_toggle, 1, 0, 2)

        self.update_interval_combo = QComboBox()
        self.update_interval_combo.addItem(
            Translations.tr("settings.interval.daily"), 24)
        self.update_interval_combo.addItem(
            Translations.tr("settings.interval.weekly"), 168)
        self.update_interval_combo.addItem(
            Translations.tr("settings.interval.monthly"), 720)
        self.field_interval = Field(
            "settings.label.interval", self.update_interval_combo)
        self.group_misc.add(self.field_interval, 2, 0)

        # Keep the app alive in the notification area when the window is
        # closed (modern layout; ignored when no system tray is available).
        self.close_to_tray_toggle = ToggleWithLabel(
            Translations.tr("settings.label.close_to_tray"))
        self.group_misc.add(self.close_to_tray_toggle, 3, 0, 2)

        # Off by default: a second launch raises the running instance's
        # window instead of starting twice (wol_app/single_instance.py).
        self.allow_multiple_toggle = ToggleWithLabel(
            Translations.tr("settings.label.allow_multiple_instances"))
        self.group_misc.add(self.allow_multiple_toggle, 4, 0, 2)

        # Public-network protection: privileged host-service commands
        # (shutdown/reboot/batch) stay disabled on a PUBLIC network unless
        # the user explicitly allows them here.
        self.allow_privileged_public_toggle = ToggleWithLabel(
            Translations.tr(
                "settings.label.allow_privileged_public_network"))
        self.group_misc.add(self.allow_privileged_public_toggle, 5, 0, 2)

        # ── macOS only: bundled WOL Host Service (install / update / remove)
        # Status text + action button in one field; the heavy lifting (admin
        # dialog, launchd registration) lives in wol_app.host_service_installer.
        self.hostservice_status: QLabel | None = None
        self.hostservice_btn: QPushButton | None = None
        self.hostservice_remove_btn: QPushButton | None = None
        self._hostservice_holder: dict[str, Any] = {}
        if sys.platform == "darwin":
            row_host = QHBoxLayout()
            row_host.setSpacing(10)
            self.hostservice_status = QLabel("")
            self.hostservice_status.setObjectName("placeholderText")
            self.hostservice_status.setWordWrap(True)
            row_host.addWidget(self.hostservice_status, 1)
            self.hostservice_btn = QPushButton("")
            self.hostservice_btn.setObjectName("primaryButton")
            self.hostservice_btn.clicked.connect(self._on_hostservice_action)
            row_host.addWidget(self.hostservice_btn, 0)
            self.hostservice_remove_btn = QPushButton("")
            self.hostservice_remove_btn.setObjectName("dangerButton")
            self.hostservice_remove_btn.clicked.connect(
                self._on_hostservice_remove)
            row_host.addWidget(self.hostservice_remove_btn, 0)
            host_container = QWidget()
            host_container.setLayout(row_host)
            self.field_hostservice = Field(
                "settings.label.hostservice", host_container)
            self.group_misc.add(self.field_hostservice, 6, 0, 2)
            self._refresh_hostservice_row()

        # ── Info label ──
        self.info_label = QLabel(Translations.tr("settings.info.text"))
        self.info_label.setObjectName("placeholderText")
        self.info_label.setWordWrap(True)
        layout.addSpacing(6)
        layout.addWidget(self.info_label)

        # ── Toolbar: reset / save (right-aligned, prototype .toolbar) ──
        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)
        toolbar.addStretch()

        self.reset_btn = QPushButton(Translations.tr("modern.settings.button.reset"))
        self.reset_btn.clicked.connect(self._reset_to_defaults)
        toolbar.addWidget(self.reset_btn)

        self.save_btn = QPushButton(Translations.tr("settings.button.save"))
        self.save_btn.setObjectName("primaryButton")
        self.save_btn.clicked.connect(self._save)
        toolbar.addWidget(self.save_btn)
        layout.addLayout(toolbar)

    # ── Load / save ──────────────────────────────────────────────────────

    def showEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        """Reload values whenever the page becomes visible."""
        super().showEvent(event)
        self._load_settings()
        # The service state may have changed since the last visit (first-start
        # prompt, terminal install): always re-read it from disk.
        if getattr(self, "hostservice_status", None) is not None:
            self._refresh_hostservice_row()

    def _select_combo_data(self, combo: QComboBox, value: Any) -> None:
        for idx in range(combo.count()):
            if combo.itemData(idx) == value:
                combo.setCurrentIndex(idx)
                return

    def _load_settings(self) -> None:
        net = self.config.get_network_settings()
        self.broadcast_ip_input.setText(net.get("broadcast_ip", "255.255.255.255"))
        self.broadcast_port_input.setValue(net.get("broadcast_port", 9))

        ui = self.config.config.get("ui", {})
        self._select_combo_data(
            self.language_combo, ui.get("language", "en"))
        self._select_combo_data(
            self.display_mode_combo, ui.get("display_mode", "auto"))
        self._select_combo_data(
            self.layout_mode_combo, self.config.get_layout_mode())

        update_settings = self.config.get_update_settings()
        self.auto_update_toggle.setChecked(
            update_settings.get("auto_check_enabled", True))
        self._select_combo_data(
            self.update_interval_combo,
            update_settings.get("check_interval_hours", 24))

        self.max_logs_input.setValue(self.config.get_max_logs())
        self._select_combo_data(
            self.default_method_combo, self.config.get_default_shutdown_method())
        self._select_combo_data(
            self.remote_desktop_resolution_combo,
            self.config.get_remote_desktop_resolution())

        # Remote routing (platform -> RDP / TurboVNC) and the VNC client
        self.vnc_viewer_input.setText(self.config.get_vnc_viewer_path())
        self.vnc_port_input.setValue(self.config.get_vnc_port())
        for os_id, combo in self.protocol_combos.items():
            self._select_combo_data(combo, self.config.get_remote_protocol(os_id))

        self.close_to_tray_toggle.setChecked(self.config.get_close_to_tray())
        self.allow_multiple_toggle.setChecked(
            self.config.get_allow_multiple_instances())
        self.allow_privileged_public_toggle.setChecked(
            self.config.get_allow_privileged_public_network())

    def _save(self) -> None:
        ip: str = self.broadcast_ip_input.text().strip()
        port: int = self.broadcast_port_input.value()

        # Input validation — identical to the classic SettingsDialog
        if not ip:
            QMessageBox.warning(
                self, Translations.tr("dialog.error.missing_ip"),
                Translations.tr("dialog.error.msg.missing_ip"))
            return
        if not _validate_broadcast_ip(ip):
            QMessageBox.warning(
                self, Translations.tr("dialog.error.invalid_ip"),
                Translations.tr("dialog.error.msg.invalid_ip"))
            return
        if not _validate_port(port):
            QMessageBox.warning(
                self, Translations.tr("dialog.error.invalid_port"),
                Translations.tr("dialog.error.msg.invalid_port"))
            return
        if len(ip) > 15:  # IPv4 max length
            QMessageBox.warning(
                self, Translations.tr("dialog.error.invalid_input"),
                Translations.tr("dialog.error.msg.long_ip"))
            return

        self.config.update_network_settings(broadcast_ip=ip, broadcast_port=port)

        selected_lang = self.language_combo.currentData()
        if selected_lang:
            self.config.update_ui_settings(language=selected_lang)
            Translations.set_language(selected_lang)

        selected_mode = self.display_mode_combo.currentData()
        if selected_mode:
            self.config.update_ui_settings(display_mode=selected_mode)

        selected_layout = self.layout_mode_combo.currentData()
        if selected_layout and selected_layout != self.config.get_layout_mode():
            self.config.set_layout_mode(selected_layout)
            self.restart_required = True

        self.config.update_update_settings(
            auto_check_enabled=self.auto_update_toggle.isChecked(),
            check_interval_hours=self.update_interval_combo.currentData(),
        )
        self.config.set_max_logs(self.max_logs_input.value())

        selected_method = self.default_method_combo.currentData()
        if selected_method:
            self.config.set_default_shutdown_method(selected_method)

        selected_resolution = self.remote_desktop_resolution_combo.currentData()
        if selected_resolution:
            self.config.set_remote_desktop_resolution(selected_resolution)

        # Remote routing: "" for the viewer path means "auto-detect again".
        self.config.set_vnc_viewer_path(self.vnc_viewer_input.text().strip())
        self.config.set_vnc_port(self.vnc_port_input.value())
        for os_id, combo in self.protocol_combos.items():
            protocol = combo.currentData()
            if protocol:
                self.config.set_remote_protocol(os_id, protocol)

        # Applied live via settings_saved → _apply_tray_mode (no restart).
        self.config.set_close_to_tray(self.close_to_tray_toggle.isChecked())
        # Takes effect on the next start (the lock is acquired at startup).
        self.config.set_allow_multiple_instances(
            self.allow_multiple_toggle.isChecked())
        # Applies immediately (checked per privileged command).
        self.config.set_allow_privileged_public_network(
            self.allow_privileged_public_toggle.isChecked())

        QMessageBox.information(
            self, Translations.tr("dialog.saved.title"),
            Translations.tr("dialog.saved.message"))
        self.settings_saved.emit()

    # ── Reset to factory defaults ────────────────────────────────────────

    def _reset_to_defaults(self) -> None:
        answer = QMessageBox.question(
            self,
            Translations.tr("modern.settings.reset.title"),
            Translations.tr("modern.settings.reset.message"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        # Settings sections only — devices, schedules and logs are kept.
        # The layout mode is deliberately preserved (resetting it would
        # eject the user from the modern layout mid-session).
        self.config.config["network"] = dict(DEFAULT_CONFIG["network"])
        self.config.config["updates"] = {
            "auto_check_enabled": DEFAULT_CONFIG["updates"]["auto_check_enabled"],
            "check_interval_hours": DEFAULT_CONFIG["updates"]["check_interval_hours"],
            "last_check_timestamp": None,
        }
        self.config.config["max_logs"] = DEFAULT_CONFIG["max_logs"]
        self.config.config["default_shutdown_method"] = DEFAULT_CONFIG["default_shutdown_method"]
        ui = self.config.config.setdefault("ui", {})
        ui["language"] = DEFAULT_CONFIG["ui"]["language"]
        ui["display_mode"] = "auto"
        ui["remote_desktop_resolution"] = DEFAULT_CONFIG["ui"]["remote_desktop_resolution"]
        ui["close_to_tray"] = DEFAULT_CONFIG["ui"]["close_to_tray"]
        ui["allow_multiple_instances"] = DEFAULT_CONFIG[
            "ui"]["allow_multiple_instances"]
        ui["allow_privileged_public_network"] = DEFAULT_CONFIG[
            "ui"]["allow_privileged_public_network"]
        # Remote routing + VNC client. Deep copy: the section nests the
        # protocol_by_os dict, a shallow copy would share it with the defaults.
        self.config.config["remote"] = copy.deepcopy(DEFAULT_CONFIG["remote"])
        self.config.save()

        Translations.set_language(DEFAULT_CONFIG["ui"]["language"])
        self._load_settings()
        self.retranslate()
        self.settings_saved.emit()

    # ── Language ─────────────────────────────────────────────────────────

    def retranslate(self) -> None:
        """Re-apply all texts after a language switch."""
        self.title.setText(Translations.tr("modern.settings.title"))
        self.subtitle.setText(Translations.tr("modern.settings.subtitle"))

        for group in (
            self.group_network, self.group_appearance,
            self.group_remote, self.group_misc,
        ):
            group.retranslate()

        self.field_broadcast_ip.retranslate("settings.label.broadcast_ip")
        self.field_broadcast_port.retranslate("settings.label.broadcast_port")
        self.field_language.retranslate("settings.label.language")
        self.field_display_mode.retranslate("settings.label.display_mode")
        self.field_layout_mode.retranslate("settings.group.layout")
        self.field_interval.retranslate("settings.label.interval")
        self.field_max_logs.retranslate("settings.label.max_logs")
        self.field_rdp.retranslate("settings.label.remote_desktop_resolution")
        self.field_vnc_viewer.retranslate("settings.label.vnc_viewer_path")
        self.field_vnc_port.retranslate("settings.label.vnc_port")
        self.protocol_heading.setText(_label("settings.label.protocol_by_os"))
        self.protocol_hint.setText(
            Translations.tr("settings.hint.protocol_by_os"))
        for field in self.field_protocol.values():
            field.retranslate()
        for combo in self.protocol_combos.values():
            combo.setItemText(0, Translations.tr("modern.devices.client_rdp"))
            combo.setItemText(1, Translations.tr("modern.devices.client_vnc"))
        self.field_shutdown_method.retranslate(
            "settings.label.default_shutdown_method")
        self.layout_hint.setText(Translations.tr("settings.layout.restart_hint"))
        self.info_label.setText(Translations.tr("settings.info.text"))

        # Combo item texts (data stays the same, only labels change)
        available = Translations.available_languages()
        for idx, name in enumerate(available.values()):
            self.language_combo.setItemText(idx, name)
        for idx, key in enumerate(
                ("settings.display_mode.auto", "settings.display_mode.light",
                 "settings.display_mode.dark")):
            self.display_mode_combo.setItemText(idx, Translations.tr(key))
        for idx, key in enumerate(
                ("settings.layout.classic", "settings.layout.modern")):
            self.layout_mode_combo.setItemText(idx, Translations.tr(key))
        for idx, key in enumerate(
                ("settings.interval.daily", "settings.interval.weekly",
                 "settings.interval.monthly")):
            self.update_interval_combo.setItemText(idx, Translations.tr(key))
        self.auto_update_toggle.setText(
            Translations.tr("settings.check.auto_update"))
        self.close_to_tray_toggle.setText(
            Translations.tr("settings.label.close_to_tray"))
        self.allow_multiple_toggle.setText(
            Translations.tr("settings.label.allow_multiple_instances"))
        self.allow_privileged_public_toggle.setText(
            Translations.tr(
                "settings.label.allow_privileged_public_network"))
        self.remote_desktop_resolution_combo.setItemText(
            0, Translations.tr("settings.label.remote_desktop_resolution_auto"))
        for idx, key in enumerate(
                ("device_dialog.method.host_service", "device_dialog.method.smb")):
            self.default_method_combo.setItemText(idx, Translations.tr(key))

        self.reset_btn.setText(Translations.tr("modern.settings.button.reset"))
        self.save_btn.setText(Translations.tr("settings.button.save"))

        # macOS host service row (labels follow the language switch too)
        if getattr(self, "hostservice_btn", None) is not None:
            self.field_hostservice.retranslate("settings.label.hostservice")
            self._refresh_hostservice_row()

    # ── macOS: bundled WOL Host Service row ──────────────────────────

    def _refresh_hostservice_row(self) -> None:
        """Update the status text and the button captions of the service row."""
        from wol_app import host_service_installer as hsi

        state, payload, installed = hsi.describe_state()
        if state == "none":
            # No payload (dev checkout) and nothing installed: nothing to do.
            self.hostservice_status.setText(
                Translations.tr("settings.hostservice.none"))
            self.hostservice_btn.setEnabled(False)
            self.hostservice_btn.setText("")
            self.hostservice_remove_btn.setVisible(False)
            return
        if state == "install":
            self.hostservice_status.setText(
                Translations.tr("settings.hostservice.not_installed"))
            self.hostservice_btn.setText(
                Translations.tr("settings.hostservice.install"))
            self.hostservice_remove_btn.setVisible(False)
        elif state == "update":
            self.hostservice_status.setText(
                Translations.tr("settings.hostservice.update_available",
                                version=payload, installed=installed or ""))
            self.hostservice_btn.setText(
                Translations.tr("settings.hostservice.update"))
            self.hostservice_remove_btn.setVisible(True)
        else:  # current
            self.hostservice_status.setText(
                Translations.tr("settings.hostservice.installed",
                                version=installed or ""))
            self.hostservice_btn.setText(
                Translations.tr("settings.hostservice.current"))
            self.hostservice_remove_btn.setVisible(True)
        self.hostservice_btn.setEnabled(
            state in ("install", "update") and not self._hostservice_holder)
        self.hostservice_remove_btn.setEnabled(not self._hostservice_holder)

    def _hostservice_texts(self) -> dict:
        """Localized prompt strings for the privileged admin dialogs."""
        return {
            "prompt_install": Translations.tr("dialog.hostservice.prompt.install"),
            "prompt_update": Translations.tr("dialog.hostservice.prompt.update"),
            "prompt_remove": Translations.tr("dialog.hostservice.prompt.remove"),
        }

    def _on_hostservice_action(self) -> None:
        from wol_app import host_service_installer as hsi

        hsi.run_privileged_action(
            "install", self._hostservice_texts(),
            self._on_hostservice_result, self._hostservice_holder)
        self.hostservice_btn.setEnabled(False)

    def _on_hostservice_remove(self) -> None:
        from wol_app import host_service_installer as hsi

        hsi.run_privileged_action(
            "remove", self._hostservice_texts(),
            self._on_hostservice_result, self._hostservice_holder)
        self.hostservice_remove_btn.setEnabled(False)

    def _on_hostservice_result(self, outcome: str, message: str) -> None:
        """Show the outcome of the admin operation and refresh the row."""
        if outcome == "cancelled":
            pass  # macOS admin dialog dismissed by the user: stays silent
        elif outcome == "removed":
            QMessageBox.information(
                self, Translations.tr("dialog.hostservice.removed.title"),
                Translations.tr("dialog.hostservice.removed.message"))
        elif outcome == "not_installed":
            pass
        elif outcome in ("failed", "no_payload") or message:
            QMessageBox.warning(
                self, Translations.tr("dialog.hostservice.failed.title"),
                Translations.tr("dialog.hostservice.failed.message")
                + "\n\n" + (message or outcome))
        else:  # installed / updated -> outcome carries the version
            QMessageBox.information(
                self, Translations.tr("dialog.hostservice.success.title"),
                Translations.tr("dialog.hostservice.success.message",
                                version=outcome))
        self._refresh_hostservice_row()
