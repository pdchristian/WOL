# WOL Host Service — Wire Protocol Specification

**Version:** 6 (Host Service 2.2.x) · **Port:** TCP **8765** · **Encoding:** UTF-8

Referenzimplementierungen:

| Plattform | Datei | Auth |
|---|---|---|
| Windows | `wol_host_service.py` | `LogonUserW` (interaktive Anmeldung) |
| Linux/Ubuntu | `wol_host_service_linux.py` | PAM (`pamela`) |

> **Diese SPEC ist der Vertrag.** Änderungen am Protokoll Müssen hier
> dokumentiert **und** gegen `protocol/schema/` + `tests/test_protocol_schema.py`
> validiert werden. Android-/Desktop-Clients implementieren ausschließlich,
> was hier steht.

---

## 1. Transport

* Eine TCP-Verbindung pro Kommando (verbinden → senden → lesen → schließen).
* **Request:** genau **eine** JSON-Zeile, abgeschlossen mit `\n` (LF).
  Maximal `65536` Bytes (`MAX_REQUEST_BYTES`).
* **Response:** genau **eine** JSON-Zeile, abgeschlossen mit `\n`.
* Kein TLS, keine Framing-Header — Plaintext im LAN (Gegenstelle ist durch
  Auth geschützt). Clients sollten Sende-/Lese-Timeouts von ≥ 10 s setzen.
* Antworten können je Kommando unterschiedlich groß sein; `run_batch` liefert
  bis zu ~128 KB (Output-Limits, siehe §5).

## 2. Request-Format

```json
{"command": "status", "username": "...", "password": "..."}
```

| Feld | Typ | Bedeutung |
|---|---|---|
| `command` | string | `status` \| `metrics` \| `shutdown` \| `reboot` \| `run_batch` (case-insensitive, wird getrimmt) |
| `username` | string | Für alle Kommandos außer `status` erforderlich (`DOMAIN\User` oder lokal). |
| `password` | string | Passwort zu `username`. |
| `ts` | number | **v6** Anti-Replay: Unix-Timestamp (Sekunden, UTC) beim Senden. Nur für `shutdown`/`reboot`/`run_batch` geprüft. |
| `nonce` | string | **v6** Anti-Replay: frischer Zufallswert (1–64 Zeichen), pro Request eindeutig. Host lehnt bereits gesehene Nonces ab. |
| *command-spezifisch* | — | `watch` (metrics), `script`/`timeout` (run_batch) — siehe unten. |

Schema: [`schema/request.json`](schema/request.json)

## 3. Response-Format (gemeinsamer Kern)

Jede Antwort enthält mindestens:

```json
{"status": "ok" | "error", "message": "..."}
```

* `status` — `"ok"` oder `"error"` — **in jeder Antwort vorhanden**.
* `message` — kurzer, menschenlesbarer Text. **Nicht als Programmlogik
  auswerten** (Formulierungen können sich ändern); für Fehlerentscheidungen
  ausschließlich `status` verwenden.
* ⚠ `message` ist **nicht** in jeder Antwort enthalten: die
  Daten-Antworten `metrics` (ok) und `run_batch` (ok) liefern **kein**
  `message` — nur die Ack-/Error-Antworten (`status`, `shutdown`, `reboot`,
  alle Fehlerfälle) tun es. Clients dürfen `message` also nie voraussetzen.

### Kanonische Fehlermeldungen

| Auslöser | Antwort |
|---|---|
| Kein/leeres Byte-Input | *(keine Antwort, Verbindung schließt)* |
| `json.loads` schlägt fehl | `{"status":"error","message":"Invalid JSON"}` |
| JSON ist kein Objekt | `{"status":"error","message":"Invalid request"}` |
| `command` unbekannt | `{"status":"error","message":"Unknown command: <cmd>"}` |
| Auth fehlgeschlagen | `{"status":"error","message":"Authentication failed"}` |
| **v6** Brute-Force-Lockout aktiv | `{"status":"error","message":"Too many failed attempts. Try again in <n>s.","retry_after":<n>}` |
| **v6** Replay/Zeitstempel abgelehnt | `{"status":"error","message":"Replay detected (nonce already used)"}` / `"Request timestamp out of range (>120s skew)"` / `"Missing replay protection (ts/nonce): update the Wake-on-LAN Manager client"` |

Schema: [`schema/response-error.json`](schema/response-error.json)

## 4. Kommandos

### 4.1 `status` — Reachability-Test (ohne Auth)

```json
→ {"command": "status"}
← {"status": "ok", "message": "online"}
```

Dient Clients als Host-Check (Port offen? Dienst läuft?). Benötigt **keine**
Credentials.

### 4.2 `metrics` — Dashboard-Metriken (mit Auth)

Request:

```json
{"command": "metrics", "username": "u", "password": "p",
 "watch": ["llama-server.exe:8080", "backup-sync.exe"]}
```

* `watch` optional, Liste von Prozessnamen (`name.exe`) oder
  `name.exe:port`; **max. 8** Einträge (`WATCH_MAX_ENTRIES`), Überzählige
  werden ignoriert. `:port` = Loopback-Check (250 ms) + Modell-Abfrage (§4.2.1).

Antwort (`status: "ok"`):

```json
{
  "status": "ok",
  "protocol": 6,
  "hostname": "FRACTAL",
  "cpu": 63.4,
  "cpu_count": 16,
  "ram_used": 12345678901,
  "ram_total": 34359738368,
  "uptime": 274320,
  "gpu": 64,
  "vram_used": 19327352832,
  "vram_total": 25769803776,
  "gpu_name": "NVIDIA GeForce RTX 4090",
  "processes": {
    "llama-server.exe:8080": {
      "running": true, "count": 1, "pid": 12044, "cpu": 12.5,
      "ram": 8589934592, "uptime": 10024,
      "model": "Qwen3.8-Flash-256k-62",
      "api_port": 8080, "api_port_open": true,
      "models": ["Qwen3.8-Flash-256k-62", "DeepSeek-R1-Distill-32B"],
      "model_metrics": {
        "Qwen3.8-Flash-256k-62": { "prompt_tps": 261.15, "predicted_tps": 26.65, "total_tokens": 77427 }
      }
    },
    "backup-sync.exe": { "running": false }
  }
}
```

Feld-Semantik:

| Feld | Typ | Bedeutung |
|---|---|---|
| `protocol` | int | Host-Protokollversion (Clients für Feature-Gating, §7). |
| `cpu` | number\|null | CPU-% (0–100) über alle Kerne. |
| `cpu_count` | int\|null | Logische Kerne. |
| `ram_used`/`ram_total` | int\|null | Bytes. |
| `uptime` | int\|null | Sekunden seit Boot. |
| `gpu` | number\|null | GPU-Auslastung % — `null` ohne NVIDIA/`nvidia-smi`. |
| `vram_used`/`vram_total` | int\|null | Bytes — `null` ohne GPU. |
| `gpu_name` | string\|null | GPU-Produktname. |
| `hostname` | string | `socket.gethostname()`. |

**Alle Werte `null` = „nicht ermittelbar“** (psutil/nvidia-smi defekt). Basis-
felder (`status`, `protocol`, `hostname`) sind immer vorhanden.

#### 4.2.1 `processes` (Watch-Liste)

* Key = **Originaler** Watch-Eintrag (z. B. `"llama-server.exe:8080"`).
* Läuft der Prozess **nicht**: nur `{"running": false}`.
* Läuft er: zusätzlich `count` (Instanzen), `pid` (niedrigste PID),
  `cpu` (% über alle Instanzen, 1 Nachkomma), `ram` (Bytes RSS, summiert),
  `uptime` (Sekunden, ältester Instanz).
* `model` (string): aus der Kommandozeile geparst (`-m`/`--model`/`--model=`),
  **nur** llama.cpp-Prozesse; Anzeigename = letzter Pfadabschnitt, bekannte
  Modell-Endungen (.gguf/.ggml/.safetensors/.bin/.pt) abgeschnitten.
  ⚠ Niemals blind `splitext` — Modellnamen enthalten Punkte
  (`Qwen3.8-Flash-256k-62`).
* `:port`-Einträge: zusätzlich `api_port` (int) und `api_port_open` (bool,
  Loopback-Connect im Code, 250 ms).
* `models` (string-Array, max 16): **nur wenn `api_port_open`** — llama-server
  `GET /v1/models`; Alias bevorzugt, sonst Datei-Stem; Resident = Status
  `loaded` **oder** `sleeping` (llama-swap hält Idle-Modelle im RAM).
  Jeder Fehler ⇒ Feld schlicht nicht vorhanden (argv-`model` bleibt Fallback).
* `model_metrics` (object, **v5**): **nur wenn `api_port_open` und mindestens
  ein Modell messbar** — pro geladenem Modell (Key = Anzeigename aus `models`)
  der Durchsatz aus dem llama.cpp-Prometheus-Endpoint
  (`GET /metrics?model=<name>`): `prompt_tps` (Input,
  `llamacpp:prompt_tokens_seconds`) und `predicted_tps` (Output,
  `llamacpp:predicted_tokens_seconds`), beides tokens/s (number). Die Gauges
  sind bei Idle-Server 0 — der Host **haelt den zuletzt gueltigen (nicht-Null)
  Wert pro (Port, Modell) fest** und liefert ihn weiter aus, statt 0 zu
  melden. `total_tokens` (int): Summe aus den kumulativen Zaehlern
  `llamacpp:prompt_tokens_total` + `llamacpp:n_decode_total` (fehlender
  Zaehler zaehlt als 0), waechst kontinuierlich und wird frisch uebernommen
  (nur wenn > 0). Einzelne Keys fehlen, wenn nur
  ein Gauge lesbar war (NaN/Inf = nicht messbar); kein Feld, wenn gar nichts
  messbar war (Dashboard zeigt dann die Modell-Zeile ohne t/s).

Schema: [`schema/response-metrics.json`](schema/response-metrics.json)

### 4.3 `shutdown` / `reboot` (mit Auth)

```json
→ {"command": "shutdown", "username": "u", "password": "p",
   "ts": 1761234567.89, "nonce": "3f9a2c1e..."}
← {"status": "ok", "message": "shutdown accepted"}
```

* Antwort kommt **vor** der Ausführung (Client muss die Bestätigung erhalten,
  bevor der Host herunterfährt — 1 s Verzögerung eingebaut).
* `message` = `"<command> accepted"`.
* Auth-Fehler ⇒ `"Authentication failed"` (Standard).
* **v6 Anti-Replay** (`ts` + `nonce`, siehe §2): der Host verwirft Requests
  mit Clock-Skew > `REPLAY_MAX_SKEW_SECONDS` oder bereits verwendetem Nonce
  (Fehlermeldungen siehe §3). Ohne `ts`/`nonce` verhält sich der Host wie
  v5, solange `require_replay` aus ist (Default); ist sie an
  (`--require-replay`), fehlen dann zwingend die Felder ⇒ Fehler.

### 4.4 `run_batch` (mit Auth + Maschinen-Freischaltung)

```json
→ {"command": "run_batch", "username": "u", "password": "p",
   "script": "@echo off\r\necho hello", "timeout": 60,
   "ts": 1761234567.89, "nonce": "3f9a2c1e..."}
← {"status": "ok", "exit_code": 0, "stdout": "hello\r\n", "stderr": "",
   "duration_ms": 152, "truncated": false}
```

* **Doppeltes Opt-in:** Auth **und** pro Maschine per
  `--enable-batch` (sonst `status: "error"`,
  `message: "Batch execution disabled on host ..."`).
* **v6 Anti-Replay:** `ts`/`nonce` werden wie bei `shutdown`/`reboot`
  geprüft (§4.3).
* `script` (string, max **32 000** Zeichen) wird als temporäre `.cmd`
  ausgeführt (Windows) bzw. über die Shell (Linux).
* `timeout` (Sekunden, optional, Default **120**, hart auf **5–3600** begrenzt).
* `stdout`/`stderr`: je max **64 000** Zeichen; `truncated: true` wenn
  abgeschnitten. `exit_code` = Prozess-Exit-Code.
* Fehler: `"Empty script"`, `"Script too long (max 32000 characters)"`,
  `"Batch timed out after <n> s"`, `"Could not run batch: <osError>"`.

Schema: [`schema/response-run_batch.json`](schema/response-run_batch.json)

## 5. Limits & Konstanten (Referenz)

| Konstante | Wert | Quelle |
|---|---|---|
| `DEFAULT_PORT` | 8765 | beide Services |
| `MAX_REQUEST_BYTES` | 65536 | beide |
| `PROTOCOL_VERSION` | 6 | beide |
| `WATCH_MAX_ENTRIES` | 8 | beide |
| `WATCH_PORT_TIMEOUT_S` | 0.25 | beide |
| `WATCH_MODELS_TIMEOUT_S` | 0.6 | beide |
| `WATCH_MAX_MODELS` | 16 | beide |
| `MODEL_FILE_EXTS` | .gguf .ggml .safetensors .bin .pt | beide |
| `MAX_SCRIPT_CHARS` | 32000 | beide |
| `BATCH_TIMEOUT_DEFAULT` / MIN / MAX | 120 / 5 / 3600 | beide |
| `MAX_BATCH_OUTPUT_CHARS` | 64000 | beide |
| `GPU_CACHE_SECONDS` | 1.5 | beide |
| `REPLAY_PROTECTED_COMMANDS` | shutdown, reboot, run_batch | beide |
| `REPLAY_MAX_SKEW_SECONDS` | 120 | beide |
| `NONCE_TTL_SECONDS` | 300 | beide |
| `NONCE_CACHE_MAX` | 4096 | beide |
| `AUTH_MAX_ATTEMPTS` | 5 (config: `auth_max_attempts`) | beide |
| `AUTH_WINDOW_SECONDS` | 900 | beide |
| `AUTH_LOCKOUT_BASE_SECONDS` / MAX | 60 / 3600 | beide |

## 6. Sicherheitsmodell

* **Kein TLS** — ausschließlich LAN-Vertrauen; Passwörter laufen im Klartext
  über die Leitung. Niemals über WAN exponieren.
* Auth-Pflicht für `metrics`, `shutdown`, `reboot`, `run_batch`
  (Windows: `LogonUserW`; Linux: PAM). `status` ist unauthentifiziert und
  liefert nur die Erreichbarkeit.
* `run_batch` führt Code als SYSTEM (Win) / root (Linux) aus — deshalb
  standardmäßig deaktiviert und nur per `--enable-batch` auf der Zielmaschine
  scharf. Clients müssen den Fehlerfall „disabled“ abfangen.
* **Brute-Force-Throttling (v6):** fehlgeschlagene Auths zählen pro
  (Client-IP, Benutzer); nach `AUTH_MAX_ATTEMPTS` im Fenster folgt ein
  exponentieller Lockout (60 s, verdoppelt, max. 1 h). Antwort enthält
  `retry_after` (siehe §3).
* **Audit-Log (v6):** Auth-Fehler, Lockouts, Replay-Verwürfe sowie
  akzeptierte `shutdown`/`reboot`/`run_batch`-Kommandos schreibt der Host
  als `AUTH …`-Zeilen ins Service-Log (ohne Passwörter). `metrics` wird
  nicht protokolliert (Polling-Flut).
* **Anti-Replay (v6):** `ts` + `nonce` auf den privilegierten Kommandos
  (§4.3/§4.4). `require_replay` (service.json, Default `false`; CLI
  `--require-replay` / `--replay-optional`) entscheidet, ob Requests ohne
  die Felder abgelehnt werden.
* **Firewall-Scope (v6):** die Windows-Inbound-Regel beschränkt die
  Quell-Adressen standardmäßig auf `LocalSubnet` (config:
  `firewall_remote_ips`, CLI `--firewall-scope`); `any` öffnet die Regel
  wie früher. Linux: ufw-Regeln auf die lokalen Subnetze (CIDR) begrenzt.

## 7. Protokoll-Versionierung

`protocol` im `metrics`-Response (und nur dort) steuert Feature-Gating:

| Version | Added | Client-Verhalten bei älterem Host |
|---|---|---|
| 1 | Basis (`status`/`shutdown`/`reboot`) | — |
| 2 | `metrics`, `run_batch` | Dashboard ausblenden |
| 3 | `watch` → `processes` | Dienste-Panel ausblenden |
| 4 | `models` pro Watch-Eintrag | argv-`model`-Fallback zeigen |
| 5 | `model_metrics` pro Watch-Eintrag (`prompt_tps`/`predicted_tps` latchen zuletzt gueltige Werte; `total_tokens` = `prompt_tokens_total` + `n_decode_total`) | Modell-Zeile ohne t/s anzeigen |
| 6 | Anti-Replay `ts`/`nonce` auf `shutdown`/`reboot`/`run_batch` (§4.3/§4.4); Auth-Throttling mit `retry_after` (§3); Audit-Log; Firewall-Quellscope | Requests ohne `ts`/`nonce` senden (Host-Accept solange `require_replay` aus); `retry_after` ignorieren |

Regel: **Nur additive Änderungen.** Neue Felder müssen für ältere Clients
ignorierbar sein. Neue Pflichtfelder oder Semantic-Änderungen ⇒ neue Major-
Kommandos statt Bruch. Jede Änderung aktualisiert SPEC + Schema + Examples
+ Contract-Test.

## 8. Referenz-Client

`wol_app/host_service_client.py` (Python/Qt) — `_request()` ist der
kanonische Transport; `get_metrics()` gated Features anhand `protocol`;
`run_batch()` nutzt Timeout + 5 s Socket-Overhead. Ein Android-Client muss
exakt dieses Verhalten nachbilden.
