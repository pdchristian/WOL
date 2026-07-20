"""Settings Dialog for Wake-on-LAN Application."""

import re
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QMessageBox, QSpinBox, QComboBox,
    QCheckBox, QGroupBox,
)
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

    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.config = config_manager
        self.setWindowTitle(Translations.tr("settings.title"))
        self.setMinimumWidth(400)
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Network settings form
        form = QFormLayout()

        self.broadcast_ip_input = QLineEdit()
        self.broadcast_ip_input.setPlaceholderText("255.255.255.255")
        form.addRow(Translations.tr("settings.label.broadcast_ip"), self.broadcast_ip_input)

        self.broadcast_port_input = QSpinBox()
        self.broadcast_port_input.setRange(1, 65535)
        self.broadcast_port_input.setValue(9)
        form.addRow(Translations.tr("settings.label.broadcast_port"), self.broadcast_port_input)

        layout.addLayout(form)

        # --- Language Group ---
        lang_group = QGroupBox(Translations.tr("settings.group.language"))
        lang_layout = QVBoxLayout()

        self.language_combo = QComboBox()
        available = Translations.available_languages()
        for code, name in available.items():
            self.language_combo.addItem(name, code)
        lang_layout.addWidget(self.language_combo)

        lang_group.setLayout(lang_layout)
        layout.addWidget(lang_group)

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
        layout.addWidget(update_group)

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

    def _load_settings(self):
        net = self.config.get_network_settings()
        self.broadcast_ip_input.setText(net.get("broadcast_ip", "255.255.255.255"))
        self.broadcast_port_input.setValue(net.get("broadcast_port", 9))

        # Load language setting
        current_lang = self.config.config.get("ui", {}).get("language", "en")
        for idx in range(self.language_combo.count()):
            if self.language_combo.itemData(idx) == current_lang:
                self.language_combo.setCurrentIndex(idx)
                break

        # Load update settings
        update_settings = self.config.get_update_settings()
        self.auto_update_checkbox.setChecked(update_settings.get("auto_check_enabled", True))
        interval_hours = update_settings.get("check_interval_hours", 24)
        for idx in range(self.update_interval_combo.count()):
            if self.update_interval_combo.itemData(idx) == interval_hours:
                self.update_interval_combo.setCurrentIndex(idx)
                break

    def _save(self):
        ip = self.broadcast_ip_input.text().strip()
        port = self.broadcast_port_input.value()

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

        # Save update settings
        auto_check = self.auto_update_checkbox.isChecked()
        interval_hours = self.update_interval_combo.currentData()
        self.config.update_update_settings(
            auto_check_enabled=auto_check,
            check_interval_hours=interval_hours,
        )

        QMessageBox.information(self, Translations.tr("dialog.saved.title"), Translations.tr("dialog.saved.message"))
        self.accept()
