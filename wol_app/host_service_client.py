"""Client for the WOL Host Service (TCP port 8765, JSON protocol).

The host service runs on the *target* Windows machine. It accepts a single
JSON line:

    {"command": "shutdown" | "reboot" | "status", "username": "...", "password": "..."}

and answers with a single JSON line:

    {"status": "ok" | "error", "message": "..."}

Authentication uses the device's stored Windows credentials (validated on
the host via LogonUserW).
"""

import json
import socket

# Default TCP port of the WOL Host Service
HOST_SERVICE_PORT = 8765

# Maximum size of a single JSON line (request or response)
_MAX_LINE_BYTES = 4096


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

    payload = json.dumps(
        {
            "command": command,
            "username": username or "",
            "password": password or "",
        },
        ensure_ascii=False,
    ).encode("utf-8")

    try:
        with socket.create_connection((ip, port), timeout=timeout) as sock:
            sock.sendall(payload + b"\n")
            data = b""
            while not data.endswith(b"\n") and len(data) < _MAX_LINE_BYTES:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                data += chunk
    except TimeoutError:
        return False, "Connection timed out"
    except OSError as e:
        return False, f"Could not connect to {ip}:{port} ({e})"

    if not data:
        return False, "No response from host service"

    try:
        response = json.loads(data.strip().decode("utf-8", errors="replace"))
    except json.JSONDecodeError:
        return False, "Invalid response from host service"

    if not isinstance(response, dict):
        return False, "Invalid response from host service"

    status = str(response.get("status", "error"))
    message = str(response.get("message", ""))
    if status == "ok":
        return True, message or "Command accepted"
    return False, message or "Command rejected by host service"
