"""WOL Host Service - Windows service for remote control via TCP.

This service runs on the *target* Windows machine and listens on TCP port
8765. It accepts a single-line JSON request:

    {"command": "shutdown" | "reboot" | "status" | "metrics" | "run_batch",
     "username": "...", "password": "..."}

and answers with a single-line JSON response:

    {"status": "ok" | "error", "message": "..."}   (plus command-specific fields)

Authentication: the supplied Windows credentials are validated with
``LogonUserW`` (interactive logon). A username of the form ``DOMAIN\\User``
is split into domain and user; without a backslash the local domain is used.

Commands:
    shutdown  - shut the machine down immediately (``shutdown /s /t 0 /f``)
    reboot    - reboot the machine immediately    (``shutdown /r /t 0 /f``)
    status    - no authentication required, answers ``{"status": "ok", ...}``
    metrics   - authenticated; answers with CPU/RAM/GPU/VRAM metrics
                (``cpu``, ``ram_used``/``ram_total``, ``gpu``,
                ``vram_used``/``vram_total``, ``gpu_name``, ``hostname``,
                ``uptime``, ``protocol``). GPU fields are ``null`` when no
                NVIDIA GPU/``nvidia-smi`` is available.
    run_batch - authenticated AND gated: executes a cmd batch script
                (``script`` field, ``timeout`` optional) and answers with
                ``exit_code``/``stdout``/``stderr``/``duration_ms``.
                Disabled by default - enable per machine with
                ``--enable-batch`` (the service runs as SYSTEM, so executing
                arbitrary scripts is a powerful operation).

CLI usage (run as administrator for install/uninstall/start/stop):

    WOL Host Service.exe --install        Install service + firewall rule
    WOL Host Service.exe --uninstall      Remove firewall rule + service
    WOL Host Service.exe --start          Start the service
    WOL Host Service.exe --stop           Stop the service
    WOL Host Service.exe --status         Show service status
    WOL Host Service.exe --enable-batch   Allow run_batch on this machine
    WOL Host Service.exe --disable-batch  Forbid run_batch (default)
    WOL Host Service.exe --run            Run in the foreground (debugging)

When started by the Windows Service Control Manager (no arguments), the
service control dispatcher is entered automatically.
"""

import ctypes
import json
import os
import socket
import socketserver
import subprocess
import sys
import threading
import time
import traceback

SERVICE_NAME = "WOLHostService"
SERVICE_DISPLAY_NAME = "WOL Host Service"
SERVICE_DESCRIPTION = (
    "Accepts remote shutdown/reboot commands from the Wake-on-LAN Manager "
    "over TCP port 8765 (JSON protocol, Windows credential authentication)."
)
FIREWALL_RULE_NAME = "WOL Host Service"
DEFAULT_PORT = 8765
MAX_REQUEST_BYTES = 65536

# Protocol version reported in the "metrics" response so the client can
# detect a host service that is too old for the dashboard features.
PROTOCOL_VERSION = 2

# Limits for run_batch (the service runs as SYSTEM - keep these strict).
MAX_SCRIPT_CHARS = 32_000
BATCH_TIMEOUT_DEFAULT = 120
BATCH_TIMEOUT_MIN = 5
BATCH_TIMEOUT_MAX = 3600
MAX_BATCH_OUTPUT_CHARS = 64_000

# Seconds a collected GPU sample is reused (nvidia-smi costs ~50-300 ms and
# would otherwise be spawned on every dashboard poll).
GPU_CACHE_SECONDS = 1.5

SERVICE_REGISTRY_PATH = rf"SYSTEM\CurrentControlSet\Services\{SERVICE_NAME}"

# Windows constant not exposed by pywin32 (same value as SC_MANAGER_ENUMERATE_SERVICE)
SC_MANAGER_QUERY = 0x0004


# --- Windows credential validation (LogonUserW) ---

LOGON32_LOGON_INTERACTIVE = 2
LOGON32_PROVIDER_DEFAULT = 0


def validate_credentials(username: str, password: str) -> bool:
    """Validate Windows credentials via LogonUserW.

    Accepts ``User`` or ``DOMAIN\\User``. Returns True only if the
    credentials are valid for the given (or local) domain.
    """
    if not username or not password:
        return False
    if "\\" in username:
        domain, user = username.split("\\", 1)
    else:
        domain, user = None, username
    if not user:
        return False

    htoken = ctypes.c_void_p()
    result = ctypes.windll.advapi32.LogonUserW(
        user,
        domain,
        password,
        LOGON32_LOGON_INTERACTIVE,
        LOGON32_PROVIDER_DEFAULT,
        ctypes.byref(htoken),
    )
    if result == 0:
        return False
    try:
        ctypes.windll.kernel32.CloseHandle(htoken)
    except Exception:
        pass
    return True


# --- Service configuration (feature gating) ---
#
# run_batch executes arbitrary scripts as SYSTEM and is therefore disabled
# by default. --enable-batch/--disable-batch persist the opt-in in a small
# JSON file next to the service log (see _CONFIG_FILE, defined with the
# logging paths below); the running service re-reads it on every request
# (cheap, takes effect without a restart).

_CONFIG_LOCK = threading.Lock()


def _read_config() -> dict:
    try:
        with open(_CONFIG_FILE, "r", encoding="utf-8") as fh:
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
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
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


def collect_metrics() -> dict:
    """Collect CPU/RAM/GPU/VRAM metrics for the dashboard.

    All sizes are bytes, percentages 0-100. psutil is imported lazily so a
    broken/missing psutil in an old build only degrades this command.
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
    return metrics


# --- Batch execution ---

def _decode_output(data: bytes) -> str:
    """Decode subprocess output (UTF-8 first, then the OEM console codepage)."""
    if not data:
        return ""
    text = data.decode("utf-8", errors="strict") if _is_valid_utf8(data) else None
    if text is not None and "\ufffd" not in text:
        return text
    # Console tools (cmd built-ins) usually answer in the OEM codepage.
    return data.decode("cp850", errors="replace")


def _is_valid_utf8(data: bytes) -> bool:
    try:
        data.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


def run_batch_script(script: str, timeout: float = BATCH_TIMEOUT_DEFAULT) -> dict:
    """Execute *script* as a temporary .cmd file and capture its output.

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

    tmp_fd, tmp_path = tempfile.mkstemp(prefix="wol_batch_", suffix=".cmd")
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8", errors="replace") as fh:
            fh.write(script)
        start = time.monotonic()
        try:
            result = subprocess.run(
                ["cmd.exe", "/d", "/c", tmp_path],
                capture_output=True,
                timeout=timeout,
                cwd=os.environ.get("TEMP", os.path.dirname(tmp_path)),
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
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
                                   "(run: WOL Host Service.exe --enable-batch)",
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
                subprocess.run(
                    ["shutdown", "/s", "/t", "0", "/f"], capture_output=True
                )
            else:
                subprocess.run(
                    ["shutdown", "/r", "/t", "0", "/f"], capture_output=True
                )
        except Exception:
            # Never let a handler exception kill the server thread.
            pass

    def _respond(self, payload: dict) -> None:
        try:
            self.request.sendall(json.dumps(payload, ensure_ascii=False).encode("utf-8") + b"\n")
        except OSError:
            pass


def _make_server(port: int) -> socketserver.ThreadingTCPServer:
    server = socketserver.ThreadingTCPServer(("0.0.0.0", port), _CommandHandler)
    server.daemon_threads = True
    return server


# --- Service diagnostics logging ---
#
# When the SCM starts the service, its stdout/stderr are NOT visible to the
# user (they go to the service session, not a console). If the service crashes
# before it can report, the only clue is "exit code 1067" in the System log.
# To make the real cause visible we log to a file under %ProgramData% and,
# when possible, to the Windows Application event log.

_LOG_DIR = os.path.join(
    os.environ.get("ProgramData", r"C:\ProgramData"), "WakeOnLAN", "WOL Host Service"
)
_LOG_FILE = os.path.join(_LOG_DIR, "wol_host_service.log")

# Persisted service settings (batch opt-in), see "Service configuration".
_CONFIG_FILE = os.path.join(_LOG_DIR, "service.json")


def _log(message: str) -> None:
    """Append a timestamped line to the service log file (best effort)."""
    try:
        os.makedirs(_LOG_DIR, exist_ok=True)
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(_LOG_FILE, "a", encoding="utf-8") as fh:
            fh.write(f"[{stamp}] {message}\n")
    except Exception:
        pass


def _log_event(event_id: int, message: str, severity: int = 1) -> None:
    """Write a message to the Windows Application event log (best effort)."""
    try:
        import win32evtlogutil

        # severity: 1=error, 2=warning, 4=information (EVENTLOG_*_TYPE)
        win32evtlogutil.ReportEvent(
            SERVICE_DISPLAY_NAME, event_id, 0, severity, [message]
        )
    except Exception:
        pass


def _log_exception(context: str) -> None:
    """Record the current exception to the log file and event log."""
    tb = traceback.format_exc()
    _log(f"EXCEPTION in {context}:\n{tb}")
    _log_event(1000, f"{context}:\n{tb}", severity=1)


# --- Service implementation (pywin32) ---

def _build_service_class():
    """Build the ServiceFramework class (imports pywin32 lazily)."""
    import win32event
    import win32service
    import win32serviceutil

    class WOLHostService(win32serviceutil.ServiceFramework):
        _svc_name_ = SERVICE_NAME
        _svc_display_name_ = SERVICE_DISPLAY_NAME
        _svc_description_ = SERVICE_DESCRIPTION

        def __init__(self, args):
            win32serviceutil.ServiceFramework.__init__(self, args)
            self.stop_event = win32event.CreateEvent(None, 0, 0, None)
            self._server = None

        def SvcStop(self):
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            win32event.SetEvent(self.stop_event)

        def SvcDoRun(self):
            import win32service as _svc
            _log(f"SvcDoRun: starting, PID={os.getpid()}, port={DEFAULT_PORT}, "
                 f"cwd={os.getcwd()}")
            try:
                self._server = _make_server(DEFAULT_PORT)
            except OSError as e:
                # e.g. port 8765 already in use. Report STOPPED cleanly instead
                # of crashing (which the SCM would log as exit code 1067).
                _log(f"SvcDoRun: failed to bind port {DEFAULT_PORT}: {e}")
                _log_event(1001, f"Could not bind TCP port {DEFAULT_PORT}: {e}", severity=1)
                self.ReportServiceStatus(_svc.SERVICE_STOPPED)
                return
            self.ReportServiceStatus(_svc.SERVICE_RUNNING)
            _log(f"SvcDoRun: listening on 0.0.0.0:{DEFAULT_PORT}")
            # serve_forever() must actually run (in a thread) - otherwise the
            # server never accepts connections AND server.shutdown() blocks
            # forever on stop, leaving the process stuck in STOP_PENDING
            # (which is why --stop/--uninstall could not terminate it).
            serve_thread = threading.Thread(
                target=self._server.serve_forever,
                kwargs={"poll_interval": 0.5},
                daemon=True,
            )
            serve_thread.start()
            try:
                while win32event.WaitForSingleObject(self.stop_event, 1000) != win32event.WAIT_OBJECT_0:
                    pass
            finally:
                _log("SvcDoRun: stopping server")
                try:
                    self._server.shutdown()
                    self._server.server_close()
                except Exception:
                    _log_exception("SvcDoRun shutdown")

    return WOLHostService


# --- Admin / service management helpers ---

def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def get_exe_path() -> str:
    """Path of the executable that should be registered as the service binary."""
    if getattr(sys, "frozen", False):
        return os.path.abspath(sys.executable)
    # Development mode: register python.exe + script
    return f'"{sys.executable}" "{os.path.abspath(sys.argv[0])}"'


def _open_service_manager(access: int):
    import win32service
    return win32service.OpenSCManager(None, None, access)


def _open_service(handle, access: int):
    import win32service
    return win32service.OpenService(handle, SERVICE_NAME, access)


def add_firewall_rule() -> bool:
    try:
        result = subprocess.run(
            [
                "netsh", "advfirewall", "firewall", "add", "rule",
                f"name={FIREWALL_RULE_NAME}", "dir=in", "action=allow",
                "protocol=TCP", f"localport={DEFAULT_PORT}", "enable=yes",
            ],
            capture_output=True, text=True, timeout=15,
        )
        return result.returncode == 0
    except Exception:
        return False


def remove_firewall_rule() -> bool:
    try:
        subprocess.run(
            [
                "netsh", "advfirewall", "firewall", "delete", "rule",
                f"name={FIREWALL_RULE_NAME}",
            ],
            capture_output=True, text=True, timeout=15,
        )
        return True
    except Exception:
        return False


def _kill_stale_service_processes() -> int:
    """Force-kill any lingering 'WOL Host Service.exe' processes (best effort).

    Safety net for the case where the service process got stuck (e.g. an older
    build that hung on stop) and the SCM no longer reports it as running.
    Returns the number of processes killed.
    """
    exe_name = os.path.basename(os.path.abspath(sys.executable)).lower() \
        if getattr(sys, "frozen", False) else "wol host service.exe"
    killed = 0
    try:
        # text=False + manual decode: tasklist output may contain locale
        # characters (e.g. umlauts) that cp1252 cannot decode.
        result = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {exe_name}", "/FO", "CSV", "/NH"],
            capture_output=True, timeout=10,
        )
        stdout = result.stdout.decode("utf-8", errors="replace")
        for line in stdout.splitlines():
            parts = [p.strip('"') for p in line.split('","')]
            if len(parts) >= 2 and parts[1].isdigit():
                pid = int(parts[1])
                if pid == os.getpid():
                    continue
                try:
                    subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                                   capture_output=True, timeout=10)
                    killed += 1
                    _log(f"Killed stale service process PID {pid}")
                except Exception:
                    pass
    except Exception:
        pass
    return killed


def service_exists() -> bool:
    import win32service
    try:
        # NOTE: pywin32 has no win32service.SC_MANAGER_QUERY. Use the module
        # constant (0x0004 == SC_MANAGER_ENUMERATE_SERVICE), same as show_status().
        sc = _open_service_manager(SC_MANAGER_QUERY)
        try:
            svc = _open_service(sc, win32service.SERVICE_QUERY_STATUS)
            win32service.CloseServiceHandle(svc)
            return True
        except Exception:
            return False
        finally:
            win32service.CloseServiceHandle(sc)
    except Exception:
        return False


def install_service() -> bool:
    """Register the Windows service (auto-start, LocalSystem) + firewall rule."""
    import win32service

    if not is_admin():
        print("ERROR: Administrator privileges required for --install.")
        return False

    bin_path = get_exe_path()
    sc = _open_service_manager(win32service.SC_MANAGER_ALL_ACCESS)
    try:
        try:
            svc = win32service.CreateService(
                sc,
                SERVICE_NAME,
                SERVICE_DISPLAY_NAME,
                win32service.SERVICE_ALL_ACCESS,
                win32service.SERVICE_WIN32_OWN_PROCESS,
                win32service.SERVICE_AUTO_START,
                win32service.SERVICE_ERROR_NORMAL,
                bin_path,
                None, 0, None,
                None, None,
            )
        except Exception as e:
            if getattr(e, "winerror", None) == 1073:  # ERROR_SERVICE_EXISTS
                print(f"INFO: Service '{SERVICE_NAME}' already exists - updating.")
                svc = _open_service(sc, win32service.SERVICE_ALL_ACCESS)
            else:
                raise
        try:
            # Point the service at the current executable (reinstall/upgrade)
            win32service.ChangeServiceConfig(
                svc,
                win32service.SERVICE_WIN32_OWN_PROCESS,
                win32service.SERVICE_AUTO_START,
                win32service.SERVICE_ERROR_NORMAL,
                bin_path,
                None, 0, None,
                None, None,
                SERVICE_DISPLAY_NAME,
            )
        finally:
            win32service.CloseServiceHandle(svc)
    finally:
        win32service.CloseServiceHandle(sc)

    # Set the service description in the registry (reliable, no struct fiddling)
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE, SERVICE_REGISTRY_PATH, 0, winreg.KEY_SET_VALUE
        )
        try:
            winreg.SetValueEx(key, "Description", 0, winreg.REG_SZ, SERVICE_DESCRIPTION)
        finally:
            winreg.CloseKey(key)
    except OSError:
        pass

    if not add_firewall_rule():
        print(f"WARNING: Could not add firewall rule '{FIREWALL_RULE_NAME}'.")
        print(f"         Add it manually: allow inbound TCP port {DEFAULT_PORT}.")

    print(f"Service '{SERVICE_DISPLAY_NAME}' installed (auto-start).")
    print(f"Firewall rule '{FIREWALL_RULE_NAME}' (inbound TCP {DEFAULT_PORT}) configured.")
    return True


def uninstall_service() -> bool:
    """Stop and delete the Windows service + remove the firewall rule."""
    import win32service

    if not is_admin():
        print("ERROR: Administrator privileges required for --uninstall.")
        return False

    remove_firewall_rule()

    if not service_exists():
        print(f"Service '{SERVICE_NAME}' not found - nothing to remove.")
        return True

    sc = _open_service_manager(win32service.SC_MANAGER_ALL_ACCESS)
    try:
        svc = _open_service(sc, win32service.SERVICE_ALL_ACCESS)
        try:
            status = win32service.QueryServiceStatus(svc)
            if status[1] != win32service.SERVICE_STOPPED:
                print(f"Stopping service '{SERVICE_DISPLAY_NAME}'...")
                try:
                    win32service.ControlService(svc, win32service.SERVICE_CONTROL_STOP)
                except Exception as e:
                    # 1061: service is already stopping (stuck in STOP_PENDING).
                    if getattr(e, "winerror", None) != 1061:
                        raise
                    print("Service is already stopping (stuck) - will terminate it.")
                deadline = time.time() + 15
                while time.time() < deadline:
                    status = win32service.QueryServiceStatus(svc)
                    if status[1] == win32service.SERVICE_STOPPED:
                        break
                    time.sleep(0.5)
                if status[1] != win32service.SERVICE_STOPPED:
                    # Still stuck (STOP_PENDING). Force-kill the lingering
                    # process(es) so DeleteService can proceed.
                    print("Service did not stop in time - terminating process(es)...")
                    _kill_stale_service_processes()
                    time.sleep(1.0)
            win32service.DeleteService(svc)
        finally:
            win32service.CloseServiceHandle(svc)
    finally:
        win32service.CloseServiceHandle(sc)

    print(f"Service '{SERVICE_DISPLAY_NAME}' removed.")
    return True


def start_service() -> bool:
    import win32service

    if not is_admin():
        print("ERROR: Administrator privileges required for --start.")
        return False
    sc = _open_service_manager(win32service.SC_MANAGER_ALL_ACCESS)
    try:
        svc = _open_service(sc, win32service.SERVICE_START)
        try:
            try:
                win32service.StartService(svc, None)
                print(f"Service '{SERVICE_DISPLAY_NAME}' started.")
            except Exception as e:
                if getattr(e, "winerror", None) == 1056:  # ERROR_SERVICE_ALREADY_RUNNING
                    print(f"Service '{SERVICE_DISPLAY_NAME}' is already running.")
                else:
                    raise
            return True
        finally:
            win32service.CloseServiceHandle(svc)
    finally:
        win32service.CloseServiceHandle(sc)


def stop_service() -> bool:
    import win32service

    if not is_admin():
        print("ERROR: Administrator privileges required for --stop.")
        return False
    sc = _open_service_manager(win32service.SC_MANAGER_ALL_ACCESS)
    try:
        svc = _open_service(
            sc,
            win32service.SERVICE_STOP | win32service.SERVICE_QUERY_STATUS,
        )
        try:
            status = win32service.QueryServiceStatus(svc)
            if status[1] == win32service.SERVICE_STOPPED:
                print(f"Service '{SERVICE_DISPLAY_NAME}' is not running - nothing to stop.")
                return True
            win32service.ControlService(svc, win32service.SERVICE_CONTROL_STOP)
            deadline = time.time() + 15
            while time.time() < deadline:
                status = win32service.QueryServiceStatus(svc)
                if status[1] == win32service.SERVICE_STOPPED:
                    break
                time.sleep(0.5)
            if status[1] != win32service.SERVICE_STOPPED:
                # Stuck (e.g. STOP_PENDING from an older build that hung on
                # stop). Force-kill the lingering process(es) as a safety net.
                print("Service did not stop in time - terminating process(es)...")
                _kill_stale_service_processes()
                time.sleep(1.0)
            print(f"Service '{SERVICE_DISPLAY_NAME}' stopped.")
            return True
        except Exception as e:
            if getattr(e, "winerror", None) == 1061:  # ERROR_SERVICE_CANNOT_ACCEPT_CTRL
                print(f"Service '{SERVICE_DISPLAY_NAME}' is already stopping.")
                return True
            if getattr(e, "winerror", None) == 1062:  # ERROR_SERVICE_NOT_STARTED
                print(f"Service '{SERVICE_DISPLAY_NAME}' is not running - nothing to stop.")
                return True
            raise
        finally:
            win32service.CloseServiceHandle(svc)
    finally:
        win32service.CloseServiceHandle(sc)


def show_status() -> bool:
    import win32service

    states = {
        win32service.SERVICE_STOPPED: "STOPPED",
        win32service.SERVICE_START_PENDING: "START_PENDING",
        win32service.SERVICE_RUNNING: "RUNNING",
        win32service.SERVICE_STOP_PENDING: "STOP_PENDING",
    }
    sc = _open_service_manager(SC_MANAGER_QUERY)
    try:
        try:
            svc = _open_service(sc, win32service.SERVICE_QUERY_STATUS)
        except Exception:
            print(f"Service '{SERVICE_DISPLAY_NAME}' is not installed.")
            return True
        try:
            status = win32service.QueryServiceStatus(svc)
            state = states.get(status[1], f"UNKNOWN({status[1]})")
            print(f"Service '{SERVICE_DISPLAY_NAME}': {state}")
            return True
        finally:
            win32service.CloseServiceHandle(svc)
    finally:
        win32service.CloseServiceHandle(sc)


def run_foreground(port: int = DEFAULT_PORT) -> None:
    """Run the TCP server in the foreground (for debugging)."""
    print(f"{SERVICE_DISPLAY_NAME} (foreground) listening on 0.0.0.0:{port}")
    print("Press Ctrl+C to stop.")
    server = _make_server(port)
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main() -> int:
    args = sys.argv[1:]
    if not args:
        # Started by the Service Control Manager - enter the dispatcher.
        try:
            import servicemanager
            WOLHostService = _build_service_class()
            _log("main: entering service dispatcher (SCM mode)")
            servicemanager.Initialize()
            servicemanager.PrepareToHostSingle(WOLHostService)
            servicemanager.StartServiceCtrlDispatcher()
            return 0
        except Exception:
            # Capture crashes that happen before/around the dispatcher (e.g.
            # failure to connect to the SCM) so the cause is not lost.
            _log_exception("main (SCM dispatcher)")
            raise

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
        print("ERROR: Could not write the service config file.")
        return 1
    if "--disable-batch" in args:
        if set_batch_allowed(False):
            print("Batch execution DISABLED on this machine (default).")
            return 0
        print("ERROR: Could not write the service config file.")
        return 1
    if "--run" in args:
        run_foreground(port)
        return 0

    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
