# Architektur: geteilte Codebasis mit Plattform-Shims

## Prinzip
Ein `wol_app/` für beide Plattformen. Plattformspezifisches wird hinter einer
dünnen Shim-Schicht gekapselt. Views/Dialoge bleiben plattformneutral.

## Entry (`run.py`)
`sys.platform`-Verzweigung:
- win32 → klassische `main()` (UI-Modus-Wahl modern/klassisch).
- linux → `run_modern_window(config, dark_mode)` (Modern UI only).
Die Modern-Window-Logik aus `C:\Python\WOL-Ubuntu\run.py` (Fusion-Style,
`maybe_start_watchdog`, `apply_display_mode`, Icon) bleibt in `run.py` und
nutzt `app_core`/`modern_main_window`.

## `app_core.py` (portiert)
`HEADLESS_MODE`, `StatusWorker`, `_track_thread`. **Views importieren NUR
`app_core`**, nie `main_window`. Windows `main_window.py` re-exportiert diese
Symbole für Abwärtskompat.

## Shim-Schicht
`wol_app/platform.py` wählt via `sys.platform`:
| API | `platform_win` | `platform_linux` |
|---|---|---|
| Master-Key | DPAPI | Datei `~/.wol_app/master_key.dat` (0600) |
| RDP | mstsc + `.rdp` + Credential-Manager | `xfreerdp` (`build_xfreerdp_args`) |
| Theme-Auto | winreg | gsettings |
| Host-Service-Install | SCM/pywin32 + Firewall | systemd-Unit + ufw |
| Netzwerk-Interfaces | `ipconfig`/psutil | `ip`/`ip neigh`/`/etc/resolv.conf`/psutil |
| Pfade | `%LOCALAPPDATA%`/`%ProgramData%` | `~/.wol_app`/`/var/log/wol-host-service` |

## Host-Service
`wol_host_service.py` bleibt Windows-Service (SCM/pywin32).
`wol_host_service_linux.py` = Linux-Variante (systemd, `systemctl poweroff|reboot`,
PAM/`pamela`), aus Port `C:\Python\WOL-Ubuntu\wol_host_service.py` übernommen.
Beide sprechen dasselbe JSON-Protokoll (v4).

## Feature-Gate
`host_service_client.HOST_SERVICE_IMPLEMENTED` bleibt exportiert;
Windows=True, Linux=True (beide Services vorhanden). Kein Feature-Skip mehr.

## Klassische UI auf Linux
Dateien (`main_window.py`, `device_dialog.py`, `log_dialog.py`,
`network_scan_dialog.py`, `schedule_dialog.py`) bleiben im Baum, werden auf
Linux nicht importiert (Gate über `sys.platform` im Entry).

## Requirements (PEP-508)
```
PyQt6>=6.6.0
cryptography>=41.0.0
psutil>=5.9.0
pywin32>=306; sys_platform == "win32"
pamela>=1.2.0; sys_platform == "linux"
```
