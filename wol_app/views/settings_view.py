"""Modern UI: "Einstellungen" screen (application & network configuration).

Layout mirrors the prototype's settings screen
(design_prototype/dark_control_center_full.html):

1. Page header (title + subtitle).
2. A two-column form grid: dim field label above each input
   (QLineEdit / QComboBox / QSpinBox / QCheckBox).
3. An info label and a toolbar with "Zurücksetzen" and "Speichern"
   (primary) aligned to the right.

Feature-identical to the classic ``SettingsDialog`` — all persistence goes
through the shared ``ConfigManager`` using the same setters and the same
input validation (``_validate_broadcast_ip`` / ``_validate_port`` are
imported from ``wol_app.settings_dialog``). The prototype's
"Auto-Refresh" and "Host-Service Port" fields have no backend and are
intentionally omitted.

The "Zurücksetzen" button restores factory defaults for the settings
sections only (network, updates, log limit, shutdown method, language,
display mode); devices, schedules and logs are kept. The layout mode is
deliberately *not* reset — doing so would eject the user from the modern
layout mid-session.

After a successful save the view emits ``settings_saved`` so the main
window can re-apply the modern theme and retranslate every screen.
"""

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
    REMOTE_DESKTOP_RESOLUTION_AUTO,
    REMOTE_DESKTOP_RESOLUTIONS,
)
from wol_app.settings_dialog import _validate_broadcast_ip, _validate_port
from wol_app.translations import Translations
from wol_app.widgets.toggle_switch import ToggleWithLabel


def _label(key: str) -> str:
    """Field label from an existing ``settings.label.*`` key.

    The classic dialog uses form labels with a trailing colon; the
    prototype's field labels have none — strip it.
    """
    return Translations.tr(key).rstrip(":").strip()


class Field(QWidget):
    """Prototype ``.field``: dim label above the input widget."""

    def __init__(self, label_key: str, widget: QWidget, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.label = QLabel(_label(label_key))
        self.label.setObjectName("fieldLabel")
        layout.addWidget(self.label)
        layout.addWidget(widget)

    def retranslate(self, label_key: str) -> None:
        self.label.setText(_label(label_key))


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

        # ── Form grid (two columns, prototype .form-grid) ──
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(16)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        # Left column: network + appearance
        self.broadcast_ip_input = QLineEdit()
        self.broadcast_ip_input.setPlaceholderText("255.255.255.255")
        self.field_broadcast_ip = Field(
            "settings.label.broadcast_ip", self.broadcast_ip_input)
        grid.addWidget(self.field_broadcast_ip, 0, 0)

        self.broadcast_port_input = QSpinBox()
        self.broadcast_port_input.setRange(1, 65535)
        self.broadcast_port_input.setValue(9)
        self.field_broadcast_port = Field(
            "settings.label.broadcast_port", self.broadcast_port_input)
        grid.addWidget(self.field_broadcast_port, 1, 0)

        self.language_combo = QComboBox()
        for code, name in Translations.available_languages().items():
            self.language_combo.addItem(name, code)
        self.field_language = Field("settings.label.language", self.language_combo)
        grid.addWidget(self.field_language, 2, 0)

        self.display_mode_combo = QComboBox()
        self.display_mode_combo.addItem(
            Translations.tr("settings.display_mode.auto"), "auto")
        self.display_mode_combo.addItem(
            Translations.tr("settings.display_mode.light"), "light")
        self.display_mode_combo.addItem(
            Translations.tr("settings.display_mode.dark"), "dark")
        self.field_display_mode = Field(
            "settings.label.display_mode", self.display_mode_combo)
        grid.addWidget(self.field_display_mode, 3, 0)

        self.layout_mode_combo = QComboBox()
        self.layout_mode_combo.addItem(
            Translations.tr("settings.layout.classic"), "classic")
        self.layout_mode_combo.addItem(
            Translations.tr("settings.layout.modern"), "modern")
        self.field_layout_mode = Field(
            "settings.group.layout", self.layout_mode_combo)
        grid.addWidget(self.field_layout_mode, 4, 0)

        layout_hint = QLabel(Translations.tr("settings.layout.restart_hint"))
        layout_hint.setObjectName("fieldHint")
        layout_hint.setWordWrap(True)
        grid.addWidget(layout_hint, 5, 0)
        self.layout_hint = layout_hint

        # Right column: updates + misc
        self.auto_update_toggle = ToggleWithLabel(
            Translations.tr("settings.check.auto_update"))
        grid.addWidget(self.auto_update_toggle, 0, 1)

        self.update_interval_combo = QComboBox()
        self.update_interval_combo.addItem(
            Translations.tr("settings.interval.daily"), 24)
        self.update_interval_combo.addItem(
            Translations.tr("settings.interval.weekly"), 168)
        self.update_interval_combo.addItem(
            Translations.tr("settings.interval.monthly"), 720)
        self.field_interval = Field(
            "settings.label.interval", self.update_interval_combo)
        grid.addWidget(self.field_interval, 1, 1)

        self.max_logs_input = QSpinBox()
        self.max_logs_input.setRange(10, 10000)
        self.max_logs_input.setSingleStep(50)
        self.max_logs_input.setValue(100)
        self.field_max_logs = Field(
            "settings.label.max_logs", self.max_logs_input)
        grid.addWidget(self.field_max_logs, 2, 1)

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
            self.remote_desktop_resolution_combo)
        grid.addWidget(self.field_rdp, 3, 1)

        self.default_method_combo = QComboBox()
        self.default_method_combo.addItem(
            Translations.tr("device_dialog.method.host_service"), "host_service")
        self.default_method_combo.addItem(
            Translations.tr("device_dialog.method.smb"), "smb")
        self.field_shutdown_method = Field(
            "settings.label.default_shutdown_method", self.default_method_combo)
        grid.addWidget(self.field_shutdown_method, 4, 1)

        layout.addLayout(grid)

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

        self.field_broadcast_ip.retranslate("settings.label.broadcast_ip")
        self.field_broadcast_port.retranslate("settings.label.broadcast_port")
        self.field_language.retranslate("settings.label.language")
        self.field_display_mode.retranslate("settings.label.display_mode")
        self.field_layout_mode.retranslate("settings.group.layout")
        self.field_interval.retranslate("settings.label.interval")
        self.field_max_logs.retranslate("settings.label.max_logs")
        self.field_rdp.retranslate("settings.label.remote_desktop_resolution")
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
        self.remote_desktop_resolution_combo.setItemText(
            0, Translations.tr("settings.label.remote_desktop_resolution_auto"))
        for idx, key in enumerate(
                ("device_dialog.method.host_service", "device_dialog.method.smb")):
            self.default_method_combo.setItemText(idx, Translations.tr(key))

        self.reset_btn.setText(Translations.tr("modern.settings.button.reset"))
        self.save_btn.setText(Translations.tr("settings.button.save"))
