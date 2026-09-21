"""WOL Host Service - Linux service for remote control via TCP.

This service runs on the *target* Linux machine (Ubuntu port) and listens on
TCP port 8765. It is the Linux counterpart of the Windows
``WOL/wol_host_service.py`` and speaks the exact same single-line JSON
protocol (protocol version 2), so Windows clients, the Ubuntu port and the
Android client (WOL-Android) can all talk to it unchanged:

    {"command": "shutdown" | "reboot" | "status" | "metrics" | "run_batch",
     "username": "...", "password": "..."}

and answers with a single-line JSON response:

    {"status": "ok" | "error", "message": "..."}   (plus command-specific fields)

Authentication: the supplied system credentials are validated through PAM
(``pamela``, service ``login``) - the Linux equivalent of the Windows
``LogonUserW`` path. The macOS variant reuses this core: /etc/pam.d/login
there routes to ``pam_opendirectory``, so the same code authenticates local
and directory accounts. A username of the form ``DOMAIN\\User`` is reduced
to the user part before authentication.

Commands (identical to the Windows service):
    status    - no authentication required, answers ``{"status": "ok", ...}``
    metrics   - authenticated; answers with CPU/RAM/GPU/VRAM metrics
                (``cpu``, ``ram_used``/``ram_total``, ``gpu``,
                ``vram_used``/``vram_total``, ``gpu_name``, ``hostname``,
                ``uptime``, ``protocol``). GPU fields are ``null`` when no
                NVIDIA GPU/``nvidia-smi`` is available.
    run_batch - authenticated AND gated: executes a bash script
                (``script`` field, ``timeout`` optional) and answers with
                ``exit_code``/``stdout``/``stderr``/``duration_ms``.
                Disabled by default - enable per machine with
                ``--enable-batch`` (the service runs as root, so executing
                arbitrary scripts is a powerful operation).
    shutdown  - shut the machine down immediately (``systemctl poweroff``)
    reboot    - reboot the machine immediately (``systemctl reboot``)

CLI usage (run with sudo for install/uninstall/start/stop):

    wol_host_service.py --install        Install systemd unit + firewall rule
    wol_host_service.py --uninstall      Remove firewall rule + systemd unit
    wol_host_service.py --start          Start the service
    wol_host_service.py --stop           Stop the service
    wol_host_service.py --status         Show service status
    wol_host_service.py --enable-batch   Allow run_batch on this machine
    wol_host_service.py --disable-batch  Forbid run_batch (default)
    wol_host_service.py --require-replay Require ts/nonce on privileged commands
    wol_host_service.py --replay-optional Accept legacy requests without ts/nonce
    wol_host_service.py --run            Run in the foreground (debugging)
    wol_host_service.py --port N         Port override for --run (default 8765)

Note: ``--enable-batch`` must be run as the same user that runs the service
(root under systemd), because the opt-in is stored in the service config
directory (see ``_LOG_DIR`` below).
"""

import json
import math
import os
import re
import shlex
import shutil
import socket
import socketserver
import subprocess
import sys
import threading
import time
import traceback
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

SERVICE_NAME = "wol-host-service"
SERVICE_DISPLAY_NAME = "WOL Host Service"
SERVICE_DESCRIPTION = (
    "Accepts remote shutdown/reboot commands from the Wake-on-LAN Manager "
    "over TCP port 8765 (JSON protocol, PAM credential authentication)."
)
FIREWALL_RULE_NAME = "WOL Host Service"
DEFAULT_PORT = 8765
MAX_REQUEST_BYTES = 65536

# Protocol version reported in the "metrics" response so the client can
# detect a host service that is too old for the dashboard features.
# v3 added the optional "watch" field on "metrics" (response: "processes").
# v4 adds "models" per watch entry with an open API port (llama-server
#    GET /v1/models -> the model names currently resident on the server).
# v5 adds "model_metrics" per watch entry: prompt/generation throughput in
#    tokens/s per model (llama.cpp GET /metrics?model=<name> -> the
#    llamacpp:prompt_tokens_seconds / llamacpp:predicted_tokens_seconds
#    Prometheus gauges).
# v6 adds optional anti-replay fields on the privileged commands
#    (shutdown/reboot/run_batch): "ts" (Unix seconds) + "nonce" (random
#    string). The service rejects stale timestamps and reused nonces; with
#    require_replay enabled (service.json) unsigned requests are refused.
PROTOCOL_VERSION = 6

# Platform shutdown/reboot commands used by the TCP handler. The macOS
# variant (wol_host_service_macos.py) reuses this module as its core and
# overrides these before serving; the Linux default stays systemctl.
SHUTDOWN_CMD = ["systemctl", "poweroff"]
REBOOT_CMD = ["systemctl", "reboot"]

# Max number of entries in a "watch" list (client configures e.g.
# ["llama-server", "ollama:11434"] - keep the loop bounded).
WATCH_MAX_ENTRIES = 8
# Seconds for the loopback connect() of the API-port check.
WATCH_PORT_TIMEOUT_S = 0.25
# Seconds for the HTTP GET of the llama-server model list.
WATCH_MODELS_TIMEOUT_S = 0.6
# Max model names surfaced per watch entry.
WATCH_MAX_MODELS = 16

# File extensions stripped from model file names for display. ONLY these -
# never a blind splitext(): model ids like "Qwen3.8-Flash-256k-62" contain
# dots that belong to the name (splitext would truncate to "Qwen3").
MODEL_FILE_EXTS = (".gguf", ".ggml", ".safetensors", ".bin", ".pt")

# Limits for run_batch (the service runs as root - keep these strict).
MAX_SCRIPT_CHARS = 32_000
BATCH_TIMEOUT_DEFAULT = 120
BATCH_TIMEOUT_MIN = 5
BATCH_TIMEOUT_MAX = 3600
MAX_BATCH_OUTPUT_CHARS = 64_000

# Seconds a collected GPU sample is reused (nvidia-smi costs ~50-300 ms and
# would otherwise be spawned on every dashboard poll).
GPU_CACHE_SECONDS = 1.5

# PAM service name used for credential validation (present on every PAM
# distribution, same policy set as interactive logins).
PAM_SERVICE = "login"

# --- Service diagnostics logging -------------------------------------------
#
# When started by systemd, stdout/stderr go to the journal; we still keep a
# plain log file (like the Windows service under %ProgramData%) so problems
# are visible even when the journal is not accessible. Root uses
# /var/log/wol-host-service, unprivileged runs fall back to
# ~/.local/share/wol-host-service. The env override is mainly for testing.

if hasattr(os, "geteuid") and os.geteuid() == 0:
    _DEFAULT_DIR = "/var/log/wol-host-service"
else:
    _DEFAULT_DIR = os.path.join(
        os.path.expanduser("~"), ".local", "share", "wol-host-service"
)

_LOG_DIR = os.environ.get("WOL_HOST_SERVICE_DIR", _DEFAULT_DIR)
_LOG_FILE = os.path.join(_LOG_DIR, "wol_host_service.log")

# Persisted service settings (batch opt-in), see "Service configuration".
_CONFIG_FILE = os.path.join(_LOG_DIR, "service.json")

SYSTEMD_UNIT_PATH = f"/etc/systemd/system/{SERVICE_NAME}.service"


def _log(message: str) -> None:
    """Append a timestamped line to the service log file (best effort)."""
    try:
        os.makedirs(_LOG_DIR, exist_ok=True)
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(_LOG_FILE, "a", encoding="utf-8") as fh:
            fh.write(f"[{stamp}] {message}\n")
    except Exception:
        pass


def _log_exception(context: str) -> None:
    """Record the current exception to the log file."""
    tb = traceback.format_exc()
    _log(f"EXCEPTION in {context}:\n{tb}")


# --- Credential validation (PAM via pamela) ---

_PAM_LOCK = threading.Lock()


def validate_credentials(username: str, password: str) -> bool:
    """Validate Linux system credentials through PAM.

    Accepts ``User`` or ``DOMAIN\\User`` (the domain part is dropped - PAM
    authenticates local accounts). Returns True only when both PAM
    authentication and account management succeed. A missing/broken
    ``pamela`` module is treated as an authentication failure.
    """
    if not username or not password:
        return False

    candidates = [username]
    if "\\" in username:
        # "DOMAIN\User" -> try the bare local user name as well.
        _, user = username.split("\\", 1)
        if user:
            candidates.append(user)

    try:
        import pamela
    except Exception as e:  # pragma: no cover - depends on system libs
        _log(f"validate_credentials: pamela unavailable: {e}")
        return False

    for candidate in candidates:
        try:
            # PAM modules are not guaranteed to be thread-safe - serialise.
            with _PAM_LOCK:
                _pam_authenticate(pamela, candidate, password)
            return True
        except Exception as e:
            _log(f"validate_credentials: PAM rejected {candidate!r}: {e}")
    return False


def _pam_authenticate(pamela, username: str, password: str) -> None:
    """Run PAM authentication + account management, tolerant of pamela 1.0.

    ``pamela`` >= 1.2 accepts ``check=True`` (runs ``pam_acct_mgmt`` so
    disabled/expired accounts are rejected). The Debian package
    (``python3-pamela`` 1.0.x) has no such keyword, so on a matching
    ``TypeError`` we retry without it (authentication only). Any other error
    - including the PAMError raised on a rejected password - propagates to
    the caller, which treats it as an authentication failure.
    """
    try:
        pamela.authenticate(username, password, service=PAM_SERVICE, check=True)
    except TypeError as te:
        # Only fall back for the missing-keyword case, never mask real errors.
        if "check" not in str(te):
            raise
        pamela.authenticate(username, password, service=PAM_SERVICE)


# --- Service configuration (feature gating) ---
#
# run_batch executes arbitrary scripts as root and is therefore disabled by
# default. --enable-batch/--disable-batch persist the opt-in in a small JSON
# file next to the service log (see _CONFIG_FILE); the running service
# re-reads it on every request (cheap, takes effect without a restart).

_CONFIG_LOCK = threading.Lock()


def _read_config() -> dict:
    try:
        with open(_CONFIG_FILE, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _write_config(patch: dict) -> bool:
    """Merge *patch* into the service config file (best effort)."""
    try:
        os.makedirs(_LOG_DIR, exist_ok=True)
        with _CONFIG_LOCK:
            data = _read_config()
            data.update(patch)
            with open(_CONFIG_FILE, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, indent=2)
        return True
    except OSError:
        return False


def is_batch_allowed() -> bool:
    """True when run_batch was explicitly enabled on this machine."""
    with _CONFIG_LOCK:
        return bool(_read_config().get("allow_batch", False))


def set_batch_allowed(allowed: bool) -> bool:
    return _write_config({"allow_batch": bool(allowed)})


# --- Auth throttling (brute-force protection) + auth audit log ---
#
# validate_credentials() checks real OS accounts via PAM, so unlimited
# attempts from the LAN are a brute-force risk. Failed attempts are counted
# per (client IP, username) with an exponential lockout; every auth failure
# and every accepted privileged command goes to the service log (audit
# trail - passwords are NEVER logged). Metrics polls are not audit-logged
# (they would flood the log on a dashboard refresh every few seconds).

AUTH_MAX_ATTEMPTS = 5            # failures per window before the lockout starts
AUTH_WINDOW_SECONDS = 900        # failures older than this are forgotten
AUTH_LOCKOUT_BASE_SECONDS = 60   # first lockout, doubles with every extra failure
AUTH_LOCKOUT_MAX_SECONDS = 3600  # cap for the exponential backoff

_auth_lock = threading.Lock()
_auth_failures: dict[tuple[str, str], list[float]] = {}


def _auth_audit(message: str) -> None:
    """Append an AUTH audit line to the service log (never contains secrets)."""
    _log(f"AUTH {message}")


def auth_reset_state() -> None:
    """Drop all throttling and replay state (tests / service start)."""
    with _auth_lock:
        _auth_failures.clear()
    replay_reset_state()


def auth_max_attempts() -> int:
    """Configurable failure threshold (``auth_max_attempts`` in service.json)."""
    try:
        value = int(_read_config().get("auth_max_attempts", AUTH_MAX_ATTEMPTS))
        return max(1, value)
    except (TypeError, ValueError):
        return AUTH_MAX_ATTEMPTS


def auth_check_allowed(client_ip: str, username: str) -> tuple[bool, int]:
    """Whether *username* from *client_ip* may attempt authentication now.

    Returns ``(allowed, retry_after_seconds)``. After the threshold of
    failures within the window is exceeded, the pair is locked out for an
    exponentially growing period (60 s, 120 s, ... capped at 1 h). When a
    lockout expires, exactly one probe attempt passes; a further failure
    re-locks immediately with the next (doubled) period.
    """
    key = (client_ip or "", username or "")
    now = time.monotonic()
    with _auth_lock:
        fails = _auth_failures.get(key)
        if not fails:
            return True, 0
        fails = [t for t in fails if now - t < AUTH_WINDOW_SECONDS]
        if not fails:
            _auth_failures.pop(key, None)
            return True, 0
        _auth_failures[key] = fails
        if len(fails) < auth_max_attempts():
            return True, 0
        excess = len(fails) - auth_max_attempts()
        lockout = min(
            AUTH_LOCKOUT_BASE_SECONDS * (2 ** excess), AUTH_LOCKOUT_MAX_SECONDS
        )
        elapsed = now - fails[-1]
        if elapsed >= lockout:
            return True, 0
        return False, int(lockout - elapsed) + 1


def auth_record_failure(client_ip: str, username: str) -> None:
    with _auth_lock:
        _auth_failures.setdefault((client_ip or "", username or ""), []).append(
            time.monotonic()
        )


def auth_record_success(client_ip: str, username: str) -> None:
    with _auth_lock:
        _auth_failures.pop((client_ip or "", username or ""), None)


# --- Replay protection (timestamp + nonce) --------------------------------
#
# Every request carries credentials, so a captured request can be replayed
# verbatim by anyone able to observe the (unencrypted) LAN traffic - the
# service cannot tell a replay from the original. For the privileged,
# one-shot commands (shutdown / reboot / run_batch) the client therefore
# adds:
#
#   ts    - Unix timestamp (seconds, UTC) at the moment of sending
#   nonce - a fresh random value, unique per request
#
# The service rejects a request whose timestamp is too far from its own
# clock (bounds the replay window) or whose nonce it has already seen
# (kills replays inside that window).
#
# "metrics" is deliberately NOT covered: it is read-only, has no one-shot
# side effect, and a dashboard polls it every few seconds - replaying it
# gains an attacker nothing while a per-poll nonce would only grow state.
#
# Rollout: with require_replay off (the default) unsigned requests are still
# accepted, so an older client keeps working against a newer service. Turn
# the requirement on with --require-replay once every client is updated.

REPLAY_PROTECTED_COMMANDS = ("shutdown", "reboot", "run_batch")
REPLAY_MAX_SKEW_SECONDS = 120   # max |service clock - request ts|
NONCE_TTL_SECONDS = 300         # a nonce stays known for >= the skew window
NONCE_CACHE_MAX = 4096

_nonce_lock = threading.Lock()
_seen_nonces: dict[str, float] = {}


def replay_reset_state() -> None:
    """Forget all known nonces (used by tests and on service start)."""
    with _nonce_lock:
        _seen_nonces.clear()


def require_replay() -> bool:
    """True when privileged commands must carry ts + nonce.

    Configured via ``"require_replay"`` in service.json (default False so a
    service update never breaks an older client).
    """
    return bool(_read_config().get("require_replay", False))


def set_require_replay(enabled: bool) -> bool:
    return _write_config({"require_replay": bool(enabled)})


def _nonce_known(nonce: str) -> bool:
    """True when *nonce* was already used; otherwise record it."""
    now = time.monotonic()
    with _nonce_lock:
        if len(_seen_nonces) > NONCE_CACHE_MAX:
            for stale in [k for k, exp in _seen_nonces.items() if exp <= now]:
                _seen_nonces.pop(stale, None)
            if len(_seen_nonces) > NONCE_CACHE_MAX:
                # Still full of live nonces - drop the oldest quarter.
                for stale, _exp in sorted(_seen_nonces.items(),
                                          key=lambda kv: kv[1],
                                          )[: NONCE_CACHE_MAX // 4]:
                    _seen_nonces.pop(stale, None)
        if nonce in _seen_nonces:
            return True
        _seen_nonces[nonce] = now + NONCE_TTL_SECONDS
        return False


def replay_check(request: dict, command: str) -> str | None:
    """Validate the anti-replay fields of *request*.

    Returns an error message when the request must be rejected, or ``None``
    when it may proceed. The nonce is only registered on success, so a
    request that later fails authentication does not burn its nonce.
    Commands outside :data:`REPLAY_PROTECTED_COMMANDS` are never checked.
    """
    if command not in REPLAY_PROTECTED_COMMANDS:
        return None

    ts = request.get("ts")
    nonce = request.get("nonce")
    has_ts = isinstance(ts, (int, float)) and not isinstance(ts, bool)
    has_nonce = isinstance(nonce, str) and bool(nonce.strip())

    if not has_ts and not has_nonce:
        if require_replay():
            return ("Missing replay protection (ts/nonce): update the "
                    "Wake-on-LAN Manager client")
        return None  # legacy client, replay protection not enforced yet
    if not has_ts:
        return "Invalid request timestamp (ts)"
    if not has_nonce:
        return "Invalid request nonce"
    if abs(time.time() - float(ts)) > REPLAY_MAX_SKEW_SECONDS:
        return f"Request timestamp out of range (>{REPLAY_MAX_SKEW_SECONDS}s skew)"
    if len(nonce) > 64:
        return "Invalid request nonce"
    if _nonce_known(nonce):
        return "Replay detected (nonce already used)"
    return None


# --- Metrics collection (psutil + nvidia-smi) ---

_gpu_cache: tuple[float, dict] = (0.0, {})
_gpu_cache_lock = threading.Lock()
_cpu_primed = False


def _query_nvidia_smi() -> dict:
    """Query GPU utilization/VRAM via nvidia-smi (aggregated over all GPUs).

    Returns ``{"gpu": float|None, "vram_used": int|None,
    "vram_total": int|None, "gpu_name": str|None}`` with VRAM in bytes.
    All values are None when nvidia-smi is unavailable (no NVIDIA GPU or
    missing driver).
    """
    empty = {"gpu": None, "vram_used": None, "vram_total": None, "gpu_name": None}
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=utilization.gpu,memory.used,memory.total,name",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True, timeout=3,
        )
        if result.returncode != 0:
            return empty
    except (OSError, subprocess.TimeoutExpired):
        return empty

    utils: list[float] = []
    vram_used = 0
    vram_total = 0
    names: list[str] = []
    for line in result.stdout.decode("utf-8", errors="replace").splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 4:
            continue
        try:
            utils.append(float(parts[0]))
            vram_used += int(float(parts[1])) * 1024 * 1024  # MiB -> bytes
            vram_total += int(float(parts[2])) * 1024 * 1024
        except ValueError:
            continue  # e.g. "[N/A]" on some drivers
        names.append(parts[3])

    if not utils or vram_total <= 0:
        return empty
    return {
        "gpu": round(sum(utils) / len(utils), 1),
        "vram_used": vram_used,
        "vram_total": vram_total,
        "gpu_name": ", ".join(names) if names else None,
    }


def _gpu_metrics_cached() -> dict:
    """GPU metrics with a short cache (see GPU_CACHE_SECONDS)."""
    global _gpu_cache
    now = time.monotonic()
    with _gpu_cache_lock:
        if now - _gpu_cache[0] < GPU_CACHE_SECONDS:
            return _gpu_cache[1]
        data = _query_nvidia_smi()
        # Replace the tuple as a whole (atomic rebinding for readers).
        _gpu_cache = (now, data)
        return data


# --- Watched processes (shared, platform-neutral via psutil) ---------------
#
# The client sends an optional "watch" list with the "metrics" command; each
# entry is "name" or "name:port" (the port turns the check into "running AND
# API reachable" - a llama-server that exists but does not answer yet shows
# as "starting" on the dashboard). Answers are keyed by the original entry
# string. Process objects are cached per PID so psutil's cpu_percent() has a
# sample window on every poll.

_WATCH_PROCS: dict[int, "object"] = {}
_WATCH_PROCS_LOCK = threading.Lock()


def _parse_watch_entry(entry: str) -> tuple[str, int | None]:
    """``"llama-server:8080"`` -> ``("llama-server", 8080)``."""
    name = str(entry).strip()
    if not name:
        return "", None
    base, sep, port_str = name.rpartition(":")
    if sep and base and port_str.isdigit():
        port = int(port_str)
        if 1 <= port <= 65535:
            return base, port
    return name, None


def _check_port_loopback(port: int) -> bool:
    """True when a TCP connect to 127.0.0.1:*port* succeeds quickly."""
    try:
        with socket.create_connection(("127.0.0.1", port),
                                      timeout=WATCH_PORT_TIMEOUT_S):
            return True
    except OSError:
        return False


def _model_display_name(raw: str) -> str:
    """File name of a model path/id for display, dots preserved.

    Takes the last path segment (``/`` or ``\\``) and strips only a known
    model file extension. A blind ``os.path.splitext`` is NOT used: model
    names such as ``Qwen3.8-Flash-256k-62`` contain dots that belong to the
    name and would be truncated to ``Qwen3``.
    """
    name = str(raw or "").replace("\\", "/").rstrip("/").rpartition("/")[2]
    lower = name.lower()
    for ext in MODEL_FILE_EXTS:
        if lower.endswith(ext):
            name = name[: -len(ext)]
            break
    return name.strip()[:64]


def _models_from_api_json(payload: dict) -> list:
    """Extract the resident model names from a llama-server ``/v1/models`` body.

    Only entries whose ``status.value`` is ``loaded`` or ``sleeping`` count
    (llama-server reports ``status`` as an object: ``{"value": "loaded",
    ...}``; some builds use a plain string). ``sleeping`` is included because
    llama-swap-style servers keep idle-but-resident models in RAM - they are
    still "geladen" and can answer immediately. The display name is the
    ``alias`` when the server was started with one, else the file name of
    ``id`` (dots preserved). Returns a de-duplicated, capped list; never
    raises on malformed input.
    """
    data = payload.get("data")
    if not isinstance(data, list):
        return []
    names: list = []
    for item in data:
        if not isinstance(item, dict):
            continue
        status = item.get("status")
        if isinstance(status, dict):
            state = str(status.get("value", "")).lower()
        else:
            state = str(status or "").lower()
        if state not in ("loaded", "sleeping"):
            continue
        name = _model_display_name(
            str(item.get("alias") or "").strip()
            or str(item.get("id") or ""))
        if name and name not in names:
            names.append(name)
        if len(names) >= WATCH_MAX_MODELS:
            break
    return names


def _fetch_loaded_models(port: int) -> list:
    """``GET http://127.0.0.1:port/v1/models`` -> loaded model names ([]).

    Plain ``http.client`` on loopback: llama-server answers the model list
    without authentication, and any failure (timeout, non-200, non-JSON, a
    non-llama API that happens to listen on the port) degrades to an empty
    list so the dashboard falls back to the command-line model name.
    """
    try:
        import http.client  # stdlib, cheap import inside the poll

        conn = http.client.HTTPConnection("127.0.0.1", port,
                                          timeout=WATCH_MODELS_TIMEOUT_S)
        try:
            conn.request("GET", "/v1/models",
                         headers={"Accept": "application/json"})
            resp = conn.getresponse()
            if resp.status != 200:
                return []
            body = resp.read(262_144)
        finally:
            conn.close()
        payload = json.loads(body.decode("utf-8", errors="replace"))
    except Exception:
        return []
    if not isinstance(payload, dict):
        return []
    return _models_from_api_json(payload)


# Prometheus gauge lines of the llama.cpp /metrics endpoint. Body is plain
# text ("# HELP ...\n# TYPE ...\nllamacpp:prompt_tokens_seconds 261.15\n");
# an optional label set ("{...}") is tolerated. Values may use exponent
# notation and the specials NaN/Inf appear until the server has answered a
# request - those are treated as "not measurable".
_PROMPT_TPS_RE = re.compile(
    r"^llamacpp:prompt_tokens_seconds(?:\s*\{[^}]*\})?\s+"
    r"([-+0-9.eE]+|NaN|[+-]Inf)\s*$", re.MULTILINE)
_PREDICTED_TPS_RE = re.compile(
    r"^llamacpp:predicted_tokens_seconds(?:\s*\{[^}]*\})?\s+"
    r"([-+0-9.eE]+|NaN|[+-]Inf)\s*$", re.MULTILINE)
# Cumulative token counters - "Total Tokens" is their sum: every processed
# prompt token plus every decoded token. Both grow monotonically while the
# server runs (reset only on restart), unlike the throughput gauges.
_PROMPT_TOKENS_TOTAL_RE = re.compile(
    r"^llamacpp:prompt_tokens_total(?:\s*\{[^}]*\})?\s+"
    r"([-+0-9.eE]+|NaN|[+-]Inf)\s*$", re.MULTILINE)
_N_DECODE_TOTAL_RE = re.compile(
    r"^llamacpp:n_decode_total(?:\s*\{[^}]*\})?\s+"
    r"([-+0-9.eE]+|NaN|[+-]Inf)\s*$", re.MULTILINE)

# llama.cpp zeroes the two throughput gauges while the server idles, so a
# 0 reading means "nothing measured since the last request", not "no
# throughput". The last valid (non-zero) reading per (port, model) is
# latched here and re-sent instead, so the dashboard shows the last known
# value instead of a flickering 0. Hard-capped against model churn in
# llama-swap setups (the entry is replaced wholesale when the cap hits).
_MODEL_TPS_CACHE: dict[tuple[int, str], dict] = {}
_MODEL_TPS_CACHE_LOCK = threading.Lock()


def _parse_prometheus_gauge(text: str,
                            pattern: "re.Pattern") -> "float | None":
    """First match of *pattern* in *text* as float (None when absent/NaN)."""
    match = pattern.search(text)
    if not match:
        return None
    try:
        value = float(match.group(1))
    except ValueError:
        return None
    if not math.isfinite(value):
        return None
    return value


def _fetch_model_metrics(port: int, model_name: str) -> "dict | None":
    """Per-model throughput from llama.cpp ``GET /metrics?model=<name>``.

    Returns ``{"prompt_tps": float, "predicted_tps": float,
    "total_tokens": int}`` - keys are omitted while not measurable. The
    two throughput gauges report 0 while the server idles: a 0 (or NaN)
    reading never overwrites the latched last valid value
    (``_MODEL_TPS_CACHE``), it is just re-sent. ``total_tokens`` is the
    sum of the cumulative counters ``llamacpp:prompt_tokens_total`` and
    ``llamacpp:n_decode_total`` (missing counters count as 0) and grows
    continuously.
    ``None`` when nothing is known at all - non-llama servers, timeouts,
    non-200 and non-numeric values all degrade quietly so the dashboard
    shows the plain model line without a suffix.
    """
    if not model_name:
        return None
    path = "/metrics?model=" + urllib.parse.quote(model_name)
    try:
        import http.client  # stdlib, cheap import inside the poll

        conn = http.client.HTTPConnection("127.0.0.1", port,
                                          timeout=WATCH_MODELS_TIMEOUT_S)
        try:
            conn.request("GET", path, headers={"Accept": "text/plain"})
            resp = conn.getresponse()
            if resp.status != 200:
                return None
            body = resp.read(262_144)
        finally:
            conn.close()
        text = body.decode("utf-8", errors="replace")
    except Exception:
        return None
    prompt = _parse_prometheus_gauge(text, _PROMPT_TPS_RE)
    predicted = _parse_prometheus_gauge(text, _PREDICTED_TPS_RE)
    counter_values = [_parse_prometheus_gauge(text, _PROMPT_TOKENS_TOTAL_RE),
                      _parse_prometheus_gauge(text, _N_DECODE_TOTAL_RE)]
    counters = [v for v in counter_values if v is not None]
    total = sum(counters) if counters else None
    fresh: dict = {}
    if prompt is not None and prompt > 0:
        fresh["prompt_tps"] = prompt
    if predicted is not None and predicted > 0:
        fresh["predicted_tps"] = predicted
    result: dict = {}
    with _MODEL_TPS_CACHE_LOCK:
        key = (port, model_name)
        if fresh:
            if (len(_MODEL_TPS_CACHE) > 256
                    and key not in _MODEL_TPS_CACHE):
                _MODEL_TPS_CACHE.clear()
            _MODEL_TPS_CACHE[key] = {**_MODEL_TPS_CACHE.get(key, {}),
                                     **fresh}
        result.update(_MODEL_TPS_CACHE.get(key, {}))
    if total is not None and total > 0:
        result["total_tokens"] = int(total)
    return result or None


def _model_from_argv(argv: list) -> str:
    """Best-effort model name from a llama.cpp-style command line.

    Reads ``-m``/``--model`` and returns the file name of the path (e.g.
    ``qwen2.5-coder-14b-q4``), with a known model extension stripped but dots
    inside the name preserved (see :func:`_model_display_name`). Returns ""
    when no such flag is present - never raises.
    """
    if not isinstance(argv, list):
        return ""
    for i, arg in enumerate(argv):
        if arg in ("-m", "--model") and i + 1 < len(argv):
            return _model_display_name(argv[i + 1])
        if arg.startswith("--model="):  # "--model=path" form
            return _model_display_name(arg.split("=", 1)[1])
    return ""


def _watched_processes(watch: list) -> dict:
    """Status of the watched process names, keyed by the original entry.

    Each value: ``{"running": bool}`` plus - when running - ``count``,
    ``pid``, ``cpu`` (percent, summed), ``ram`` (bytes, summed), ``uptime``
    (seconds) and, for ``name:port`` entries, ``api_port``/``api_port_open``.
    """
    entries: dict[str, tuple[str, int | None]] = {}
    for raw in list(watch)[:WATCH_MAX_ENTRIES]:
        name, port = _parse_watch_entry(str(raw))
        if name:
            entries[str(raw)] = (name, port)
    result: dict[str, dict] = {key: {"running": False} for key in entries}
    if not entries:
        return result
    try:
        import psutil  # type: ignore
    except Exception:
        return result  # no psutil -> everything reports as not running

    wanted = {name.lower() for name, _port in entries.values()}
    found: dict[str, list] = {name.lower(): [] for name in wanted}
    now = time.time()
    with _WATCH_PROCS_LOCK:
        alive: set[int] = set()
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                pname = (proc.info["name"] or "").lower()
                if pname not in wanted:
                    continue
                pid = proc.info["pid"]
                cached = _WATCH_PROCS.get(pid)
                if cached is None:
                    # First sighting: cpu_percent() needs two calls, so the
                    # first poll reports 0 - keep the object for the next one.
                    _WATCH_PROCS[pid] = proc
                    cpu = 0.0
                else:
                    cpu = cached.cpu_percent(interval=None)
                alive.add(pid)
                ram = 0
                try:
                    mem = proc.memory_info()
                    ram = int(mem.rss)
                except (psutil.Error, OSError):
                    pass
                # cmdline is only read for matching processes (a full
                # cmdline scan of every process would be too expensive on
                # each poll); used to surface the llama.cpp model name.
                try:
                    argv = proc.cmdline()
                except (psutil.Error, OSError):
                    argv = []
                found[pname].append(
                    (pid, cpu, ram, now - proc.create_time(), argv))
            except (psutil.NoSuchProcess, psutil.AccessDenied,
                    psutil.ZombieProcess, OSError):
                continue
        # Drop cached objects of processes that disappeared.
        for dead in [p for p in _WATCH_PROCS if p not in alive]:
            del _WATCH_PROCS[dead]

    port_tasks: list[tuple[dict, int]] = []
    for key, (name, port) in entries.items():
        procs = found.get(name.lower(), [])
        if not procs:
            continue
        entry_result = {
            "running": True,
            "count": len(procs),
            "pid": min(p[0] for p in procs),
            "cpu": round(sum(p[1] for p in procs), 1),
            "ram": sum(p[2] for p in procs),
            "uptime": int(max(p[3] for p in procs)),
        }
        model = _model_from_argv(min(procs, key=lambda p: p[0])[4])
        if model:
            entry_result["model"] = model
        result[key] = entry_result
        if port:
            entry_result["api_port"] = port
            entry_result["api_port_open"] = False  # set below
            port_tasks.append((entry_result, port))

    # Loopback checks in parallel so one closed port never adds its full
    # timeout to every other entry (0.25 s worst case for the whole poll).
    if port_tasks:
        with ThreadPoolExecutor(max_workers=len(port_tasks)) as pool:
            futures = {pool.submit(_check_port_loopback, p): e
                       for e, p in port_tasks}
            for fut in futures:
                try:
                    futures[fut]["api_port_open"] = bool(fut.result())
                except Exception:
                    pass
        # On top of the open port, ask the llama-server API which models it
        # currently reports as loaded (GET /v1/models). Only done for ready
        # entries; failures degrade to no "models" field (the argv-derived
        # "model" above stays as the fallback on the dashboard).
        ready = [(e, p) for e, p in port_tasks if e.get("api_port_open")]
        if ready:
            with ThreadPoolExecutor(max_workers=len(ready)) as pool:
                model_futures = {pool.submit(_fetch_loaded_models, p): e
                                 for e, p in ready}
                for fut in model_futures:
                    try:
                        names = fut.result()
                    except Exception:
                        names = []
                    if names:
                        model_futures[fut]["models"] = names
            # On top of the model list, read the prompt/generation
            # throughput per model from the llama.cpp Prometheus endpoint
            # (GET /metrics?model=<name>, protocol v5 "model_metrics"). One
            # request per loaded model, run in parallel with a bounded
            # worker count; a model whose metrics cannot be read is simply
            # absent from the map (the dashboard omits its t/s suffix).
            tps_tasks: list[tuple[dict, int, str]] = []
            for entry_result, port in ready:
                for model in entry_result.get("models", []):
                    tps_tasks.append((entry_result, port, model))
            if tps_tasks:
                with ThreadPoolExecutor(
                        max_workers=min(len(tps_tasks), 8)) as pool:
                    tps_futures = {
                        pool.submit(_fetch_model_metrics, port, model):
                            (entry_result, model)
                        for entry_result, port, model in tps_tasks}
                    for fut in tps_futures:
                        try:
                            metrics = fut.result()
                        except Exception:
                            metrics = None
                        if metrics:
                            tps_entry, tps_model = tps_futures[fut]
                            tps_entry.setdefault(
                                "model_metrics", {})[tps_model] = metrics
    return result


def collect_metrics(watch: "list | None" = None) -> dict:
    """Collect CPU/RAM/GPU/VRAM metrics for the dashboard.

    Watch entries with an open llama-server port additionally report
    ``models`` (v4) and ``model_metrics`` (v5: per-model prompt/generation
    throughput in tokens/s from ``GET /metrics?model=<name>``).

    All sizes are bytes, percentages 0-100. psutil is imported lazily so a
    broken/missing psutil in an old build only degrades this command.
    *watch* (optional list of process names, see :func:`_watched_processes`)
    adds a ``processes`` field to the response.
    """
    global _cpu_primed
    metrics: dict = {
        "status": "ok",
        "protocol": PROTOCOL_VERSION,
        "hostname": "",
        "cpu": None,
        "cpu_count": None,
        "ram_used": None,
        "ram_total": None,
        "uptime": None,
    }
    try:
        metrics["hostname"] = socket.gethostname()
    except Exception:
        pass
    try:
        import psutil  # type: ignore

        if not _cpu_primed:
            # First call with interval=None always returns 0.0 - sample a
            # short blocking window instead so the first poll is plausible.
            _cpu_primed = True
            metrics["cpu"] = psutil.cpu_percent(interval=0.15)
        else:
            metrics["cpu"] = psutil.cpu_percent(interval=None)
        metrics["cpu_count"] = psutil.cpu_count(logical=True)
        vm = psutil.virtual_memory()
        metrics["ram_used"] = vm.used
        metrics["ram_total"] = vm.total
        metrics["uptime"] = max(0, int(time.time() - psutil.boot_time()))
    except Exception as e:
        _log(f"collect_metrics: psutil failed: {e}")

    try:
        metrics.update(_gpu_metrics_cached())
    except Exception as e:
        _log(f"collect_metrics: gpu failed: {e}")
        metrics.update({"gpu": None, "vram_used": None, "vram_total": None, "gpu_name": None})

    if watch:
        try:
            metrics["processes"] = _watched_processes(watch)
        except Exception as e:
            _log(f"collect_metrics: watch failed: {e}")
    return metrics


# --- Batch execution ---

def _decode_output(data: bytes) -> str:
    """Decode subprocess output (UTF-8, undecodable bytes replaced)."""
    if not data:
        return ""
    return data.decode("utf-8", errors="replace")


def run_batch_script(script: str, timeout: float = BATCH_TIMEOUT_DEFAULT) -> dict:
    """Execute *script* as a temporary .sh file and capture its output.

    Returns a response dict (``status``/``exit_code``/``stdout``/``stderr``/
    ``duration_ms``/``truncated``). Caller must have authenticated and
    checked :func:`is_batch_allowed` first.
    """
    if not script or not script.strip():
        return {"status": "error", "message": "Empty script"}
    if len(script) > MAX_SCRIPT_CHARS:
        return {
            "status": "error",
            "message": f"Script too long (max {MAX_SCRIPT_CHARS} characters)",
        }
    timeout = max(BATCH_TIMEOUT_MIN, min(BATCH_TIMEOUT_MAX, float(timeout)))

    import tempfile

    tmp_fd, tmp_path = tempfile.mkstemp(prefix="wol_batch_", suffix=".sh")
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8", errors="replace") as fh:
            fh.write(script)
        os.chmod(tmp_path, 0o700)
        start = time.monotonic()
        try:
            result = subprocess.run(
                ["/bin/bash", tmp_path],
                capture_output=True,
                timeout=timeout,
                cwd=os.environ.get("HOME", os.path.dirname(tmp_path)),
            )
        except subprocess.TimeoutExpired:
            return {
                "status": "error",
                "message": f"Batch timed out after {int(timeout)} s",
            }
        except OSError as e:
            return {"status": "error", "message": f"Could not run batch: {e}"}
        duration_ms = int((time.monotonic() - start) * 1000)

        stdout = _decode_output(result.stdout)
        stderr = _decode_output(result.stderr)
        truncated = len(stdout) > MAX_BATCH_OUTPUT_CHARS or len(stderr) > MAX_BATCH_OUTPUT_CHARS
        return {
            "status": "ok",
            "exit_code": result.returncode,
            "stdout": stdout[:MAX_BATCH_OUTPUT_CHARS],
            "stderr": stderr[:MAX_BATCH_OUTPUT_CHARS],
            "duration_ms": duration_ms,
            "truncated": truncated,
        }
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


# --- Power action (shutdown / reboot) ---

def _execute_power(command: str) -> None:
    """Run the OS power command for an accepted shutdown/reboot request.

    ``SHUTDOWN_CMD``/``REBOOT_CMD`` are read at call time so the macOS
    variant can override them.

    SAFETY GUARD: when the environment variable ``WOL_TEST_NO_POWER`` is
    set, the OS command is NOT executed. The test suite sets this variable
    (see tests/conftest.py) so a unit/integration test that drives the
    handler in-process can never shut down or reboot the machine running
    the tests — even if a future test forgets to mock ``subprocess.run``.
    """
    if os.environ.get("WOL_TEST_NO_POWER"):
        return
    if command == "shutdown":
        subprocess.run(SHUTDOWN_CMD, capture_output=True)
    else:
        subprocess.run(REBOOT_CMD, capture_output=True)


# --- TCP command handler ---

class _CommandHandler(socketserver.BaseRequestHandler):
    """Handles one TCP connection: read one JSON line, answer one JSON line."""

    def handle(self) -> None:  # noqa: N802 (socketserver API)
        try:
            data = b""
            while not data.endswith(b"\n") and len(data) < MAX_REQUEST_BYTES:
                chunk = self.request.recv(4096)
                if not chunk:
                    break
                data += chunk
            if not data:
                return

            line = data.strip().decode("utf-8", errors="replace")
            try:
                request = json.loads(line)
            except json.JSONDecodeError:
                self._respond({"status": "error", "message": "Invalid JSON"})
                return
            if not isinstance(request, dict):
                self._respond({"status": "error", "message": "Invalid request"})
                return

            command = str(request.get("command", "")).strip().lower()
            username = str(request.get("username", ""))
            password = str(request.get("password", ""))
            try:
                client_ip = self.client_address[0]
            except Exception:
                client_ip = ""

            if command == "status":
                # Reachability probe - no authentication required.
                self._respond({"status": "ok", "message": "online"})
                return

            if command not in ("metrics", "shutdown", "reboot", "run_batch"):
                self._respond(
                    {"status": "error", "message": f"Unknown command: {command}"}
                )
                return

            # Brute-force throttling: reject before touching the PAM path.
            allowed, retry_after = auth_check_allowed(client_ip, username)
            if not allowed:
                _auth_audit(
                    f"LOCKED {command} user={username!r} from {client_ip} "
                    f"(retry in {retry_after}s)"
                )
                self._respond({
                    "status": "error",
                    "message": f"Too many failed attempts. Try again in {retry_after}s.",
                    "retry_after": retry_after,
                })
                return

            # Replay protection for the privileged one-shot commands.
            replay_error = replay_check(request, command)
            if replay_error is not None:
                _auth_audit(
                    f"REPLAY-REJECT {command} user={username!r} from {client_ip}: "
                    f"{replay_error}"
                )
                self._respond({"status": "error", "message": replay_error})
                return

            if not validate_credentials(username, password):
                auth_record_failure(client_ip, username)
                _auth_audit(f"FAILED {command} user={username!r} from {client_ip}")
                self._respond({"status": "error", "message": "Authentication failed"})
                return
            auth_record_success(client_ip, username)

            if command == "metrics":
                # Dashboard metrics - authenticated. Not audit-logged (a live
                # dashboard polls every few seconds and would flood the log).
                watch = request.get("watch")
                if isinstance(watch, list) and watch:
                    self._respond(collect_metrics(watch=watch))
                else:
                    self._respond(collect_metrics())
                return

            if command == "run_batch":
                # Arbitrary script execution - the per-machine opt-in
                # (--enable-batch) is required in addition to auth.
                if not is_batch_allowed():
                    self._respond({
                        "status": "error",
                        "message": "Batch execution disabled on host "
                                   "(run: wol_host_service.py --enable-batch)",
                    })
                    return
                _auth_audit(f"RUN_BATCH user={username!r} from {client_ip}")
                script = str(request.get("script", ""))
                try:
                    batch_timeout = float(request.get("timeout", BATCH_TIMEOUT_DEFAULT))
                except (TypeError, ValueError):
                    batch_timeout = BATCH_TIMEOUT_DEFAULT
                self._respond(run_batch_script(script, batch_timeout))
                return

            # shutdown / reboot - privileged, always audit-logged.
            _auth_audit(f"{command.upper()} user={username!r} from {client_ip}")

            # Acknowledge first, then execute - the client must receive the
            # confirmation before the machine goes down.
            self._respond({"status": "ok", "message": f"{command} accepted"})
            time.sleep(1.0)
            _execute_power(command)
        except Exception:
            # Never let a handler exception kill the server thread.
            pass

    def _respond(self, payload: dict) -> None:
        try:
            self.request.sendall(json.dumps(payload, ensure_ascii=False).encode("utf-8") + b"\n")
        except OSError:
            pass


def _make_server(port: int) -> socketserver.ThreadingTCPServer:
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    server = socketserver.ThreadingTCPServer(("0.0.0.0", port), _CommandHandler)
    server.daemon_threads = True
    return server


# --- systemd integration ---

def is_root() -> bool:
    """True when the current process may manage the systemd unit."""
    return hasattr(os, "geteuid") and os.geteuid() == 0


def get_exec_start() -> str:
    """ExecStart line for the systemd unit (venv python + this script)."""
    if getattr(sys, "frozen", False):
        return f"{os.path.abspath(sys.executable)} --run"
    return f"{sys.executable} {shlex.quote(os.path.abspath(__file__))} --run"


def build_unit_file() -> str:
    """Systemd unit content (auto-start, restart on failure)."""
    return (
        "[Unit]\n"
        f"Description={SERVICE_DISPLAY_NAME} - remote shutdown/metrics for the "
        "Wake-on-LAN Manager\n"
        "After=network-online.target\n"
        "Wants=network-online.target\n"
        "\n"
        "[Service]\n"
        "Type=simple\n"
        f"ExecStart={get_exec_start()}\n"
        "Restart=on-failure\n"
        "RestartSec=5\n"
        "\n"
        "[Install]\n"
        "WantedBy=multi-user.target\n"
    )


def _systemctl(*args: str, timeout: float = 30.0) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["systemctl", *args], capture_output=True, text=True, timeout=timeout
    )


# Unit paths. --install writes to /etc (the admin location); the Debian
# package ships its unit to /usr/lib (dpkg-owned). Both are checked so the CLI
# never clobbers a packaged installation.
PACKAGED_UNIT_PATHS = (
    f"/usr/lib/systemd/system/{SERVICE_NAME}.service",
    f"/lib/systemd/system/{SERVICE_NAME}.service",
)


def packaged_unit_installed() -> bool:
    """True when the unit comes from the Debian package (dpkg-owned)."""
    return any(os.path.exists(path) for path in PACKAGED_UNIT_PATHS)


def _local_subnet_cidrs() -> list[str]:
    """CIDR strings of all local IPv4 networks (interface address + netmask).

    Used to scope the ufw rule to the machine's own subnets. Best effort:
    returns an empty list when no usable address is found, in which case
    :func:`add_firewall_rule` falls back to the previous unrestricted rule.
    """
    import ipaddress
    import socket as _socket

    try:
        import psutil  # type: ignore
    except ImportError:
        return []
    cidrs: list[str] = []
    try:
        addrs = psutil.net_if_addrs()
    except Exception:
        return []
    for name, entries in addrs.items():
        if name.lower().startswith("lo"):
            continue
        for entry in entries:
            if entry.family != _socket.AF_INET or not entry.address:
                continue
            try:
                net = ipaddress.ip_network(
                    f"{entry.address}/{entry.netmask or ''}", strict=False)
                if net.prefixlen >= 8:  # reject nonsensical /0../7 scopes
                    cidrs.append(str(net))
            except ValueError:
                continue
    return cidrs


def add_firewall_rule() -> bool:
    """Allow inbound TCP 8765 through ufw, scoped to the local subnets.

    The rule is limited to traffic from this machine's own networks
    (``from <CIDR>``) so a routable interface on an untrusted network cannot
    reach the service. When the scope cannot be determined the previous
    unrestricted rule is used as fallback.
    """
    if shutil.which("ufw") is None:
        return True  # no ufw on this machine - nothing to do
    try:
        status = subprocess.run(
            ["ufw", "status"], capture_output=True, text=True, timeout=15
        )
        if "active" not in status.stdout.lower():
            return True  # ufw installed but inactive - ports are open anyway
        cidrs = _local_subnet_cidrs()
        if not cidrs:
            result = subprocess.run(
                ["ufw", "allow", f"{DEFAULT_PORT}/tcp"],
                capture_output=True, text=True, timeout=15,
            )
            return result.returncode == 0
        for cidr in cidrs:
            result = subprocess.run(
                ["ufw", "allow", "from", cidr, "to", "any",
                 f"port {DEFAULT_PORT}/tcp"],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode != 0:
                return False
        return True
    except Exception:
        return False


def remove_firewall_rule() -> bool:
    """Remove the ufw rule for TCP 8765 (best effort)."""
    if shutil.which("ufw") is None:
        return True
    try:
        subprocess.run(
            ["ufw", "delete", "allow", f"{DEFAULT_PORT}/tcp"],
            capture_output=True, text=True, timeout=15,
        )
        return True
    except Exception:
        return False


def install_service() -> bool:
    """Install + enable the systemd unit (root) and configure the firewall."""
    if not is_root():
        print("ERROR: Root privileges required for --install (use sudo).")
        return False

    if packaged_unit_installed():
        print(f"INFO: The '{SERVICE_DISPLAY_NAME}' is already installed as part")
        print("      of the 'wake-on-lan-manager' Debian package. Managing it")
        print("      with --install would replace the packaged unit file, so")
        print("      nothing was changed. Use --start/--stop/--status instead")
        print("      (or remove the package first to install from source).")
        return True

    unit = build_unit_file()
    try:
        with open(SYSTEMD_UNIT_PATH, "w", encoding="utf-8") as fh:
            fh.write(unit)
    except OSError as e:
        print(f"ERROR: Could not write {SYSTEMD_UNIT_PATH}: {e}")
        return False

    result = _systemctl("daemon-reload")
    if result.returncode != 0:
        print(f"ERROR: systemctl daemon-reload failed: {result.stderr.strip()}")
        return False
    result = _systemctl("enable", "--now", SERVICE_NAME)
    if result.returncode != 0:
        print(f"ERROR: systemctl enable --now failed: {result.stderr.strip()}")
        return False

    if not add_firewall_rule():
        print(f"WARNING: Could not add firewall rule '{FIREWALL_RULE_NAME}'.")
        print(f"         Add it manually: allow inbound TCP port {DEFAULT_PORT}.")

    print(f"Service '{SERVICE_DISPLAY_NAME}' installed (systemd, auto-start).")
    print(f"Unit file: {SYSTEMD_UNIT_PATH}")
    print(f"Firewall:  inbound TCP {DEFAULT_PORT} configured (ufw, when active).")
    print(f"Batch execution is disabled by default "
          f"(enable: sudo {os.path.basename(sys.argv[0])} --enable-batch).")
    return True


def uninstall_service() -> bool:
    """Stop, disable and remove the systemd unit + firewall rule."""
    if not is_root():
        print("ERROR: Root privileges required for --uninstall (use sudo).")
        return False

    if packaged_unit_installed():
        print("INFO: The unit is provided by the 'wake-on-lan-manager' Debian")
        print("      package and will not be removed. Uninstall the package")
        print("      instead:  sudo apt remove wake-on-lan-manager")
        return True

    remove_firewall_rule()

    if not os.path.exists(SYSTEMD_UNIT_PATH):
        print(f"Service '{SERVICE_DISPLAY_NAME}' not installed - nothing to remove.")
        return True

    _systemctl("stop", SERVICE_NAME)
    _systemctl("disable", SERVICE_NAME)
    try:
        os.remove(SYSTEMD_UNIT_PATH)
    except OSError as e:
        print(f"ERROR: Could not remove {SYSTEMD_UNIT_PATH}: {e}")
        return False
    _systemctl("daemon-reload")

    print(f"Service '{SERVICE_DISPLAY_NAME}' removed.")
    return True


def start_service() -> bool:
    if not is_root():
        print("ERROR: Root privileges required for --start (use sudo).")
        return False
    result = _systemctl("start", SERVICE_NAME)
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        if "already running" in detail.lower():
            print(f"Service '{SERVICE_DISPLAY_NAME}' is already running.")
            return True
        print(f"ERROR: Could not start service: {detail}")
        return False
    print(f"Service '{SERVICE_DISPLAY_NAME}' started.")
    return True


def stop_service() -> bool:
    if not is_root():
        print("ERROR: Root privileges required for --stop (use sudo).")
        return False
    result = _systemctl("stop", SERVICE_NAME)
    if result.returncode != 0:
        print(f"ERROR: Could not stop service: {result.stderr.strip()}")
        return False
    print(f"Service '{SERVICE_DISPLAY_NAME}' stopped.")
    return True


def show_status() -> bool:
    active = _systemctl("is-active", SERVICE_NAME).stdout.strip() or "unknown"
    enabled = _systemctl("is-enabled", SERVICE_NAME).stdout.strip() or "unknown"
    if enabled == "not-found" or active == "unknown":
        print(f"Service '{SERVICE_DISPLAY_NAME}' is not installed.")
        return True
    print(f"Service '{SERVICE_DISPLAY_NAME}': {active.upper()} ({enabled})")
    return True


# --- Foreground mode ---

def run_foreground(port: int = DEFAULT_PORT) -> None:
    """Run the TCP server in the foreground (for debugging)."""
    print(f"{SERVICE_DISPLAY_NAME} (foreground) listening on 0.0.0.0:{port}")
    print("Press Ctrl+C to stop.")
    _log(f"run_foreground: starting, PID={os.getpid()}, port={port}")
    try:
        server = _make_server(port)
    except OSError as e:
        print(f"ERROR: Could not bind TCP port {port}: {e}")
        _log(f"run_foreground: failed to bind port {port}: {e}")
        raise SystemExit(1) from e
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main() -> int:
    args = sys.argv[1:]

    # CLI mode
    port = DEFAULT_PORT
    if "--port" in args:
        idx = args.index("--port")
        try:
            port = int(args[idx + 1])
        except (IndexError, ValueError):
            print("ERROR: --port requires a number.")
            return 1
        args = [a for i, a in enumerate(args) if i not in (idx, idx + 1)]

    if "--install" in args:
        return 0 if install_service() else 1
    if "--uninstall" in args:
        return 0 if uninstall_service() else 1
    if "--start" in args:
        return 0 if start_service() else 1
    if "--stop" in args:
        return 0 if stop_service() else 1
    if "--status" in args:
        return 0 if show_status() else 1
    if "--enable-batch" in args:
        if set_batch_allowed(True):
            print("Batch execution ENABLED on this machine.")
            return 0
        print("ERROR: Could not write the service config file "
              f"({_CONFIG_FILE}). Run with sudo when the service runs as root.")
        return 1
    if "--disable-batch" in args:
        if set_batch_allowed(False):
            print("Batch execution DISABLED on this machine (default).")
            return 0
        print("ERROR: Could not write the service config file "
              f"({_CONFIG_FILE}). Run with sudo when the service runs as root.")
        return 1
    if "--require-replay" in args:
        if set_require_replay(True):
            print("Replay protection REQUIRED for shutdown/reboot/run_batch "
                  "(clients without ts/nonce are rejected).")
            return 0
        print("ERROR: Could not write the service config file "
              f"({_CONFIG_FILE}). Run with sudo when the service runs as root.")
        return 1
    if "--replay-optional" in args:
        if set_require_replay(False):
            print("Replay protection OPTIONAL (legacy clients still accepted).")
            return 0
        print("ERROR: Could not write the service config file "
              f"({_CONFIG_FILE}). Run with sudo when the service runs as root.")
        return 1
    if "--run" in args:
        run_foreground(port)
        return 0

    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
