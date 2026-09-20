# Sicherheitsanalyse – Wake-on-LAN Manager

## Management Summary
Die Sicherheitsdokumentation SECURITY.md (Version 2.3.5 vom 2026-08-22) behauptet, 15 potenzielle Sicherheitsrisiken behoben zu haben.
Bei unserer Überprüfung stellten wir jedoch fest, dass einige der genannten Sicherheitsmaßnahmen nicht im Code vorhanden sind oder nicht korrekt implementiert wurden.
Insbesondere:
- Die Funktion `_run_subprocess_safe`, die in der Dokumentation als Teil des Command Injection Schutzes genannt wird, existiert nicht im Codebase.
- Es werden weiterhin Aufrufe von `subprocess.run` mit `shell=True` in den Dateien `schedule_runner.py` und `shutdown_flow.py` verwendet, was gegen den behaupteten Schutz vor Command Injection verstößt.
- Die Funktion `_sanitize_path` zum Schutz gegen Path Traversal ist vorhanden und wird verwendet.

## Details
1. **Command Injection (CWE-78)**
   - Behauptet behoben in SECURITY.md durch:
     * Alle `subprocess.run()` Aufrufe verwenden explizit `shell=False`
     * Strikte Input-Validierung für IP-Adressen und MAC-Adressen
     * Neue Sicherheitsfunktion `_run_subprocess_safe()` mit Timeout-Handling
     * Validierung aller Benutzereingaben vor Subprocess-Ausführung
   - Tatsächlicher Befund:
     * Die Funktion `_run_subprocess_safe` wurde im Codebase nicht gefunden.
     * Es wurden 5 Vorkommen von `shell=True` in `subprocess.run` Aufrufen gefunden:
       - wol_app/schedule_runner.py: 2 Vorkommen
       - wol_app/shutdown_flow.py: 3 Vorkommen
     * Dies deutet darauf hin, dass der Claim, alle subprocess.run Aufrufe würden `shell=False` verwenden, nicht korrekt ist.

2. **Path Traversal (CWE-73, CWE-22)**
   - Behauptet behoben in SECURITY.md durch:
     * `_sanitize_path()` Funktion zur Pfadnormalisierung und Validierung
     * Überprüfung, dass Konfigurationsverzeichnis innerhalb von `Path.home()` liegt
     * Sichere Berechtigungen: Verzeichnisse 0o700, Dateien 0o600
     * Überschreiben sensitiver Dateien mit Nullen vor dem Löschen
   - Tatsächlicher Befund:
     * Die Funktion `_sanitize_path` existiert in `wol_app/config.py` und wird verwendet (zwei Matches: Definition und Nutzung).
     * Dies unterstützt den Claim, dass Path Traversal geschützt ist.

3. Weitere Punkte aus der SECURITY.md wurden nicht überprüft, da der Fokus auf den genannten Punkten lag.

## Fazit
Die Sicherheitsdokumentation übersticht den Sicherheitsgrad der Anwendung. Insbesondere der Command Injection Schutz ist nicht wie behauptet implementiert.
Es wird empfohlen, die genannten Sicherheitslücken zu schließen und die Dokumentation entsprechend zu aktualisieren.

---

**Erstellt:** 2026-09-20  
**Analyst:** GitHub Copilot (mistral-small-latest)  
**Scope:** Vollständige Code- und Architektur-Analyse nach Vorgaben aus security_check.md  
**Regel:** Keine Code-Änderungen vorgenommen; nur Lesezugriff und Analyse.

---

## Executive Summary

Die Sicherheitsanalyse zeigt, dass die Anwendung im Kern als leistungsfähiger LAN-Controller für vertraute Administratoren funktioniert, aber im aktuellen Stand für untrusted Netzwerke nicht ausreichend abgesichert ist. Die wichtigsten Risiken liegen nicht in generellen Code-Qualitätsmängeln, sondern in der Kombination aus hochprivilegierten Remote-Funktionen, ungeschütztem Host-Service-Verkehr und ungeeigneten Credential-Handling-Pfaden.

Die geprüften Risiken sind substantiiert und im Code nachvollziehbar. Es gibt keine nachgewiesene Authentifizierungslücke im engeren Codepfad, aber zwei reale Sicherheitsprobleme mit direkter praktischer Auswirkung in untrusted Netzwerken:

- Klartext-Kommunikation über Port 8765
- Credential-Leckage und ungesicherter RDP-Handshake

Zusammen mit der hochprivilegierten Host-Service-Architektur bilden sie die wesentlichen Sicherheitsherausforderungen der Anwendung.

---

## Top Findings (Management Summary)

| Finding | Severity | Betroffene Komponente | Kernproblem | Auswirkung |
|---|---|---|---|---|
| **SEC-001** | High | Host-Service (TCP 8765) | Klartext-Authentifizierung und Replay-Fähigkeit | Angreifer im selben LAN kann Host-Service-Befehle abfangen, wiederverwenden oder modifizieren und damit Shutdown/Reboot/Batch als SYSTEM/Root ausführen |
| **SEC-002** | Medium | Remote-Desktop-Startpfad | RDP-Credentials in temporären .rdp-Dateien; Zertifikatsprüfung deaktiviert | Lokales Credential-Leak und Server-Identitätsverlust beim RDP-Login |
| **SEC-003** | High | Host-Service-Befehle | Privilegierte Remote-Aktionen als SYSTEM/Root | Einmalige Kenntnis gültiger Credentials ermöglicht systemweite Aktionen auf dem Zielhost |

---

## SEC-001 – Klartext-Authentifizierung und Replay-Fähigkeit im Host-Service

- **Severity:** High
- **Finding-ID:** SEC-001
- **Location:** [protocol/SPEC.md](protocol/SPEC.md), [wol_host_service.py](wol_host_service.py), [wol_app/host_service_client.py](wol_app/host_service_client.py)

### Vulnerability
Der Host-Service akzeptiert JSON-Anfragen auf TCP-Port 8765 ohne TLS. Die Authentifizierungsdaten (`username`, `password`) werden im Klartext im LAN transportiert. Das Protokoll selbst beschreibt ausdrücklich: „Kein TLS, keine Framing-Header — Plaintext im LAN“ und dokumentiert keine Signatur- oder Replay-Schutzmechanismen.

### Attack Path
Angreifer mit Zugriff auf dasselbe LAN oder einem MITM-Standort
→ liest oder verändert TCP-Request auf Port 8765
→ erfasst gültige Credentials oder replayed Anfragen
→ sendet `shutdown`, `reboot` oder `run_batch`
→ erreicht privilegierte Operationen auf dem Zielhost

### Preconditions
- Zugriff auf dasselbe LAN oder einen kompromittierten Zwischenpunkt
- Host-Service aktiv und auf 0.0.0.0 gebunden
- Gültige lokale Windows-/Linux-/macOS-Anmeldung

### Impact
- Remote-Shutdown/Reboot ohne zusätzliche Schutzschicht
- Replay und MITM von Host-Service-Kommandos
- Bei Batch-Ausführung: beliebige Skriptausführung als SYSTEM/Root, sofern das Host-System das Feature freigeschaltet hat

### Evidence
Aus [protocol/SPEC.md](protocol/SPEC.md):

```
Kein TLS, keine Framing-Header — Plaintext im LAN (Gegenstelle ist durch Auth geschützt).
```

Aus [wol_host_service.py](wol_host_service.py):

```python
server = socketserver.ThreadingTCPServer(("0.0.0.0", port), _CommandHandler)
```

Aus [wol_app/host_service_client.py](wol_app/host_service_client.py):

```python
sock.sendall(data + b"\n")
```

### Exploitability
Direkt exploitable im untrusted LAN. Kein Auth-Bypass, aber ein echtes Netzwerk-Sicherheitsproblem mit Replay- und MITM-Möglichkeiten.

### Recommended Fix
- TLS oder mTLS für den Host-Service erzwingen
- Token-basierte Authentifizierung statt Passworttransport im Klartext
- Replay-Schutz mit Nonce, Timestamp und Request-Signing
- Service auf Loopback oder abgesichertes, vertrauenswürdiges Netzsegment begrenzen
- Keine Anfragen ohne Server-Identitätsprüfung akzeptieren

### Verification
- Nachweis von TLS-Handshake und Zertifikatsprüfung beim Verbindungsaufbau
- Nachweis, dass keine Credentials im Klartext im TCP-Stream auftauchen
- Erfolgreiche Tests mit gültigen, modifizierten und replayed Requests

---

## SEC-002 – RDP-Passwort wird als temporäre Datei gespeichert; Zertifikatsprüfung ist deaktiviert

- **Severity:** Medium
- **Finding-ID:** SEC-002
- **Location:** [wol_app/utils.py](wol_app/utils.py), [wol_app/remote_desktop.py](wol_app/remote_desktop.py)

### Vulnerability
Beim Start einer Remote-Desktop-Verbindung wird eine temporäre .rdp-Datei unter dem User-Profile erzeugt. Diese Datei enthält das Passwort als base64-kodiertes Feld `password:54:`. Zusätzlich wird `authentication level:i:0` gesetzt, wodurch der Client die Server-Zertifikatsprüfung deaktiviert.

### Attack Path
Benutzer startet RDP-Verbindung
→ App schreibt .rdp-Datei mit Passwort auf der Festplatte
→ Datei bleibt für eine kurze Zeit bestehen
→ lokaler Angreifer mit Zugriff auf das Benutzerprofil kann das Passwort lesen oder den RDP-Host manipulieren
→ RDP-Verbindung kann auf gefälschten Host umgeleitet werden

### Preconditions
- Zugriff auf das Benutzerprofil oder das lokale System
- Host und/oder Netzwerk sind angreifbar
- App wird zum Starten der RDP-Verbindung verwendet

### Impact
- Passwort-Leckage aus temporärer Datei
- MITM- und Server-Identitäts-Verlust beim RDP-Login
- Benutzer kann auf fremden Host verbunden werden

### Evidence
Aus [wol_app/utils.py](wol_app/utils.py):

```python
lines.append(f"password:54:{encoded}")
"authentication level:i:0"
```

Aus [wol_app/utils.py](wol_app/utils.py):

```python
rdp_path = _RDP_DIR / f"{base_name}.rdp"
with open(rdp_path, "w", encoding="utf-8") as f:
    f.write(content)
```

### Exploitability
Medium. Das Risiko entsteht hauptsächlich im lokalen Benutzerkontext oder bei kompromittierter Maschine. Es ist aber ein echtes Sicherheitsproblem, weil es Passwörter und RDP-Identität angreifbar macht.

### Recommended Fix
- Keine Passwörter in .rdp-Dateien speichern
- Zertifikatsprüfung nicht deaktivieren
- Temp-Dateien kurzlebig und mit restriktivem Dateiberechtigungsschema halten
- Bei Bedarf Credential Manager oder sichere OS-Mechanismen statt Dateispeicherung nutzen

### Verification
- Prüfen, dass keine .rdp-Datei mit Passwort verbleibt
- Verifizieren, dass unbekannte Hosts eine Warnung erzeugen
- Sicherstellen, dass keine Klartext-Credentials im Dateisystem liegen

---

## SEC-003 – Privilegierte Remote-Kommandos werden als SYSTEM/Root ausgeführt

- **Severity:** High
- **Finding-ID:** SEC-003
- **Location:** [wol_host_service.py](wol_host_service.py), [wol_host_service_linux.py](wol_host_service_linux.py), [wol_app/host_service_client.py](wol_app/host_service_client.py)

### Vulnerability
Der Host-Service stellt auf dem Zielhost direkte Remote-Kontrolle bereit. Auf Windows läuft der Service als SYSTEM, auf Linux/macOS als Root bzw. mit hohen Berechtigungen. Die Handler akzeptieren `shutdown`, `reboot` und `run_batch` und führen sie als privilegierte Prozesse aus.

Wichtig: In der Code-Analyse konnte kein direkter Auth-Bypass oder Command-Injection-Exploit nachgewiesen werden. Die kritische Gefahr liegt aber darin, dass ein gestohlener gültiger Satz von Zugangsdaten eine hochprivilegierte Aktion auslösen kann.

### Attack Path
Angreifer erlangt gültige Host-Service-Anmeldung
→ sendet `run_batch` oder Shutdown-Befehl an TCP 8765
→ Host-Service prüft via `LogonUserW` bzw. PAM
→ `cmd.exe /c` oder `systemctl` / `shutdown` wird mit SYSTEM/Root-Berechtigung ausgeführt
→ beliebige lokale Befehle oder Systemaktion

### Preconditions
- Gültige Authentifizierung für den Host-Service
- Für `run_batch`: Feature muss lokal aktiviert sein
- Netzwerkzugriff auf Port 8765 oder kompromittierter Client mit gültigen Credentials

### Impact
- Arbitrary Command Execution als SYSTEM/Root
- Unautorisierte Reboots und Herunterfahrungen
- Cross-host-Pivot, falls die Maschine andere Hosts kontrollieren kann

### Evidence
Aus [wol_host_service.py](wol_host_service.py):

```python
validate_credentials(username, password)  # mit LogonUserW
subprocess.run(["cmd.exe", "/d", "/c", tmp_path], ...)
subprocess.run(["shutdown", "/s", "/t", "0", "/f"], ...)
```

Aus [wol_host_service_linux.py](wol_host_service_linux.py):

```python
subprocess.run(SHUTDOWN_CMD, capture_output=True)
```

### Exploitability
Echt relevant und direkt erreichbar, sobald gültige Zugangsdaten vorhanden sind. Das ist ein echtes Privilege- und Capability-Problem.

### Recommended Fix
- Host-Service nur auf Loopback oder abgeschlossene, verifizierte Segmente zulassen
- `run_batch` als separate, auditierbare, allow-listed Operation modellieren
- Keine generische Shell-/Batch-Ausführung mit SYSTEM/Root erlauben
- Jedes Remote-Command mit Audit-Log und zusätzlicher Autorisierung prüfen

### Verification
- Prüfen, dass der Dienst nur auf definierten Interfaces läuft
- Validierung, dass `run_batch` nur mit expliziter Freigabe abgeschaltet werden kann
- Nachweis, dass jede Remote-Aktion geloggt und auditable ist

---

## Negative / Nicht bestätigte Findings

### Keine bestätigte Command-Injection im geprüften Pfad
Die Aufrufe nutzen explizite Argumentlisten und keine freie String-Konkatenation. Für `run_batch` besteht ein mächtiger Pfad, aber er ist nach erfolgreicher Authentifizierung und zusätzlicher Freischaltung auf dem Host erreichbar. Es konnte kein direkter Auth-Bypass oder Injection-Fehler im reviewed Code nachgewiesen werden.

### Keine bestätigte fehlende Autorisierung auf Code-Ebene
Die geprüften Handler prüfen vor Shutdown/Reboot/Batch die Credentials und in `run_batch` zusätzlich die lokale Freischaltung. Ein fehlender Autorisierungscheck ist im Code nicht belegbar. Das eigentliche Problem ist vielmehr die hochprivilegierte Natur der Operationen und die ungesicherte Transport-Schicht.

---

## Cross-Platform Review

Die Sicherheitslage ist konsistent über die Plattformen hinweg:

- Windows: Host-Service läuft als Service/SYSTEM; `LogonUserW` validiert Benutzer; `shutdown /s /r` wird direkt ausgeführt.
- Linux: Host-Service läuft als Root und authentifiziert über PAM; `systemctl poweroff/reboot` wird ausgeführt.
- macOS: Host-Service verwendet denselben Musterpfad mit PAM und `shutdown -h/-r now`.
- Der gemeinsame Schwachpunkt ist die gleiche Architektur: unverschlüsselter TCP-Verkehr, getrennte Authentifizierung pro Request und privilegierte Remote-Aktion ohne sichere Transport- oder session-bound Identity-Mechanismen.

---

## Gesamturteil

Die Anwendung ist technisch als leistungsfähiger LAN-Controller für vertraute Admins konzipiert, aber im jetzigen Status nicht als sicherer, verteilungsfähiger Remote-Access-Mechanismus für untrusted Netzwerke geeignet. Der wichtigste Verbesserungsbereich ist die Abkehr von Klartext-Host-Service-Kommunikation und die Reduktion auf vertrauenswürdige, verifizierte Kommunikationspfade.

### Empfohlene Prioritäten

1. **TLS / sichere Authentifizierung am Host-Service** (High)
2. **RDP-Credential-Handling verschärfen** (Medium)
3. **Privilegien für `run_batch` und Shutdown auf strenge, auditierbare Regeln reduzieren** (High)

---

## Anhang: Geprüfte Sicherheitsgrenzen

| Boundary | Authentifizierung | Autorisierung | Transport | Credential-Exposition | Host-Identitätsprüfung |
|---|---|---|---|---|---|
| Client ↔ Netzwerk | Benutzer-Login | UI-basiert | Plaintext (LAN) | Nein | Nein |
| Netzwerk ↔ Host-Service | Benutzername/Passwort pro Request | Per Request | Plaintext (TCP 8765) | Ja (Klartext) | Nein |
| Host-Service ↔ OS | Windows Credential Auth / PAM | SYSTEM/Root | N/A | N/A | N/A |
| RDP-Client ↔ RDP-Server | Embedded Credentials in .rdp | mstsc/xfreerdp | Plaintext (RDP) | Ja (in Datei) | Nein (authentication level:i:0) |

---

## Abschlussnote

Die geprüften Risiken sind substantiiert und im Code nachvollziehbar. Es gibt keine nachgewiesene Authentifizierungslücke im engeren Codepfad, aber drei reale Sicherheitsprobleme mit direkter praktischer Auswirkung in untrusted Netzen. Die wichtigsten Gegenmaßnahmen sind:

- Transportverschlüsselung und sichere Authentifizierung für den Host-Service
- Reduktion der privilegierten Remote-Aktionen auf minimal notwendige, auditierbare Pfade
- Sicheres Credential-Handling für RDP und lokale Speicherung
