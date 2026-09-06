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
``LogonUserW`` path. A username of the form ``DOMAIN\\User`` is reduced to
the user part before authentication.

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
    wol_host_service.py --run            Run in the foreground (debugging)
    wol_host_service.py --port N         Port override for --run (default 8765)

Note: ``--enable-batch`` must be run as the same user that runs the service
(root under systemd), because the opt-in is stored in the service config
directory (see ``_LOG_DIR`` below).
"""

import json
import os
import shlex
import shutil
import socket
import socketserver
import subprocess
import sys
import threading
import time
import traceback
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
PROTOCOL_VERSION = 4

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
    return result


def collect_metrics(watch: "list | None" = None) -> dict:
    """Collect CPU/RAM/GPU/VRAM metrics for the dashboard.

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

            if command == "status":
                # Reachability probe - no authentication required.
                self._respond({"status": "ok", "message": "online"})
                return

            if command == "metrics":
                # Dashboard metrics - authentication required.
                if not validate_credentials(username, password):
                    self._respond({"status": "error", "message": "Authentication failed"})
                    return
                watch = request.get("watch")
                if isinstance(watch, list) and watch:
                    self._respond(collect_metrics(watch=watch))
                else:
                    self._respond(collect_metrics())
                return

            if command == "run_batch":
                # Arbitrary script execution - authentication AND the
                # per-machine opt-in (--enable-batch) are required.
                if not validate_credentials(username, password):
                    self._respond({"status": "error", "message": "Authentication failed"})
                    return
                if not is_batch_allowed():
                    self._respond({
                        "status": "error",
                        "message": "Batch execution disabled on host "
                                   "(run: wol_host_service.py --enable-batch)",
                    })
                    return
                script = str(request.get("script", ""))
                try:
                    batch_timeout = float(request.get("timeout", BATCH_TIMEOUT_DEFAULT))
                except (TypeError, ValueError):
                    batch_timeout = BATCH_TIMEOUT_DEFAULT
                self._respond(run_batch_script(script, batch_timeout))
                return

            if command not in ("shutdown", "reboot"):
                self._respond(
                    {"status": "error", "message": f"Unknown command: {command}"}
                )
                return

            if not validate_credentials(username, password):
                self._respond({"status": "error", "message": "Authentication failed"})
                return

            # Acknowledge first, then execute - the client must receive the
            # confirmation before the machine goes down.
            self._respond({"status": "ok", "message": f"{command} accepted"})
            time.sleep(1.0)
            if command == "shutdown":
                subprocess.run(["systemctl", "poweroff"], capture_output=True)
            else:
                subprocess.run(["systemctl", "reboot"], capture_output=True)
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


def add_firewall_rule() -> bool:
    """Allow inbound TCP 8765 through ufw (skipped when ufw is inactive)."""
    if shutil.which("ufw") is None:
        return True  # no ufw on this machine - nothing to do
    try:
        status = subprocess.run(
            ["ufw", "status"], capture_output=True, text=True, timeout=15
        )
        if "active" not in status.stdout.lower():
            return True  # ufw installed but inactive - ports are open anyway
        result = subprocess.run(
            ["ufw", "allow", f"{DEFAULT_PORT}/tcp"],
            capture_output=True, text=True, timeout=15,
        )
        return result.returncode == 0
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
    if "--run" in args:
        run_foreground(port)
        return 0

    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
