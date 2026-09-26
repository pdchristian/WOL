# Build Guide — Wake-on-LAN Manager

Kurze, pragmatische Bauanleitung für alle Plattformen. Version ist immer
`wol_app/__init__.py` (Single Source of Truth); die Build-Skripte synchronisieren
die Docs automatisch (`update_docs_version.py`).

Vor dem jeweiligen Plattform-Build:

```bash
# Windows
py -3.12 -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt

# macOS / Linux (venv-Name dort: .venv)
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
```

`requirements-dev.txt` bringt PyInstaller, pytest und jsonschema mit.

---

## Windows (v2.3.6)

Kompletter Build in einem Schritt:

```powershell
.\build.ps1
```

Ablauf (8 Schritte): Docs-Sync → Clean → App (`Wake-on-LAN Manager.spec`) →
Host Service (`wol_host_service.spec`, onedir) + onefile-Variante → Uninstaller →
Installer-Helper → Inno Setup (`setup.iss` → `dist\Wake-on-LAN Manager WinInstaller.exe`).

- **Pflicht:** Projekt-`venv\` muss existieren — das Skript erzwingt
  `venv\Scripts\python.exe -m PyInstaller` (niemals PyInstaller von PATH).
- **Inno Setup 6** wird gebraucht: `winget install --id JRSoftware.InnoSetup`
  (Skript findet ISCC automatisch in LOCALAPPDATA / Program Files).
- Ergebnis: `dist\Wake-on-LAN Manager Setup.exe`, `dist\WOL Host Service\`,
  `dist_onefile\WOL Host Service.exe`.
- Nach Service-Builds die Warn-Datei `build\wol_host_service\warn-wol_host_service.txt`
  auf „missing module" prüfen.

## Ubuntu / Linux (.deb)

```bash
./packaging/build_deb.sh
# → dist/wake-on-lan-manager_<version>-1_all.deb
sudo apt install ./dist/wake-on-lan-manager_*_all.deb
```

- Nutzt nur `dpkg-deb` — kein debhelper, kein fakeroot, kein root nötig.
- Shippt Modern UI (klassische UI-Dateien werden exkludiert) + Host Service als
  systemd-Unit (`wol-host-service`, TCP 8765) + CLI `/usr/bin/wol-host-service`.
- **Pitfall:** Build nicht auf NTFS-Mounts (z. B. `/mnt/c` unter WSL) — dpkg-deb
  lehnt das control-Verzeichnis wegen 777-Rechten ab. Projekt nach `/tmp` kopieren:
  ```bash
  tar --exclude=venv --exclude=.venv --exclude=build --exclude='dist*' \
      --exclude=android* --exclude=ios --exclude=design_prototype \
      --exclude=graphify-out --exclude=.git --exclude=__pycache__ \
      -cf - . | (mkdir -p /tmp/wolbuild && tar -xf - -C /tmp/wolbuild)
  cd /tmp/wolbuild && ./packaging/build_deb.sh
  ```
- Alternative ohne Paketierung (Dev-Pfad): `./install.sh` (apt-Deps + venv +
  GNOME-Desktop-Eintrag, optional Host Service).
- Tests: `QT_QPA_PLATFORM=offscreen python -m pytest tests -q`.

## macOS (Apple Silicon, .app + .dmg)

```bash
./packaging/macos/build_macos.sh
# → dist/Wake-on-LAN Manager.app
# → dist/Wake-on-LAN-Manager_<version>_arm64.dmg
```

- Erwartet das venv unter `.venv/` (nicht `venv/`).
- Baut erst den Host Service (`wol_host_service_macos.spec`) und bettet ihn als
  `Contents/Resources/WOL Host Service` in die App ein — der Build bricht ab,
  wenn die Payload fehlt.
- `icon_macos.icns` wird bei Bedarf aus `icon_modern.png` neu erzeugt (sips/iconutil).
- **Unsigned** (kein Developer-Account): ad-hoc codesign im Skript; Ersterststart
  per Rechtsklick → Öffnen oder `xattr -dr com.apple.quarantine`.
- Host Service manuell/installativ: `packaging/macos/install_host_service.command`.

## Android (WebView-Shell, `android_html/`)

```powershell
.\build_html.ps1          # nur Debug-APK
.\build_html.ps1 -Tests   # erst Unit-Tests (:app:testDebugUnitTest), dann APK
```

- Voraussetzungen: **JDK 21** (`JAVA_HOME`, im Skript auf
  `C:\Program Files\Android\openjdk\jdk-21.0.8` gesetzt) + **Android SDK** +
  Gradle 8.7 (`C:\tools\gradle-8.7\bin\gradle.bat`, kein Wrapper). Pfade ggf.
  im Skript anpassen.
- Ergebnis: `dist_onefile\wolmanager-android-html-<version>-debug.apk`
  (alte APKs werden vorher gelöscht).
- Nach Edits an `app/src/main/assets/app/app.js` immer `node --check app.js`
  laufen lassen — ein Syntaxfehler im I18N-Objekt lässt die WebView-App leer
  erscheinen.
- Bei jedem Fix-Build `versionName` (und `versionCode`) in
  `android_html/app/build.gradle.kts` erhöhen, sonst testet der Nutzer evtl.
  einen alten Stand.

## iOS / watchOS (`ios/`)

**Nur auf einem Mac baubar** (Xcode 15+, Apple Silicon empfohlen).

```bash
brew install xcodegen
cd ios
xcodegen generate          # erzeugt WolManager.xcodeproj aus project.yml
open WolManager.xcodeproj   # Signing-Team setzen → ▶
```

- Das mitgeführte `.xcodeproj` geht auch direkt; nach Swift-Datei-Neuanlagen aber
  besser XcodeGen neu generieren lassen (oder Datei manuell in `project.pbxproj`
  eintragen).
- Tests: `xcodebuild -scheme WolManager -destination 'platform=iOS Simulator,name=iPhone 15' test`
- Watch-App: eigenes Schema `WolManagerWatch` (watchOS 10+).
- Device-Build: Gratis-Apple-ID reicht für das eigene Gerät (Team + Bundle-ID
  `de.wolmanager`, „Trust" auf dem Gerät).
- Details und Plattform-Hinweise: [ios/README.md](ios/README.md).

---

## Versionieren (alle Plattformen)

```bash
python update_version.py <x.y.z>   # syncpt wol_app/__init__.py + Specs/Doku
```

Danach je Plattform neu bauen: Android zusätzlich `versionCode` in
`build.gradle.kts`++, iOS `MARKETING_VERSION` via `project.yml`/`Info.plist`/`pbxproj`.

## Schnell-Referenz

| Plattform | Befehl | Ergebnis | Toolchain |
|---|---|---|---|
| Windows | `.\build.ps1` | Setup-EXE + Service | PyInstaller + Inno Setup 6 |
| Ubuntu | `./packaging/build_deb.sh` | `.deb` | dpkg-deb (kein root) |
| macOS | `./packaging/macos/build_macos.sh` | `.app` + `.dmg` | PyInstaller, unsigned |
| Android | `.\build_html.ps1` | Debug-APK | JDK 21 + Gradle 8.7 + SDK |
| iOS/watchOS | Xcode auf dem Mac | `.app` | Xcode 15+ / XcodeGen |
