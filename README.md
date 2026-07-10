# Wake-on-LAN Manager

A modern Windows GUI application for sending Wake-on-LAN magic packets to up to 8 PCs.

## Features

- **Device Management** — Add, edit, and remove devices with friendly names, MAC addresses, and optional IP addresses
- **Wake-on-LAN** — Send magic packets to individual devices or wake all at once
- **Status Monitoring** — Ping devices to check online/offline status (requires IP configured)
- **Scheduling** — Schedule automatic wake-ups by time and day of week
- **Network Settings** — Configure broadcast IP and port
- **Activity Log** — Full history of all wake attempts with timestamps

## Requirements

- Python 3.10+
- PyQt6

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
python run.py
```

### Quick Start

1. **Add Devices**: File → Manage Devices → Add Device (enter name, MAC address, optional IP)
2. **Wake a Device**: Select from the table and click "Wake Selected", or click "Wake All Devices"
3. **Configure Network**: Tools → Network Settings (broadcast IP/port)
4. **Set Schedules**: File → Manage Schedules
5. **View Logs**: Tools → View Logs

## Configuration

Settings are stored in `~/.wol_app/config.json`.
