# Wake-on-LAN Manager — Android-App

Native Android-Version (Kotlin + Jetpack Compose) des WOL Managers, 1:1 umgesetzt
nach dem Prototyp `design_prototype/Android_50.html`.

## Funktionsumfang (v2.3.0)

| Bereich | Funktion |
|---|---|
| **Geräte** | Kachel-/Listenansicht, Suche, Sortierung (Name/IP/MAC/Status), Wake (Magic Packet), Shutdown (Host Service), Status-Ping, Long-Press-Menü, „Alle starten" |
| **Verwalten** | Geräte-CRUD, Duplikat-Prüfung (MAC), Netzwerk-Scan als TCP-Port-Sweep über alle aktiven /24-Netze, Ergebnisse direkt hinzufügen |
| **Zeitplan** | Wake/Shutdown pro Wochentag + Uhrzeit; Ausführung durch In-App-Ticker (5 s) **und** WorkManager (15-min-Periode mit 20-min-Nachholfenster) |
| **Protokolle** | Level-Filter, Suche, CSV-Export (Semikolon, UTF-8 BOM — wie Windows-App), Leeren |
| **Einstellungen** | Broadcast-IP/Port, Sprache (System/de/en/fr/es), Anzeigemodus (Auto/Hell/Dunkel), Auto-Update, Prüfintervall, Max-Logs, Standard-Methode; Über-Leiste mit Update-Check (GitHub) und Changelog-Link |
| **Dashboard** | Live-Metriken (CPU/RAM/GPU/VRAM) als Gauge-Ringe mit Sparklines, Prozess-Beobachtung (llama.cpp-Erkennung), Batch-Editor + Konsole, Uptime |

### Plattformbedingte Einschränkungen

- **Remote Desktop**: auf Android nicht verfügbar → deaktivierte Kacheln, Hinweis-Toast.
- **Netzwerk-Scan**: ohne Root kein ICMP/ARP — stattdessen TCP-Sweep (Port 8765 u. a.); MAC-Adressen bleiben leer.
- **SMB-Shutdown**: nicht verfügbar → Hinweis; Host-Service-Shutdown funktioniert voll.
- **Schedules**: While-alive-Garantie nur über WorkManager mit ±15-min-Genauigkeit; exakte Minute nur, solange die App geöffnet ist (Ticker).

## Daten & Kompatibilität

- `devices.json` im App-internen Speicher bleibt ein **JSON-ARRAY im Windows-Format**
  (Name, MAC, IP, Benutzer, `allow_batch`, `shutdown_method`, `watch_processes`, Batches).
- **Passwörter** werden niemals in `devices.json` geschrieben — sie liegen verschlüsselt
  in `EncryptedSharedPreferences` (Fallback: app-interne Klartextdatei, falls KeyStore versagt).
- Host-Service-Protokoll **v4** (TCP 8765, eine JSON-Zeile pro Request/Response):
  `status`, `metrics` (+`watch`), `shutdown`, `reboot`, `run_batch`.

## Build

Voraussetzungen: JDK 21, Android SDK 34, Gradle 8.7 (kein Wrapper im Repo).

```powershell
$env:JAVA_HOME = 'C:\Program Files\Android\openjdk\jdk-21.0.8'
Set-Location C:\Python\WOL\android
C:\tools\gradle-8.7\bin\gradle.bat :app:assembleDebug --no-daemon --console=plain
```

Ergebnis: `android/app/build/outputs/apk/debug/app-debug.apk`
(veröffentlicht als `dist_onefile/wolmanager-android-2.3.0-debug.apk`).

Unit-Tests (34 Stück: MagicPacket, Validierung, Schedule-Engine, CSV, Repo,
Host-Service-Protokoll, Versionsvergleich):

```powershell
C:\tools\gradle-8.7\bin\gradle.bat :app:testDebugUnitTest --no-daemon --console=plain
```

## Installation

1. APK auf das Gerät kopieren (Download, USB oder `adb install -r wolmanager-android-2.3.0-debug.apk`).
2. „Installation aus unbekannten Quellen" erlauben.
3. Berechtigungen: Internet/Lokales Netzwerk (automatisch); Multicast wird intern per `MulticastLock` geholt.

> Hinweis: Die App ist **debug-signiert**. Für eine Release-Version Signierung in
> `android/app/build.gradle.kts` (`signingConfigs`) einrichten und `:app:assembleRelease` bauen.

## Projektstruktur

```
android/
  app/src/main/java/de/wolmanager/
    WolApplication.kt        AppContainer, Ticker, Wake/Shutdown/Status
    MainActivity.kt          Locale-Wrapper, Theme, Entry Point
    data/                    Models, Repo (JSON), SecureStore
    net/                     MagicPacket, HostServiceClient (v4), NetworkScanner
    sched/                   ScheduleEngine, ScheduleWorker (WorkManager)
    ui/                      App/BottomBar, common/, devices/, manage/,
                             schedule/, logs/, settings/, dashboard/
    util/                    Validation, Csv, LocaleUtil, QuickSettings
  app/src/main/res/          strings (de/en/fr/es), themes, launcher-Icon
  app/src/test/java/         Unit-Tests
```
