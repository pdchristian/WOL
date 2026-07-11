# Wake-on-LAN Manager

A modern Windows GUI application for sending Wake-on-LAN magic packets to devices on your local network.

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
