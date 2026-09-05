# Wake-on-LAN Manager

**Version 2.2.1 - Service Watch Edition**

A modern Windows GUI application for sending Wake-on-LAN magic packets to devices on your local network.

> **New in 2.2.1:** **Remote Desktop auto-retry for xrdp/Ubuntu hosts** — if a session with a stored password closes within 10 seconds (black screen, window vanishes), the app offers to reconnect **without the stored password** so it can be typed directly into the Remote Desktop prompt.
> **New in 2.2.0:** **Watched processes / service status** on the dashboard — watch named processes (e.g. `llama-server.exe`) on the target and see live status chips, PID, uptime, RAM/CPU, API-port reachability and the loaded llama.cpp model. Configured per device directly in the device dialog. Requires **WOL Host Service protocol v3** (older hosts simply hide the panel).
> **New in 2.1.0:** a per-device **Dashboard** — live **CPU / RAM / GPU / VRAM** gauges with rolling sparklines plus **remote batch execution** (per-device script library, console output, exit code & duration). Opened via the 📊 tile on each device (no sidebar entry). Requires the updated **WOL Host Service** (protocol v2); batch runs need a double opt-in (per-device checkbox + `--enable-batch` on the target).
> **New in 2.0.0:** a redesigned **Modern UI** ("Dark Control Center") with a sidebar and four native areas — *Geräte* (device status cards or device list), *Verwalten* (device management + network scan), *Zeitplan* (schedules) and *Protokolle* (activity log) — plus native *Einstellungen* and *Über* screens. It is feature-identical to the classic window and can be selected at install time or switched in **Settings → Design** at any time.

🔒 **Security Note:** Passwords are encrypted with AES-256-GCM (DPAPI-protected master key), legacy plaintext passwords are auto-re-encrypted on load, and all subprocess calls use `shell=False` with input validation. See [SECURITY.md](SECURITY.md) for details.

## Features

- **Modern UI (new in 2.0.0)** — A redesigned "Dark Control Center" layout with a sidebar and native *Geräte* / *Verwalten* / *Zeitplan* / *Protokolle* / *Einstellungen* / *Über* screens (dark or light display mode). The *Geräte* screen offers a **card view and a list view** (toggle icon) plus a **sort drop-down** (name / IP / MAC / status). Feature-identical to the classic window; choose it at install time or switch it in **Settings → Design**
- **Device Dashboard (new in 2.1.0)** — Per-device live metrics (CPU / RAM / GPU / VRAM ring gauges + rolling sparklines, hostname & uptime, configurable 2–10 s polling) and **remote batch execution** with a per-device script library, console output (stdout/stderr, exit code, duration) and cancellation. GPU/VRAM via `nvidia-smi` (NVIDIA only, "n/a" otherwise). Opened via the 📊 tile on each device — no sidebar entry. Batch runs are double-gated: a per-device checkbox plus `--enable-batch` on the target host (SYSTEM privileges!)
- **Watched processes / service status (new in 2.2.0)** — The dashboard can watch named processes on the target (e.g. `llama-server.exe`) and shows a live **status chip** in the header plus a **Services panel** (PID, uptime, process RAM/CPU, API-port reachability and the loaded llama.cpp model). Configure per device via `config.json` → `"watch_processes": ["llama-server.exe:8080"]` (the `:port` turns the chip green only once the API also answers; without it, "running" is enough). Requires Host Service **protocol v3** — older hosts simply omit it (chip hidden, no error). A heuristic "⚡ Inference active" badge lights up while a ready service coincides with high GPU load.
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

### Unreleased

#### 🔄 Remote Desktop: automatic second attempt without password
- **Fast-exit detection for xrdp/Ubuntu hosts:** when a stored password is used and `mstsc` closes again within 10 seconds (black screen, window vanishes — the typical response of an xrdp host to a wrong password), the app now asks whether to reconnect **without the stored password**. Confirming deletes the `TERMSRV/<host>` entry from the Windows Credential Manager and reopens `mstsc` with the username pre-filled, so the password can be typed directly into the Remote Desktop prompt. The password stored in the device record stays untouched, and a `RDP/WARNING` entry is written to the log
- **No false alarms:** sessions that survive the 10-second window, connections without a stored password (mstsc prompts anyway) and the retry attempt itself are never watched or re-prompted
- **`use redirection server name:i:1`:** every generated `.rdp` file now carries this option, which xrdp (Ubuntu) hosts require so the client keeps the address it connected to as the server identity after the RDP redirection hop

#### 🌐 Host names as device addresses
- **The device address field accepts host names:** besides IPv4 addresses, entries like `ubuntu-mercury` or `nas01.lan` are now valid (RFC 1123). Ping status checks, SMB shutdown and Remote Desktop all resolve names natively — useful for devices with changing DHCP addresses and for xrdp/Linux hosts that must be reached by name
- **Fixed:** `update_device()` truncated the IP field to 15 characters (IPv4 limit), silently cutting host names short; the limit is now 253 (max DNS name length)
- **Fixed (RDP to xrdp):** credentials are registered with the Credential Manager under the `TERMSRV/<host>` target that `mstsc` actually reads (previously a prefix-less generic entry that mstsc never picked up — xrdp hosts dropped the session immediately); generated `.rdp` files set `authentication level:i:0` so self-signed server certificates no longer trigger the per-connect security warning

### Version 2.2.0 - Service Watch Edition (2026-09-04)

#### 👁 Watched processes / service status
- **Process watching on the dashboard:** each device can watch up to 8 named processes on the target (e.g. `llama-server.exe`). The dashboard header shows a live **status chip** per watched process — green (running, API port answers), amber (*starting…*, process runs but the port is closed) or grey (not running); chips are hidden while the device is offline or the host service is too old
- **Services panel with details:** per watched process the dashboard shows PID, uptime, process RAM and CPU, plus the **loaded llama.cpp model** (parsed from the command line, `-m` / `--model`) when detected; llama.cpp processes get a 🦙 icon
- **API-port probing:** an entry may carry a port suffix (`llama-server.exe:8080`); the host service checks loopback reachability (250 ms, parallel) and the chip only turns green once the API also answers
- **"⚡ Inference active" badge:** heuristic indicator that lights up on the dashboard while a watched service is ready and GPU load stays high (≥ 60 % over consecutive polls)
- **Device dialog field:** watched processes are configured directly in the device dialog (*Beobachtete Prozesse*, comma-separated) — no manual `config.json` editing needed; stored per device as `"watch_processes"`
- **Host service protocol v3:** the `metrics` request accepts an optional `"watch"` list (max 8 entries); the response gains a `"processes"` map keyed by the original entry. Fully back-compatible — v2 clients and v3 clients behave correctly in both directions; older hosts simply omit the field

### Version 2.1.0 - Dashboard Edition (2026-09-03)

#### 📊 Device Dashboard (per device)
- **Live performance metrics:** a new dashboard screen shows **CPU load, RAM usage, GPU load and VRAM usage** as ring gauges with rolling sparklines (last 60 samples), plus hostname, IP · MAC, online badge and uptime. Polling interval selectable (2 / 3 / 5 / 10 s, default 3 s), auto-pauses when hidden, single-flight requests
- **Opened via the 📊 tile** on each device card/row (between the remote-desktop tiles and edit) and the context menu — deliberately **no sidebar entry**
- **GPU/VRAM via `nvidia-smi`** (utilisation + memory, multi-GPU aggregated, cached 1.5 s); machines without an NVIDIA GPU show "k/A"
- **Remote batch execution:** per-device script library (new/duplicate/delete, persisted in `config.json`), script editor with per-batch timeout (5–3600 s) and a console showing stdout/stderr, exit code and duration; running batches can be stopped
- **Double opt-in for batches (security):** a per-device "allow batch execution" checkbox in the dashboard **and** an admin-side `--enable-batch` switch on the WOL Host Service (persisted in `%ProgramData%\...\service.json`, re-read per request). Scripts run with SYSTEM privileges — disabled by default on both sides
- **Host service protocol v2:** new authenticated `metrics` and `run_batch` commands (psutil-based CPU/RAM/uptime; output size caps, UTF-8/cp850 decoding); older services are detected and reported ("Host service too old for the dashboard")
- **Cancellable workers:** dashboard metric/batch threads close their in-flight socket on cancel/back-navigation, so switching devices or closing the window never blocks

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
