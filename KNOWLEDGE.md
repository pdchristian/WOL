# Wake-on-LAN Manager — Open Knowledge Format (OKF)

| Field               | Value                                                                  |
|---------------------|------------------------------------------------------------------------|
| **title**           | Wake-on-LAN Manager                                                    |
| **version**         | 2.1.0                                                                 |
| **okf_version**     | 1.0                                                                   |
| **created**         | 2026-07-21                                                            |
| **language**        | en                                                                    |
| **license**         | Proprietary                                                           |
| **platform**        | Windows 10/11                                                         |
| **runtime**         | Python 3.10+                                                          |
| **author**          | pdchristian                                                           |
| **repository**      | https://github.com/pdchristian/WOL                                     |
| **description**     | A powerful desktop application for managing network devices via Wake-on-LAN magic packets, ICMP ping status monitoring, remote shutdown (SMB and Host Service), and automated scheduling. Ships two interchangeable UIs — a classic window and a modern "Dark Control Center" sidebar layout (new in 2.0.0) — built with PyQt6 and hardened against CWE-2025 top security risks. |

---

## 1. Project Overview

Wake-on-LAN Manager is a Windows desktop GUI application that enables users to discover, manage, and remotely wake network devices using Wake-on-LAN (WoL) magic packets. The application provides device management with encrypted credential storage, automatic status monitoring via ICMP ping, configurable scheduling for automated wake/shutdown operations, network scanning for device discovery, and an auto-update system integrated with GitHub Releases.

### Key Capabilities
- Send WoL magic packets to individual devices or all enabled devices simultaneously
- Real-time device status monitoring (online/offline/unknown) via ICMP ping
- Remote shutdown of devices via Windows SMB net use / shutdown.exe
- Remote shutdown via the optional **WOL Host Service** (Windows service, JSON over TCP port 8765, Windows credential authentication)
- Automated scheduling (cron-like, per-device with day-of-week selection)
- Network discovery scanning across all local interfaces
- Multi-language support (English, German, French, Spanish)
- Auto-update checking and downloading from GitHub Releases
- Professional installer/uninstaller with Windows registry integration
- **Two interchangeable UIs (new in 2.0.0):** a classic window (`MainWindow`) and a modern **"Dark Control Center"** sidebar layout (`ModernMainWindow`) with native *Devices / Manage / Schedule / Logs / Settings / About* screens — feature-identical, selectable at install time or in Settings

### Default Configuration Path
```
%USERPROFILE%\.wol_app\config.json     — main configuration file
%USERPROFILE%\.wol_app\master_key.dat  — DPAPI-protected master encryption key
```

---

## 2. Technical Architecture

### 2.1 Runtime & Framework

| Layer            | Technology                                  |
|------------------|---------------------------------------------|
| Language         | Python 3.10+                                |
| GUI Framework    | PyQt6 >= 6.6.0                              |
| Encryption       | cryptography >= 41.0.0 (AES-256-GCM)        |
| Packaging        | PyInstaller                                 |
| OS               | Windows 10 / 11                             |
| Key Protection   | Windows DPAPI (CryptProtectData/UnprotectData via ctypes) |

### 2.2 Module Dependency Graph

```
run.py
 └── wol_app/main_window.py        (MainWindow, StatusWorker, entry point main())
      ├── wol_app/config.py        (ConfigManager singleton, input validation)
      ├── wol_app/crypto.py        (AES-256-GCM encrypt/decrypt, DPAPI key)
      ├── wol_app/wol_engine.py    (WOLEngine: WoL packets, ping, shutdown, scheduler)
      ├── wol_app/network_scanner.py  (interface detection, subnet scanning)
      ├── wol_app/translations.py  (Translations singleton, i18n)
      ├── wol_app/device_dialog.py   (add/edit device UI)
      ├── wol_app/schedule_dialog.py (schedule management UI)
      ├── wol_app/settings_dialog.py (network/language/update settings UI)
      ├── wol_app/log_dialog.py    (activity log viewer)
      ├── wol_app/network_scan_dialog.py (ScanWorker, NetworkScanDialog)
      ├── wol_app/updater.py       (UpdateChecker, DownloadWorker)
      ├── wol_app/update_dialog.py (UpdateAvailableDialog, _launch_installer_safe)
      │
      │  Modern UI (new in 2.0.0) — selected when ui.layout_mode == "modern"
      ├── wol_app/modern_main_window.py  (ModernMainWindow, run_modern_window)
      │    ├── wol_app/modern_theme.py    (DARK/LIGHT tokens, apply_modern_theme)
      │    ├── wol_app/views/devices_view.py   (DevicesView — status cards + device list)
      │    ├── wol_app/views/manage_view.py    (ManageView — devices + network scan)
      │    ├── wol_app/views/schedule_view.py  (ScheduleView — schedule rows)
      │    ├── wol_app/views/logs_view.py      (LogsView — event log)
      │    ├── wol_app/views/settings_view.py  (SettingsView — native settings screen)
      │    ├── wol_app/views/update_view.py    (UpdateView — about + update check)
      │    └── wol_app/views/dashboard_view.py (DeviceDashboardView — live metrics + batches)
      │
      │  Shared modern dialogs/widgets
      ├── wol_app/views/device_edit_dialog.py  (ModernDeviceDialog)
      ├── wol_app/views/schedule_edit_dialog.py (ModernScheduleEditDialog)
      ├── wol_app/widgets/toggle_switch.py     (ToggleSwitch / ToggleWithLabel)
      │
      │  Host-service integration
      ├── wol_app/host_service_client.py  (send_host_command, get_metrics, run_batch — TCP 8765)
      └── wol_app/metrics_worker.py       (MetricsWorker / BatchWorker — cancellable QThread workers)

installer.py                    (standalone installer, registry integration, UI-mode choice)
uninstaller.py                  (standalone uninstaller, data wiping)
build.ps1                       (PowerShell build orchestration script)
```

### 2.3 Application Entry Points

| Entry Point         | Purpose                                          |
|---------------------|--------------------------------------------------|
| `run.py`            | Source development entry point                    |
| `dist/Wake-on-LAN Manager.exe` | Production packaged executable (PyInstaller)   |
| `dist/Wake-on-LAN Manager Installer.exe` | Self-contained Windows installer           |
| `dist/uninstall.exe`  | Clean removal with data wiping                   |

### 2.4 Threading Model

The application uses a QThread-based worker pattern for all background operations:

```
MainWindow (QApplication main thread)
 ├── StatusWorker       → QThread for periodic status refresh (30s interval)
 ├── UpdateChecker      → QThread for GitHub release checking
 ├── DownloadWorker     → QThread for update downloads
 └── ScanWorker         → QThread (in network_scan_dialog) for subnet scanning

DeviceDashboardView (modern UI, stack index 6)
 ├── MetricsWorker      → QThread per poll tick (get_metrics, 5 s socket timeout)
 └── BatchWorker        → QThread per batch run (run_batch, timeout + 5 s)
     Both subclass _CancellableWorker: cancel() closes the in-flight socket
     (sock_sink pattern in host_service_client._request) so the thread exits
     immediately — required to avoid "QThread: Destroyed while thread is
     still running" at window teardown. run() returns silently when cancelled.

Scheduler              → threading.Timer (60s recurrence, re-arms on each check)
```

**Module-level thread registry** (`_active_threads` in `main_window.py`):
All created QThread instances are appended to a module-level list `_active_threads` to prevent premature garbage collection during C-level I/O operations. Threads are removed from the registry on the `finished` signal via a connected callback.

**HEADLESS_MODE** environment variable:
When set, disables all background threads (status worker, update checker, scheduler) for test/CI environments.

---

## 3. Security Model

### 3.1 Command Injection Protection (CWE-78)

All subprocess calls throughout the codebase enforce `shell=False`. A unified safe wrapper `_run_subprocess_safe()` is used in `wol_engine.py` and `network_scanner.py`:

```python
def _run_subprocess_safe(cmd, timeout=10, **kwargs):
    """Run subprocess with shell=False enforcement and timeout."""
    result = subprocess.run(
        cmd,
        capture_output=True,
        timeout=timeout,
        check=False,
        encoding="utf-8",
        errors="replace",
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        **kwargs,
    )
    return result
```

Key enforcement points:
- All `subprocess.run()` calls use `shell=False` (default when passing a list)
- Fixed command lists are constructed with validated inputs
- Timeouts range from 1s (ping) to 15s (permission fixes)
- `CREATE_NO_WINDOW` flag suppresses console flash on Windows

### 3.2 Path Traversal Protection (CWE-73, CWE-22)

Path sanitization is enforced in `config.py`:

```python
def _sanitize_path(path_str: str) -> Path:
    """Normalize and validate a file path."""
    path = Path(path_str).resolve()
    home = Path.home().resolve()
    if not str(path).startswith(str(home)):
        raise ValueError(f"Path outside user home directory: {path}")
    return path
```

Configuration directory creation uses restrictive permissions (`0o700` for directories, `0o600` for files). Custom config paths are validated to remain within the user's home directory.

### 3.3 Password Encryption (CWE-256, CWE-522)

Password storage pipeline:
1. **Input validation**: max 128 chars, no control characters (ord < 32 or > 126)
2. **Encryption**: AES-256-GCM with 12-byte random nonce per encryption
3. **Key protection**: Master key cached at module level, persisted via Windows DPAPI in `~/.wol_app/master_key.dat`
4. **Memory clearing**: `_secure_clear_memory()` zeroes sensitive strings after use
5. **Storage format**: `base64(nonce || tag || ciphertext)`

```
┌──────────────┐     ┌───────────────┐     ┌──────────────┐
│ Plaintext    │ ──► │ AES-256-GCM   │ ──► │ base64 blob  │
│ Password     │     │ (nonce + key) │     │ (stored)     │
└──────────────┘     └───────────────┘     └──────────────┘
                                ▲
                                │ loaded from
                        ┌───────────────┐
                        │ DPAPI blob    │
                        │ (master_key.  │
                        │  dat)         │
                        └───────────────┘
```

### 3.4 Denial of Service Protection (CWE-250, CWE-200)

Defined safety constants in `network_scanner.py`:

| Constant              | Value | Purpose                          |
|-----------------------|-------|----------------------------------|
| MAX_CONCURRENT_THREADS| 16    | Max parallel ping threads        |
| MAX_SCAN_TIMEOUT      | 2s    | Per-host ping timeout            |
| MAX_SUBNET_SIZE       | 256   | Max hosts scanned per subnet     |

Additional protections:
- Log entries capped at 100 by default (`max_logs` config)
- All subprocess calls have timeouts (1s–15s range)
- Network scan progress callbacks are bounded

### 3.5 Input Validation Functions

| Function                | Location      | Constraints                                    |
|-------------------------|---------------|-------------------------------------------------|
| `_validate_ip(ip)`      | wol_engine    | IPv4 regex `^\d{1,3}(\.\d{1,3}){3}$`            |
| `_validate_mac(mac)`    | wol_engine    | Format `XX:XX:XX:XX:XX:XX` or `XX-XX-XX-XX-XX-XX` |
| `_validate_device_name(name)` | config   | Max 64 chars, no control chars, no forbidden chars (/, \, :, *, ?, ", <, >, \|) |
| `_validate_username(u)` | config       | Max 64 chars, no control chars                   |
| `_validate_password(p)` | config       | Max 128 chars, no control chars (ord 32–126)     |
| `_validate_broadcast_ip(ip)` | settings | IPv4 pattern allowing `255` suffix for broadcast |

### 3.6 Secure Information Logging

- Log entries sanitized to remove control characters
- Max 256 characters per log field
- Sensitive data (MAC addresses, full passwords) excluded from log messages
- Log length enforced by `max_logs` configuration (default: 100 entries)

---

## 4. Configuration System

### 4.1 ConfigManager (`config.py`)

Thread-safe singleton-style configuration manager with JSON persistence. Key methods:

| Method                          | Return Type       | Description                                  |
|---------------------------------|-------------------|----------------------------------------------|
| `get_devices()`                 | `list[dict]`      | Returns all configured devices               |
| `get_device_by_id(device_id)`   | `Optional[dict]`  | Lookup device by UUID                        |
| `add_device(name, mac)`         | `Optional[dict]`  | Create device (validates inputs)             |
| `remove_device(device_id)`      | `bool`            | Delete device by ID                          |
| `update_device(device_id, **kw)`| `bool`            | Update device fields with validation         |
| `get_schedules()`               | `list[dict]`      | Returns all configured schedules             |
| `add_schedule(...)`             | `Optional[dict]`  | Create schedule entry                        |
| `remove_schedule(schedule_id)`  | `bool`            | Delete schedule by ID                        |
| `update_schedule(schedule_id, **kw)` | `bool`       | Update schedule fields                       |
| `get_logs()`                    | `list[dict]`      | Returns activity log entries                 |
| `add_log(device, action, status, message)` | `None`  | Append log entry with sanitization           |
| `clear_logs()`                  | `None`            | Clear all log entries                        |
| `save()`                        | `None`            | Encrypt passwords and persist to JSON        |
| `should_check_for_updates()`    | `bool`            | Check interval-based update eligibility      |

### 4.2 Default Configuration Schema

```json
{
  "devices": [],
  "network": {
    "broadcast_ip": "255.255.255.255",
    "broadcast_port": 9
  },
  "schedules": [],
  "logs": [],
  "max_logs": 100,
  "ui": {
    "device_sort_column": 0,
    "device_sort_order": "ascending",
    "language": "en",
    "remote_desktop_resolution": "1920x1080",
    "layout_mode": "classic",
    "layout_mode_user_set": false,
    "display_mode": "auto",
    "devices_view_mode": "grid",
    "devices_sort_key": "name",
    "dashboard_interval_ms": 3000
  },
  "updates": {
    "auto_check_enabled": true,
    "check_interval_hours": 24,
    "last_check_timestamp": null
  }
}
```

> **UI layout & display mode (new in 2.0.0):**
> - `ui.layout_mode` — `"classic"` (single-view `MainWindow`) or `"modern"` (sidebar `ModernMainWindow`). On first start the installer-written registry value `HKLM\SOFTWARE\Wake-on-LAN Manager\UiMode` wins (see `ConfigManager._apply_installer_ui_mode`); `layout_mode_user_set` is set to `true` once the user picks a layout in Settings, after which the registry hint is ignored.
> - `ui.display_mode` — `"auto"` / `"light"` / `"dark"`; respected by both layouts (defaults to `"auto"` when absent).
> - `ui.devices_view_mode` — `"grid"` (Kachelansicht) or `"list"` (Geräteliste) on the modern Devices screen; toggled via the toolbar icon, persisted by `ConfigManager.set_devices_view_mode()`.
> - `ui.devices_sort_key` — `"name"` / `"ip"` / `"mac"` / `"status"` sort order of the modern Devices screen (status ranks Online → Offline → Unknown); persisted by `ConfigManager.set_devices_sort_key()`.
> - `ui.dashboard_interval_ms` — polling interval of the per-device dashboard (ms, clamped to 2000–60000, default 3000); `ConfigManager.get/set_dashboard_interval_ms()`.

### 4.3 Device Schema

```json
{
  "id": "uuid4-string",
  "name": "string (max 64 chars)",
  "mac": "XX:XX:XX:XX:XX:XX",
  "ip": "IPv4 string (optional, max 15 chars)",
  "username": "string (optional, for remote shutdown)",
  "password": "string (optional, AES-256-GCM encrypted at rest)",
  "enabled": true,
  "allow_batch": false,
  "batches": [
    { "id": "uuid4-string", "name": "string", "script": "cmd/batch text",
      "timeout": 120 }
  ]
}
```

> **Dashboard fields (protocol v2):** `allow_batch` is the per-device client-side
> opt-in for remote batch execution (the host service has its own independent
> opt-in). `batches` is the per-device batch library (max 50 entries, script
> max 32 000 chars, timeout 5–3600 s, default 120 s) shown in the dashboard
> editor; managed via `ConfigManager.set_device_batches()` /
> `set_device_allow_batch()`. Malformed entries are skipped on read.

### 4.4 Schedule Schema

```json
{
  "id": "uuid4-string",
  "device_id": "references device.id",
  "hour": 0,
  "minute": 0,
  "days": ["Mon", "Tue", ...],
  "action": "wake|shutdown",
  "enabled": true
}
```

---

## 5. Core Components

### 5.1 WOLEngine (`wol_engine.py`)

Primary engine for WoL operations, status checking, and scheduling.

**Magic Packet Construction:**
```python
def _create_magic_packet(mac: str) -> bytes:
    """Create a standard WoL magic packet."""
    addr = mac.replace(":", "").replace("-", "")
    byte_addr = bytes.fromhex(addr)
    return b"\xff" * 6 + byte_addr * 16  # 6×FF + 16×MAC = 102 bytes
```

**Key Methods:**

| Method                            | Description                                    |
|-----------------------------------|-------------------------------------------------|
| `send_wake_packet(device_id)`     | Send WoL magic packet with interface detection  |
| `wake_all()`                      | Wake all enabled devices sequentially           |
| `check_device_status(device_id)`  | Ping device, return (status, message) tuple     |
| `check_all_statuses()`            | Check status of all enabled devices             |
| `get_device_status(device_id)`    | Get cached status string                        |
| `remote_shutdown(device_id)`      | Remote shutdown via SMB net use + shutdown.exe  |
| `start_scheduler()`               | Start 60s recurrence scheduler                  |
| `stop_scheduler()`                | Cancel active scheduler timer                   |

**Interface Detection (`find_interface_for_device`):**
Scans all local interfaces via `get_local_interfaces()` and selects the interface whose subnet matches the target device's IP address. Falls back to interface-agnostic broadcast if no match is found.

**Scheduler Signals:**
The engine emits a `schedule_fired(device_id, action)` PyQt signal when a scheduled event triggers. The MainWindow connects this signal to `_on_schedule_fired()` which dispatches the appropriate WoL or shutdown action.

### 5.2 Network Scanner (`network_scanner.py`)

Network discovery module for finding active devices on the local network.

| Function                        | Description                                |
|---------------------------------|--------------------------------------------|
| `get_local_interfaces()`        | Parse ipconfig output for IPv4/netmask pairs|
| `scan_subnet(cidr, timeout)`   | Multi-threaded ping sweep of subnet         |

**Interface Parsing:**
Handles both English and German `ipconfig` output:
```python
# English:  "IPv4 . . . . . . . . . . . : 192.168.1.10"
# German:   "IPv4-Adresse  . . . . . . . : 192.168.1.10"
```

**Scan Safety:**
- Subnets larger than `/24` (>256 hosts) are capped at 256 targets
- Concurrent threads limited to 16
- Per-host timeout is 2 seconds
- Duplicate IP results are deduplicated across interfaces

### 5.3 Updater (`updater.py`)

GitHub Releases integration for automatic update detection and download.

**Constants:**
```python
GITHUB_RELEASES_URL = "https://api.github.com/repos/pdchristian/WOL/releases/latest"
APP_NAME = "Wake-on-LAN Manager"
INSTALLER_FILENAME = "Wake-on-LAN Manager Installer.exe"
```

| Class/Method              | Description                              |
|---------------------------|------------------------------------------|
| `UpdateChecker`           | QObject worker for background checks     |
| `DownloadWorker`          | QObject worker for file downloads        |
| `_parse_version(version)` | Parse "v1.5.1" → (1, 5, 1) tuple         |
| `check_for_updates_sync()`| Synchronous version check for manual triggers |

**Update Check Flow:**
1. GET `GITHUB_RELEASES_URL` with 2-second timeout
2. Parse JSON response, extract `tag_name` and `body` (release notes)
3. Compare versions via `_parse_version()` tuple comparison
4. Emit `update_available(release_info)` or `no_update_available()` signal

**Download Flow:**
1. Extract download URL from release assets
2. Download to `%TEMP%\{INSTALLER_FILENAME}` via `urllib.request.urlretrieve` with reporthook for progress
3. Signal `download_finished(path)` when complete
4. Launcher calls `_launch_installer_safe()` with UAC elevation via `ShellExecuteW("runas", ...)`

### 5.4 Translations (`translations.py`)

Singleton i18n system with English fallback chain.

**Supported Locales:**

| Code | Language   | File                              |
|------|------------|-----------------------------------|
| en   | English    | `wol_app/locales/en.json`         |
| de   | Deutsch    | `wol_app/locales/de.json`         |
| fr   | Français   | `wol_app/locales/fr.json`         |
| es   | Español    | `wol_app/locales/es.json`         |

**Fallback Chain:**
```
tr("key", **kwargs)
  → look up in active locale JSON
    → NOT FOUND → look up in English (en.json)
      → NOT FOUND → return key string as-is
```

Format placeholders supported via `str.format(**kwargs)`:
```python
Translations.tr("scan.scanning_subnet", ip="192.168.1.0")
# → "Scanning subnet 192.168.1.0..."
```

### 5.5 WOL Host Service Protocol (TCP 8765, JSON lines, protocol v2)

One JSON object per line in, one JSON object per line out. All commands
authenticate first with `validate_credentials(username, password)`
(LogonUserW, interactive profile) unless noted otherwise.

| Command | Request | Response |
|---------|---------|----------|
| `shutdown` | `{"command":"shutdown","username","password"}` | `{"status":"ok"\|"error","message"}` |
| `metrics` (v2) | `{"command":"metrics","username","password"}` | `{"status":"ok","protocol":2,"hostname","cpu","cpu_count","ram_used","ram_total","uptime","gpu","vram_used","vram_total","gpu_name"}` — bytes / per-cent, each field `null` when unavailable |
| `run_batch` (v2) | `{"command":"run_batch","username","password","script","timeout"}` | `{"status":"ok","exit_code","stdout","stderr","duration_ms","truncated"}` or `{"status":"error","message"}` |

**`metrics` implementation (`wol_host_service.py`):**
- CPU/RAM/uptime via `psutil` (lazy import — the service still starts without it);
  `psutil.cpu_percent` is primed with `interval=0.15` on the first call.
- GPU/VRAM via `nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total,name
  --format=csv,noheader,nounits`; multiple GPUs are aggregated (mean utilisation,
  summed memory); results cached `GPU_CACHE_SECONDS` (1.5 s). No NVIDIA driver,
  timeout, or parse error → all GPU fields `null` ("k/A" in the UI).

**`run_batch` security gating (double opt-in):**
- Host side: disabled by default. Enable per machine with
  `"WOL Host Service.exe" --enable-batch` / `--disable-batch`, persisted in
  `%ProgramData%\WakeOnLAN\WOL Host Service\service.json` (`{"allow_batch": true}`,
  re-read on every request). Requests are rejected with `"disabled"` otherwise.
- Client side: per device `allow_batch` must be checked in the dashboard.
- Execution: script is written to a temp `.cmd` and run as `cmd.exe /d /c`
  (cwd `%TEMP%`, `CREATE_NO_WINDOW`), max 32 000 chars, timeout 5–3600 s
  (default 120 s), combined output truncated at 64 000 chars (`"truncated": true`).
  Output is decoded UTF-8 strict first, then cp850 (console OEM codepage).
- ⚠ Scripts run with the privileges of the service (SYSTEM) — the feature is
  off by default and must stay an explicit admin decision per target machine.

**Client (`host_service_client.py`):** shared `_request()` core (connect →
send line → read line, size-capped: 4 KB request, 16 KB metrics, 128 KB batch).
`get_metrics()` rejects `protocol < 2` with "Host service too old for the
dashboard". `sock_sink` exposes the connected socket to the caller so
`_CancellableWorker.cancel()` can close it mid-flight.

**Service config file:** `%ProgramData%\WakeOnLAN\WOL Host Service\service.json`
(`_CONFIG_FILE`, guarded by `_CONFIG_LOCK`) — currently only `allow_batch`.

---

## 6. Installer Framework

### 6.1 installer.py

Professional Windows installer with registry-based Add/Remove Programs integration.

**Installer Metadata:**
| Field          | Value                                |
|----------------|--------------------------------------|
| App Name       | "Wake-on-LAN Manager"                |
| Version        | 1.5.0                                |
| Publisher      | "pdchristian"                        |
| Install Dir    | `%ProgramFiles%\Wake-on-LAN Manager` |
| Registry Key   | `SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\WakeOnLAN` |

**Registry Values Written:**
```
DisplayName     = "Wake-on-LAN Manager"
DisplayVersion  = "1.5.0"
Publisher       = "pdchristian"
InstallLocation = <actual path>
UninstallString = "<path>\uninstall.exe"
ModifyPath      = "<path>\uninstall.exe"
NoModify        = 1
NoRepair        = 1
URLInfoAbout    = "https://github.com/pdchristian/WOL"
EstimatedSize   = <calculated bytes>
```

**Installation Steps:**
1. Admin privilege check via `ctypes.windll.shell32.IsUserAnAdmin()`; re-launch with UAC if needed
2. Detect existing installation and prompt for overwrite or upgrade
3. Copy application and uninstaller to `%ProgramFiles%\Wake-on-LAN Manager`
4. Create Start Menu shortcut (Programs > Wake-on-LAN Manager)
5. Optionally create desktop shortcut
6. Register in Windows Add/Remove Programs
7. Fix permissions on `~/.wol_app/` via `fix_wol_app_permissions()` if needed

**Permission Fix Sequence:**
```powershell
takeown /f "%USERPROFILE%\.wol_app" /r /d y        # Take ownership
icacls "%USERPROFILE%\.wol_app" /reset /t /c /q
# grant the INTERACTIVE desktop user, not the elevated helper's account
icacls "%USERPROFILE%\.wol_app" /grant <DOMAIN\User>:(CI)(OI)F /t
```
Fast-path check `user_has_full_control()` tests current access before running
expensive commands. The target account is resolved by `get_active_user_account()`
(owner of the running `explorer.exe`), because the elevated helper may run under
a *different* admin account ("Run as different administrator").

**App-side ACL hardening (`wol_app.utils.ensure_user_data_dir`):**
`mkdir(mode=0o700)` has no ACL effect on Windows — a new directory only inherits
its parent's DACL. Every creation point of `~/.wol_app` (config dir, log dir,
`master_key.dat` parent, `~/.wol_app/rdp`) therefore goes through
`ensure_user_data_dir()`, which grants the interactive user `(OI)(CI)F` via
`icacls` whenever the process is elevated. If a write still fails with
`PermissionError` (folder left behind by an older elevated start),
`launch_remote_desktop()` calls `_repair_dir_permissions()` — takeown + icacls,
elevated through a single UAC prompt when needed — and retries once.

### 6.2 uninstaller.py

Clean removal with secure data wiping.

**Uninstallation Steps:**
1. Terminate any running instance of the application (`taskkill`)
2. Delete Start Menu shortcut
3. Remove application directory and all contents
4. Securely wipe user data files:
   - `config.json` → overwrite with zeros, then delete
   - `master_key.dat` → overwrite with zeros, then delete
5. Remove `.wol_app` directory if empty
6. Clean up Add/Remove Programs registry key
7. Clean up orphaned registry entries matching "Wake-on-LAN"

**Elevated Process Handling:**
When running under elevation (different user context), the installer resolves the correct user profile via:
```python
username = os.environ.get("USERNAME", "")
user_dir = Path(os.path.expandvars(f"%USERPROFILE%"))
```

---

## 7. UI Components

### 7.1 MainWindow (`main_window.py`)

Central application window with device table, toolbar actions, and menu bar.

**Menu Structure:**
```
File
 ├── Devices (Ctrl+D)        → Device Manager dialog
 ├── Schedule (Ctrl+S)       → Schedule Manager dialog
 └── Exit (Ctrl+Q)           → Close application

Tools
 ├── Network Scan (Ctrl+N)   → Network Scan dialog
 ├── Settings (Ctrl+E)       → Settings dialog
 └── Logs (Ctrl+L)          → Log Viewer dialog

Help
 ├── Check for Updates (Ctrl+U) → Manual update check
 └── About                   → About dialog
```

**Toolbar Actions:**
| Button              | Action                               |
|---------------------|--------------------------------------|
| Wake Selected       | Send WoL packet to selected devices  |
| Wake All            | Wake all enabled devices             |
| Ping                | Refresh status for selected device   |
| Refresh Statuses    | Check all device statuses            |
| Shutdown            | Remote shutdown of selected device   |
| Manage Devices      | Open device manager                  |

**Device Table Columns:**
`[Name] [MAC] [IP Address] [Status] [Enabled]`

### 7.2 Modern UI (`modern_main_window.py`, new in 2.0.0)

A second, feature-identical main window: a **sidebar-based "Dark Control Center"** layout. It is selected at startup by `main()` when `ConfigManager.get_layout_mode() == "modern"` (otherwise the classic `MainWindow` runs). The layout mode is:

- Chosen **at install time** — the Inno Setup installer writes `HKLM\SOFTWARE\Wake-on-LAN Manager\UiMode` (`modern`/`classic`), read once on first start by `ConfigManager._apply_installer_ui_mode()`.
- Switchable **at runtime** via `ConfigManager.set_layout_mode()` from the Settings dialog / SettingsView (requires an app restart).

**`ModernMainWindow` structure:**
- Left **sidebar** (fixed 230 px) with two sections:
  - *Areas*: `Devices` / `Manage` / `Schedule` / `Logs` (exclusive-checked nav buttons)
  - *Application*: `Settings` / `About` / `Quit`
- Right **`QStackedWidget`** with six sidebar screens plus one detail screen:

| Index | Screen            | Module (`views/`)   | Replaces (classic)              |
|-------|-------------------|---------------------|--------------------------------|
| 0     | Devices           | `devices_view.py`   | device table + status column    |
| 1     | Manage            | `manage_view.py`    | Device Manager + Network Scan   |
| 2     | Schedule          | `schedule_view.py`  | Schedule Manager dialog         |
| 3     | Logs              | `logs_view.py`      | Log Viewer dialog               |
| 4     | Settings          | `settings_view.py`  | Settings dialog                 |
| 5     | About / Update    | `update_view.py`    | About dialog + manual update    |
| 6     | Device Dashboard  | `dashboard_view.py` | (new — no sidebar entry)        |

**Key behaviors:**
- **Dual view** (`DevicesView`): the toolbar toggle (icon top-left, SVG glyphs `#viewListButton` three-lines / `#viewGridButton` four-tiles) switches between
  - **Card grid** — responsive; each card shows a live status dot, IP/MAC, Remote-Desktop tiles (fullscreen/window), a 📊 dashboard tile and a primary action button that swaps between *Wake* (offline/unknown) and *Shutdown* (online).
  - **Device list** (`DeviceListRow`) — panel rows with status dot, name, mono "IP · MAC" and action tiles on the right (🖥️ remote fullscreen / 🪟 remote window / 📊 dashboard / ✏️ edit; double-click also edits).
  Both views share `_statuses` and rebuild via `refresh_devices()`. Auto-refresh every 30 s (`QTimer`), paused when hidden.
- **Sorting** (`DevicesView`): drop-down left of the search field — *Namen* (alphabetical), *IP-Adresse* (numeric via `_ip_sort_key`), *MAC-Adresse* (ascending), *Status* (rank Online → Offline → Unknown, then name). Persisted to `ui.devices_sort_key`; applies to both views; re-sorts after status updates when sorting by status.
- **Cross-sync:** `ModernMainWindow._on_devices_changed` keeps the device lists of `DevicesView` and `ManageView` in sync when a device is added/edited/removed in either area.
- **Shared flows:** both layouts reuse `wol_app/remote_desktop.py` (`start_remote_desktop`) and `wol_app/shutdown_flow.py` (`confirm_shutdown`/`execute_shutdown`), the same `ConfigManager` API, the same `WOLEngine`, and the classic `UpdateAvailableDialog` for downloads.
- **Theming:** `modern_theme.py` provides `DARK`/`LIGHT` token sets and `apply_modern_theme()`; objectName-based QSS so it never leaks into the classic UI. Respects `ui.display_mode` (auto/light/dark).
- **Native dialogs:** `ModernDeviceDialog` (`views/device_edit_dialog.py`) and `ModernScheduleEditDialog` (`views/schedule_edit_dialog.py`); `widgets/toggle_switch.py` provides `ToggleSwitch`/`ToggleWithLabel`.
- **Settings reset:** `SettingsView._reset_to_defaults()` restores factory defaults for the settings sections only (network, updates, log limit, shutdown method, language, display mode, RDP resolution) — devices/schedules/logs and the layout mode are preserved.
- **Device Dashboard (`dashboard_view.py`, stack index 6, no sidebar entry):** opened via the 📊 tile on each device card/row (between the remote-desktop tiles and edit) or the context menu — `DevicesView.dashboard_requested(device_id)` → `ModernMainWindow.open_device_dashboard()` (also refreshes the header on `_on_devices_changed`; `closeEvent` and `back_requested` → nav index 0 call `cancel_workers()`). Widgets: `RingGauge` (painted arc, "–" when `None`), `Sparkline` (60-sample deque, gaps break the line), `MetricCard` (CPU/RAM/GPU/VRAM, gauge colours from theme tokens `gauge_cpu`/`gauge_ram`/`gauge_gpu`/`gauge_vram`). Polls `get_metrics()` every `ui.dashboard_interval_ms` (single-flight `_metrics_busy`, paused in `hideEvent`, guarded by `HEADLESS_MODE`); offline keeps the last values but flips the badge and shows the error in `status_line`. Batch library (QListWidget + editor + console) persists via `ConfigManager.set_device_batches()`; running a batch requires the device's `allow_batch` checkbox and the host-side gate (see §5.5).

### 7.3 Dialog Components

| Dialog               | Module                    | Purpose                         |
|----------------------|---------------------------|---------------------------------|
| DeviceDialog         | `device_dialog.py`        | Add/edit device with validation |
| ScheduleDialog       | `schedule_dialog.py`      | Manage wake/shutdown schedules  |
| SettingsDialog       | `settings_dialog.py`      | Network, language, update config|
| LogDialog            | `log_dialog.py`           | View/clear activity logs        |
| NetworkScanDialog    | `network_scan_dialog.py`  | Discover devices on network     |
| UpdateAvailableDialog| `update_dialog.py`        | Show release notes + download   |
| UpdateErrorDialog    | `update_dialog.py`        | Network error during update     |
| UpdateInfoDialog     | `update_dialog.py`        | "Already up to date" message    |

---

## 8. Build System

### 8.1 build.ps1

PowerShell script that orchestrates the three-stage PyInstaller build:

```powershell
# Stage 1: Clean previous builds (dist/, build/)
# Stage 2: pyinstaller "Wake-on-LAN Manager.spec" → main app EXE
# Stage 3: pyinstaller "uninstaller.spec"          → uninstaller EXE
# Stage 4: pyinstaller "installer.spec" --clean    → installer EXE
# Stage 5: Verify all outputs exist and report sizes
```

**PyInstaller Spec Files:**

| Spec File                      | Output                                        | Description                     |
|--------------------------------|-----------------------------------------------|---------------------------------|
| `Wake-on-LAN Manager.spec`     | `dist/Wake-on-LAN Manager.exe`                 | Main application                |
| `uninstaller.spec`             | `dist/uninstall.exe`                           | Standalone uninstaller          |
| `installer.spec`               | `dist/Wake-on-LAN Manager Installer.exe`       | Full installer with embedded app|

### 8.2 Build Prerequisites

```
Python 3.10+
PyInstaller (pip install pyinstaller)
PyQt6>=6.6.0
cryptography>=41.0.0
PowerShell 5.1+ (for build.ps1)
```

---

## 9. Data Flow Diagrams

### 9.1 Wake Packet Flow
```
User clicks "Wake Selected"
    → MainWindow._wake_selected()
        → WOLEngine.send_wake_packet(device_id)
            → ConfigManager.get_device_by_id(id)
                → _create_magic_packet(mac)  # 102-byte packet
                    → find_interface_for_device(device)
                        → get_local_interfaces()
                            → ipconfig parsing
                                → subnet match calculation
                                    → UDP socket (broadcast)
                                        → sock.sendto(packet, (IP, port))
```

### 9.2 Configuration Save Flow
```
User saves device dialog
    → ConfigManager.save()
        → _encrypt_devices(config)
            → crypto.encrypt_password(plaintext)
                → AES-256-GCM(nonce + key)
                    → base64 encoding
                        → json.dump to config.json (0o600 permissions)
                            → _decrypt_devices(config)  # in-memory stays plaintext
```

### 9.3 Scheduler Flow
```
Application starts
    → WOLEngine.start_scheduler()
        → threading.Timer(60, _run_scheduler_check)
            → every 60 seconds:
                → compare current time/day with each enabled schedule
                    → MATCH → emit schedule_fired(device_id, action)
                        → MainWindow._on_schedule_fired()
                            → send_wake_packet() OR remote_shutdown()
                                → add_log(action, status, message)
```

---

## 10. Version History (Selected Milestones)

| Version | Date       | Edition                    | Key Changes                                    |
|---------|------------|----------------------------|-------------------------------------------------|
| 2.1.0   | 2026-09-03 | Dashboard Edition          | Per-device dashboard (CPU/RAM/GPU/VRAM ring gauges + sparklines, 2–10 s polling, NVIDIA-only GPU via nvidia-smi), remote batch execution with per-device library + console, host service protocol v2 (`metrics`/`run_batch`, double opt-in gating via `--enable-batch`), 📊 tile in devices view (no sidebar entry), cancellable socket workers |
| 2.0.0   | 2026-09-01 | Modern UI Edition          | Modern "Dark Control Center" sidebar layout (Devices/Manage/Schedule/Logs/Settings/About screens), installer UI-mode choice, display mode (dark/light/auto), Devices screen with card/list dual view and sort drop-down |
| 1.10.0  | 2026-08-22 | Search & Remote Desktop Edition | Remote Desktop sessions (fullscreen/window), device search in main window/device manager/scanner/schedules |
| 1.6.0   | 2026-08-05 | Improvement Edition        | Lazy permissions fix, logging module, thread tracking, parallel wake/ping |
| 1.5.1   | 2026-07-21 | Scheduler Fix Edition      | Scheduler reliability improvements              |
| 1.5.0   | 2026-07-19 | Installer Pro Edition      | Professional installer with registry integration|
| 1.3.3   | 2026-07-18 | Console Flash Fix Edition  | Fixed console flash on startup, icacls syntax    |
| 1.3.2   | 2026-07-18 | Permission Fix Edition     | Fast-path permission checks, reduced timeouts    |
| 1.3.1   | 2026-07-18 | Security Hardened Edition  | Full security audit, 15 risks remediated         |

---

## 11. Environment Variables

| Variable       | Effect                                       |
|----------------|----------------------------------------------|
| HEADLESS_MODE  | Disables background threads (status worker, update checker, scheduler); intended for test/CI environments |

---

## 12. File Permissions Model

| Path                                  | Permission | Purpose                              |
|---------------------------------------|------------|--------------------------------------|
| `~/.wol_app/`                         | 0o700      | Owner-only directory access           |
| `~/.wol_app/config.json`              | 0o600      | Owner read/write for config data      |
| `~/.wol_app/master_key.dat`           | (default)  | DPAPI-protected binary blob           |

---

## 13. Known Dependencies Matrix

| Package         | Minimum Version | Purpose                            |
|-----------------|-----------------|------------------------------------|
| Python          | 3.10            | Runtime requirement                |
| PyQt6           | 6.6.0           | GUI framework                      |
| cryptography    | 41.0.0          | AES-256-GCM encryption             |
| psutil          | 5.9.0           | Host-service CPU/RAM metrics (dashboard) |
| pywin32         | 306             | WOL Host Service (Windows service) |
| PyInstaller     | (any recent)    | Packaging to standalone EXE        |

All other imports are from the Python standard library (`json`, `socket`, `subprocess`, `threading`, `ctypes`, `urllib`, `uuid`, `datetime`, `tempfile`, `os`, `sys`, `logging`). `psutil` is imported lazily inside `collect_metrics()`; both host-service specs list it in `hiddenimports`.

---

## 14. Glossary

| Term                    | Definition                                                      |
|-------------------------|-----------------------------------------------------------------|
| WoL                     | Wake-on-LAN: network protocol to power on a computer via magic packet |
| Magic Packet            | 102-byte UDP datagram (6×FF + 16×MAC address)                   |
| DPAPI                   | Windows Data Protection API for user-level key encryption       |
| AES-256-GCM             | Advanced Encryption Standard, 256-bit key, Galois/Counter Mode  |
| CIDR                    | Classless Inter-Domain Routing notation for subnet addresses     |
| Broadcast IP            | Network address (typically 255.255.255.255) for UDP broadcast   |
| ICMP Ping               | Internet Control Message Protocol echo request for reachability |
| UAC Elevation           | Windows User Account Control privilege elevation                |
| CREATE_NO_WINDOW        | Windows subprocess flag to suppress console window creation     |

---

*This document was generated in Open Knowledge Format (OKF) v1.0 and serves as the authoritative knowledge source for the Wake-on-LAN Manager project.*
