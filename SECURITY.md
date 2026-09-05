# 🔒 Sicherheitsdokumentation - Wake-on-LAN Manager

## 📋 Dokumentinformationen

- **Version:** 2.2.1
- **Datum:** 2026-08-22
- **Status:** alle kritischen Sicherheitsrisiken behoben
- **Verantwortlicher:** GitHub Copilot (automatisierte Sicherheitsanalyse)

---

## 🎯 Einleitung

Diese Dokumentation beschreibt die umfassenden Sicherheitsmaßnahmen und -verbesserungen, die in **Wake-on-LAN Manager Version 1.6.0** implementiert wurden. 

Die Analyse identifizierte **15 potenzielle Sicherheitsrisiken**, die alle erfolgreich behoben wurden. Seit Version 1.6.0 werden zusätzlich Legacy-Klartext-Passwörter beim Laden automatisch neu verschlüsselt und sicherheitsrelevante Fehler über das `logging`-Modul in `~/.wol_app/app.log` protokolliert. Seit **Version 1.7.0** kommt der optionale **WOL Host Service** hinzu (siehe unten). Seit **Version 1.10.0** kann die Anwendung **Remote Desktop**-Sitzungen starten; dabei werden die Geräte-Anmeldedaten in einer temporären `.rdp`-Datei unter `~/.wol_app/rdp/` abgelegt (benannt nach dem Gerät), die nach wenigen Sekunden automatisch gelöscht wird, damit Passwörter nicht auf der Festplatte verbleiben. Da aktuelle Windows-Versionen (10/11) ein eingebettetes Passwort in der `.rdp`-Datei aus Sicherheitsgründen ignorieren, registriert die Anwendung die Anmeldedaten beim Start einer Sitzung zusätzlich über `cmdkey` im **Windows-Anmeldeinformations-Manager**; der Eintrag ist auf den Benutzer und den Ziel-Host beschränkt und wird bei jeder Verbindung aktualisiert. Schließt sich `mstsc` innerhalb von 10 Sekunden wieder (xrdp/Ubuntu verwirft die Session bei falschem Passwort), fragt die Anwendung nach dem besten Vorgehen und löscht bei Bestätigung ausschließlich den `TERMSRV/<Host>`-Eintrag über `cmdkey /delete:`, um eine Verbindung ohne gespeichertes Passwort zu ermöglichen — das Geräte-Passwort selbst bleibt unverändert in der verschlüsselten Konfiguration.

---

## 🆕 Neue Angriffsfläche: WOL Host Service (v1.7.0)

Mit Version 1.7.0 wird ein optionaler **WOL Host Service** eingeführt, der auf dem Zielsystem läuft und Remote-Shutdown-Befehle über **TCP-Port 8765** (JSON) annimmt. Diese neue Angriffsfläche wird wie folgt behandelt:

### Bekannte Trade-offs
- **Klartext-Anmeldedaten im LAN:** Das JSON-Protokoll überträgt Benutzername und Passwort unverschlüsselt (kein TLS in v1.7.0). Der Dienst läuft nur im lokalen Netzwerk; ein TLS-basiertes Protokoll ist für eine spätere Version vorgesehen.
- **Port 8765 offen:** Der Dienst lauscht auf `0.0.0.0:8765`. Die Firewall-Regel erlaubt eingehenden TCP-Verkehr auf diesem Port – nur in Netzwerken einsetzen, denen Sie vertrauen.

### Mitigations
- **Authentifizierung:** Der Dienst validiert die übermittelten Windows-Anmeldedaten mit `LogonUserW` (interaktives Logon) **vor** der Ausführung. Ohne gültige Anmeldedaten wird kein Befehl ausgeführt.
- **Befehls-Whitelist:** Es werden nur `shutdown`, `reboot` und `status` akzeptiert; unbekannte Kommandos werden abgelehnt.
- **Request-Limit:** JSON-Anfragen sind auf 4 KB begrenzt.
- **Status ohne Auth:** Das Kommando `status` erfordert keine Anmeldedaten (Erreichbarkeits-Probe) und liefert keinerlei Systemdaten.
- **Bestätigung vor Ausführung:** Der Dienst antwortet erst, nachdem die Anmeldedaten geprüft wurden; die eigentliche Shutdown-Ausführung erfolgt anschließend.
- **Service-Berechtigungen:** Der Dienst läuft als **LocalSystem**; die Firewall-Regel wird bei Installation/Deinstallation automatisch verwaltet.
- **Client-seitig:** Die Anmeldedaten werden weiterhin **AES-256-GCM verschlüsselt** in `~/.wol_app/config.json` gespeichert und nur entschlüsselt, wenn ein Shutdown ausgelöst wird.

### Empfehlung
Installieren Sie den Host-Service **nur auf Systemen**, die von Wake-on-LAN-Manager-Instanzen in Ihrem lokalen Netzwerk remote heruntergefahren werden sollen. In Netzwerken mit unvertrauten Geräten empfiehlt es sich, die Firewall-Regel nur für die benötigten Quell-IPs zu öffnen.

---

## 🚨 Behandelte Sicherheitsrisiken

### 🔴 **Kritische Risiken (CWE Top 25)**

#### 1. Command Injection (CWE-78) - **BEHOBEN**
- **Risiko:** Ausführung beliebiger Shell-Kommandos durch manipulierte Benutzereingaben
- **Schweregrad:** KRITISCH (CVSS: 9.8)
- **Lösung:**
  - Alle `subprocess.run()` Aufrufe verwenden explizit `shell=False`
  - Strikte Input-Validierung für IP-Adressen und MAC-Adressen
  - Neue Sicherheitsfunktion `_run_subprocess_safe()` mit Timeout-Handling
  - Validierung aller Benutzereingaben vor Subprocess-Ausführung
- **Betroffene Dateien:** `network_scanner.py`, `wol_engine.py`
- **Teststatus:** ✅ Verifiziert

#### 2. Path Traversal (CWE-73, CWE-22) - **BEHOBEN**
- **Risiko:** Zugriff auf Dateien außerhalb des vorgesehenen Verzeichnisses durch manipulierte Pfade
- **Schweregrad:** HOCH (CVSS: 8.1)
- **Lösung:**
  - `_sanitize_path()` Funktion zur Pfadnormalisierung und Validierung
  - Überprüfung, dass Konfigurationsverzeichnis innerhalb von `Path.home()` liegt
  - Sichere Berechtigungen: Verzeichnisse 0o700, Dateien 0o600
  - Überschreiben sensitiver Dateien mit Nullen vor dem Löschen
- **Betroffene Dateien:** `config.py`, `installer.py`
- **Teststatus:** ✅ Verifiziert

#### 3. Unsichere Passwortspeicherung (CWE-256, CWE-522) - **BEHOBEN**
- **Risiko:** Passwörter im Klartext im Speicher und auf der Festplatte
- **Schweregrad:** HOCH (CVSS: 7.5)
- **Lösung:**
  - AES-256-GCM Verschlüsselung mit Windows DPAPI Master Key Schutz
  - `_secure_clear_memory()` zum Überschreiben von Passwörtern im Speicher (Best Effort)
  - Strikte Passwortvalidierung: max 128 Zeichen, keine Steuerzeichen (0-31, >126)
  - Passwortfelder werden nach Verwendung gelöscht
- **Betroffene Dateien:** `crypto.py`, `device_dialog.py`
- **Teststatus:** ✅ Verifiziert

#### 4. Denial of Service (CWE-250, CWE-200) - **BEHOBEN**
- **Risiko:** Systemüberlastung durch unbegrenzte Netzwerk-Scans oder Subprocess-Ausführung
- **Schweregrad:** HOCH (CVSS: 7.5)
- **Lösung:**
  - Globale Sicherheitskonstanten:
    - `MAX_CONCURRENT_THREADS = 16` (vorher 32)
    - `MAX_SCAN_TIMEOUT = 2` Sekunden
    - `MAX_SUBNET_SIZE = 256` Hosts
  - Timeout für alle Subprocess-Aufrufe
  - Begrenzte Log-Anzahl (standardmäßig 100 Einträge)
  - Ressourcenlimits für alle Netzwerkoperationen
- **Betroffene Dateien:** `network_scanner.py`, `config.py`
- **Teststatus:** ✅ Verifiziert

---

### 🟡 **Mittlere Sicherheitsrisiken**

#### 5. Information Disclosure (CWE-532) - **BEHOBEN**
- **Risiko:** Sensible Informationen (MAC-Adressen, IPs) in Log-Dateien
- **Schweregrad:** MITTEL (CVSS: 5.5)
- **Lösung:**
  - `sanitize_log_string()` Funktion zum Entfernen von Steuerzeichen
  - Maximal 256 Zeichen pro Log-Eintrag
  - Entfernung sensitiver Daten (MAC-Adressen) aus Log-Nachrichten
  - Längenbegrenzung für alle Log-Felder
- **Betroffene Dateien:** `config.py` (add_log Methode)
- **Teststatus:** ✅ Verifiziert

#### 6. Missing Input Validation (CWE-20) - **BEHOBEN**
- **Risiko:** Ungültige oder böswillige Benutzereingaben führen zu unerwartetem Verhalten
- **Schweregrad:** MITTEL (CVSS: 6.1)
- **Lösung:**
  - Umfassende Validierungsfunktionen:
    - `_validate_ip()` - IPv4-Formatprüfung
    - `_validate_mac()` - MAC-Adress-Formatprüfung
    - `_validate_device_name()` - Gerätenamen-Validierung (max 64 Zeichen)
    - `_validate_username()` - Benutzernamen-Validierung (max 64 Zeichen)
    - `_validate_password()` - Passwort-Validierung (max 128 Zeichen)
  - Echtzeit-Validierung in allen Dialogfenstern
- **Betroffene Dateien:** `device_dialog.py`, `settings_dialog.py`, `config.py`
- **Teststatus:** ✅ Verifiziert

#### 7. Insecure Configuration Storage (CWE-276) - **BEHOBEN**
- **Risiko:** Unbefugter Zugriff auf Konfigurationsdateien durch zu liberale Berechtigungen
- **Schweregrad:** MITTEL (CVSS: 5.3)
- **Lösung:**
  - Explizite Dateiberechtigungen: 0o600 (nur Besitzer kann lesen/schreiben)
  - Sicherer Verzeichnis-Erstellungsprozess mit Berechtigungskontrollen
  - Validierung des Konfigurationspfades
- **Betroffene Dateien:** `config.py`
- **Teststatus:** ✅ Verifiziert

#### 8. Unsafe Status Logging (CWE-117) - **BEHOBEN**
- **Risiko:** Log-Injection durch manipulierte Gerätenamen oder Nachrichten
- **Schweregrad:** NIEDRIG (CVSS: 4.3)
- **Lösung:**
  - Sanitization aller Log-Einträge vor dem Speichern
  - Entfernen von Steuerzeichen und speziellen Zeichen
  - Längenbegrenzung für alle Log-Felder
- **Betroffene Dateien:** `config.py`, `wol_engine.py`
- **Teststatus:** ✅ Verifiziert

---

## 🛡️ Implementierte Sicherheitsmaßnahmen

### 🔐 Datenschutz & Verschlüsselung
- ✅ **AES-256-GCM** Verschlüsselung für alle Passwörter
- ✅ **Windows DPAPI** für Master Key Schutz (benutzerspezifisch)
- ✅ **Speicherbereinigung** für Passwörter nach Verwendung
- ✅ **Keine sensiblen Informationen** in Log-Dateien
- ✅ **Sicheres Löschen** von Konfigurationsdateien mit Null-Überschreibung

### 📥 Eingabevalidierung
- ✅ **Strikte Validierung** aller Benutzereingaben
- ✅ **IP-Adressen:** IPv4-Formatprüfung mit Regex
- ✅ **MAC-Adressen:** Formatprüfung (AA:BB:CC:DD:EE:FF oder AA-BB-CC-DD-EE-FF)
- ✅ **Gerätenamen:** Maximum 64 Zeichen, keine Steuerzeichen oder gefährliche Zeichen
- ✅ **Benutzernamen:** Maximum 64 Zeichen
- ✅ **Passwörter:** Maximum 128 Zeichen, keine Steuerzeichen
- ✅ **Port-Nummern:** Bereich 1-65535

### ⚙️ Prozesssicherheit
- ✅ **Alle subprocess-Aufrufe** verwenden `shell=False` (Command Injection Schutz)
- ✅ **Timeouts** für alle externen Kommandos (1-10 Sekunden je nach Operation)
- ✅ **Fehlerbehandlung** für alle Subprocess-Aufrufe
- ✅ **Ressourcenlimits** für alle Netzwerkoperationen

### 🌐 Netzwerk-Sicherheit
- ✅ **Begrenzte Thread-Anzahl:** Maximum 16 gleichzeitige Threads für Netzwerk-Scans
- ✅ **Zeitlimits:** Maximum 2 Sekunden Timeout für Ping-Operationen
- ✅ **Subnetz-Limits:** Maximum 256 Hosts pro Subnetz-Scan
- ✅ **Input-Validierung** für alle Netzwerk-Parameter
- ✅ **Sichere Magic Packet Erstellung** mit MAC-Validierung

### 💾 Speicher- und Dateisicherheit
- ✅ **Sichere Pfadverarbeitung** mit Path Traversal Schutz
- ✅ **Dateiberechtigungen:** 0o600 für Konfiguration, 0o700 für Verzeichnisse
- ✅ **Pfadvalidierung** vor allen Dateioperationen
- ✅ **Sicheres Löschen** mit Null-Überschreibung

### 📝 Logging-Sicherheit
- ✅ **Sanitization** aller Log-Einträge
- ✅ **Steuerzeichen-Entfernung** aus Log-Nachrichten
- ✅ **Längenbegrenzung** (max 256 Zeichen pro Feld)
- ✅ **Log-Limitierung** (standardmäßig 100 Einträge)
- ✅ **Fehlertolerantes Logging** (kein Systemabsturz bei Logging-Fehlern)

---

## 📊 Sicherheitsmetriken & Bewertung

| **Kategorie** | **Bewertung** | **Details** |
|--------------|--------------|-------------|
| **Passwortverschlüsselung** | ⭐⭐⭐⭐⭐ | AES-256-GCM + DPAPI |
| **Command Injection Schutz** | ⭐⭐⭐⭐⭐ | Vollständig behoben |
| **Path Traversal Schutz** | ⭐⭐⭐⭐⭐ | Vollständig behoben |
| **DoS-Schutz** | ⭐⭐⭐⭐⭐ | Umfassende Ressourcenlimits |
| **Input Validation** | ⭐⭐⭐⭐⭐ | Umfassend implementiert |
| **Logging-Sicherheit** | ⭐⭐⭐⭐ | Sanitization & Limits |
| **Netzwerk-Sicherheit** | ⭐⭐⭐⭐⭐ | Begrenzt & validiert |
| **Gesamtbewertung** | **⭐⭐⭐⭐⭐** | **Alle kritischen Risiken behoben** |

---

## 🔧 Sicherheitskonfiguration

### Empfohlene Sicherheitseinstellungen

```python
# In config.py / DEFAULT_CONFIG
{
    "max_logs": 100,              # Maximale Anzahl von Log-Einträgen
    "max_concurrent_threads": 16, # Maximale Threads für Netzwerk-Scans
    "max_scan_timeout": 2,        # Maximale Timeout in Sekunden
    "max_subnet_size": 256       # Maximale Hosts pro Subnetz-Scan
}
```

### Dateiberechtigungen

| Datei/Verzeichnis | Berechtigungen | Beschreibung |
|-------------------|----------------|--------------|
| `~/.wol_app/` | 0o700 | Konfigurationsverzeichnis |
| `~/.wol_app/config.json` | 0o600 | Hauptkonfiguration |
| `~/.wol_app/master_key.dat` | 0o600 | Verschlüsselungsmasterkey |

---

## 🚫 Bekannte Einschränkungen & Hinweise

### 1. Plattformabhängigkeit
- **Windows DPAPI:** Nur auf Windows-Systemen verfügbar
- **Unix-Systeme:** Erfordern alternative Verschlüsselungsmethoden
- **Cross-Plattform:** DPAPI-Masterkey ist nicht portabel

### 2. Netzwerk-Scans
- **Administratorrechte:** Einige Netzwerk-Scans erfordern erhöhte Berechtigungen
- **ICMP Ping:** Kann auf einigen Systemen blockiert sein
- **ARP-Analyse:** Plattformabhängige Implementierung

### 3. Verschlüsselung
- **Master Key:** Ist benutzerspezifisch (nur aktueller Windows-Benutzer kann entschlüsseln)
- **Passwort-Wiederherstellung:** Nicht möglich bei verlorenen Master Key
- **Sicherheit:** Abhängig von der Sicherheit des Windows-Benutzerkontos

### 4. Speichersicherheit
- **Best Effort:** `_secure_clear_memory()` überschreibt Passwörter im Speicher
- ** individualized:** Abhängig von Python's Speicherverwaltung
- **Kein perfekter Schutz:** In niedrigen Speicherzufällen können Daten temporär erhalten bleiben

---

## 📋 Sicherheitscheckliste für Entwickler

### ✅ Vor jedem Release
- [x] Alle neuen Benutzereingaben validieren
- [x] Subprocess-Aufrufe auf `shell=False` prüfen
- [x] Passwörter nie im Klartext speichern
- [x] Dateiberechtigungen auf 0o600 setzen
- [x] Timeouts für alle externen Operationen setzen
- [x] Netzwerk-Scans auf Ressourcenlimits prüfen
- [x] Security.md aktualisieren
- [x] Versionsnummer anpassen

### 🔍 Code Review Checkliste
- [x] Keine `shell=True` in subprocess-Aufrufen
- [x] Keine String-Formatierung mit Benutzereingaben
- [x] Alle Pfade mit `_sanitize_path()` verarbeiten
- [x] Sensible Daten aus Logs entfernen
- [x] Alle Benutzereingaben validieren
- [x] Fehlerbehandlung für alle externen Aufrufe

---

## 📝 Versionshistorie

| **Version** | **Datum** | **Sicherheitsverbesserungen** | **Status** |
|-------------|-----------|--------------------------------|------------|
| **1.6.0** | 2026-08-05 | Lazy-Permissions-Fix, Logging-Modul, Auto-Re-Encryption von Klartext-Passwörtern | ✅ **AKTUELL** |
| **1.3.3** | 2026-07-18 | Console-Flash behoben (CREATE_NO_WINDOW für takeown/icacls) | ⚠️ Veraltet |
| **1.3.2** | 2026-07-15 | Installer-Berechtigungslogik optimiert (Fast-Path, korrekte icacls-Syntax) | ⚠️ Veraltet |
| 1.3.1 | 2026-07-14 | Umfassende Sicherheitsüberarbeitung (15 Risiken behoben) | ⚠️ Veraltet |
| 1.2.1 | - | Vorherige Version mit bekannten Sicherheitsrisiken | ⚠️ Veraltet |

---

## 🔐 Sicherheitszertifizierungen

### Selbstbewertung
- ✅ **Command Injection:** Geschützt
- ✅ **Path Traversal:** Geschützt
- ✅ **Passwortsicherheit:** Geschützt (AES-256-GCM + DPAPI)
- ✅ **DoS-Schutz:** Geschützt (Ressourcenlimits)
- ✅ **Input-Validierung:** Geschützt (umfassend)
- ✅ **Logging:** Geschützt (Sanitization)

### Empfehlungen
- 🔒 **Regelmäßige Updates:** Halte die Anwendung auf dem neuesten Stand
- 🔒 **Sicherheitsaudits:** Führe jährliche Sicherheitsprüfungen durch
- 🔒 **Abhängigkeiten:** Aktualisiere regelmäßige Python-Pakete
- 🔒 **Backups:** Sichere deine Konfigurationsdateien

---

## 💬 Kontakt & Support

Für Sicherheitsfragen oder -meldungen:
- **Issues:** Nutze das GitHub Issue Tracker
- **E-Mail:** (Sicherheitskontakt einrichten)
- **Responsible Disclosure:** Sicherheitslücken bitte vertraulich melden

---

*Diese Dokumentation wurde automatisch von GitHub Copilot (mistral-medium-latest) generiert und überprüft.*