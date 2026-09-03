# Wake-on-LAN Manager

**Version 2.0.0 - Modern UI Edition**

A modern Windows GUI application for sending Wake-on-LAN magic packets to devices on your local network.

> **New in 2.0.0:** a redesigned **Modern UI** ("Dark Control Center") with a sidebar and four native areas — *Geräte* (device status cards or device list), *Verwalten* (device management + network scan), *Zeitplan* (schedules) and *Protokolle* (activity log) — plus native *Einstellungen* and *Über* screens. It is feature-identical to the classic window and can be selected at install time or switched in **Settings → Design** at any time.

🔒 **Security Note:** Passwords are encrypted with AES-256-GCM (DPAPI-protected master key), legacy plaintext passwords are auto-re-encrypted on load, and all subprocess calls use `shell=False` with input validation. See [SECURITY.md](SECURITY.md) for details.

## Features

- **Modern UI (new in 2.0.0)** — A redesigned "Dark Control Center" layout with a sidebar and native *Geräte* / *Verwalten* / *Zeitplan* / *Protokolle* / *Einstellungen* / *Über* screens (dark or light display mode). The *Geräte* screen offers a **card view and a list view** (toggle icon) plus a **sort drop-down** (name / IP / MAC / status). Feature-identical to the classic window; choose it at install time or switch it in **Settings → Design**
- **Device Management** — Add, edit, and remove devices with friendly names, MAC addresses, and optional IP addresses (no device limit)
- **Wake-on-LAN** — Send magic packets to individual devices or wake all at once (parallel, up to 8 concurrent)
- **Status Monitoring** — Ping devices to check online/offline status (auto-refresh every 30 seconds, up to 16 concurrent)
- **Scheduling** — Schedule automatic wake-ups and remote shutdowns by time and day of week
- **Network Scanner** — Auto-discover devices across all local network interfaces with DNS name resolution
- **Remote Shutdown** — Two methods: SMB (Windows shared folder) and **Host Service** (a small Windows service on the target machine, JSON over TCP port 8765)
- **Host Service** — Optional Windows service (`WOL Host Service`) that accepts remote shutdown/reboot/status commands over TCP port 8765. With it, both **Windows** and **Android** clients can shut down this PC remotely (Android: [pdchristian/WOL-Android](https://github.com/pdchristian/WOL-Android)); installable via the installer
- **Network Settings** — Configure broadcast IP and port
- **Activity Log** — Full history of all wake attempts with timestamps and CSV export
- **Multi-Language** — English, German, French, and Spanish
- **Auto-Update** — Checks GitHub Releases for new versions on startup

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
- Asks whether to install the **WOL Host Service** (default: yes) — enables other Wake-on-LAN Manager instances (Windows/Android) to shut down this PC remotely
- The uninstaller asks whether to remove the host service (default: yes)

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

### Version 2.0.0 - Modern UI Edition (2026-09-01)

#### 🎨 Modern UI ("Dark Control Center")
- **New application design:** a sidebar-based control center with four native areas — *Geräte* (device status cards), *Verwalten* (device management + network scan), *Zeitplan* (schedules) and *Protokolle* (activity log) — plus native *Einstellungen* and *Über* screens
- **Device cards:** each device is shown as a card with a live status dot, IP/MAC, Remote-Desktop tiles (fullscreen/window) and a primary action button that switches between *Aufwecken* (wake, while offline) and *Herunterfahren* (shutdown, while online); auto-refresh every 30 s
- **Card / list dual view:** the *Geräte* screen toggles between the card grid and a **device list** (rows with status dot, name, IP · MAC and three action tiles: remote fullscreen / remote window / edit) via the icon in the top-left of the toolbar; the chosen view is persisted
- **Sort drop-down:** left of the search field — *Namen* (alphabetical), *IP-Adresse* (numeric), *MAC-Adresse* (ascending) or *Status* (online → offline → unknown); applies to both views and is persisted
- **Native settings & update screens:** *Einstellungen* (network, language, display mode, design, updates, log limit, shutdown method, RDP resolution) and *Über* (about + "Nach Updates suchen" / changelog) are full screens instead of dialogs
- **Design choice at install time:** the installer asks for **Modern app** or **Classic app** (recorded in the registry); the layout can be changed later in **Settings → Design** (requires an app restart)
- **Display mode:** dark / light / auto is respected by both layouts
- **Feature parity:** both layouts share the same engine, config, dialogs and workers — only the presentation differs

### Version 1.10.3 (2026-08-25)

#### 🖥️ Remote Desktop
- **Automatic RDP password fill-in:** Windows 10/11 `mstsc` ignores a password embedded in the `.rdp` file. The app now registers the device credentials with the **Windows Credential Manager** via `cmdkey` (`/generic:<host> /user:<user> /pass:<pass>`) before starting `mstsc`, so the password no longer has to be re-entered for each connection (falls back to the `mstsc` login prompt if registration fails)

### Version 1.10.0 - Search & Remote Desktop Edition (2026-08-22)

#### 🖥️ Remote Desktop
- **Remote Desktop sessions** from the device table context menu: right-click a device → **Remote Fullscreen** or **Remote Window**
- Uses the device's IP, username and password (credentials embedded in a temporary `.rdp` file, auto-deleted after a few seconds)
- Because Windows 10/11 `mstsc` ignores an embedded password, the app also registers the credentials with the **Windows Credential Manager** via `cmdkey` before connecting — so the password is filled in automatically (falls back to the mstsc prompt if registration fails)
- **Windowed mode** uses the resolution configured in **Settings → Remote Desktop** (`1920x1080` default, 6 presets)
- Session geometry is forced via `mstsc` command-line arguments (`/f`, `/w:`, `/h:`) for reliable full-screen/window behavior

#### 🔍 Device Search
- **Search field** above the device table in the main window and the device manager — live-filters by name, MAC, IP or user
- **Search field** in the network scanner (filters by hostname/IPv4/IPv6/MAC)
- **Search field** in the schedule manager (filters by device, time, action, days and enabled state)

### Version 1.6.0 - Improvement Edition (2026-08-05)

#### 🔒 Security & Startup
- **Lazy permissions fix:** `_fix_directory_permissions()` uses a `permissions_fixed.marker` file in `~/.wol_app/` — the `takeown`/`icacls` subprocess calls only run once per user profile (no more slow startup)
- **Logging via `logging` module** to `~/.wol_app/app.log` — security-relevant failures are never silently swallowed (`except: pass` removed)
- **Legacy plaintext passwords** are auto-re-encrypted on load (`_reencrypt_plaintext_passwords`)

#### 🛠️ Reliability
- **Thread tracking:** `_track_thread()` in `main_window.py` auto-removes QThread references on finish — no memory leak
- **Version parsing:** `_parse_version()` in `updater.py` normalizes to 3 segments and rejects invalid versions

#### ⚡ Performance
- **`wake_all()`** uses a `ThreadPoolExecutor` (max 8 concurrent)
- **Status checks** run parallel pings (max 16 concurrent)

#### 🧪 Tests & Maintenance
- **pytest suite** in `tests/` (37 tests)
- **`get_local_interfaces()`** prefers psutil, falls back to locale-aware `ipconfig` parsing
- **ruff config** in `pyproject.toml` (runs clean)

### Version 1.5.x - Scheduler/Installer Fix Editions (2026-07-19/21)

- **1.5.1 (2026-07-21) — Scheduler Fix Edition:** Scheduler reliability improvements
- **1.5.0 (2026-07-19) — Installer Pro Edition:** Professional installer with Windows registry (Add/Remove Programs) integration

### Version 1.4.x - Feature Editions

- Multi-language support (English, German, French, Spanish)
- Network scanner with DNS name resolution
- Remote shutdown via TCP shutdown client
- Auto-update checking from GitHub Releases

### Version 1.3.3 - Console Flash Fix Edition (2026-07-18)

#### 🐛 Bug Fixes
- **Eliminated console flash on startup:** Added `creationflags=subprocess.CREATE_NO_WINDOW` to all permission-related subprocess calls (`takeown`/`icacls`) in `_fix_directory_permissions()` — no more flickering terminal windows at app launch

### Version 1.3.2 - Installer Permissions Fix Edition (2026-07-15)

#### 🔧 Installer Improvements
- **Permissions Fast-Path:** Added pre-check to skip permission fixes when user already has full control (~1 sec vs ~30+ sec on data migration)
- **Fixed icacls syntax:** Corrected `/grant:f` (invalid) to `/grant` with `(CI)(OI)F` flag
- **Removed parent directory fix:** Eliminated unnecessary `icacls` on entire user home directory (`C:\Users\cp`) that caused 30-second timeouts
- **Reduced timeouts:** All permission commands reduced from 30s to 15s per step

### Version 1.3.1 - Security Enhanced Edition (2026-07-14)

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
- `installer.py`: Secure deletion of user data, version 1.3.1

#### ✅ Tests
- All security tests pass successfully
- Comprehensive input validation verified
- Encryption/decryption functionality confirmed

### Version 1.2.1
- Previous stable release
