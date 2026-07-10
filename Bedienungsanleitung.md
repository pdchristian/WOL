# Wake-on-LAN Manager – Bedienungsanleitung

## Inhaltsverzeichnis
1. [Installation](#installation)
2. [Deinstallation](#deinstallation)
3. [Start der Anwendung](#start-der-anwendung)
4. [Geräte verwalten](#geräte-verwalten)
5. [Wake-on-LAN senden](#wake-on-lan-senden)
6. [Status prüfen](#status-prüfen)
7. [Zeitpläne erstellen](#zeitpläne-erstellen)
8. [Netzwerkeinstellungen](#netzwerkeinstellungen)
9. [Protokoll anzeigen](#protokoll-anzeigen)
10. [Tastenkürzel](#tastenkürzel)
11. [Häufige Fragen](#häufige-fragen)
12. [Systemanforderungen](#systemanforderungen)

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

*Version 1.0.0 | Wake-on-LAN Manager*
