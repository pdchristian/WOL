# Wake-on-LAN Manager – Bedienungsanleitung

## Inhaltsverzeichnis
1. [Installation](#installation)
2. [Deinstallation](#deinstallation)
3. [Start der Anwendung](#start-der-anwendung)
4. [Die moderne Benutzeroberfläche](#die-moderne-benutzeroberfläche)
5. [Geräte verwalten](#geräte-verwalten)
6. [Wake-on-LAN senden](#wake-on-lan-senden)
7. [Status prüfen](#status-prüfen)
8. [Remote Shutdown](#remote-shutdown)
9. [Herunterfahren mit Host-Service](#herunterfahren-mit-host-service)
10. [Remote Desktop](#remote-desktop)
11. [Geräte-Dashboard (Performance & Batches)](#geräte-dashboard-performance--batches)
12. [Zeitpläne erstellen](#zeitpläne-erstellen)
13. [Netzwerkeinstellungen](#netzwerkeinstellungen)
14. [Protokoll anzeigen](#protokoll-anzeigen)
15. [Passwort-Verschlüsselung](#passwort-verschlüsselung)
16. [Tastenkürzel](#tastenkürzel)
17. [Häufige Fragen](#häufige-fragen)
18. [Systemanforderungen](#systemanforderungen)

---

## Installation

### Mit dem Installer (empfohlen)
1. Die Datei `Wake-on-LAN Manager Installer.exe` herunterladen.
2. Doppelklicken Sie auf die Datei – der Installer fordert automatisch Administratorrechte an (UAC-Abfrage).
3. Der Installer führt folgende Schritte durch:
   - Kopiert die Anwendung nach `C:\Program Files\WakeOnLAN`
   - Erstellt einen Startmenü-Eintrag unter **Wake-on-LAN Manager**
   - Erstellt eine Desktop-Verknüpfung
   - Registriert die Anwendung in der Windows-Programmliste (Deinstallationsprogramme)
4. Bei einer **Neuinstallation** werden Sie gefragt, ob vorhandene Geräteeinträge und Einstellungen behalten oder gelöscht werden sollen.
5. Der Installer fragt, ob der **WOL Host Service** mitinstalliert werden soll (Standard: **Ja**). Dieser Dienst erlaubt es anderen Wake-on-LAN-Manager-Instanzen (Windows oder Android), diesen PC remote herunterzufahren.

### Aus dem Quellcode starten
1. Python 3.10+ installieren.
2. Abhängigkeiten installieren: `pip install -r requirements.txt`
3. App starten: `python run.py`

---

## Deinstallation

### Über das Startmenü
1. Öffnen Sie das Windows-Startmenü.
2. Navigieren Sie zu **Wake-on-LAN Manager → Uninstall Wake-on-LAN Manager**.
3. Bestätigen Sie die Deinstallation.

### Über die Windows-Programmliste
1. Öffnen Sie **Einstellungen → Apps → Installierte Apps** (oder *Systemsteuerung → Programme deinstallieren*).
2. Suchen Sie **Wake-on-LAN Manager** und klicken Sie auf **Deinstallieren**.
3. Bestätigen Sie die Abfrage – alle Dateien, Verknüpfungen und Registrierungseinträge werden entfernt.

> **Hinweis:** Bei der Deinstallation werden auch alle Geräteeinträge und Einstellungen gelöscht. Der Uninstaller fragt zusätzlich, ob der **WOL Host Service** entfernt werden soll (Standard: **Ja**).

---

## Start der Anwendung

Starten Sie die Anwendung über:
- Die **Desktop-Verknüpfung** (Doppelklick)
- Das **Windows-Startmenü** → *Wake-on-LAN Manager*

> **Ab Version 2.0.0** gibt es zwei Oberflächen – die **moderne** (Standard) und die **klassische** Ansicht. Welche beim Start geladen wird, haben Sie beim Installieren gewählt oder können Sie in den **Einstellungen → Design** ändern (Details im [nächsten Kapitel](#die-moderne-benutzeroberfläche)). Beide bieten identische Funktionen.

**Klassische Ansicht – Hauptbestandteile:**
- **Menüleiste** oben (Datei, Tools, Hilfe)
- **Aktionen-Schaltflächen** (Alle Geräte wecken, Status aktualisieren)
- **Gerätetabelle** mit Name, MAC-Adresse, IP und Status
- **Statusleiste** unten mit aktuellen Meldungen

---

## Die moderne Benutzeroberfläche

Mit **Version 2.2.0** ist ein neues, modernes App-Design (**"Dark Control Center"**) hinzugekommen: Statt der klassischen Fensteransicht mit Menüleiste und Tabelle führt die moderne Oberfläche eine **Seitenleiste (Sidebar)** mit **vier nativen Bereichen** und zwei nativen App-Bildschirmen ein. **Version 2.1.0** ergänzt das **Geräte-Dashboard** mit Live-Performance-Werten (CPU/RAM/GPU/VRAM) und entfernter Batch-Ausführung. **Version 2.2.0** fügt dem Dashboard die **Prozess-Überwachung** hinzu: benannte Prozesse (z. B. `llama-server.exe`) werden auf dem Zielsystem beobachtet und als Live-Status-Chips mit Details (PID, Uptime, RAM/CPU, API-Port, geladenes llama.cpp-Modell) angezeigt – konfigurierbar direkt im Geräte-Dialog (Details im Kapitel [Geräte-Dashboard](#geräte-dashboard-performance--batches)).

> **Wichtig:** Die moderne und die klassische Oberfläche bieten **exakt dieselben Funktionen** – sie unterscheiden sich nur im Layout. Alle Einstellungen, Geräte, Zeitpläne, Protokolle und Sicherheitsfunktionen sind identisch. Sie können jederzeit zwischen beiden wechseln.

### Das App-Design wählen

- **Beim Installieren:** Der Installer fragt nach dem gewünschten Design – **Moderne App** (dunkles Control-Center-Layout mit Seitenleiste) oder **Klassische App** (traditionelles Fenster-Layout).
- **Jederzeit in der App:** Unter **Einstellungen → Design** (klassisch: **Tools → Einstellungen...**, modern: Bildschirm **Einstellungen**) können Sie zwischen **Klassische App** und **Moderne App** wechseln.
  > **Hinweis:** Eine Änderung des Designs erfordert einen **Neustart der App**.

### Anzeige-Modus (dunkel / hell / automatisch)
Im selben Bereich **Design/Anzeige** wählen Sie den **Anzeige-Modus**:
- **Automatisch** – folgt dem Windows-Systemthema
- **Hell** – helles Design
- **Dunkel** – dunkles Design

Der gewählte Modus wird von **beiden** Layouts (modern und klassisch) respektiert.

### Aufbau der modernen Oberfläche

Die moderne Oberfläche besteht aus zwei Teilen:

**1. Seitenleiste (links)** mit zwei Abschnitten:

| Abschnitt | Einträge |
|-----------|----------|
| **Bereiche** | 💻 **Geräte** · 🔧 **Verwalten** · 🕒 **Zeitplan** · 📋 **Protokolle** |
| **Applikation** | ⚙ **Einstellungen** · ℹ **Über** · ⏻ (App beenden) |

**2. Arbeitsbereich (rechts)** – je nach gewähltem Eintrag wird der passende Bildschirm angezeigt:

| Bildschirm | Inhalt |
|------------|--------|
| **💻 Geräte** | Alle Geräte mit Live-Status, wahlweise als **Kacheln** oder **Geräteliste** (Umschalter links oben), mit Sortier-Drop-down und Suchfeld |
| **🔧 Verwalten** | **Geräte-Verwaltung** (Hinzufügen, Bearbeiten, Löschen, Import/Export, Suchen) und **Netzwerk-Scan** |
| **🕒 Zeitplan** | Zeitpläne für automatisches Aufwecken/Herunterfahren (mit Live-Suche) |
| **📋 Protokolle** | Alle Ereignisse der App (mit Suchfeld, Level-Filter und CSV-Export) |
| **⚙ Einstellungen** | Alle App- und Netzwerkeinstellungen (natives Bildschirm statt Dialog) |
| **ℹ Über** | Versionsinfo, **Nach Updates suchen** und **Changelog** |
| **📊 Geräte-Dashboard** | Live-Performance (CPU/RAM/GPU/VRAM) und Batch-Ausführung für ein einzelnes Gerät – wird nur über das 📊-Symbol in der Geräteansicht geöffnet (kein Seitenleisten-Eintrag) |

### Die Geräteansicht (Bereiche → Geräte)
Der Bildschirm **Geräte** zeigt alle Geräte in **zwei Ansichten**, die Sie über das **Umschalt-Icon links oben** in der Symbolleiste wechseln können:

- **Kachelansicht** (Standard) – Icon mit **drei horizontalen Linien** → wechselt zur Listenansicht
- **Listenansicht** – Icon mit **vier Kacheln** → wechselt zurück zur Kachelansicht

Die zuletzt gewählte Ansicht wird **gespeichert** und beim nächsten Start wiederhergestellt.

#### Kachelansicht
Jedes Gerät wird als **Karte** dargestellt:
- **Name** mit **Status-Punkt** (🟢 online / 🔴 offline / 🟡 unbekannt)
- **IP- und MAC-Adresse**
- **Remote-Desktop-Kacheln** (🖥️ Vollbild / 🪟 Fenster) und **📊 Dashboard** (öffnet das [Geräte-Dashboard](#geräte-dashboard-performance--batches))
- **Aktions-Button:**
  - Gerät **offline/unbekannt** → **Aufwecken** (sendet das Wake-on-LAN-Signal)
  - Gerät **online** → **Herunterfahren** (Remote-Shutdown)

#### Listenansicht
Jedes Gerät wird als **Zeile** dargestellt:
- **Status-Punkt** (🟢 online / 🔴 offline / 🟡 unbekannt)
- **Name** sowie **IP- und MAC-Adresse** in einer Mono-Zeile darunter
- **Drei Aktions-Icons rechts:**
  - 🖥️ **Remote Vollbild** – startet die Remote-Desktop-Sitzung im Vollbild
  - 🪟 **Remote Fenster** – startet die Remote-Desktop-Sitzung im Fenster
  - ✏️ **Bearbeiten** – öffnet den Geräte-Dialog (alternativ **Doppelklick** auf die Zeile)

#### Sortierung und Suche
Links neben dem Suchfeld befindet sich ein **Sortier-Drop-down** mit folgenden Optionen:

| Sortierung | Reihenfolge |
|------------|-------------|
| **Namen** | alphabetisch (A–Z) |
| **IP-Adresse** | numerisch (z. B. 192.168.2.9 vor 192.168.2.50) |
| **MAC-Adresse** | aufsteigend |
| **Status** | **Online → Offline → Unbekannt** (bei Gleichstand alphabetisch nach Name) |

Die gewählte Sortierung wird **gespeichert** und gilt für **beide Ansichten**. Über das Suchfeld können Sie die Geräte zusätzlich **live filtern** (nach Name, MAC, IP oder Benutzername). Die Status-Punkte werden **alle 30 Sekunden automatisch** aktualisiert — bei Sortierung nach **Status** sortiert sich die Liste nach jedem Update neu.

> **Tipp:** Die Bereiche *Verwalten*, *Zeitplan*, *Protokolle*, *Einstellungen* und *Über* sind in der modernen Oberfläche **eigene Bildschirme** (keine Dialoge mehr). Die klassischen Menüs (Datei, Tools, Hilfe) existieren in der modernen Oberfläche nicht – alle Funktionen sind über die Seitenleiste erreichbar.

---

## Geräte verwalten

> **Moderne Oberfläche:** In der modernen Ansicht finden Sie die Geräte-Verwaltung unter **Bereiche → Verwalten** (statt über das Menü *Datei → Geräte verwalten...*). Dort können Sie Geräte hinzufügen, bearbeiten, löschen, importieren/exportieren und mit Suchfeld filtern – zusätzlich ist der **Netzwerk-Scan** direkt auf demselben Bildschirm integriert.

### Geräte suchen
Über dem Suchfeld der Gerätetabelle (im Hauptfenster und im Geräte-Manager) können Sie die Liste **live filtern**. Geben Sie einen Begriff ein – die Tabelle zeigt nur noch Geräte, deren **Name**, **MAC-Adresse**, **IP-Adresse** oder **Benutzername** den Suchbegriff enthält. Ein leeres Feld zeigt wieder alle Geräte.

### Gerät hinzufügen
1. Menü: **Datei → Geräte verwalten...** (oder `Strg+D`)
2. Klicken Sie auf **+ Gerät hinzufügen**.
3. Geben Sie folgende Daten ein:
   - **Gerätename:** Ein sprechender Name (z. B. "Büro-PC", "Gaming-Rig")
   - **MAC-Adresse:** Die MAC-Adresse des Zielsystems (Format: `AA:BB:CC:DD:EE:FF`)
   - **IP-Adresse / Hostname:** Optional, für Status-Prüfung per Ping. Neben IPv4-Adressen sind auch Hostnamen erlaubt (z. B. `ubuntu-mercury` oder `nas01.lan`) – nützlich für Geräte mit wechselnder DHCP-Adresse und für Linux-/xrdp-Rechner, die per Namen erreichbar sein müssen
   - **Nutzer:** Optional, Benutzername für Remote-Shutdown (z. B. `Administrator` oder `Benutzername`)
   - **Passwort:** Optional, Passwort für Remote-Shutdown (wird verschlüsselt gespeichert)
4. Klicken Sie auf **Speichern**.

### Gerät bearbeiten
1. Menü: **Datei → Geräte verwalten...**
2. Wählen Sie das Gerät in der Tabelle aus.
3. Klicken Sie auf **Bearbeiten**.
4. Ändern Sie die gewünschten Felder und klicken Sie auf **Aktualisieren**.

### Gerät löschen
1. Menü: **Datei → Geräte verwalten...**
2. Wählen Sie das Gerät aus und klicken Sie auf **Löschen**.
3. Bestätigen Sie die Abfrage.

---

## Wake-on-LAN senden

### Einzelnes Gerät wecken
1. Wählen Sie ein Gerät in der Tabelle aus.
2. Klicken Sie auf **Ausgewähltes Gerät wecken**.
3. Ein Magic Packet wird an die MAC-Adresse gesendet.

### Alle Geräte wecken
1. Klicken Sie oben auf **Alle Geräte wecken**.
2. Bestätigen Sie die Abfrage.
3. Alle aktivierten Geräte erhalten ein Wake-on-LAN-Signal.

> **Voraussetzung:** Wake-on-LAN muss im BIOS/UEFI und in den Netzwerkeinstellungen des Zielsystems aktiviert sein.

### Kontextmenü (Rechtsklick)
Ein Rechtsklick auf ein Gerät in der Tabelle öffnet ein Kontextmenü mit weiteren Aktionen:
- **Remote Fullscreen** – startet eine Remote-Desktop-Sitzung im Vollbild
- **Remote Window** – startet eine Remote-Desktop-Sitzung in einem Fenster (mit der in den Einstellungen gewählten Auflösung)
- **Herunterfahren** – fährt das Gerät remote herunter
- **Status aktualisieren** / **Ping** – prüft den Gerätestatus

---

## Status prüfen

### Manuelles Aktualisieren
Klicken Sie auf **Status aktualisieren**. Die App pingt alle konfigurierten IPs und aktualisiert die Spalte "Status":
- 🟢 **Online** – Gerät antwortet auf Ping
- 🔴 **Offline** – Gerät antwortet nicht (aus oder im Ruhezustand)
- 🟡 **Unbekannt** – Keine IP konfiguriert oder Fehler beim Prüfen

### Automatisches Aktualisieren
Der Status wird alle **30 Sekunden** automatisch aktualisiert.

### Einzelnes Gerät prüfen
1. Wählen Sie ein Gerät aus.
2. Klicken Sie auf **Ausgewähltes Gerät ping'en**.
3. Ein Dialog zeigt den aktuellen Status an.

---

## Remote Shutdown

Mit dieser Funktion können Sie ein konfiguriertes Gerät über das Netzwerk herunterfahren. Es gibt zwei Varianten: **Shutdown ohne Anmeldedaten** (für Systeme mit offenen Freigaben) und **Shutdown mit Benutzername und Passwort** (für Systeme mit geschützten Freigaben).

### Voraussetzungen am Zielsystem
Bevor Remote-Shutdown funktioniert, müssen folgende Einstellungen am **Zielsystem** vorgenommen werden:

1. **Registry-Eintrag hinzufügen:**
   ```
   [HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System]
     "LocalAccountTokenFilterPolicy"=dword:00000001
   ```
   > Dieser Eintrag ermöglicht den Zugriff auf lokale Administrator-Konten über das Netzwerk.

2. **Date- und Druckerfreigabe** muss aktiviert sein.
3. Eine **IP-Adresse** muss für das Gerät konfiguriert sein.
4. **Firewall-Einstellungen:** Stellen Sie sicher, dass der Zugriff auf **IPC$** (SMB, Port 445) nicht blockiert wird.

---

### Shutdown ohne Benutzername und Passwort
Falls das Zielsystem keine Authentifizierung für die Remote-Shutdown-Funktion erfordert (z. B. bei offenen Freigaben oder lokalen Konten mit Standardberechtigungen), gehen Sie wie folgt vor:

1. **Gerät auswählen:**
   Wählen Sie in der Hauptansicht das gewünschte Gerät aus der Tabelle aus.

2. **Shutdown auslösen:**
   Klicken Sie auf die Schaltfläche **Herunterfahren**.

3. **Bestätigen:**
   Ein Dialogfenster erscheint zur Bestätigung. Klicken Sie auf **Ja**, um den Shutdown-Befehl zu senden.

4. **Ausführung:**
   Die Anwendung sendet den Shutdown-Befehl über das Netzwerk an das Zielsystem. Das Gerät wird heruntergefahren.

> **Hinweis:** Diese Methode funktioniert nur, wenn das Zielsystem keine Authentifizierung für Remote-Befehle erfordert. Falls der Shutdown fehlschlägt, verwenden Sie die Methode **mit Benutzername und Passwort**.

---

### Shutdown mit Benutzername und Passwort
Falls das Zielsystem eine Authentifizierung erfordert (z. B. bei Domänen-Konten oder geschützten Freigaben), müssen Sie **Nutzername** und **Passwort** für das Gerät hinterlegen:

1. **Gerät konfigurieren:**
   - Öffnen Sie den Geräte-Manager (**Datei → Geräte verwalten...** oder `Strg+D`).
   - Wählen Sie das Gerät aus und klicken Sie auf **Bearbeiten**.
   - Tragen Sie im Feld **Nutzer** den Benutzernamen ein (z. B. `Administrator` oder `Domain\Benutzername`).
   - Tragen Sie im Feld **Passwort** das zugehörige Passwort ein.
     > **Sicherheit:** Das Passwort wird **automatisch verschlüsselt** gespeichert (siehe [Passwort-Verschlüsselung](#passwort-verschlüsselung)).
   - Klicken Sie auf **Aktualisieren**, um die Änderungen zu speichern.

2. **Shutdown auslösen:**
   - Wählen Sie das Gerät in der Hauptansicht aus.
   - Klicken Sie auf **Herunterfahren**.

3. **Verbindung herstellen:**
   Die Anwendung stellt eine Verbindung zum Zielsystem her, indem sie den Befehl `net use` verwendet, um eine Sitzung mit der Freigabe `IPC$` herzustellen. Dabei werden die hinterlegten Anmeldedaten verwendet.

4. **Shutdown-Befehl senden:**
   Nach erfolgreicher Authentifizierung wird der Shutdown-Befehl (`shutdown /s /t 0`) an das Zielsystem gesendet. Das Gerät wird sofort heruntergefahren.

> **Hinweis:**
> - Die Authentifizierung erfolgt über **Windows SMB (Server Message Block)**.
> - Falls die Verbindung fehlschlägt, prüfen Sie die **Berechtigungen** des Benutzers auf dem Zielsystem.
> - Das Passwort wird **verschlüsselt** gespeichert und ist nur auf dem aktuellen System lesbar.

---

## Herunterfahren mit Host-Service

Diese zweite Shutdown-Variante setzt einen kleinen Windows-Dienst (**WOL Host Service**) auf dem Zielsystem voraus. Der Dienst lauscht auf **TCP-Port 8765** und akzeptiert JSON-Befehle (`shutdown`, `reboot`, `status`). Die Authentifizierung erfolgt mit den **im Geräteeintrag hinterlegten Windows-Benutzerdaten** – es sind also keine offenen Freigaben oder Registry-Anpassungen am Zielsystem nötig.

> **Windows- und Android-Clients:** Mit dem **WOL Host Service** können sowohl **Windows-Clients** (diese Anwendung) als auch **Android-Clients** ([WOL-Android](https://github.com/pdchristian/WOL-Android)) Windows-PCs über das Netzwerk herunterfahren. Die Android-App spricht denselben Host-Service auf Port 8765 an.

### Voraussetzungen am Zielsystem
1. Der **WOL Host Service** muss installiert und gestartet sein (Auto-Start). Installation bequem über den Installer oder manuell:
   ```
   "C:\Program Files\WakeOnLAN\WOL Host Service.exe" --install
   ```
2. Die **Inbound-Firewall-Regel** für TCP-Port 8765 muss vorhanden sein (wird bei `--install` automatisch angelegt).
3. Eine **IP-Adresse** muss für das Gerät konfiguriert sein.
4. Für das Gerät müssen **Benutzername und Passwort** eines Kontos mit Shutdown-Berechtigung hinterlegt sein (z. B. `Administrator` oder `DOMAIN\Benutzer`).

### Shutdown-Methode pro Gerät wählen
1. Öffnen Sie den **Geräte-Manager** (**Datei → Geräte verwalten...** oder `Strg+D`).
2. Wählen Sie das Gerät aus und klicken Sie auf **Bearbeiten**.
3. Setzen Sie im Feld **Shutdown-Methode** den Wert **Host-Service (empfohlen)** oder **SMB (Windows-Freigabe)**.
4. Speichern Sie die Änderungen.

> **Standard-Methode:** In den Einstellungen (**Tools → Einstellungen... → Remote-Herunterfahren**) können Sie die Standard-Methode für **neue** Geräte festlegen. Der anfängliche Standard ist **Host-Service**. Bestehende Geräte (vor v1.7.0) behalten die bisherige SMB-Methode.

### Herunterfahren auslösen
1. Wählen Sie das Gerät in der Hauptansicht aus.
2. Klicken Sie auf **Herunterfahren** und bestätigen Sie den Dialog.
3. Die Anwendung sendet den JSON-Befehl an den Host-Service des Zielsystems. Das Gerät wird sofort heruntergefahren.

> **Hinweis:** Auch **geplante Shutdowns** (Zeitpläne) verwenden die pro Gerät gewählte Methode. Die **Android-App** ([WOL-Android](https://github.com/pdchristian/WOL-Android)) nutzt ausschließlich den Host-Service – so lassen sich auch von Android-Geräten aus Windows-PCs herunterfahren.

### Protokoll (Übersicht)
- **Anfrage:** `{"command": "shutdown", "username": "...", "password": "..."}` (eine Zeile)
- **Antwort:** `{"status": "ok", "message": "..."}` (eine Zeile)
- Der Dienst prüft die Anmeldedaten vor der Ausführung und bestätigt die Anfrage, bevor das System heruntergefahren wird.

### Bedienung des WOL Host Service
Der **WOL Host Service** kann über die Kommandozeile gesteuert werden. Führen Sie die folgenden Befehle **als Administrator** aus (Rechtsklick → „Als Administrator ausführen“):

| Befehl | Wirkung |
|--------|---------|
| `"WOL Host Service.exe" --install` | Dienst installieren (Auto-Start) + Firewall-Regel für TCP 8765 anlegen |
| `"WOL Host Service.exe" --start` | Dienst starten |
| `"WOL Host Service.exe" --stop` | Dienst stoppen |
| `"WOL Host Service.exe" --status` | Dienststatus anzeigen (`RUNNING`, `STOPPED`, ...) |
| `"WOL Host Service.exe" --uninstall` | Dienst entfernen (stoppt und löscht ihn) + Firewall-Regel entfernen |
| `"WOL Host Service.exe" --run` | Dienst im Vordergrund ausführen (nur zum Testen/Debuggen, ohne Dienstcontroller) |

**Beispiel (Installation, Start und Status):**
```
cd "C:\Program Files\WakeOnLAN"
"WOL Host Service.exe" --install
"WOL Host Service.exe" --start
"WOL Host Service.exe" --status
```

> **Hinweis:** `--run` startet den TCP-Server nur im Vordergrund und ist für kurze Tests gedacht. Für den Dauerbetrieb (auch nach einem Neustart) muss der Dienst über `--install` + `--start` als Windows-Dienst registriert werden.

### Dienst manuell entfernen (falls `--uninstall` nicht funktioniert)
In seltenen Fällen kann der Dienst einen defekten Zustand haben – z. B. wenn die registrierte Binärdatei (`ImagePath`) nicht mehr existiert. Dann schlagen `--uninstall` oder `--install` mit dem Fehler *„Das System kann die angegebene Datei nicht finden“* fehl. In diesem Fall kann der Dienst **manuell** mit dem Windows-Befehl `sc.exe` entfernt werden:

```
sc.exe delete WOLHostService
```

**Ablauf:**
1. **Als Administrator** eine Eingabeaufforderung oder PowerShell öffnen.
2. Den Dienst löschen:
   ```
   sc.exe delete WOLHostService
   ```
3. Prüfen, dass der Dienst entfernt wurde:
   ```
   sc.exe query WOLHostService
   ```
   Erwartete Antwort: *„Der angegebene Dienst ist nicht als installierter Dienst vorhanden.“*

Falls `sc.exe delete` ebenfalls fehlschlägt, kann der Registry-Schlüssel des Dienstes direkt gelöscht werden:
```
reg delete "HKLM\SYSTEM\CurrentControlSet\Services\WOLHostService" /f
```

Nach der Entfernung kann der Dienst mit `--install` und `--start` sauber neu registriert werden.

---

## Remote Desktop

Die Anwendung kann für ein Gerät eine **Remote-Desktop-Sitzung** (RDP) starten. Dazu werden die im Geräteeintrag gespeicherten **IP-Adresse**, **Benutzername** und **Passwort** verwendet.

### Remote Desktop starten
1. Klicken Sie mit der **rechten Maustaste** auf das Gerät in der Gerätetabelle.
2. Wählen Sie im Kontextmenü:
   - **Remote Fullscreen** – öffnet die Sitzung im Vollbild
   - **Remote Window** – öffnet die Sitzung in einem Fenster mit der konfigurierten Auflösung
3. Die Windows-Remotedesktopverbindung (`mstsc`) startet und verbindet sich mit dem Gerät.

> **Voraussetzung:** Auf dem Zielsystem muss **Remotedesktop** aktiviert sein (Systemeigenschaften → Remotefunktionen → „Remotedesktopverbindungen zulassen“). Das Gerät muss eine **IP-Adresse oder einen Hostnamen** besitzen; Benutzername und Passwort sind optional – ohne Passwort fragt `mstsc` beim Verbinden danach.

> **Linux-/xrdp-Gegenstellen:** Manche xrdp-Konfigurationen (typisch für Ubuntu) trennen Verbindungen auf die rohe IPv4-Adresse sofort wieder. Tragen Sie in diesem Fall den **Hostnamen** des Rechners (z. B. `ubuntu-mercury`) im Feld *IP-Adresse / Hostname* ein – die Anwendung verbindet Remote Desktop dann über den Namen.

> **Passwort-Anmeldung:** Aktuelle Windows-Versionen (10/11) übernehmen das Passwort aus Sicherheitsgründen nicht mehr aus der `.rdp`-Datei. Die Anwendung legt die Anmeldedaten daher beim Start einer Remote-Desktop-Sitzung automatisch über `cmdkey` im **Windows-Anmeldeinformations-Manager** ab – zwingend mit dem Ziel-Präfix `TERMSRV/`, da `mstsc` sonst keinen Eintrag findet (`/generic:TERMSRV/<IP> /user:<Benutzer> /pass:<Passwort>`). `mstsc` liest diesen Eintrag beim Verbinden aus – Sie müssen das Passwort dann nicht neu eingeben. Ist die Registrierung nicht möglich, fragt `mstsc` wie bisher nach dem Passwort.

> **Linux-/xrdp-Gegenstellen:** Gegenüber Windows-Hosts, die ohne passenden Anmelde-Eintrag einfach noch einmal nachfragen, bricht `xrdp` (Ubuntu) eine Verbindung ohne Passwort sofort ab – das `mstsc`-Fenster öffnet und schließt sich in diesem Fall innerhalb einer Sekunde. Stellen Sie daher sicher, dass Benutzername **und** Passwort am Gerät hinterlegt sind. Zusätzlich setzt die Anwendung `authentication level:i:0`, damit bei selbstsignierten Server-Zertifikaten (bei xrdp üblich) nicht bei jeder Verbindung die Sicherheitswarnung erscheint.

### Auflösung für das Fenster einstellen
1. Menü: **Tools → Einstellungen...**
2. In der Gruppe **Remote Desktop** wählen Sie im Drop-Down **Auflösung** die gewünschte Fensterauflösung (z. B. `1920 × 1080`).
3. Klicken Sie auf **Speichern**.

> **Hinweis:** Die Anmeldedaten werden in einer temporären `.rdp`-Datei abgelegt, die wenige Sekunden nach dem Start automatisch gelöscht wird, damit das Passwort nicht auf der Festplatte verbleibt.

---

## Geräte-Dashboard (Performance & Batches)

Das **Geräte-Dashboard** zeigt für ein einzelnes Gerät live **CPU-Auslastung**, **RAM-Nutzung**, **GPU-Auslastung** und **VRAM-Nutzung** – zusätzlich können auf dem Zielsystem **Batch-Skripte** ausgeführt werden. Das Dashboard ist ein eigener Bildschirm innerhalb der modernen Oberfläche (kein eigener Menüpunkt).

### Dashboard öffnen
- **Kachelansicht:** klicken Sie auf der Gerätekarte auf das **📊**-Symbol (neben 🖥️ und 🪟).
- **Listenansicht:** klicken Sie in der Zeile rechts auf das **📊**-Symbol.
- **Kontextmenü (Rechtsklick auf das Gerät):** **Dashboard öffnen**.

Mit **← Zurück** (links oben) kehren Sie zur Geräteansicht zurück.

### Live-Metriken
Vier Karten zeigen jeweils einen Ring-Gauge mit Prozentwert, eine Detailzeile (z. B. `12,0 / 32,0 GB` oder die GPU-Bezeichnung) und einen kleinen **Verlaufs-Sparkline** der letzten Messungen. Oberhalb der Karten stehen Hostname, IP/MAC, Online-Status und die **Uptime**.

Das Dashboard aktualisiert die Werte automatisch im gewählten **Intervall** (Drop-down rechts oben: 2 / 3 / 5 / 10 Sekunden; Standard 3 s). Im Hintergrund wird jeweils nur eine Messung gleichzeitig ausgeführt; ist das Gerät nicht erreichbar, wechselt das Abzeichen auf **Offline** und die Fehlerursache erscheint unter der Konsole.

**Voraussetzungen am Zielsystem:**
1. Aktualisierter **WOL Host Service** (Protokollversion 3 – enthalten ab dieser Version; ältere Dienste melden *„Host service too old for the dashboard“*).
2. Im Dashboard ist das Kontrollkästchen **Batch-Ausführung auf diesem Gerät erlauben** aktiviert (siehe unten) – es wird nur einmal pro Gerät gesetzt.
3. Für **GPU/VRAM**: NVIDIA-Grafikkarte mit aktuellem Treiber (`nvidia-smi` im Systempfad). Ohne NVIDIA-GPU stehen die beiden Karten auf **k/A**.

> Die Messwerte werden mit den Anmeldedaten des Geräts abgefragt (wie beim Remote Shutdown). Ohne gültige Benutzerdaten im Geräteeintrag liefert das Dashboard keine Werte.

### Beobachtete Prozesse (Service-Status)

Das Dashboard kann **benannte Prozesse auf dem Zielsystem beobachten** – z. B. einen lokalen llama.cpp-Server. Pro Gerät sind bis zu **8 Prozesse** konfigurierbar:

1. Öffnen Sie den **Geräte-Dialog** (Bearbeiten-Symbol bzw. Rechtsklick → *Bearbeiten*).
2. Tragen Sie das Feld **Beobachtete Prozesse** ein – kommagetrennt, z. B. `llama-server.exe, ollama.exe`.
3. Mit einem **Port-Suffix** (`llama-server.exe:8080`) prüfen Sie zusätzlich, ob die API des Prozesses antwortet.

Im Dashboard erscheint daraufhin:

- Ein **Status-Chip** pro Prozess im Kopfbereich: **grün** (läuft, API-Port erreichbar bzw. kein Port geprüft), **gelb** (*startet…* – Prozess läuft, Port noch geschlossen) oder **grau** (läuft nicht). Ist das Gerät offline oder der Host Service zu alt (vor Protokoll v3), werden die Chips ausgeblendet.
- Ein **Service-Panel** mit **PID**, **Uptime**, **Prozess-RAM** und **Prozess-CPU** – bei llama.cpp-Prozessen zusätzlich das **geladene Modell** (aus der Kommandozeile erkannt, 🦙-Symbol).
- Ein **⚡ Inferenz aktiv**-Abzeichen, wenn ein bereiter Service mit dauerhaft hoher GPU-Auslastung (≥ 60 %) zusammenfällt.

> **Hinweis:** Die Prozess-Beobachtung erfordert den **WOL Host Service ab Protokollversion 3** auf dem Zielsystem. Ältere Dienste ignorieren die Anfrage einfach – es erscheint kein Fehler, das Panel wird nur nicht angezeigt.

### Batches erstellen und ausführen
Im unteren Bereich verwalten Sie eine **Batch-Bibliothek pro Gerät**:

1. **Neu** – legt einen leeren Batch an.
2. **Name**, **Skript** (beliebiger `cmd`-Batchtext, bis 32.000 Zeichen) und **Timeout** (5–3600 s, Standard 120 s) im Editor ausfüllen – Änderungen werden mit **Speichern** dauerhaft im Geräteeintrag gesichert.
3. **Duplizieren** / **Löschen** – Batch vervielfältigen oder entfernen (mit Rückfrage).
4. **Ausführen** – sendet das Skript an das Zielsystem; **stdout/stderr**, **Exit-Code** und **Laufzeit** erscheinen in der **Konsole** darunter. Sehr lange Ausgaben werden gekürzt und mit *[… gekürzt …]* markiert. Mit **Stop** brechen Sie die laufende Ausführung ab.

**Sicherheit – doppelte Freischaltung:** Batch-Skripte laufen auf dem Zielsystem mit den Rechten des Host Service (**SYSTEM**!). Deshalb ist die Ausführung **zweifelt abgesichert**:
- **Clientseitig:** das Kontrollkästchen **Batch-Ausführung auf diesem Gerät erlauben** im Dashboard (pro Gerät gespeichert).
- **Zielsystemseitig:** der Host Service ist standardmäßig gesperrt. Ein Administrator muss es einmalig pro Rechner aktivieren:
  ```
  "C:\Program Files\WakeOnLAN\WOL Host Service.exe" --enable-batch
  ```
  Rückgängig mit `--disable-batch`. Die Einstellung wird in `%ProgramData%\WakeOnLAN\WOL Host Service\service.json` gespeichert und bei jeder Anfrage neu gelesen. Ohne diese Freigabe antwortet der Dienst mit *„Batch execution is disabled on this host“*.

> **Warnung:** Aktivieren Sie `--enable-batch` nur auf Rechnern, denen Sie vertrauen, und verwenden Sie ausschließlich starke Kennwörter – jeder mit gültigen Anmeldedaten kann dann Befehle mit SYSTEM-Rechten ausführen.

---

## Zeitpläne erstellen

1. Menü: **Datei → Zeitpläne verwalten...** (oder `Strg+S`)
2. Klicken Sie auf **+ Zeitplan hinzufügen**.
3. Konfigurieren Sie:
   - **Gerät:** Wählen Sie das Zielgerät
   - **Stunde & Minute:** Wann soll das Gerät geweckt werden?
   - **Tage:** An welchen Wochentagen? (Mo–So)
   - **Aktiviert:** Haken setzen, um den Zeitplan zu aktivieren
4. Klicken Sie auf **Speichern**.

> Der Zeitplan-Checker läuft im Hintergrund und löst Wake-on-LAN-Signale automatisch aus.

> **Tipp:** Über dem Suchfeld der Zeitplan-Tabelle können Sie die Liste **live filtern** – nach Gerätename, Zeit (HH:MM), Aktion, Wochentagen oder Aktiviert-Zustand.

---

## Netzwerkeinstellungen

1. Menü: **Tools → Netzwerkeinstellungen...**
2. Konfigurieren Sie:
   - **Broadcast-IP:** Standard `255.255.255.255` (für lokales Netzwerk)
   - **Broadcast-Port:** Standard `7` (oder `9`)
3. Klicken Sie auf **Speichern**.

> Ändern Sie die Broadcast-IP nur, wenn Sie ein spezifisches Subnetz ansprechen müssen (z. B. `192.168.2.255`).

> **Netzwerkscanner:** Der Scanner entdeckt Geräte im lokalen Netzwerk. Über dem Suchfeld der Ergebnis-Tabelle können Sie die Liste **live filtern** – nach Hostname, IPv4, IPv6 oder MAC-Adresse.

---

## Protokoll anzeigen

1. Menü: **Tools → Protokoll anzeigen...** (oder `Strg+L`)
2. Das Protokoll zeigt alle Aktionen mit Zeitstempel:
   - Wake-on-LAN-Sendungen (erfolgreich/fehlerhaft)
   - Automatische Zeitplan-Auslösungen
   - Fehlermeldungen
3. Klicken Sie auf **Protokoll löschen**, um den Verlauf zu leeren.

---

## Passwort-Verschlüsselung

Der **Wake-on-LAN Manager** schützt alle gespeicherten Passwörter durch eine starke Verschlüsselung, um die Sicherheit Ihrer Anmeldedaten zu gewährleisten. Diese Funktion ist besonders wichtig, wenn Sie die **Shutdown-Funktion mit Benutzername und Passwort** nutzen.

---

### Wie funktioniert die Verschlüsselung?

Die Passwort-Verschlüsselung basiert auf einer Kombination aus **AES-256-GCM** und **Windows DPAPI** (Data Protection API):

1. **AES-256-GCM-Verschlüsselung:**
   - Passwörter werden mit dem **AES-256-GCM-Algorithmus** verschlüsselt, einem der sicherten Verschlüsselungsstandards.
   - Dieser Algorithmus bietet **Authentizität** (Datenintegrität) und **Vertraulichkeit** (Geheimhaltung).

2. **Schlüsselverwaltung mit Windows DPAPI:**
   - Der **Verschlüsselungsschlüssel** selbst wird nicht in der Konfigurationsdatei gespeichert, sondern über die **Windows Data Protection API (DPAPI)** geschützt.
   - DPAPI bindet den Schlüssel an den aktuellen **Windows-Benutzer** und das **System**, auf dem die Verschlüsselung stattfindet.
   - Dadurch können **nur der aktuelle Benutzer auf demselben System** die Passwörter entschlüsseln.

3. **Sicherer Speicherort:**
   - Verschlüsselte Passwörter werden in der Datei `config.json` im Ordner `%USERPROFILE%\.wol_app\` gespeichert.
   - Selbst wenn die Datei kopiert oder gestohlen wird, sind die Passwörter **nicht lesbar**, da der Schlüssel fehlt.

---

### Sicherheit und Nutzung

#### Vorteile der Verschlüsselung
✅ **Kein Klartext:** Passwörter werden **nie** im Klartext in Dateien oder der Registry gespeichert.
✅ **Systemspezifisch:** Passwörter sind nur auf dem System lesbar, auf dem sie verschlüsselt wurden.
✅ **Benutzerspezifisch:** Jeder Windows-Benutzer hat seinen eigenen Verschlüsselungsschlüssel. Passwörter eines Benutzers sind für andere Benutzer **nicht zugänglich**.<|reserved_token_163700|>
✅ **Export/Import:** Auch beim Exportieren oder Importieren von Geräten bleiben die Passwörter verschlüsselt und werden automatisch entschlüsselt, wenn sie auf demselben System importiert werden.

#### Wichtige Hinweise
⚠ **Systemwechsel:**
   - Wenn Sie die Konfigurationsdatei (`config.json`) auf ein **anderes System** kopieren, können die Passwörter **nicht entschlüsselt** werden, da der DPAPI-Schlüssel systemspezifisch ist.
   - In diesem Fall müssen Sie die Passwörter manuell erneut eingeben.

⚠ **Benutzerwechsel:**
   - Falls ein anderer Windows-Benutzer auf demselben System die Anwendung nutzt, kann dieser die Passwörter **nicht entschlüsseln**, da sie an Ihren Benutzerkonten gebunden sind.

⚠ **Sicherheitskopie:**
   - Erstellen Sie regelmäßig **Sicherheitskopien** Ihrer Geräteeinstellungen (über **Datei → Geräte exportieren...**).
   - Beachten Sie, dass die exportierten Passwörter **nur auf demselben System und Benutzer** entschlüsselt werden können.

---

### Technische Details
| Komponente | Beschreibung |
|------------|-------------|
| **Algorithmus** | AES-256-GCM (256-Bit-Schlüssel, Galois/Counter Mode) |
| **Schlüsselverwaltung** | Windows DPAPI (Data Protection API) |
| **Speicherort** | `%USERPROFILE%\.wol_app\config.json` |
| **Kompatibilität** | Windows 10/11 (64-Bit) |
| **Performance** | Verschlüsselung/Entschlüsselung erfolgt in Echtzeit und ist nicht spürbar.

---

### Häufige Fragen zur Verschlüsselung

#### Werden meine Passwörter beim Speichern verschlüsselt?
Ja, **sofort nach dem Speichern** eines Geräts mit Passwort wird dieses verschlüsselt. Sie sehen das Passwort policier in der Geräteverwaltung, aber in der Datei `config.json` ist es verschlüsselt.

#### Kann ich die verschlüsselten Passwörter manuell entschlüsseln?
Nein. Die Entschlüsselung erfolgt automatisch durch die Anwendung und ist **nicht manuell möglich**, um die Sicherheit zu gewährleisten.

#### Was passiert, wenn ich Windows neu installiere?
Bei einer Neuinstallation von Windows geht der DPAPI-Schlüssel verloren. In diesem Fall müssen Sie die Passwörter **manuell erneut eingeben**, sobald Sie die Anwendung wieder verwenden.

#### Funktioniert die Verschlüsselung auch auf älteren Windows-Versionen?
Die Verschlüsselung ist für **Windows 10 und 11** optimiert. Ältere Versionen werden nicht unterstützt.

---

## Tastenkürzel

| Taste | Aktion |
|-------|--------|
| `Strg+D` | Geräte verwalten |
| `Strg+S` | Zeitpläne verwalten |
| `Strg+L` | Protokoll anzeigen |
| `Strg+Q` | Anwendung beenden |

---

## Häufige Fragen

### Warum wird mein Gerät nicht geweckt?
- Wake-on-LAN ist im BIOS/UEFI deaktiviert → Aktivieren Sie "Wake-on-LAN" oder "PME Event Wake".
- Die MAC-Adresse ist falsch → Prüfen Sie die Adresse im Zielsystem (`ipconfig /all` unter Windows).
- Firewall blockiert UDP-Pakete → Erlauben Sie UDP-Port 7/9.

### Warum zeigt der Status "Unbekannt" an?
- Keine IP-Adresse wurde für das Gerät konfiguriert. Fügen Sie die IP in den Geräteeinstellungen hinzu.

### Wo werden die Einstellungen gespeichert?
- Alle Daten werden in `%USERPROFILE%\.wol_app\` gespeichert.

---

## Systemanforderungen

| Komponente | Anforderung |
|------------|-------------|
| Betriebssystem | Windows 10/11 (64-Bit) |
| Python | 3.10+ (nur für Quellcode-Variante) |
| Netzwerk | Lokales Netzwerk (LAN), UDP-Port 7 oder 9 offen |
| BIOS/UEFI | Wake-on-LAN aktiviert auf den Zielsystemen |

---

*Version 2.2.0 | Wake-on-LAN Manager*
