# WOL Host Service — Wire Protocol Specification

**Version:** 10 (Host Service 2.5.x) · **Port:** TCP **8765** · **Encoding:** UTF-8

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
| `api_key` | string | **v10** Key, den die Inferenz-API auf einem überwachten Port erwartet (max. 128 Zeichen, nur druckbares ASCII). Der Host sendet ihn als `Authorization: Bearer <key>` bei allen Loopback-Probes (`/v1/models`, `/health`, `/props`, `/metrics`). Nur für `metrics` ausgewertet. |
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
| **v6** Host in öffentlichem Netzwerk (Gate aktiv) | `{"status":"error","message":"Blocked: host is connected to a public network (enable on the host with --allow-public on)","error":"network_untrusted"}` |

Schema: [`schema/response-error.json`](schema/response-error.json)

## 4. Kommandos

### 4.1 `status` — Reachability-Test (ohne Auth)

```json
→ {"command": "status"}
← {"status": "ok", "message": "online", "os": "ubuntu"}
```

Dient Clients als Host-Check (Port offen? Dienst läuft?). Benötigt **keine**
Credentials.

* `os` (**v8**): normalisierte Plattform des Hosts — `"windows"`, `"macos"`
  oder die Linux-Distribution (`"ubuntu"`, `"debian"`, …; `"linux"` wenn
  `/etc/os-release` nicht lesbar). Bewusst **auth-frei**, damit der
  Netzwerk-Scan Geräte ohne Credentials beschriften kann; ein ICMP-Ping
  verrät die Plattform über das TTL ebenfalls. Ältere Services lassen das
  Feld weg.

### 4.2 `metrics` — Dashboard-Metriken (mit Auth)

Request:

```json
{"command": "metrics", "username": "u", "password": "p",
 "watch": ["llama-server.exe:8080", "backup-sync.exe", ":8081"],
 "api_key": "secret"}
```

* `watch` optional, Liste von Prozessnamen (`name.exe`) oder
  `name.exe:port`; **max. 8** Einträge (`WATCH_MAX_ENTRIES`), Überzählige
  werden ignoriert. `:port` = Loopback-Check (250 ms) + Modell-Abfrage (§4.2.1).
  **v7:** Port-only-Einträge (`":8081"` oder nacktes `"8081"`) beobachten nur
  die API auf dem Port — ohne Prozessnamen-Prüfung.
* `api_key` optional (**v10**): Key für die Inferenz-API der überwachten
  Ports. Der Host hängt ihn als `Authorization: Bearer <key>` an jede
  Loopback-Anfrage. Server, die mit API-Key starten (`llama-server
  --api-key`, Strata `API_KEY`), antworten ohne Key mit **401** auf
  `/metrics` — dem Dashboard fehlt dann `requests_active`, und der
  Inferenz-Blitz bleibt bernsteinfarben („Aktivität nicht messbar“), obwohl
  inferiert wird. Leere, überlange (>`WATCH_API_KEY_MAX_CHARS`) oder
  nicht-druckbare Werte werden ignoriert; ältere Hosts kennen das Feld nicht.

Antwort (`status: "ok"`):

```json
{
  "status": "ok",
  "protocol": 9,
  "hostname": "FRACTAL",
  "os": "windows",
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
      "api_port": 8080, "api_port_open": true, "api_up": true,
      "api_kind": "llama.cpp",
      "api_features": ["models", "health", "props", "metrics"],
      "api_info": { "server": "build 5023", "context": 8192, "slots": 4 },
      "models": ["Qwen3.8-Flash-256k-62", "DeepSeek-R1-Distill-32B"],
      "model_metrics": {
        "Qwen3.8-Flash-256k-62": { "prompt_tps": 261.15, "predicted_tps": 26.65, "total_tokens": 77427 }
      },
      "requests_active": 2
    },
    ":8081": {
      "running": false,
      "api_port": 8081, "api_port_open": true, "api_up": true,
      "api_kind": "openai",
      "api_features": ["models", "health", "metrics"],
      "api_info": { "server": "Strata 0.1.30", "context": 262144, "slots": 1 },
      "models": ["qwen3.8-flash-next-iq3_s"],
      "model_metrics": {
        "qwen3.8-flash-next-iq3_s": { "prompt_tps": 398.0, "predicted_tps": 72.2, "total_tokens": 19456405 }
      },
      "requests_active": 0
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
| `os` | string | **v8** — Plattform des Hosts (`windows`/`macos`/Linux-Distribution), siehe §4.1. |

**Alle Werte `null` = „nicht ermittelbar“** (psutil/nvidia-smi defekt). Basis-
felder (`status`, `protocol`, `hostname`, `os`) sind immer vorhanden.

#### 4.2.1 `processes` (Watch-Liste)

* Key = **Originaler** Watch-Eintrag (z. B. `"llama-server.exe:8080"`).
* **Port-only-Eintrag (v7):** `":8080"` oder ein nacktes `"8080"` nennt
  keinen Prozess — der Host ueberwacht nur die API auf dem Port, egal welche
  Software dahinter laeuft. Solche Einträge melden `running: false` (kein
  Prozess beobachtet), aber `api_port`/`api_port_open`/`api_up` zeigen, ob
  die API lebt. Der Port wird **unabhaengig von einem Prozessnamen-Treffer**
  geprobt.
* Läuft der Prozess **nicht** (und kein Port offen): nur `{"running": false}`.
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
* `api_up` (bool, **v7**): **nur wenn `api_port_open`** — `GET /v1/models`
  antwortete 200 mit einem JSON-Objekt (OpenAI-Vertrag erfuellt, egal welche
  Software). `models` kann trotzdem leer sein (kein Modell geladen).
* `api_kind` (string, **v7**): **nur wenn `api_port_open`** — grobe
  Server-Klassifikation aus `/props`/`/health`: `"llama.cpp"` (llama.cpp und
  kompatible Forks wie Strata: `build_info`/`total_slots`/`chat_template`),
  `"openai"` (reiner OpenAI-Vertrag) oder `"unknown"`.
* `api_features` (string-Array, **v7**): **nur wenn `api_port_open`** — die
  Endpunkte, die geantwortet haben (Teilmenge von `models`,`health`,
  `props`,`metrics`). Das Dashboard kann daraus ableiten, was verfuegbar ist,
  statt still zu scheitern.
* `api_info` (object, **v7**): **nur wenn `api_port_open` und mindestens ein
  Extra ermittelbar** — Anzeige-Zusatz aus `/props`/`/health`: `server`
  (Build/Version, string), `context` (max. Kontextgroesse, int), `slots`
  (gleichzeitige Slots, int), `model_alias` (string). Einzelne Keys fehlen,
  wenn die Quelle sie nicht liefert.
* `models` (string-Array, max 16): **nur wenn `api_port_open`** — OpenAI-API
  `GET /v1/models`; Alias bevorzugt, sonst Datei-Stem; Resident = Status
  `loaded` **oder** `sleeping` (llama-swap hält Idle-Modelle im RAM).
  Jeder Fehler ⇒ Feld schlicht nicht vorhanden (argv-`model` bleibt Fallback).
* `model_metrics` (object, **v5**): **nur wenn `api_port_open` und mindestens
  ein Modell messbar** — pro geladenem Modell (Key = Anzeigename aus `models`)
  der Durchsatz (`prompt_tps` Input, `predicted_tps` Output, tokens/s) und
  `total_tokens` (int, kumulativ). Der Host versteht **zwei** Body-Formate
  von `GET /metrics?model=<name>`:
  * **Prometheus-Text** (llama.cpp): Gauges `llamacpp:prompt_tokens_seconds`
    / `llamacpp:predicted_tokens_seconds`; `total_tokens` =
    `llamacpp:prompt_tokens_total` + `llamacpp:n_decode_total`.
  * **JSON** (andere OpenAI-Server, z. B. Strata, **v7**): gemappt auf
    dieselben Keys — `predicted_tps` ← `live.tok_s`, `prompt_tps` ←
    `live.prefill_tok_s_mean`, `total_tokens` ← `totals.prompt_tokens` +
    `totals.output_tokens` (first-hit-Kandidatenliste).
  Die Gauges sind bei Idle-Server 0 — der Host **haelt den zuletzt gueltigen
  (nicht-Null) Wert pro (Port, Modell) fest** und liefert ihn weiter aus,
  statt 0 zu melden. `total_tokens` waechst kontinuierlich und wird frisch
  uebernommen (nur wenn > 0). Einzelne Keys fehlen, wenn nur ein Wert lesbar
  war (NaN/Inf = nicht messbar); kein Feld, wenn gar nichts messbar war
  (Dashboard zeigt dann die Modell-Zeile ohne t/s).
* `requests_active` (int ≥ 0, **v9**): **nur wenn `api_port_open` und
  `/metrics` lesbar** — wie viele Inferenz-Requests der Server **gerade
  jetzt** verarbeitet. Frisch gelesen (im Gegensatz zu den latched
  Durchsatz-Gauges), daher verlaessliches "Job laeuft"-Signal fuer die
  Geraeliste. Ein einziges `GET /metrics` (ohne model-Filter) pro Poll,
  parallel zur Modell-Liste:
  * **Prometheus-Text** (llama.cpp): `llamacpp:requests_processing` +
    `llamacpp:requests_deferred` (Summe; beide Gauges melden die echte
    aktuelle Slot-/Queue-Anzahl, kein Latching).
  * **JSON** (andere OpenAI-Server, z. B. Strata): 1 wenn `live.queued` > 0
    oder `live.state`/`live.phase` eine nicht-Idle-Phase nennt
    (Idle = `idle`/`waiting`/`ready`) oder `live.tok_s` /
    `live.prefill_tok_s_mean` > 0; sonst 0.
  Kein Feld, wenn `/metrics` nicht antwortet/parsebar (Client verbirgt dann
  sein Inferenz-Badge statt zu raten).

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
| `PROTOCOL_VERSION` | 10 | beide |
| `WATCH_MAX_ENTRIES` | 8 | beide |
| `WATCH_API_KEY_MAX_CHARS` | 128 | beide |
| `WATCH_PORT_TIMEOUT_S` | 0.25 | beide |
| `WATCH_MODELS_TIMEOUT_S` | 0.6 | beide |
| `WATCH_MAX_MODELS` | 16 | beide |
| `WATCH_PROBE_TTL_S` | 10 | beide |
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
  liefert nur die Erreichbarkeit — seit v8 zusätzlich die Plattform (`os`),
  was keine vertrauliche Information ist (ein ICMP-Ping verrät sie über das
  TTL ebenfalls) und Clients eine agentenlose Beschriftung im Netzwerk-Scan
  erlaubt.
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
* **Netzwerk-Profil-Gate (v6):** Auf einem öffentlich klassifizierten
  Netzwerk (Windows: NLM-Kategorie `Public`; Linux: alle aktiven
  firewalld-Zonen `public`) sind `shutdown`/`reboot`/`run_batch`
  standardmäßig gesperrt (Antwort mit `error: "network_untrusted"`,
  Audit-Zeile `NETWORK-REJECT`); `status`/`metrics` bleiben verfügbar.
  Undetektierbare Profile sperren nie. Steuerung host-seitig:
  `--network-gate on|off` (Default on) und `--allow-public on|off`
  (Override pro Maschine). Der Client prüft zusätzlich client-seitig
  (read-only-Modus im UI, abschaltbar in den Einstellungen) — die
  Host-Prüfung ist maßgeblich.
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
| 7 | Port-only-Watch-Einträge (`:8080`/`8080`), Port-Probe ohne Prozess-Treffer; `api_up`/`api_kind`/`api_features`/`api_info` pro Watch-Eintrag; JSON-`/metrics`-Mapping (nicht-llama.cpp-Server) | Port-only-Einträge zeigen nichts an; Namens-Watch funktioniert wie bei v3–v5; neue Felder ignorieren |
| 8 | `os` auf `status` (auth-frei) und `metrics` — Plattform des Hosts (§4.1) | Plattform aus TTL/Fingerprint-Heuristik schätzen oder Spalte leer lassen |
| 9 | `requests_active` pro Watch-Eintrag (Inferenz laeuft gerade — llama.cpp `requests_processing`+`requests_deferred`, JSON-Server `live.*`) | Inferenz-Badge in der Geraeliste nicht anzeigen |
| 10 | `api_key` auf `metrics` — `Authorization: Bearer <key>` fuer alle Loopback-Probes der ueberwachten Ports (§4.2) | Feld weglassen; bei Servern mit API-Key bleibt `requests_active`/`model_metrics` unbeantwortbar (Bernstein-Badge) |

Regel: **Nur additive Änderungen.** Neue Felder müssen für ältere Clients
ignorierbar sein. Neue Pflichtfelder oder Semantic-Änderungen ⇒ neue Major-
Kommandos statt Bruch. Jede Änderung aktualisiert SPEC + Schema + Examples
+ Contract-Test.

## 8. Referenz-Client

`wol_app/host_service_client.py` (Python/Qt) — `_request()` ist der
kanonische Transport; `get_metrics()` gated Features anhand `protocol`;
`run_batch()` nutzt Timeout + 5 s Socket-Overhead. Ein Android-Client muss
exakt dieses Verhalten nachbilden.
