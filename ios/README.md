# Wake-on-LAN Manager — iOS (Swift + WKWebView)

Native iOS-App (Swift, UIKit) mit dem Web-Frontend aus `WebApp/` in einer
`WKWebView` — gleiche Architektur wie `android_html/`, identische
Funktionalität wie die Windows- und Android-App (Protokoll v4).

Frontend-Referenz: `../design_prototype/iOS_50.html`

## Aufbau

```
ios/
├── project.yml                 # XcodeGen-Konfiguration (bevorzugt)
├── WolManager.xcodeproj        # Mitgeführtes Fallback-Projekt
├── WebApp/                     # HTML/CSS/JS-Frontend (in den Bundle kopiert)
│   ├── index.html
│   ├── app.css                 # iOS-Optik (Dark/Light, Safe-Area, SF-Fonts)
│   ├── app.js
│   └── bridge.js               # JS-Bridge (window.Android → native)
├── WolManager/                 # Swift-Quellen
│   ├── AppDelegate.swift / SceneDelegate.swift
│   ├── AppContainer.swift      # Services + Scheduler-Ticker
│   ├── Info.plist
│   ├── Assets.xcassets         # AppIcon (1024), AccentColor, LaunchBackground
│   ├── Model/                  # Models, Repo (JSON-Dateien), SecureStore (Keychain)
│   ├── Net/                    # MagicPacket, HostServiceClient (TCP 8765), NetworkScanner, Ipv4Resolver
│   ├── Sched/                  # ScheduleEngine + BGAppRefreshTask
│   ├── Util/                   # Validation, Csv, UpdateCheck, Haptics, RemoteDesktop
│   └── WebView/                # Bridge (27 Methoden), WebViewController, DocumentPicker
└── WolManagerTests/            # XCTest-Suite (8 Klassen)
```

## Build auf dem Mac (Apple Silicon)

Voraussetzungen: macOS mit **Xcode 15+** (iOS-Simulator 16+), optional Homebrew.

### Variante A — XcodeGen (bevorzugt, Projekt aus `project.yml`)

```bash
brew install xcodegen
cd ios
xcodegen generate
open WolManager.xcodeproj
```

Dann in Xcode: Target *WolManager* → *Signing & Capabilities* → eigenes
Team wählen → ▶ (iPhone 15 Simulator).

### Variante B — mitgeführtes `.xcodeproj` direkt öffnen

```bash
cd ios
open WolManager.xcodeproj
```

Das Projekt ist bereits checkt; nur das Signing-Team eintragen.

### Tests

```bash
cd ios
xcodebuild -scheme WolManager -destination 'platform=iOS Simulator,name=iPhone 15' test
```

### Device-Build (Gratis-Apple-ID reicht zum Testen auf dem eigenen iPhone)

Gerät anschließen, in Xcode Team + Bundle-ID `de.wolmanager` setzen,
„Trust" auf dem Gerät bestätigen, ▶ drücken.

## Berechtigungen / Hinweise

- **Lokales Netzwerk**: Beim ersten Wake/Scan/Status fragt iOS
  „Standortfreigabe für das lokale Netzwerk" — zwingend *Erlauben*,
  sonst scheitern WOL, Scan und Host-Service (iOS 14+).
- **Ping**: iOS erlaubt kein ICMP — die Ping-Funktion mißt die
  TCP-Verbindungszeit zu Port 8765 (oder Geräte-Port). Der Ping meldet jetzt
  differenziert, ob die DNS-Auflösung des Host-Namens fehlschlug oder der
  Port nicht erreichbar ist (statt nur „Ziel nicht erreichbar").
- **Host-Name statt IP**: Wie Android löst `Ipv4Resolver.swift` Namen gezielt
  zu **allen** IPv4-A-Records auf, und `HostServiceClient.connectIpv4` probiert
  jeden Kandidaten mit frischem Socket (Status + Ping). Damit werden Geräte mit
  Dual-Stack (AAAA) oder Mehrfach-/veralteten A-Records (z. B.
  `blade-18.fritz.box`) nicht mehr fälschlich als offline angezeigt.
- **Remote-Desktop** (2.3.3): Öffnet die **Windows App** (ehem. Microsoft
  Remote Desktop) per URI – Kandidaten: `rdp://full%20address=s:…&username=s:…`
  (Legacy, für iOS dokumentiert) und `ms-rd://add/host/…?username=…`
  (Schemata in `LSApplicationQueriesSchemes`). Host = IP/Hostname, sonst
  Gerätename; der Benutzer wird vorbefüllt. Kein Schema überträgt Passwörter
  → das Passwort wird in die **Zwischenablage** kopiert und die Web-UI zeigt
  einen Hinweis-Toast. Das beim Verbinden entstehende Profil bleibt auf dem
  Gerät bestehen (gewollt – kein Löschen wie unter Windows). Fehler:
  `remote.notinstalled` / `remote.nohost`.
- **Dashboard-Wischen**: Im Dashboard wechselt ein Wisch nach links/rechts zum
  nächsten/vorherigen Gerät – in genau der Reihenfolge, die gerade im
  Gerätemanager sortiert ist (zyklisch, Anzeige `Position/Gesamt` neben dem
  Titel). Kurzer Haptik-Impuls bei Wechsel; vertikales Scrollen bleibt erhalten.
- **Passwörter** liegen im Keychain
  (`kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly`), `devices.json`
  bleibt frei von Klartext — wie auf Android.
- **Hintergrund**: Zeitpläne laufen best-effort weiter (Timer bei aktiver
  App + `BGAppRefreshTask` `de.wolmanager.schedule-refresh` mit 20-Minuten-
  Nachhol-Fenster). iOS kann Hintergrund-Timer jederzeit pausieren —
  Wecker funktionieren zuverlässig, wenn die App regelmäßig geöffnet wird.
- **Datenformat**: identisch zur Windows-App (`devices.json` als Array,
  snake_case-Felder); Export/Import über den iOS-Datei-Picker.

## Bridge-Vertrag (JS ↔ Swift)

Identisch zu `android_html/`: `window.Android.call(callId, method, paramsJson)`
→ `window.__nativeResult(callId, {ok, data|error})`, Events via
`window.__nativeEvent({type, ...})`. iOS ergänzt `remote {id, mode}` →
`{ok, host, username, passwordCopied, hasPassword}` (Fehler
`remote.notinstalled` / `remote.nohost`). Details: `WolManager/WebView/Bridge.swift`,
`WolManager/Util/RemoteDesktop.swift`.
