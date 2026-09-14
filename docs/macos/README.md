# macOS-Port (Apple Silicon) – Arbeitsdokumentation

Zusätzlich zu Windows und Ubuntu läuft der Wake-on-LAN Manager nativ auf
macOS 11+ (nur arm64 / Apple Silicon). Modern UI wie beim Ubuntu-Port
(Monorepo, plattformverzweigter Einstieg in `run.py`). Der Host Service
existiert als eigene macOS-Variante (launchd, PAM).

## Status
| Phase | Inhalt | Status |
|---|---|---|
| M0 | Vorbereitung (Entscheidungen: arm64-only, unsigned, .dmg, voller Umfang) | ✅ fertig |
| M1 | Plattform-Shims: `build_ping_args` (BSD ping), ARP/`ndp`-Parser, Dark Mode (`AppleInterfaceStyle`) | ✅ fertig |
| M2 | Remote Desktop über **Microsoft Remote Desktop** (`rdp://`-URI, Fast-Exit-Retry ohne Passwort) | ✅ fertig |
| M3 | Updater: `.dmg`-Asset auswählen und per `open` mounten | ✅ fertig |
| M4 | macOS Host Service: `wol_host_service_macos.py` (LaunchDaemon, PAM/pamela, `shutdown -h/-r now`), `packaging/macos/install_host_service.command` | ✅ fertig (E2E: TCP status + PAM-Auth im Freeze verifiziert) |
| M5 | SMB-Shutdown-Guard (nur win32) + Locale-Keys (DE/EN/FR/ES) | ✅ fertig |
| M6 | Packaging: `Wake-on-LAN Manager-macos.spec` (.app), `packaging/macos/build_macos.sh` (.app + .dmg + optional Service), `icon_macos.icns` | ✅ fertig |
| M7 | Tests: `tests/test_macos_support.py` + Windows-only-Tests plattformfest gemacht; Full-Suite grün auf macOS | ✅ fertig (486 passed, 5 skipped) |
| M8 | Build-Verifikation auf echter Hardware (App-Start, DMG-Mount, Service-Freeze) | ✅ fertig |
| M9 | Host Service in die .app einbetten: Erststart-Abfrage + Installieren/Aktualisieren/Entfernen in den Einstellungen (`wol_app/host_service_installer.py`) | ✅ fertig (Build + 542-Testsuite grün) |

## Build & Distribution

```bash
# App (mit eingebettetem Host Service) + DMG (unsigned, ad-hoc signiert):
./packaging/macos/build_macos.sh
```

Ergebnis: `dist/Wake-on-LAN Manager.app`,
`dist/Wake-on-LAN Manager_<version>_arm64.dmg` (~48 MB, enthält
`Applications`-Symlink). Das Service-Bundle wird zuerst als
`dist/WOL Host Service/` (onedir) gebaut und dann in die App eingebettet
(`Contents/Resources/WOL Host Service`); der Build bricht ab, wenn die
Payload in der .app fehlt.

- **Unsigned:** kein Apple-Developer-Account. Der Build wird lokal mit
  Ad-hoc-Signatur (`codesign -s -`) versehen — ohne jede Signatur verweigert
  macOS arm64-Binaries den Start. Für die Verteilung bleibt die App
  notariatsfrei: Erster Start per **Rechtsklick → Öffnen** (einmalig) oder
  `xattr -dr com.apple.quarantine <App>`.
- **Architektur:** bewusst arm64-only (`target_arch='arm64'` in beiden Specs).
  Intel-Macs werden nicht unterstützt; universal2 wäre möglich, aber die
  Zielgeräte sind Apple Silicon.

## Plattform-Entscheidungen
- **Eigene `utils`-Zweige statt Fork:** `sys.platform == "darwin"`-Abzweigungen
  in `utils.py` (RDP), `theme.py` (Dark Mode), `network_scanner.py` (ping/arp/
  ndp), `wol_engine.py` (Ping-Argumente), `config`/`update_dialog` (.dmg).
- **Ping:** BSD `ping` kennt kein `-4` und kein `-w <ms>` → `build_ping_args()`
  liefert pro Plattform die richtigen Argumente (`-c` + `-W <ms>` auf macOS).
- **Remote Desktop:** kein `mstsc`; die **Microsoft Remote Desktop** App
  (`com.microsoft.rdc.macos`) wird per Legacy-`rdp://full%20address=s:…&
  username=s:…`-URI geöffnet. Password kann der URI nicht transportieren
  (wie iOS/Android); bei Schema-Failure fällt `_launch_remote_desktop_macos`
  auf `open -b <bundleid>` zurück. Fast-Exit-Retry öffnet ohne Credentials.
- **Host Service:** teilt den kompletten Kern mit `wol_host_service_linux.py`
  (`import wol_host_service_linux as core`, Protokoll v5, pamela/PAM
  `service=login`, psutil-Metriken, watch/models, run_batch opt-in). Nur
  Power-Kommandos (`/usr/sbin/shutdown -h|-r now`) und Service-Verwaltung
  (LaunchDaemon `de.wolmanager.hostservice` in `/Library/LaunchDaemons`,
  `launchctl bootstrap/kickstart/bootout`) unterscheiden sich. Firewall:
  `socketfilterfw --add/--unblockapp` best-effort. Log:
  `/var/log/wol-host-service.log`.
  - **Installation aus der App** (`wol_app/host_service_installer.py`): die
    .app enthält das Service-Bundle unter `Contents/Resources/WOL Host
    Service`. Beim **ersten Start** fragt die App (nur im eingefrorenen
    Build, nur wenn eine installierbare/neuere Payload vorhanden ist), ob
    der Dienst installiert oder aktualisiert werden soll; ein „Nein" wird
    pro Payload-Version gemerkt (`ui.hostservice_prompted_version` in
    `config.json`). In den **Einstellungen** gibt es zusätzlich eine
    Statuszeile mit *Installieren / Aktualisieren* und *Entfernen*.
  - **Privilegien ohne Developer ID:** kein `sudo`-Terminal, sondern
    `osascript … with administrator privileges` (Passwort- oder Touch-ID-
    Dialog). Das Root-Skript (Payload kopieren, Quarantäne-xattr löschen,
    `--install`/`--uninstall` des Service-Binaries, Versions-Marker
    `/usr/local/lib/wol-host-service/service_version.txt` schreiben) liegt
    in einer Temp-Datei und läuft mit Ausgabe-Umleitung nach
    `/tmp/wol-host-service-install.log` (für lesbare Fehlermeldungen).
    Abbruch (-128) wird kommentarlos behandelt.
  - **Versionsvergleich:** Payload-Version (`service_version.txt` neben dem
    Binary, sonst App-Version) vs. installierte Version (Marker, sonst
    „0.0.0" bei Altinstallationen via `install_host_service.command`,
    sonst „nicht installiert").
  - Warum nicht `dscl`? `dscl . -authonly` verhält sich im nicht-interaktiven
    Aufruf unzuverlässig (Exit-Code 0 trotz Fehler) → PAM ist der verifizierte
    Weg.
- **SMB-Fernabschaltung** ist ein reiner Windows-Mechanismus (`net use`/
  `shutdown /i`-Semantik) → auf macOS/Ubuntu bewusst gesperrt mit lokalem
  Hinweis auf den Host Service (`dialog.shutdown_smb_unsupported.*`).
- **Updater:** `_installer_suffix()` → `.dmg`; Download wie Windows, Start per
  `open` (mountet das Image). Der eigentliche Austausch bleibt Drag & Drop auf
  `Applications` — daher kein automatischer Install wie unter Windows.
- **Konfiguration:** wie immer `~/.wol_app/` (`config.json`, `master_key.dat`
  AES-256-GCM; auf macOS ohne DPAPI — identische KDF wie der Linux/Ubuntu-Pfad).
- **venv-Name:** auf macOS/Linux `.venv`, Windows `venv`. Build-Skripte
  prüfen das explicit.

## Bekannte macOS-Eigenheiten
- Erster Start einer heruntergeladenen, nicht notarisierten .app verlangt
  Rechtsklick → Öffnen (einmalig pro Kopie).
- `Microsoft Remote Desktop` muss installiert sein, sonst meldet der
  Remote-Desktop-Knopf einen Fehler mit Installationslink (App Store).
- Das launchd-Log schreibt nach `/var/log/wol-host-service.log`; die Datei
  existiert erst nach dem ersten Start des Daemons.
- Der Update-Dialog öffnet die `.dmg` — der Nutzer verschiebt die App selbst;
  ein vollständig automatischer Self-Update wie unter Windows (.exe-Installer)
  ist auf macOS ohne Installer-Tooling nicht abgebildet.
- `wol_app/updater.py` (unbenutzt, nur Referenz) bleibt .exe-zentriert — die
  reale Update-Pipeline ist `update_dialog.py`.

## Dateien
- `Wake-on-LAN Manager-macos.spec` – PyInstaller-Bundle-Spec (Info.plist mit
  `de.wolmanager`, dynamische Version aus `wol_app/__init__.py`, `icon_macos.icns`)
- `icon_macos.icns` – generiert aus `icon_modern.png` (sips + iconutil; vom
  Build-Skript bei Bedarf neu erzeugt)
- `packaging/macos/build_macos.sh` – Build (Service-Bundle → .app mit
  eingebetteter Payload → DMG)
- `packaging/macos/install_host_service.command` – Endanwender-Install für den
  LaunchDaemon (sucht dist-Bundle, sonst Repo + .venv); Alternative zur
  Erstinstallation aus der App
- `wol_app/host_service_installer.py` – Install/Update/Remove des eingebetteten
  Dienstes (Qt-freier Kern + Worker; Erststart-Abfrage, Einstellungen-Zeile)
- `wol_host_service_macos.py` – Service-Variante (launchd/PAM, `--version`)
- `wol_host_service_macos.spec` – onedir-Spec des Service-Bundles
- `tests/test_macos_support.py` – Ping-Args, RDP-URI/`open`-Aufrufe, .dmg-Suffix,
  Dark-Detection, SMB-Guard, Host-Service-Installer (State-Matrix,
  Prompt-Gating, Skript-Builder, osascript-Runner mit Fake-Runner,
  Install/Remove-Flows, Config-Marker)

## Releases / GitHub
Assets pro Release: `Wake-on-LAN Manager Installer.exe` (Windows),
`wake-on-lan-manager_<v>-1_all.deb` (Ubuntu),
`Wake-on-LAN Manager_<v>_arm64.dmg` (macOS). Der Updater wählt pro Plattform
das passende Asset über die Suffix-Erkennung.

## Versionierung
`wol_app/__init__.py` ist Quelle; `update_docs_version.py` pflegt u. a.
`Wake-on-LAN Manager-macos.spec` (Header-Kommentar) mit. plist-Werte werden
zur Buildzeit dynamisch gelesen (kein Drift).
