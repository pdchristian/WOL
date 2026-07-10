# Wake-on-LAN Manager – Bedienungsanleitung

## Inhaltsverzeichnis
1. [Installation](#installation)
2. [Start der Anwendung](#start-der-anwendung)
3. [Geräte verwalten](#geräte-verwalten)
4. [Wake-on-LAN senden](#wake-on-lan-senden)
5. [Status prüfen](#status-prüfen)
6. [Zeitpläne erstellen](#zeitpläne-erstellen)
7. [Netzwerkeinstellungen](#netzwerkeinstellungen)
8. [Protokoll anzeigen](#protokoll-anzeigen)
9. [Tastenkürzel](#tastenkürzel)
10. [Häufige Fragen](#häufige-fragen)

---

## Installation

### Option 1: Standalone-Executable (empfohlen)
1. Die Datei `Wake-on-LAN Manager.exe` an einen beliebigen Ort kopieren (z. B. Desktop oder Programme-Ordner).
2. Optional: Eine Verknüpfung auf dem Desktop erstellen.
3. Fertig – keine weitere Installation nötig.

### Option 2: Aus dem Quellcode starten
1. Python 3.10+ installieren.
2. Abhängigkeiten installieren: `pip install -r requirements.txt`
3. App starten: `python run.py`

---

## Start der Anwendung

Doppelklicken Sie auf `Wake-on-LAN Manager.exe`. Die Hauptansicht zeigt eine Tabelle mit allen konfigurierten Geräten und deren Status.

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

> **Hinweis:** Pro App können bis zu 8 Geräte konfiguriert werden.

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
- Alle Daten werden in `%USERPROFILE%\.wol_app\config.json` gespeichert.

---

*Version 1.0 | Wake-on-LAN Manager*
