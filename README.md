# Wake-on-LAN Manager

**Version 1.3.0 - Security Enhanced Edition**

A modern Windows GUI application for sending Wake-on-LAN magic packets to devices on your local network.

🔒 **Security Note:** This version includes comprehensive security improvements. See [SECURITY.md](SECURITY.md) for details.

## Features

- **Device Management** — Add, edit, and remove devices with friendly names, MAC addresses, and optional IP addresses (no device limit)
- **Wake-on-LAN** — Send magic packets to individual devices or wake all at once
- **Status Monitoring** — Ping devices to check online/offline status (auto-refresh every 30 seconds)
- **Scheduling** — Schedule automatic wake-ups by time and day of week
- **Network Settings** — Configure broadcast IP and port
- **Activity Log** — Full history of all wake attempts with timestamps

## Requirements

- Windows 10/11 (64-Bit)
- Python 3.10+ (only for source installation)

## Installation

### Installer (recommended)

Download `Wake-on-LAN Manager Installer.exe` and double-click to run. The installer:

- Automatically requests administrator privileges via UAC
- Installs the application to `C:\Program Files\WakeOnLAN`
- Creates a **Start Menu** entry and a **Desktop shortcut**
- Registers the app in Windows **Add/Remove Programs**
- On reinstall, asks whether to **keep or remove** existing device entries and settings

### From Source

```bash
pip install -r requirements.txt
```

## Usage

### Installed Version

Launch via the Desktop shortcut or from the Start Menu → *Wake-on-LAN Manager*.

### From Source

```bash
python run.py
```

### Quick Start

1. **Add Devices**: File → Manage Devices → Add Device (enter name, MAC address, optional IP)
2. **Wake a Device**: Select from the table and click "Wake Selected", or click "Wake All Devices"
3. **Configure Network**: Tools → Network Settings (broadcast IP/port)
4. **Set Schedules**: File → Manage Schedules
5. **View Logs**: Tools → View Logs

## Uninstallation

- **Start Menu** → *Wake-on-LAN Manager → Uninstall Wake-on-LAN Manager*
- Or via Windows **Settings → Apps → Installed Apps**

> All device entries and settings are removed during uninstallation.

## Configuration

All data is stored in `%USERPROFILE%\.wol_app\`.

## Documentation

A detailed user manual is available in German:

- [Bedienungsanleitung.md](Bedienungsanleitung.md)
- [Bedienungsanleitung.pdf](Bedienungsanleitung.pdf)

### Security Documentation

- [SECURITY.md](SECURITY.md) - Comprehensive security measures and improvements

## 📝 Changelog

### Version 1.3.0 - Security Enhanced Edition (2026-07-14)

#### 🔒 Security Improvements
- **Command Injection Protection:** All subprocess calls use `shell=False` with input validation
- **Path Traversal Protection:** Secure path processing with permission controls
- **Password Security:** AES-256-GCM encryption with DPAPI, memory sanitization
- **DoS Protection:** Resource limits for network scans (16 threads, 2s timeout, 256 hosts)
- **Input Validation:** Comprehensive validation of all user inputs
- **Security Documentation:** Added SECURITY.md with detailed analysis

#### 🔧 Technical Changes
- `network_scanner.py`: Secure subprocess execution with resource limits
- `crypto.py`: Memory sanitization for passwords, input validation
- `config.py`: Path validation, secure file permissions, log sanitization
- `device_dialog.py`: Input validation for devices
- `settings_dialog.py`: Input validation for network settings
- `wol_engine.py`: Secure magic packet creation and status checks
- `installer.py`: Secure deletion of user data, version 1.3.0

#### ✅ Tests
- All security tests pass successfully
- Comprehensive input validation verified
- Encryption/decryption functionality confirmed

### Version 1.2.1
- Previous stable release
