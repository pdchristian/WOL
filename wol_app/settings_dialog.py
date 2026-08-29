"""Settings Dialog for Wake-on-LAN Application."""

import re
from typing import Any

from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from wol_app.config import (
    REMOTE_DESKTOP_RESOLUTION_AUTO,
    REMOTE_DESKTOP_RESOLUTIONS,
)
from wol_app.theme import apply_display_mode
from wol_app.translations import Translations


def _validate_broadcast_ip(ip: str) -> bool:
    """Validiert Broadcast-IP-Adressen"""
    if not ip:
        return False
    # IPv4 oder spezielle Broadcast-Adressen
    ipv4_pattern = r'^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?|255)$'
    return bool(re.match(ipv4_pattern, ip))


def _validate_port(port: int) -> bool:
    """Validiert Port-Nummern"""
    return 1 <= port <= 65535


class SettingsDialog(QDialog):
    """Dialog for configuring network and broadcast settings."""

    def __init__(self, config_manager, parent=None) -> None:
        super().__init__(parent)
        self.config: Any = config_manager
        self.setWindowTitle(Translations.tr("settings.title"))
        self.setMinimumWidth(640)
        # True when a setting (e.g. the layout mode) only takes effect after an app restart.
        self.restart_required: bool = False
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Two-column arrangement: too many groups for a single column.
        columns = QHBoxLayout()
        columns.setSpacing(16)
        left_col = QVBoxLayout()
        left_col.setSpacing(12)
        right_col = QVBoxLayout()
        right_col.setSpacing(12)
        columns.addLayout(left_col, 1)
        columns.addLayout(right_col, 1)
        layout.addLayout(columns)

        # ── Left column ──────────────────────────────────────────────────

        # --- Network Group ---
        network_group = QGroupBox(Translations.tr("settings.group.network"))
        form = QFormLayout()

        self.broadcast_ip_input = QLineEdit()
        self.broadcast_ip_input.setPlaceholderText("255.255.255.255")
        form.addRow(Translations.tr("settings.label.broadcast_ip"), self.broadcast_ip_input)

        self.broadcast_port_input = QSpinBox()
        self.broadcast_port_input.setRange(1, 65535)
        self.broadcast_port_input.setValue(9)
        form.addRow(Translations.tr("settings.label.broadcast_port"), self.broadcast_port_input)

        network_group.setLayout(form)
        left_col.addWidget(network_group)

        # --- Language Group ---
        lang_group = QGroupBox(Translations.tr("settings.group.language"))
        lang_layout = QVBoxLayout()

        self.language_combo = QComboBox()
        available = Translations.available_languages()
        for code, name in available.items():
            self.language_combo.addItem(name, code)
        lang_layout.addWidget(self.language_combo)

        lang_group.setLayout(lang_layout)
        left_col.addWidget(lang_group)

        # --- Display Mode Group ---
        display_group = QGroupBox(Translations.tr("settings.group.display_mode"))
        display_layout = QVBoxLayout()

        self.display_mode_combo = QComboBox()
        # Auto / Light / Dark
        self.display_mode_combo.addItem(Translations.tr("settings.display_mode.auto"), "auto")
        self.display_mode_combo.addItem(Translations.tr("settings.display_mode.light"), "light")
        self.display_mode_combo.addItem(Translations.tr("settings.display_mode.dark"), "dark")
        display_layout.addWidget(self.display_mode_combo)

        display_group.setLayout(display_layout)
        left_col.addWidget(display_group)

        # --- Layout Mode Group (classic / modern) ---
        layout_group = QGroupBox(Translations.tr("settings.group.layout"))
        layout_mode_layout = QVBoxLayout()

        self.layout_mode_combo = QComboBox()
        self.layout_mode_combo.addItem(Translations.tr("settings.layout.classic"), "classic")
        self.layout_mode_combo.addItem(Translations.tr("settings.layout.modern"), "modern")
        layout_mode_layout.addWidget(self.layout_mode_combo)

        layout_hint = QLabel(Translations.tr("settings.layout.restart_hint"))
        layout_hint.setWordWrap(True)
        layout_mode_layout.addWidget(layout_hint)

        layout_group.setLayout(layout_mode_layout)
        left_col.addWidget(layout_group)

        # ── Right column ─────────────────────────────────────────────────

        # --- Auto-Update Group ---
        update_group = QGroupBox(Translations.tr("settings.group.auto_update"))
        update_layout = QVBoxLayout()

        self.auto_update_checkbox = QCheckBox(Translations.tr("settings.check.auto_update"))
        update_layout.addWidget(self.auto_update_checkbox)

        grid = QGridLayout()
        grid.setColumnStretch(1, 1)
        interval_label = QLabel(Translations.tr("settings.label.interval"))
        grid.addWidget(interval_label, 0, 0)
        self.update_interval_combo = QComboBox()
        self.update_interval_combo.addItem(Translations.tr("settings.interval.daily"), 24)
        self.update_interval_combo.addItem(Translations.tr("settings.interval.weekly"), 168)
        self.update_interval_combo.addItem(Translations.tr("settings.interval.monthly"), 720)
        grid.addWidget(self.update_interval_combo, 0, 1)
        update_layout.addLayout(grid)

        update_group.setLayout(update_layout)
        right_col.addWidget(update_group)

        # --- Log Settings Group ---
        log_group = QGroupBox(Translations.tr("settings.group.logs"))
        log_layout = QFormLayout()

        self.max_logs_input = QSpinBox()
        self.max_logs_input.setRange(10, 10000)
        self.max_logs_input.setSingleStep(50)
        self.max_logs_input.setValue(100)
        log_layout.addRow(Translations.tr("settings.label.max_logs"), self.max_logs_input)

        log_group.setLayout(log_layout)
        right_col.addWidget(log_group)

        # --- Remote Desktop Group ---
        rdp_group = QGroupBox(Translations.tr("settings.group.remote_desktop"))
        rdp_layout = QFormLayout()

        self.remote_desktop_resolution_combo = QComboBox()
        # "Optimized 16:9" first (sentinel "auto"), then the fixed resolutions.
        self.remote_desktop_resolution_combo.addItem(
            Translations.tr("settings.label.remote_desktop_resolution_auto"),
            REMOTE_DESKTOP_RESOLUTION_AUTO,
        )
        for resolution in REMOTE_DESKTOP_RESOLUTIONS:
            w, h = resolution.split("x")
            self.remote_desktop_resolution_combo.addItem(f"{w} × {h}", resolution)
        rdp_layout.addRow(
            Translations.tr("settings.label.remote_desktop_resolution"),
            self.remote_desktop_resolution_combo,
        )

        rdp_group.setLayout(rdp_layout)
        right_col.addWidget(rdp_group)

        # --- Shutdown Group ---
        shutdown_group = QGroupBox(Translations.tr("settings.group.shutdown"))
        shutdown_layout = QFormLayout()

        self.default_method_combo = QComboBox()
        self.default_method_combo.addItem(
            Translations.tr("device_dialog.method.host_service"),
            "host_service",
        )
        self.default_method_combo.addItem(
            Translations.tr("device_dialog.method.smb"),
            "smb",
        )
        shutdown_layout.addRow(
            Translations.tr("settings.label.default_shutdown_method"),
            self.default_method_combo,
        )

        shutdown_group.setLayout(shutdown_layout)
        right_col.addWidget(shutdown_group)

        # Info label
        info_label = QLabel(
            Translations.tr("settings.info.text")
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # Buttons
        btn_layout = QHBoxLayout()
        self.save_btn = QPushButton(Translations.tr("dialog.button.save"))
        self.save_btn.clicked.connect(self._save)
        self.cancel_btn = QPushButton(Translations.tr("dialog.button.cancel"))
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.cancel_btn)

        layout.addStretch()
        layout.addLayout(btn_layout)

    def _load_settings(self) -> None:
        net = self.config.get_network_settings()
        self.broadcast_ip_input.setText(net.get("broadcast_ip", "255.255.255.255"))
        self.broadcast_port_input.setValue(net.get("broadcast_port", 9))

        # Load language setting
        current_lang = self.config.config.get("ui", {}).get("language", "en")
        for idx in range(self.language_combo.count()):
            if self.language_combo.itemData(idx) == current_lang:
                self.language_combo.setCurrentIndex(idx)
                break

        # Load display mode setting
        current_mode = self.config.config.get("ui", {}).get("display_mode", "auto")
        for idx in range(self.display_mode_combo.count()):
            if self.display_mode_combo.itemData(idx) == current_mode:
                self.display_mode_combo.setCurrentIndex(idx)
                break

        # Load layout mode setting (classic / modern)
        current_layout = self.config.get_layout_mode()
        for idx in range(self.layout_mode_combo.count()):
            if self.layout_mode_combo.itemData(idx) == current_layout:
                self.layout_mode_combo.setCurrentIndex(idx)
                break

        # Load update settings
        update_settings = self.config.get_update_settings()
        self.auto_update_checkbox.setChecked(update_settings.get("auto_check_enabled", True))
        interval_hours = update_settings.get("check_interval_hours", 24)
        for idx in range(self.update_interval_combo.count()):
            if self.update_interval_combo.itemData(idx) == interval_hours:
                self.update_interval_combo.setCurrentIndex(idx)
                break

        # Load log settings
        self.max_logs_input.setValue(self.config.get_max_logs())

        # Load default shutdown method
        current_method = self.config.get_default_shutdown_method()
        for idx in range(self.default_method_combo.count()):
            if self.default_method_combo.itemData(idx) == current_method:
                self.default_method_combo.setCurrentIndex(idx)
                break

        # Load remote desktop resolution
        current_resolution = self.config.get_remote_desktop_resolution()
        for idx in range(self.remote_desktop_resolution_combo.count()):
            if self.remote_desktop_resolution_combo.itemData(idx) == current_resolution:
                self.remote_desktop_resolution_combo.setCurrentIndex(idx)
                break

    def _save(self) -> None:
        ip: str = self.broadcast_ip_input.text().strip()
        port: int = self.broadcast_port_input.value()

        # Input-Validierung
        if not ip:
            QMessageBox.warning(self, Translations.tr("dialog.error.missing_ip"), Translations.tr("dialog.error.msg.missing_ip"))
            return

        if not _validate_broadcast_ip(ip):
            QMessageBox.warning(self, Translations.tr("dialog.error.invalid_ip"), Translations.tr("dialog.error.msg.invalid_ip"))
            return

        if not _validate_port(port):
            QMessageBox.warning(self, Translations.tr("dialog.error.invalid_port"), Translations.tr("dialog.error.msg.invalid_port"))
            return

        # Länge der Eingaben begrenzen
        if len(ip) > 15:  # IPv4 max length
            QMessageBox.warning(self, Translations.tr("dialog.error.invalid_input"), Translations.tr("dialog.error.msg.long_ip"))
            return

        self.config.update_network_settings(broadcast_ip=ip, broadcast_port=port)

        # Save language setting
        selected_lang = self.language_combo.currentData()
        if selected_lang:
            self.config.update_ui_settings(language=selected_lang)
            Translations.set_language(selected_lang)

        # Save display mode setting
        selected_mode = self.display_mode_combo.currentData()
        if selected_mode:
            self.config.update_ui_settings(display_mode=selected_mode)
            # Apply the theme immediately (no restart required)
            app = QApplication.instance()
            if app is not None:
                apply_display_mode(app, selected_mode)

        # Save layout mode setting (takes effect after an app restart)
        selected_layout = self.layout_mode_combo.currentData()
        if selected_layout and selected_layout != self.config.get_layout_mode():
            self.config.set_layout_mode(selected_layout)
            self.restart_required = True

        # Save update settings
        auto_check: bool = self.auto_update_checkbox.isChecked()
        interval_hours = self.update_interval_combo.currentData()
        self.config.update_update_settings(
            auto_check_enabled=auto_check,
            check_interval_hours=interval_hours,
        )

        # Save log settings
        self.config.set_max_logs(self.max_logs_input.value())

        # Save default shutdown method
        selected_method = self.default_method_combo.currentData()
        if selected_method:
            self.config.set_default_shutdown_method(selected_method)

        # Save remote desktop resolution
        selected_resolution = self.remote_desktop_resolution_combo.currentData()
        if selected_resolution:
            self.config.set_remote_desktop_resolution(selected_resolution)

        QMessageBox.information(self, Translations.tr("dialog.saved.title"), Translations.tr("dialog.saved.message"))
        self.accept()
