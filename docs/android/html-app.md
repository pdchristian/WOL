# Wake-on-LAN Manager – HTML-App für Android (`android_html/`)

Eigenständige Android-Variante als **WebView-Shell**: Die komplette UI ist HTML/CSS/JS
(abgeleitet vom Prototyp `design_prototype/Android_50.html`) und wird von einer dünnen
Kotlin-Schicht mit nativen Fähigkeiten versorgt. (Eine frühere native Compose-Variante
unter `android/` wurde mit 2.3.1 entfernt; diese App ist die Android-Version.)

## Build

Voraussetzungen (wie in `build_html.ps1` hinterlegt):

- JDK 21: `C:\Program Files\Android\openjdk\jdk-21.0.8`
- Gradle 8.7: `C:\tools\gradle-8.7\bin\gradle.bat` (kein Wrapper)
- Android SDK: `C:\Users\cp\AppData\Local\Android\Sdk` (in `local.properties`)

```powershell
# APK bauen (-> dist_onefile\wolmanager-android-html-<version>-debug.apk)
.\build_html.ps1

# inklusive Unit-Tests
.\build_html.ps1 -Tests
```

Installation auf dem Gerät: APK kopieren und öffnen (Debug-Signatur), z. B.
`adb install -r dist_onefile\wolmanager-android-html-2.3.3-debug.apk`.

Wichtige Parameter: `applicationId de.wolmanager.html`, `versionName 2.3.3`,
minSdk 26, compileSdk 34, AGP 8.5.2, Kotlin 2.0.21 – **kein Compose**.

## Architektur

```
WebViewActivity (ComponentActivity, fullscreen, edge-to-edge)
 └── WebView  →  file:///android_asset/app/index.html
      ├── bridge.js   – JS-Fassade window.Native (real / Browser-Demo-Stub)
      ├── app.css     – Stil aus Android_50.html, ohne Phone-Frame
      └── app.js      – komplette UI (I18N de/en/fr/es, Screens, Sheets)
 └── Bridge ("Android")  – @JavascriptInterface, JSON camelCase
      ├── AppContainer (WolApplication): Repo, SecureStore, HostServiceClient,
      │   NetworkScanner, ScheduleEngine/Worker (WorkManager), MagicPacket
      └── SAF: CreateDocument/OpenDocument für Geräte-Import/-Export und CSV
```

### Bridge-Protokoll (JS ↔ Kotlin)

- Aufruf: `Android.call(callId, method, paramsJson)` → Antwort asynchron über
  `window.__nativeResult(callId, {ok:true,data}|{ok:false,error})`.
- Events (Streaming): `window.__nativeEvent({type, …})` mit Typen
  `scan-progress`, `scan-found`, `scan-done`, `wake-result`, `wake-all-done`,
  `status`, `status-done`, `exported`, `imported`.
- `Android.setSheetOpen(bool)` –Native meldt offenes Bottom-Sheet; die
  Zurück-Taste schließt zuerst das Sheet (`WebViewActivity.onBackPressed`).

Methoden: `snapshot`, `info`, `saveDevice`, `deleteDevice`, `getPassword`,
`saveSchedule`, `deleteSchedule`, `saveSettings`, `resetSettings`, `clearLogs`,
`log`, `wake`, `shutdown`, `status`, `ping`, `metrics`, `runBatch`,
`scanIfaces`, `scanStart`, `scanStop`, `wakeAll`, `refreshStatus`,
`exportDevices`, `exportCsv`, `importDevices`, `updateCheck`, `vibrate`,
`remote`.

`remote({id, mode})` öffnet die installierte **Windows App** (früher „Microsoft
Remote Desktop“, `com.microsoft.rdc.androidx`) per `rdp://`-URI mit vorgefertigtem
Profil (Rechner = IP/Hostname, Fallback Gerätename; Benutzer = Geräte-Benutzer).
Das Profil bleibt in der Windows App bestehen (kein Löschen wie unter Windows).
Das Android-URI-Schema kann **kein Passwort** übertragen (kein Attribut dafür, kein
Zugang zum Credential Manager) — die Bridge legt das Geräte-Passwort deshalb in die
Zwischenablage und die UI weist per Toast darauf hin, damit es im Verbindungsfenster
eingefügt wird. Fehler: `remote.notinstalled` (keine App), `remote.nohost`
(keine Adresse). URI-Bau/Kodierung: `util/RemoteDesktop.kt` (JVM-testbar).

### Entwicklung im Browser (ohne Gerät)

`app/src/main/assets/app/index.html` direkt im Desktop-Browser öffnen. Ohne
`window.Android` schaltet `bridge.js` automatisch auf einen Demo-Stub mit
Prototyp-Daten (Fractal/A4-H20/A4-TV, simulierte Metriken/Scans) um.
Syntax-Check: `node --check app.js && node --check bridge.js`.

## Unterschiede zur nativen Compose-Variante / Windows-App

- **Entfernt:** Einstellungsfelder „Auflösung“ und „Design (Klassisch/Moderne)“,
  Shutdown-Methode SMB (nur Host Service v4), Statusbar-Uhr/Phone-Rahmen.
- **Remote-Desktop:** öffnet die Windows App per `rdp://`-URI mit vorausgefülltem
  Profil (Rechner + Benutzer); das Passwort liegt danach in der Zwischenablage
  (URI-Schema kann es nicht übertragen). Profil bleibt bestehen. Siehe
  `remote`-Methode oben.
- **Netzwerk-Scan:** TCP-Sweep (Ports 8765, 445, 135, 80, 443, 22). Ab 2.3.4 nur
  über die **tatsächliche Verbindung**: WLAN-Transport (plus VPN-Tunnel), Mobilfunk
  aus; Bereichsfilter blendet `169.*` (APIPA) und komplett `172.*`
  (Virtualisierungs-/VPN-Adapter) aus — Parität zur Desktop-App
  (`is_real_interface`). Die Netzliste wird beim Öffnen des Verwalten-Tabs
  geladen (sichtbar **vor** „Scan starten“); `scanStart` erhält die UI-Auswahl
  (`{ifaces:[{name,ip,prefix,dns}]}`) und scannt exakt diese. Ohne WLAN: Hinweis
  „Kein WLAN-Netzwerk gefunden“ + deaktivierter Button. Android liefert keine
  MAC-Adressen → gefundene Geräte werden mit Platzhalter-MAC
  `00:00:00:00:00:00` in den Dialog übernommen.
- **Dashboard:** echte Host-Service-v4-Metriken (CPU/RAM/GPU/VRAM, überwachte
  Prozesse mit PID/API-Port, Modell-Badges) im eingestellten Intervall.
  Wischen nach links/rechts wechselt zum nächsten/vorherigen Gerät – in
  genau der Reihenfolge, die gerade im Gerätemanager sortiert ist
  (`sortDevices()`; Anzeige `Position/Gesamt` neben dem Titel, zyklisch).

## Windows-Kompatibilität der Geräte-Dateien

- `devices.json` im App-Speicher ist ein **JSON-Array** im Windows-Format
  (`name, mac, ip, username, enabled, batches, allow_batch, watch_processes`).
- Passwörter liegen in `EncryptedSharedPreferences` (`pw_<id>`), nie in `devices.json`.
- **Export** (SAF): JSON-Array mit **Klartext-Passwörtern** – der Windows-Import
  (`wol_app/device_io.py`) liest Klartext und DPAPI. Überwachte Prozesse
  (`watch_processes`) werden mit exportiert (leere Liste entfällt).
- **Import:** JSON-Array; matching per Name (Update) sonst Neuanlage; ungültige
  MACs werden übersprungen; DPAPI-verschlüsselte Passwörter (Base64 ≥ 13 Bytes)
  können auf Android nicht entschlüsselt werden und werden geleert;
  `watch_processes` werden übernommen (fehlender Schlüssel = bestehende behalten).

## Bekannte Fallstricke

- `MulticastLock.acquire()` muss **ohne Argument** aufgerufen werden.
- `File.renameTo()` überschreibt nicht – temporäre Datei vorher löschen (Repo-Atomarwrite).
- Dashboard-Tick rendert DOM neu → Event-Delegation nur über
  `[data-act]`/`[data-id]`-Selektoren, nie über gespeicherte Knotenreferenzen.
- `kotlinx.serialization`: `intOrNull`/`booleanOrNull` sind **Properties**, keine Funktionen.
- `Bridge` hat ein Property `host: BridgeHost`. Eine lokale `val host` im selben
  Scope **überschattet** es → `host.openExternal(...)` schlägt fehl (Unresolved).
  Lokale Host-Variable deshalb `rdpHost` nennen.
- Theme-Umschaltung wirkt auf `document.documentElement` (`html[data-theme=…]`),
  nicht mehr auf `#phone`.
