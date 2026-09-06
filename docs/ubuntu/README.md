# Ubuntu / Debian-Port – Arbeitsdokumentation

Zusätzlich zur Windows-Version wird der Wake-on-LAN Manager als Ubuntu-Debian-Paket
(`.deb`) bereitgestellt. Funktionen identisch außer der klassischen UI
(Modern UI only). Host Service als Linux-/systemd-Variante.

## Status
| Phase | Inhalt | Status |
|---|---|---|
| P0 | Vorbereitung (Branch `Ubuntu-Version`, Doku, `.gitignore`) | ✅ fertig |
| P1 | Merge in Monorepo (`app_core.py`, plattformverzweigter `run.py`) | ✅ fertig |
| P2 | Plattform-Shims (crypto/theme/watchdog/utils-RDP, PEP-508) | ✅ fertig |
| P3 | Feature-Parität 2.2.0 + 2.2.1 (`wol_host_service_linux.py` v4, xfreerdp-Retry) | ✅ fertig |
| P4 | `.deb`-Packaging (`packaging/`, Modern-only, LF-Skripte) | ✅ fertig |
| P5 | VM-Verifikation + GitHub Release | 🔄 wartet auf echte Ubuntu-VM (Guide: `vm-test-guide.md`) |

## Bekannte Linux-Eigenheiten
- Der „Jetzt aktualisieren"-Knopf im Update-Dialog lädt die Windows-`.exe`
  herunter; auf Linux schlägt das Starten fehl (no-op, kein Crash). Empfehlung:
  Release-Seite via Changelog-Link nutzen (funktioniert wie bei Android/Port).
- `settings_dialog.py` wird mitgeliefert, weil `settings_view.py` dessen
  reine Validatoren importiert; der Dialog selbst wird auf Linux nie geöffnet.
- `test_sidebar.py`-Fehler/`0xC0000409` beim pytest-Teardown auf Windows sind
  vorbestehende Flakiness (Qt-Shutdown-Race), unabhängig von diesem Port.

## Dateien
- `00-architecture.md` – Shim-Architektur, Monorepo-Layout, Divergenz-Matrix
- `01-merge-shims.md` – P1 + P2 Detail
- `02-feature-parity.md` – P3 Detail
- `03-packaging-release.md` – P4 + P5 Detail
- `vm-test-guide.md` – VM-Aufbau, Build, Install, Smoke-Checks (P5)

## Entscheidungen
- Monorepo, **geteilte Codebasis** mit Plattform-Shims (kein Fork).
  Basis = `c:\Python\WOL` (Windows, v2.2.1, Source of Truth).
- Version: auf **2.2.2** angleichen (Windows + Ubuntu synchron).
- Build/Test: **echte Ubuntu-VM/Host** (Repo liefert Skripte + Anleitung).
- Distribution: **lokales `.deb` + GitHub Release** (kein PPA/apt-Repo).
- RDP: **analoger Retry für xfreerdp** (nicht überspringen).
- Klassische UI: in Ubuntu **nicht** enthalten.

## Paritätslücke Port(2.1.0) → Windows(2.2.1)
- Watched Processes (Host-Protokoll v3/v4: `watch`/`processes`/`models`, llama.cpp),
  `watch_processes`-Config-API, Dashboard `ServiceChip`/`ServiceRow`/`svc_panel`,
  `INFERENCE_GPU_PCT/POLLS`-Heuristik, `:port`-Loopback-Probe.
- 2.2.1 RDP-Fast-Exit-Retry (Windows mstsc) → xfreerdp-Analogon.
- `config.ip` `[:15]` → `[:253]` + `validate_ip_or_hostname` (Hostname-Support).
- ~19 Locale-Keys: 17× `modern.dashboard.svc.*` + 2× `dialog.rdp_retry.*`.
- Port-Tests fehlen: `test_remote_desktop`, `test_shutdown_flow`.

## Referenzbaum (Port-Vorlage)
`C:\Python\WOL-Ubuntu` (v2.1.0) liegt außerhalb des Workspace und dient als
Vorlage für: `app_core.py`, `run.py` (modern entry), `crypto.py` (file key),
`theme.py` (gsettings), `network_scanner.py` (`ip`/`ip neigh`),
`remote_desktop.py` (xfreerdp), `wol_host_service.py` (systemd/PAM),
`packaging/` (.deb), `install.sh`, `requirements.txt` (pamela).
