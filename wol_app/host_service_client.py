"""Client for the WOL Host Service (TCP port 8765, JSON protocol).

The host service runs on the *target* Windows machine. It accepts a single
JSON line and answers with a single JSON line. This module exposes three
facades over the shared :func:`_request` core:

- :func:`send_host_command` — ``shutdown`` / ``reboot`` / ``status``
- :func:`get_metrics`       — CPU/RAM/GPU/VRAM metrics for the dashboard
- :func:`run_batch`         — run a cmd batch script (host must opt in)

Authentication uses the device's stored Windows credentials (validated on
the host via LogonUserW).
"""

import json
import socket

# Default TCP port of the WOL Host Service
HOST_SERVICE_PORT = 8765

# Maximum size of a single JSON line (request or response), per command.
_MAX_LINE_BYTES = 4096
_MAX_METRICS_BYTES = 16_384
_MAX_BATCH_BYTES = 131_072

# Protocol version that introduced "metrics" / "run_batch" (host service
# responses without a "protocol" field are older than that).
_MIN_PROTOCOL_DASHBOARD = 2


def _request(
    ip: str,
    payload: dict,
    port: int,
    timeout: float,
    max_bytes: int,
    sock_sink: "callable | None" = None,
) -> tuple[bool, dict | str]:
    """Send one JSON request line and return ``(ok, response_dict|error_str)``.

    ``ok`` is True only when a JSON object could be read back. Transport and
    parse errors return ``(False, human_readable_message)``.

    *sock_sink*, when given, receives the connected socket as soon as it is
    established. Callers use this to close the socket from another thread
    (``cancel``) so a blocked ``recv``/``sendall`` aborts immediately instead
    of running until the timeout — important when a dashboard is closed while
    a request is still in flight.
    """
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    try:
        with socket.create_connection((ip, port), timeout=timeout) as sock:
            if sock_sink is not None:
                sock_sink(sock)
            sock.sendall(data + b"\n")
            buf = b""
            while not buf.endswith(b"\n") and len(buf) < max_bytes:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                buf += chunk
    except TimeoutError:
        return False, "Connection timed out"
    except OSError as e:
        return False, f"Could not connect to {ip}:{port} ({e})"

    if not buf:
        return False, "No response from host service"

    try:
        response = json.loads(buf.strip().decode("utf-8", errors="replace"))
    except json.JSONDecodeError:
        return False, "Invalid response from host service"

    if not isinstance(response, dict):
        return False, "Invalid response from host service"
    return True, response


def send_host_command(
    ip: str,
    command: str,
    username: str = "",
    password: str = "",
    port: int = HOST_SERVICE_PORT,
    timeout: float = 10.0,
) -> tuple[bool, str]:
    """Send a command to the WOL Host Service on *ip*.

    Args:
        ip: IPv4 address (or hostname) of the target machine.
        command: "shutdown", "reboot" or "status".
        username: Windows username (optionally "DOMAIN\\User").
        password: Windows password.
        port: TCP port of the host service (default 8765).
        timeout: socket timeout in seconds.

    Returns:
        (success, message) tuple. The message is a short, human-readable
        description suitable for logs and dialogs.
    """
    if command not in ("shutdown", "reboot", "status"):
        return False, f"Unknown command: {command}"

    ok, response = _request(
        ip,
        {
            "command": command,
            "username": username or "",
            "password": password or "",
        },
        port,
        timeout,
        _MAX_LINE_BYTES,
    )
    if not ok:
        return False, str(response)

    status = str(response.get("status", "error"))
    message = str(response.get("message", ""))
    if status == "ok":
        return True, message or "Command accepted"
    return False, message or "Command rejected by host service"


def get_metrics(
    ip: str,
    username: str = "",
    password: str = "",
    port: int = HOST_SERVICE_PORT,
    timeout: float = 5.0,
    sock_sink: "callable | None" = None,
) -> tuple[bool, dict | str]:
    """Fetch CPU/RAM/GPU/VRAM metrics from the host service.

    Returns:
        (True, metrics_dict) on success — keys include ``cpu``, ``cpu_count``,
        ``ram_used``/``ram_total``, ``gpu``, ``vram_used``/``vram_total``,
        ``gpu_name``, ``hostname``, ``uptime``, ``protocol`` (individual
        values may be ``None`` when unavailable).
        (False, error_message) on any transport/auth/protocol error. A host
        service without dashboard support is reported explicitly.
    """
    ok, response = _request(
        ip,
        {"command": "metrics", "username": username or "", "password": password or ""},
        port,
        timeout,
        _MAX_METRICS_BYTES,
        sock_sink,
    )
    if not ok:
        return False, str(response)

    if str(response.get("status", "error")) != "ok":
        return False, str(response.get("message") or "Metrics rejected by host service")

    protocol = response.get("protocol")
    if isinstance(protocol, int) and protocol < _MIN_PROTOCOL_DASHBOARD:
        return False, "Host service too old for the dashboard (update WOL Host Service)"

    return True, response


def run_batch(
    ip: str,
    script: str,
    username: str = "",
    password: str = "",
    timeout: float = 120.0,
    port: int = HOST_SERVICE_PORT,
    sock_sink: "callable | None" = None,
) -> tuple[bool, dict | str]:
    """Run a cmd batch *script* on the host machine.

    The host must have enabled batch execution (``--enable-batch``); the
    credentials are validated there. The socket stays open until the script
    finishes, so the socket timeout is *timeout* plus a small margin.

    Returns:
        (True, result_dict) with ``exit_code``/``stdout``/``stderr``/
        ``duration_ms``/``truncated`` on success.
        (False, error_message) on transport/auth/gating errors.
    """
    ok, response = _request(
        ip,
        {
            "command": "run_batch",
            "username": username or "",
            "password": password or "",
            "script": script,
            "timeout": timeout,
        },
        port,
        timeout + 5.0,
        _MAX_BATCH_BYTES,
        sock_sink,
    )
    if not ok:
        return False, str(response)

    if str(response.get("status", "error")) != "ok":
        return False, str(response.get("message") or "Batch rejected by host service")

    return True, response
