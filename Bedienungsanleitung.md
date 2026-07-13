# Wake-on-LAN Manager – Bedienungsanleitung

## Inhaltsverzeichnis
1. [Installation](#installation)
2. [Deinstallation](#deinstallation)
3. [Start der Anwendung](#start-der-anwendung)
4. [Geräte verwalten](#geräte-verwalten)
5. [Wake-on-LAN senden](#wake-on-lan-senden)
6. [Status prüfen](#status-prüfen)
7. [Remote Shutdown](#remote-shutdown)
8. [Zeitpläne erstellen](#zeitpläne-erstellen)
9. [Netzwerkeinstellungen](#netzwerkeinstellungen)
10. [Protokoll anzeigen](#protokoll-anzeigen)
11. [Passwort-Verschlüsselung](#passwort-verschlüsselung)
12. [Tastenkürzel](#tastenkürzel)
13. [Häufige Fragen](#häufige-fragen)
14. [Systemanforderungen](#systemanforderungen)

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

> **Hinweis:** Bei der Deinstallation werden auch alle Geräteeinträge und Einstellungen gelöscht.

---

## Start der Anwendung

Starten Sie die Anwendung über:
- Die **Desktop-Verknüpfung** (Doppelklick)
- Das **Windows-Startmenü** → *Wake-on-LAN Manager*

Die Hauptansicht zeigt eine Tabelle mit allen konfigurierten Geräten und deren Status.

**Hauptbestandteile:**
- **Menüleiste** oben (Datei, Tools, Hilfe)
- **Aktionen-Schaltflächen** (Alle Geräte wecken, Status aktualisieren)
- **Gerätetabelle** mit Name, MAC-Adresse, IP und Status
- **Statusleiste** unten mit aktuellen Meldungen

---

## Geräte verwalten

### Gerät hinzufügen
1. Menü: **Datei → Geräte verwalten...** (oder `Strg+D`)
2. Klicken Sie auf **+ Gerät hinzufügen**.
3. Geben Sie folgende Daten ein:
   - **Gerätename:** Ein sprechender Name (z. B. "Büro-PC", "Gaming-Rig")
   - **MAC-Adresse:** Die MAC-Adresse des Zielsystems (Format: `AA:BB:CC:DD:EE:FF`)
   - **IP-Adresse:** Optional, für Status-Prüfung per Ping
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

---

## Netzwerkeinstellungen

1. Menü: **Tools → Netzwerkeinstellungen...**
2. Konfigurieren Sie:
   - **Broadcast-IP:** Standard `255.255.255.255` (für lokales Netzwerk)
   - **Broadcast-Port:** Standard `7` (oder `9`)
3. Klicken Sie auf **Speichern**.

> Ändern Sie die Broadcast-IP nur, wenn Sie ein spezifisches Subnetz ansprechen müssen (z. B. `192.168.2.255`).

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

*Version 1.2.1 | Wake-on-LAN Manager*
