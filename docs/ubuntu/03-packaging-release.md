# Phase 4 – `.deb`-Packaging  (depends on P2; Test nach P3)

4.1 `packaging/` aus Port übernehmen: `build_deb.sh`,
    `deb/DEBIAN/{control.in,postinst,prerm,postrm}`, `deb/wol-host-service.service`.
4.2 `build_deb.sh` anpassen:
    - Nur Modern-UI-Dateien stagehn (klassische UI-Dateien `main_window.py`,
      `device_dialog.py`, `log_dialog.py`, `network_scan_dialog.py`,
      `schedule_dialog.py` + Windows-`utils.py`-Anteile ausschließen;
      stattdessen `sys.platform`-Shims, die auf Linux nie win32 importieren).
    - Host-Service: `wol_host_service_linux.py` als
      `/usr/share/wake-on-lan-manager/wol_host_service.py` stagehn.
    - `Depends`: python3(>=3.10), python3-pyqt6, python3-cryptography, python3-psutil,
      python3-pamela, libpam0g, iputils-ping, iproute2. `Recommends`: freerdp2-x11,
      avahi-daemon.
    - `/usr/bin/{wake-on-lan-manager,wol-host-service}` Launcher.
    - Version aus `wol_app/__init__.py` (=2.2.2). hicolor-Icons.
4.3 `control.in` Description auf 2.2.x-Features aktualisieren (watched processes).
4.4 `install.sh` (Dev-Pfad) beibehalten; README-Tabelle prüfen.
4.5 Optional `.github/workflows/release.yml`: ubuntu-latest → `build_deb.sh` →
    Release-Asset `*.deb`.

# Phase 5 – VM-Verifikation + Release  (depends on P3,P4)

5.1 `docs/ubuntu/vm-test-guide.md` (s. eigene Datei).
5.2 Smoke-Checks: App-Grid-Start, WOL single/all, Scanner (`ip neigh`),
    Dashboard-Metrics, Watched Processes, Remote Shutdown (PAM), xfreerdp,
    Logs/CSV, Sprache (de/en/fr/es).
5.3 Host-Service: `wol-host-service --status`, `systemctl status wol-host-service`,
    Port 8765 offen, `--enable-batch` Opt-in, ufw-Regel 8765.
5.4 `QT_QPA_PLATFORM=offscreen pytest -q` (alle Tests).
5.5 Version final 2.2.2; CHANGELOG + README aktualisieren; GitHub Release mit
    `.deb`-Asset.

## Abnahmekriterium P4+P5
`dpkg-deb --info`/`dpkg -L` sauber; App + Host-Service in VM funktional;
Release-Asset herunterladbar.
