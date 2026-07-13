"""Settings Dialog for Wake-on-LAN Application."""

import re
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QMessageBox, QSpinBox,
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
        QMessageBox.information(self, "Saved", "Network settings saved successfully.")
        self.accept()
