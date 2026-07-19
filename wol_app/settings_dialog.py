"""Settings Dialog for Wake-on-LAN Application."""

import re
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QMessageBox, QSpinBox, QComboBox,
    QCheckBox, QGroupBox,
)


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
        self.setWindowTitle("Network Settings")
        self.setMinimumWidth(400)
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Network settings form
        form = QFormLayout()

        self.broadcast_ip_input = QLineEdit()
        self.broadcast_ip_input.setPlaceholderText("255.255.255.255")
        form.addRow("Broadcast IP:", self.broadcast_ip_input)

        self.broadcast_port_input = QSpinBox()
        self.broadcast_port_input.setRange(1, 65535)
        self.broadcast_port_input.setValue(9)
        form.addRow("Broadcast Port:", self.broadcast_port_input)

        layout.addLayout(form)

        # --- Auto-Update Group ---
        update_group = QGroupBox("Auto-Update")
        update_layout = QVBoxLayout()

        self.auto_update_checkbox = QCheckBox("Automatisch nach Updates suchen")
        update_layout.addWidget(self.auto_update_checkbox)

        grid = QGridLayout()
        grid.setColumnStretch(1, 1)
        interval_label = QLabel("Prüfintervall:")
        grid.addWidget(interval_label, 0, 0)
        self.update_interval_combo = QComboBox()
        self.update_interval_combo.addItem("Jeden Tag", 24)
        self.update_interval_combo.addItem("Alle 12 Stunden", 12)
        self.update_interval_combo.addItem("Alle 6 Stunden", 6)
        grid.addWidget(self.update_interval_combo, 0, 1)
        update_layout.addLayout(grid)

        update_group.setLayout(update_layout)
        layout.addWidget(update_group)

        # Info label
        info_label = QLabel(
            "Wake-on-LAN uses UDP broadcast packets.\n"
            "Default broadcast address is 255.255.255.255 on port 9.\n"
            "Some networks may require a directed broadcast address."
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # Buttons
        btn_layout = QHBoxLayout()
        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self._save)
        self.cancel_btn = QPushButton("Cancel")
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
            QMessageBox.warning(self, "Missing IP", "Please enter a broadcast IP address.")
            return

        if not _validate_broadcast_ip(ip):
            QMessageBox.warning(self, "Invalid IP", "Invalid broadcast IP address format. Use IPv4 or 255.255.255.255")
            return

        if not _validate_port(port):
            QMessageBox.warning(self, "Invalid Port", "Port must be between 1 and 65535.")
            return

        # Länge der Eingaben begrenzen
        if len(ip) > 15:  # IPv4 max length
            QMessageBox.warning(self, "Invalid Input", "IP address too long.")
            return

        self.config.update_network_settings(broadcast_ip=ip, broadcast_port=port)

        # Save update settings
        auto_check = self.auto_update_checkbox.isChecked()
        interval_hours = self.update_interval_combo.currentData()
        self.config.update_update_settings(
            auto_check_enabled=auto_check,
            check_interval_hours=interval_hours,
        )

        QMessageBox.information(self, "Saved", "Settings saved successfully.")
        self.accept()
