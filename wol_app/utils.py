"""Wake-on-LAN Application - Shared Utilities.

Central location for validation helpers, subprocess wrappers, and common
utility functions used across multiple modules.
"""

import base64
import os
import re
import subprocess
import tempfile
import threading
import time

# ── Validation ──────────────────────────────────────────────────────────────

def validate_ip(ip: str) -> bool:
    """Validate an IPv4 address with strict regex."""
    ipv4_pattern = r'^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
    return bool(re.match(ipv4_pattern, ip))


def validate_mac(mac: str) -> bool:
    """Validate MAC address format (colon or hyphen separated).

    Accepts: AA:BB:CC:DD:EE:FF or AA-BB-CC-DD-EE-FF
    """
    mac_pattern = r'^([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}$'
    return bool(re.match(mac_pattern, mac.strip()))


def validate_device_name(name: str) -> bool:
    """Validate device name for safety."""
    if not name or len(name) > 64:
        return False
    # No control characters
    if any(ord(c) < 32 or ord(c) > 126 for c in name):
        return False
    # No potentially dangerous characters
    forbidden_chars = ['<', '>', '"', "'", ';', '|', '&', '$', '`', '\\']
    if any(char in name for char in forbidden_chars):
        return False
    return True


def validate_username(username: str) -> bool:
    """Validate username for safety."""
    if not username:
        return True  # Username is optional
    if len(username) > 64:
        return False
    if any(ord(c) < 32 or ord(c) > 126 for c in username):
        return False
    return True


def validate_password(password: str) -> bool:
    """Validate password for safety."""
    if not password:
        return True  # Password is optional
    if len(password) > 128:
        return False
    if any(ord(c) > 126 for c in password):
        return False
    return True


# ── Subprocess ──────────────────────────────────────────────────────────────

def run_subprocess_safe(command, timeout: int = 5, **kwargs):
    """Safe execution of subprocess with strict limits.

    * Always uses ``shell=False`` to prevent command injection.
    * Handles ``capture_output`` correctly (mutually exclusive with
      explicit ``stdout``/``stderr`` in Python).
    """
    try:
        if kwargs.get('capture_output') is not None:
            safe_kwargs = {
                'timeout': timeout,
                'shell': False,
                **kwargs
            }
        else:
            safe_kwargs = {
                'stdout': subprocess.PIPE,
                'stderr': subprocess.PIPE,
                'timeout': timeout,
                'shell': False,
                **kwargs
            }
        result = subprocess.run(command, **safe_kwargs)
        return result
    except subprocess.TimeoutExpired as e:
        raise TimeoutError(f"Command timed out: {' '.join(command)}") from e
    except Exception as e:
        raise RuntimeError(f"Command failed: {' '.join(command)} - {str(e)}") from e

# ── Remote Desktop ──────────────────────────────────────────────────────────

def _build_rdp_content(
    ip: str,
    username: str,
    password: str,
    fullscreen: bool,
    width: int,
    height: int,
) -> str:
    """Build the content of a temporary ``.rdp`` file for *ip*.

    mstsc cannot take credentials on the command line, so the username and
    password are embedded in the file. ``password:54:`` is base64-encoded
    UTF-16LE — the exact format mstsc expects.
    """
    lines = [
        f"full address:s:{ip}",
        # Use the embedded password instead of prompting when one is set.
        f"prompt for password:i:{0 if password else 1}",
    ]
    if username:
        lines.append(f"username:s:{username}")
    if password:
        encoded = base64.b64encode(password.encode("utf-16-le")).decode("ascii")
        lines.append(f"password:54:{encoded}")
    if fullscreen:
        lines.append("fullscreen:i:1")
    else:
        lines.append("fullscreen:i:0")
        lines.append(f"desktopwidth:i:{int(width)}")
        lines.append(f"desktopheight:i:{int(height)}")
        # Do not span the window over multiple monitors.
        lines.append("use multimon:i:0")
    return "\r\n".join(lines) + "\r\n"


def _cleanup_rdp_file(path: str, delay: float) -> None:
    """Delete *path* after *delay* seconds (runs in a daemon thread)."""
    time.sleep(delay)
    try:
        os.remove(path)
    except OSError:
        pass


def launch_remote_desktop(
    ip: str,
    username: str = "",
    password: str = "",
    fullscreen: bool = True,
    width: int = 1920,
    height: int = 1080,
    cleanup_delay: float = 5.0,
) -> None:
    """Launch Windows Remote Desktop (``mstsc``) to *ip*.

    A temporary ``.rdp`` file carrying the credentials is written and passed
    to mstsc; it is deleted *cleanup_delay* seconds later so the password
    does not linger on disk.

    The session geometry is forced via **command-line arguments**, because
    mstsc is known to ignore ``fullscreen:i:0`` inside an .rdp file (it then
    falls back to full-screen). The .rdp file is still passed so that the
    credentials (which mstsc cannot take on the command line) are supplied:

    * ``fullscreen=True``  → ``mstsc /v:<ip> /f <file>``
    * ``fullscreen=False`` → ``mstsc /v:<ip> /w:<width> /h:<height> <file>``

    The ``/w:``/``/h:``/``/f`` arguments have the highest precedence and
    reliably determine whether the session opens in a window or full-screen.

    Args:
        ip: Target host (IPv4 address or name).
        username: Optional RDP user; empty leaves mstsc's default.
        password: Optional RDP password; empty makes mstsc prompt.
        fullscreen: Full-screen mode when True, windowed mode when False.
        width: Window width in pixels (windowed mode only).
        height: Window height in pixels (windowed mode only).
        cleanup_delay: Seconds to wait before deleting the temp file.

    Raises:
        ValueError: if *ip* is empty.
        OSError: if mstsc cannot be started (e.g. not found).
    """
    if not ip:
        raise ValueError("IP address is empty")

    content = _build_rdp_content(ip, username, password, fullscreen, width, height)
    fd, rdp_path = tempfile.mkstemp(suffix=".rdp", prefix="wol_rdp_")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(content)

    # Force the geometry on the command line (reliable) and let the .rdp
    # file supply the credentials. The .rdp path is always the last argument.
    if fullscreen:
        cmd = ["mstsc", f"/v:{ip}", "/f", rdp_path]
    else:
        cmd = [
            "mstsc",
            f"/v:{ip}",
            f"/w:{int(width)}",
            f"/h:{int(height)}",
            rdp_path,
        ]
    try:
        subprocess.Popen(cmd)
    except Exception:
        # mstsc could not start; do not leak the credential file.
        try:
            os.remove(rdp_path)
        except OSError:
            pass
        raise

    threading.Thread(
        target=_cleanup_rdp_file,
        args=(rdp_path, cleanup_delay),
        daemon=True,
    ).start()

# ── Sorting helpers ────────────────────────────────────────────────────────

def get_ip_key(ip_str: str) -> tuple:
    """Convert an IP address string to a tuple of integers for numerical sorting.

    Returns ``(0, 0, 0, 0)`` for invalid or empty strings.
    """
    try:
        parts = list(map(int, ip_str.split('.') if ip_str else [0, 0, 0, 0]))
        while len(parts) < 4:
            parts.append(0)
        return tuple(parts)
    except (ValueError, AttributeError):
        return (0, 0, 0, 0)


def make_sort_key(column: int, is_ip: bool = False):
    """Return a key function that extracts a sortable value from a row tuple.

    ``column`` is the index of the value inside the row tuple. When ``is_ip``
    is True the value is treated as an IPv4 address and converted to a numeric
    key so 10.0.0.2 sorts after 10.0.0.10 correctly.
    """
    def key(row) -> tuple:
        value = row[column]
        if is_ip:
            return get_ip_key(str(value))
        return value
    return key


def sort_rows(rows: list, column: int, reverse: bool = False,
              is_ip: bool = False) -> list:
    """Return *rows* sorted by the value at *column*.

    ``is_ip`` enables numeric IP sorting (10.0.0.10 > 10.0.0.2).
    """
    key = make_sort_key(column, is_ip=is_ip)
    return sorted(rows, key=key, reverse=reverse)


# ── Path helpers ────────────────────────────────────────────────────────────

def get_resource_path(filename: str) -> str:
    """Get path to a bundled resource file.

    Works both in PyInstaller frozen mode and development mode.
    """
    if getattr(__import__('sys'), 'frozen', False):
        base_path = __import__('sys')._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
        # Also check dist/ folder (installer builds)
        dist_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), '..', 'dist'
        )
        if os.path.exists(os.path.join(dist_path, filename)):
            base_path = dist_path
    return os.path.join(base_path, filename)
