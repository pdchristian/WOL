# Phase 3 – Feature-Parität 2.2.0 + 2.2.1  (depends on P2)

## 3.1 Host-Service watch/processes/models (Linux)
In `wol_host_service_linux.py` ergänzen (Vorbild Windows `wol_host_service.py`):
- `collect_metrics(watch=...)` → `processes`-Map im `metrics`-Response.
- `_watched_processes`: psutil-Suche (name/pid/cpu/ram/uptime/count), CPU%-Cache.
- `_check_port_loopback` (`:port`-Probe, loopback).
- `_fetch_loaded_models` (llama.cpp `GET /v1/models`) + `_model_from_argv`
  (`-m/--model`), `_model_display_name`, `_models_from_api_json`.
- Konstanten `WATCH_MAX_ENTRIES`, `WATCH_PORT_TIMEOUT_S`, `WATCH_MODELS_TIMEOUT_S`,
  `WATCH_MAX_MODELS`, `MODEL_FILE_EXTS`. `PROTOCOL_VERSION = 4`.

## 3.2 Client
`host_service_client.get_metrics(ip, ..., watch=[...])` sendet `watch` (Cap 8).
Der Client ist plattformneutral – nur ein Kwarg ergänzt.

## 3.3 Config (nur falls Port-Lücke im Monorepo-Code existiert)
Windows-`config.py` hat bereits `MAX_WATCH_PROCESSES_PER_DEVICE`,
`get/set_device_watch_processes`, `ip[:253]` + `validate_ip_or_hostname`.
Monorepo-Basis = Windows → nichts zu tun, außer Linux-Pfade in `config.py`
über den Shim (P2.4) abzusichern.

## 3.4 Metrics-Worker
Windows-`MetricsWorker` hat bereits `watch`. Monorepo → unverändert.

## 3.5 Dashboard-UI (`views/dashboard_view.py`)
Windows-Implementierung hat ServiceChips/svc_panel/INFERENCE-Heuristik bereits.
Monorepo → unverändert; nur Batch-Default-Skript plattformabhängig:
Linux `#!/bin/bash`-Platzhalter (statt `@echo off`).

## 3.6 Geräte-Dialog (`views/device_edit_dialog.py`)
Windows hat `watch_input`-Feld bereits. Monorepo → unverändert.

## 3.7 RDP-Retry (analog, xfreerdp)
Linux-`remote_desktop.py`: xfreerdp-Kindprozess überwachen; Exit <10 s MIT
gespeichertem Passwort → Prompt „ohne Passwort neu verbinden" (`/p:` weglassen,
`+auto-reconnect` bleibt). Locale-Keys `dialog.rdp_retry.*` nutzen.
Windows-mstsc-Logik bleibt in Windows-`remote_desktop.py`/`utils.py`.

## 3.8 Locale
`modern.dashboard.svc.*` und `dialog.rdp_retry.*` sind in den Windows-locales
bereits vorhanden. Prüfen, ob alle 4 Sprachen vollständig sind;
`python check_translations.py` → 0 missing.

## Abnahmekriterium P3
Windows-Tests grün inkl. watch-Abdeckung; neue Linux-Tests für watch/RDP grün
(offscreen); Dashboard zeigt Service-Chips in VM.
