# Phase 1 – Merge in Monorepo  (depends on P0)

1.1 `app_core.py` aus Port → `wol_app/app_core.py`. Windows `main_window.py`
    importiert `HEADLESS_MODE`/`StatusWorker`/`_track_thread` aus `app_core`
    (Re-Export, Verhalten unverändert).
1.2 Moderne Dialoge aus Port übernehmen, falls Windows-Baum abweicht:
    `views/device_edit_dialog.py`, `views/schedule_edit_dialog.py`,
    `views/shutdown_confirm_dialog.py`. `views/`+`widgets/`-Dateilisten abgleichen.
1.3 `run.py` plattformverzweigt (siehe Architektur). `run_modern_window`-Logik
    aus Port-`run.py` in den geteilten Entry verlagern.
1.4 Klassische UI-Dateien bleiben; auf Linux kein Import.

# Phase 2 – Plattform-Shims  (depends on P1)

2.1 `platform_base.py` (Protocol/ABC) + `platform.py` (Factory via `sys.platform`).
2.2 `platform_win.py`: DPAPI-Key, mstsc/`.rdp`/`cmdkey`, winreg-Theme, win32-SCM,
    `ipconfig`, `%LOCALAPPDATA%`/`%ProgramData%`.
2.3 `platform_linux.py`: Datei-Master-Key, `build_xfreerdp_args`+`xfreerdp_available`,
    gsettings, systemd-Install, `ip`/`ip neigh`, `~/.wol_app`/`/var/log/...`.
2.4 Umstellen auf Shim-Aufrufe: `crypto.py`, `theme.py`, `config.py` (Pfade),
    `watchdog.py` (Logpfad). **Windows-Verhalten muss bitgenau bleiben** →
    Regressionstests zuerst grün.
    Hinweis: `remote_desktop.py` und `network_scanner.py` behalten ihre
    plattformspezifischen Implementierungen (Windows: mstsc/.rdp, Linux:
    xfreerdp/`ip neigh`) und werden per `sys.platform`-Import geladen.
2.5 `settings_dialog.py`-Validatoren `_validate_broadcast_ip`/`_validate_port`
    bleiben wie sie sind (Windows-Dialog existiert; Linux-views importieren
    daraus – unverändert lassen, solange Tests grün).
2.6 `requirements.txt` PEP-508-Marker (siehe Architektur).

## Abnahmekriterium P1+P2
Windows-`pytest` unverändert grün; App startet auf Windows wie vorher;
`python -c "import wol_app.platform"` löst auf beiden Plattformen korrekt auf.
