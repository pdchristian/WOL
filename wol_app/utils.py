"""Wake-on-LAN Application - Shared Utilities.

Central location for validation helpers, subprocess wrappers, and common
utility functions used across multiple modules.
"""

import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

from wol_app.translations import Translations

# ── Validation ──────────────────────────────────────────────────────────────

def validate_ip(ip: str) -> bool:
    """Validate an IPv4 address with strict regex."""
    ipv4_pattern = r'^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
    return bool(re.match(ipv4_pattern, ip))


# RFC 1123 hostname: labels of alphanumerics plus interior hyphens,
# 1-63 chars each, optionally dot-separated (FQDN), max 253 chars total.
_HOSTNAME_RE = re.compile(
    r'^(?=.{1,253}$)'
    r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?'
    r'(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*$'
)


def validate_hostname(hostname: str) -> bool:
    """Validate a DNS hostname / FQDN (RFC 1123, single-label allowed)."""
    return bool(_HOSTNAME_RE.match(hostname.strip()))


def validate_ip_or_hostname(value: str) -> bool:
    """Validate a device address: either an IPv4 address or a hostname.

    Devices are addressed by ping, shutdown and Remote Desktop (``mstsc``),
    all of which accept host names. Host names are especially useful for
    xrdp/Linux hosts that must be reached by name (e.g. ``ubuntu-mercury``)
    and for devices whose DHCP address changes.

    A value whose labels are all numeric must be a valid IPv4 address —
    otherwise a mistyped address such as ``999.1.1.1`` would silently pass as
    a "hostname".
    """
    value = value.strip()
    if not value:
        return False
    if validate_ip(value):
        return True
    if not validate_hostname(value):
        return False
    if all(label.isdigit() for label in value.split(".")):
        # Looks like an IPv4 address but failed validate_ip().
        return False
    return True


def resolve_ipv4_all(value: str) -> list[str]:
    """Return every IPv4 address *value* resolves to (deduplicated, in order).

    A DNS name may carry several A records (e.g. a Fritz!Box listing a stale
    DHCP lease next to the current one). Callers that probe reachability
    should try all candidates instead of trusting the first one, because the
    resolver order is not deterministic on Windows.
    """
    value = (value or "").strip()
    if not value:
        return []
    if validate_ip(value):
        return [value]
    try:
        infos = socket.getaddrinfo(value, None, socket.AF_INET, socket.SOCK_STREAM)
    except (OSError, UnicodeError):
        return []
    ips: list[str] = []
    for family, _, _, _, sockaddr in infos:
        ip = sockaddr[0] if family == socket.AF_INET else ""
        if ip and ip not in ips:
            ips.append(ip)
    return ips


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


def validate_api_key(api_key: str) -> bool:
    """Validate a dashboard API key for safety.

    The key travels to the host service and ends up in an ``Authorization``
    header of the local inference-API probes, so control characters (CR/LF
    included) and non-ASCII are rejected. The length cap must match
    ``ConfigManager.MAX_API_KEY_CHARS``.
    """
    if not api_key:
        return True  # API key is optional
    if len(api_key) > 128:
        return False
    if any(ord(c) < 32 or ord(c) > 126 for c in api_key):
        return False
    return True


# RustDesk addresses a peer by its own id: the 9-digit id, the UUID used for
# unattended access, a host name, or the "host:port" form of Direct IP Access.
# 64 chars is far above every form and must match
# ``ConfigManager.MAX_RUSTDESK_ID_CHARS``.
_RUSTDESK_ID_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}(?::[0-9]{1,5})?$')


def validate_rustdesk_id(peer_id: str) -> bool:
    """Validate a RustDesk peer id ("" = not set, the peer is reached by IP).

    The id is handed to ``rustdesk --connect`` as a plain argument, never
    through a shell, but it is still restricted to the characters a RustDesk id
    can legitimately contain: no spaces, no slashes, no shell metacharacters.
    A ``:port`` suffix (Direct IP Access) must be a usable TCP port.
    """
    if not peer_id:
        return True  # the id is optional
    if len(peer_id) > 64:
        return False
    if not _RUSTDESK_ID_RE.match(peer_id):
        return False
    _, sep, port = peer_id.rpartition(":")
    if sep and not 1 <= int(port) <= 65535:
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


# ── Ping (status checks + scanner) ─────────────────────────────────────────

def build_ping_args(host: str, count: int = 1, timeout_ms: int = 1000) -> list[str]:
    """Platform-correct ``ping`` argv for a bounded reachability probe.

    The three OSes disagree on every relevant flag:

    * Windows: ``-4`` (force IPv4 - IPv6 replies carry no ``TTL=`` token),
      ``-n`` count, ``-w`` per-reply wait in **milliseconds**.
    * macOS/BSD: no ``-4`` (IPv4 literals need none), ``-c`` count,
      ``-W`` per-reply wait in **milliseconds**; without ``-W`` an
      unreachable host blocks for ~10 s.
    * Linux: ``-c`` count, ``-w`` total deadline in **seconds**.
    """
    if sys.platform == "win32":
        return ["ping", "-4", "-n", str(count), "-w", str(int(timeout_ms)), host]
    if sys.platform == "darwin":
        return ["ping", "-c", str(count), "-W", str(int(timeout_ms)), host]
    return ["ping", "-c", str(count), "-w", str(max(1, int(timeout_ms) // 1000)), host]


# ── Remote Desktop ──────────────────────────────────────────────────────────

def _build_rdp_content(
    ip: str,
    username: str,
    password: str,
    fullscreen: bool,
    width: int,
    height: int,
    prompt_for_password: bool = False,
    auth_level: int = 1,
) -> str:
    """Build the content of a temporary ``.rdp`` file for *ip*.

    The password is **never** written to the file. Windows 10/11 ``mstsc``
    ignores an embedded ``password:54:`` field anyway, and keeping it out of
    the file closes the local credential leak (the temp file lives in the
    user profile). Credentials reach mstsc through the Windows Credential
    Manager entry registered by :func:`_register_rdp_credentials`; when that
    registration failed, *prompt_for_password* makes mstsc ask the user
    instead of connecting with an empty password.

    *auth_level* maps to mstsc's ``authentication level``:

    * ``0`` — connect without verifying the server certificate (insecure,
      legacy; typical for xrdp hosts that ship a self-signed certificate).
    * ``1`` — warn on an unexpected certificate (default; the user sees a
      MITM warning instead of silently trusting a spoofed host).
    * ``2`` — connect only when the server certificate matches exactly.

    *prompt_for_password* forces mstsc's credential prompt even when a
    password is set. Used as a fallback when the password could not be
    registered with the Credential Manager: connecting without credentials
    is not a graceful failure — Windows hosts re-prompt, but xrdp hosts
    (Linux) drop the connection immediately.
    """
    try:
        level = int(auth_level)
    except (TypeError, ValueError):
        level = 1
    if level not in (0, 1, 2):
        level = 1

    prompt = (not password) or prompt_for_password
    lines = [
        f"full address:s:{ip}",
        # Use the Credential Manager entry instead of prompting when the
        # password was registered; the password itself is never in this file.
        f"prompt for password:i:{1 if prompt else 0}",
        # Server certificate validation. Default 1 = warn on an unexpected
        # certificate so a spoofed host cannot connect silently. 0 disables
        # verification (legacy, for self-signed xrdp hosts); 2 requires an
        # exact certificate match.
        f"authentication level:i:{level}",
        # Keep the address we connected to as the server identity after an
        # RDP redirection/broker hop. Required for xrdp (Ubuntu) hosts, which
        # otherwise present a redirection name the client cannot match or
        # resolve; harmless for plain Windows hosts.
        "use redirection server name:i:1",
    ]
    if username:
        lines.append(f"username:s:{username}")
    # NOTE: the password is intentionally NOT embedded (no "password:54:").
    # It is supplied via the Windows Credential Manager (cmdkey) or, when
    # that is unavailable, by mstsc's own prompt (prompt_for_password).
    if fullscreen:
        lines.append("fullscreen:i:1")
    else:
        # gnome-remote-desktop (Ubuntu) rejects odd session dimensions — see
        # _even_size — so the geometry keys always carry even pixel values.
        w, h = _even_size(width), _even_size(height)
        lines.append("fullscreen:i:0")
        lines.append(f"desktopwidth:i:{w}")
        lines.append(f"desktopheight:i:{h}")
        # Do not span the window over multiple monitors.
        lines.append("use multimon:i:0")
        # Position the window at 10,10 (winposstr = left,top,right,bottom).
        lines.append(
            f"winposstr:s:0,1,10,10,{w + 10},{h + 10}"
        )
    return "\r\n".join(lines) + "\r\n"


def _even_size(value: int) -> int:
    """Round *value* down to the nearest even number (never below 0).

    gnome-remote-desktop hosts (Ubuntu 22.04+, the built-in RDP server) run
    their H.264/AVC encoder over the session framebuffer, which requires
    **even** width and height. A session requested with an odd dimension is
    dropped by the server immediately, and mstsc surfaces this as the
    misleading "Critical error (error code: 5) — not enough virtual memory"
    dialog. Every session geometry the app generates (desktopwidth/height,
    /w:/h:, winposstr) is therefore forced to even values so windowed
    sessions also work against gnome-remote-desktop hosts.
    """
    v = max(0, int(value))
    return v - (v % 2)


def _cleanup_rdp_file(path: str, delay: float) -> None:
    """Delete *path* after *delay* seconds (runs in a daemon thread)."""
    time.sleep(delay)
    try:
        os.remove(path)
    except OSError:
        pass


def _monitor_mstsc_fast_exit(process, started_at: float,
                             fast_exit_window: float, callback) -> None:
    """Invoke *callback* when *process* exits within *fast_exit_window* seconds.

    Runs in a daemon thread. *started_at* is a ``time.monotonic()`` value taken
    just before ``mstsc`` was launched, so the measured lifetime is accurate.

    A wrong password against an xrdp/Linux host (typical for Ubuntu) shows as a
    black screen followed by an immediate exit — a very short process lifetime
    is the signal that the caller offers a password-less retry for. The monitor
    waits at most ``fast_exit_window + 30`` seconds; a session that survives
    the window (or is still running when the extra wait expires) never triggers
    *callback*. Any error is swallowed: the monitor must never crash the app.
    """
    try:
        process.wait(timeout=fast_exit_window + 30.0)
    except Exception:  # noqa: BLE001 - TimeoutExpired/wait errors => still running
        return
    if (time.monotonic() - started_at) <= fast_exit_window:
        try:
            callback()
        except Exception:  # noqa: BLE001 - never propagate out of the monitor
            pass


def _sanitize_filename_part(name: str) -> str:
    """Make *name* safe to use as a single Windows filename segment."""
    cleaned = re.sub(r'[\\/:*?"<>|]', "_", str(name)).strip()
    cleaned = re.sub(r"\s+", "_", cleaned)
    return cleaned or "device"


# ── User data directory helpers ─────────────────────────────────────────────

def _is_elevated() -> bool:
    """Return True when the current process runs elevated (as administrator)."""
    if os.name != "nt":
        return False
    try:
        import ctypes

        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def ensure_user_data_dir(path: Path) -> None:
    """Create *path* (with parents) and guarantee the interactive user owns it.

    ``mkdir(mode=0o700)`` has **no effect as an ACL on Windows**: the new
    directory simply inherits the parent's access rights. When the app happens
    to run elevated (e.g. launched via "Run as administrator", or from an
    elevated context), the created ``~/.wol_app`` tree can end up with an
    owner/DACL that blocks the normal (non-elevated) user later — Windows then
    shows the "You need permission to access this folder" (Fortsetzen)
    dialog on the next start.

    To prevent this, every creation point of the user data directory goes
    through this helper: after ``mkdir`` it explicitly grants ``Full`` control
    to the current interactive user (``USERDOMAIN\\USERNAME``) via ``icacls``.
    The grant runs only when the process is elevated (a non-elevated process
    creates the folder with its own token anyway and could not change the
    ACLs regardless). Best-effort: failures are reported via the returned
    boolean rather than raising, so folder creation itself never breaks.

    Args:
        path: Directory to create and protect (e.g. ``~/.wol_app``).

    Returns:
        True if the directory exists afterwards; False otherwise.
    """
    import logging

    try:
        path.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        # Folder may already exist but be inaccessible — try the ACL repair
        # below anyway before giving up.
        pass
    except OSError:
        return False

    if os.name == "nt" and _is_elevated():
        username = os.environ.get("USERNAME", "")
        userdomain = os.environ.get("USERDOMAIN", ".")
        if username:
            user_account = f"{userdomain}\\{username}"
            # Only the directory itself is granted here; recursion happens at
            # the app-level repair (config._fix_directory_permissions) when a
            # full-tree fix is needed.
            try:
                subprocess.run(
                    ["icacls", str(path), "/grant", f"{user_account}:(OI)(CI)F", "/Q"],
                    capture_output=True,
                    timeout=10,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            except Exception as exc:  # noqa: BLE001 - best effort by design
                logging.getLogger("wol_app.utils").warning(
                    "icacls grant failed for %s: %s", path, exc
                )

    return path.is_dir()


def _repair_dir_permissions(path: Path) -> bool:
    """Best-effort ACL repair so *path* becomes writable by the current user.

    Used as a self-healing fallback when writing into the user data directory
    fails with ``PermissionError`` (e.g. the folder was created by a previous
    elevated app start and is owned by the administrator account).

    * Elevated process: run ``takeown`` + ``icacls`` directly.
    * Non-elevated process: run them through a single elevated
      ``cmd /c ...`` (triggers one UAC prompt) and wait up to 30 s.

    Returns True if the commands reported success; never raises.
    """
    if os.name != "nt" or not path.exists():
        return False
    username = os.environ.get("USERNAME", "")
    userdomain = os.environ.get("USERDOMAIN", ".")
    if not username:
        return False
    user_account = f"{userdomain}\\{username}"
    commands = (
        f'takeown /f "{path}" /r /d y '
        f'& icacls "{path}" /reset /t /c /q '
        f'& icacls "{path}" /grant "{user_account}":(OI)(CI)F /t /c /q'
    )
    try:
        if _is_elevated():
            result = subprocess.run(
                ["cmd", "/c", commands],
                capture_output=True,
                timeout=60,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            return result.returncode == 0

        # Not elevated: ask Windows for a single elevation for the repair.
        import ctypes
        from ctypes import wintypes

        class SHELLEXECUTEINFOW(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD),
                ("fMask", ctypes.c_ulong),
                ("hwnd", wintypes.HWND),
                ("lpVerb", wintypes.LPCWSTR),
                ("lpFile", wintypes.LPCWSTR),
                ("lpParameters", wintypes.LPCWSTR),
                ("lpDirectory", wintypes.LPCWSTR),
                ("nShow", ctypes.c_int),
                ("hInstApp", wintypes.HINSTANCE),
                ("lpIDList", ctypes.c_void_p),
                ("lpClass", wintypes.LPCWSTR),
                ("hkeyClass", wintypes.HKEY),
                ("dwHotKey", wintypes.DWORD),
                ("hIconOrMonitor", ctypes.c_void_p),
                ("hProcess", wintypes.HANDLE),
            ]

        SEE_MASK_NOCLOSEPROCESS = 0x00000040
        info = SHELLEXECUTEINFOW()
        info.cbSize = ctypes.sizeof(SHELLEXECUTEINFOW)
        info.fMask = SEE_MASK_NOCLOSEPROCESS
        info.lpVerb = "runas"
        info.lpFile = "cmd.exe"
        info.lpParameters = f"/c {commands}"
        info.nShow = 0  # SW_HIDE
        if not ctypes.windll.shell32.ShellExecuteExW(ctypes.byref(info)):
            return False
        if info.hProcess:
            # INFINITE would risk blocking the UI; 30 s is plenty for takeown.
            try:
                kernel32 = ctypes.windll.kernel32
                kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
                kernel32.WaitForSingleObject(info.hProcess, 30000)
            finally:
                ctypes.windll.kernel32.CloseHandle(info.hProcess)
        return True
    except Exception:  # noqa: BLE001 - best effort by design
        return False


# Directory that holds the per-device temporary ``.rdp`` files. The files are
# written here so they live alongside the rest of the app data; they are still
# deleted after the connection starts (see launch_remote_desktop).
_RDP_DIR = Path.home() / ".wol_app" / "rdp"


def auto_rdp_resolution(
    screen_width: int,
    screen_height: int,
    fraction: float | None = None,
    minimum: tuple[int, int] = (1280, 720),
) -> tuple[int, int]:
    """Return a 16:9 remote-desktop window size slightly smaller than *screen*.

    Used by the "Optimized 16:9" remote desktop setting: the window is sized
    to a clean 16:9 resolution at *fraction* of the primary display so it fits
    on screen without scrolling.

    The size is derived primarily from the screen **height**: the window must
    never be taller than the display, so on ultra-wide (21:9+) monitors the
    height drives the 16:9 window and the width is computed from it. As a
    safety net, if that width would still exceed the screen width, the size is
    recomputed from the width instead so nothing falls off-screen.

    Args:
        screen_width: Physical width of the primary screen in pixels.
        screen_height: Physical height of the primary screen in pixels.
        fraction: Fraction of the screen size to use; defaults to
            REMOTE_DESKTOP_AUTO_FRACTION from config.
        minimum: Lower clamp (width, height); keeps the window usable.

    Returns:
        A (width, height) 16:9 pair that fits the given screen. Both values
        are always **even**: gnome-remote-desktop hosts (Ubuntu) reject odd
        session dimensions (see :func:`_even_size`), and raw screen sizes at
        fractional DPI scaling multiplied by a fraction routinely produce
        odd pixel counts.
    """
    if screen_width <= 0 or screen_height <= 0:
        return minimum
    # Resolve the default from config so there is a single source of truth for
    # the auto-resolution fraction (REMOTE_DESKTOP_AUTO_FRACTION). The import
    # is lazy to avoid a circular import: config.py imports from this module.
    if fraction is None:
        from wol_app.config import REMOTE_DESKTOP_AUTO_FRACTION

        fraction = REMOTE_DESKTOP_AUTO_FRACTION
    # 1) Height-first: derive the 16:9 window from the screen height so it can
    #    never be taller than the display (important for 21:9+ monitors).
    target_height = int(round(screen_height * fraction))
    target_width = int(round(target_height * 16 / 9))
    # 2) Safety net: if the width would exceed the screen width, recompute from
    #    the width instead so the window still fits fully on screen.
    if target_width > screen_width:
        target_width = screen_width
        target_height = int(round(target_width * 9 / 16))
    min_w, min_h = minimum
    if target_width < min_w:
        target_width = min_w
        target_height = int(round(min_w * 9 / 16))
    if target_height < min_h:
        target_height = min_h
    # gnome-remote-desktop (Ubuntu) drops sessions with odd dimensions with
    # mstsc's "critical error (code 5)" dialog — never hand it odd numbers.
    return (_even_size(target_width), _even_size(target_height))


def _register_rdp_credentials(host: str, username: str, password: str) -> bool:
    """Store Remote Desktop credentials in the Windows Credential Manager.

    Windows 10/11 ``mstsc`` ignores the password embedded in an ``.rdp``
    file for security reasons, so the credentials are registered with the
    Windows Credential Manager via ``cmdkey`` instead. mstsc reads the
    matching entry automatically when it connects to *host*, which lets the
    session open without re-prompting for the password.

    IMPORTANT: mstsc only picks up entries whose target carries the
    ``TERMSRV/`` prefix (``TERMSRV/<host>``) — a plain generic entry without
    the prefix is never offered to Remote Desktop. Without a matching entry
    mstsc connects with an empty password, which a Windows host masks with a
    re-prompt dialog but an xrdp host answers by dropping the connection
    immediately (the mstsc window opens and closes right away).

    A generic entry stored under the bare *host* (the pre-TERMSRV format used
    by older app versions) is deleted so it cannot linger in the Credential
    Manager.

    Args:
        host: Target host (IPv4 address or name) as used by mstsc.
        username: RDP username; empty skips registration.
        password: RDP password; empty skips registration.

    Returns:
        True when *username* and *password* were stored (or nothing needed to
        be stored because one of them is empty). False when a password was
        present but ``cmdkey`` could not run or reported an error — the caller
        then forces mstsc's own credential prompt instead of connecting with
        an empty password.
    """
    if not username or not password:
        return True
    # Remove a legacy entry stored under the bare host (old format without
    # the TERMSRV/ prefix). Non-fatal: the entry usually does not exist.
    try:
        subprocess.run(["cmdkey", f"/delete:{host}"], check=False)
    except OSError:
        pass
    cmd = [
        "cmdkey",
        f"/generic:TERMSRV/{host}",
        f"/user:{username}",
        f"/pass:{password}",
    ]
    try:
        result = subprocess.run(cmd, check=False)
    except OSError:
        # cmdkey is unavailable; the caller will make mstsc prompt instead.
        return False
    return getattr(result, "returncode", 0) == 0


def _delete_rdp_credentials(host: str) -> bool:
    """Remove the ``TERMSRV/<host>`` entry from the Windows Credential Manager.

    Used before a password-less retry: while the stored entry exists, mstsc
    keeps authenticating with it automatically and never shows its credential
    prompt — the connection would fail exactly like the first attempt. Only
    the Credential Manager entry is deleted; the password stored in the device
    record stays untouched.

    Args:
        host: Target host (IPv4 address or name) as used by mstsc.

    Returns:
        True when ``cmdkey`` reported success. False on errors — non-fatal:
        the entry usually does not exist, and mstsc prompts on its own when
        no credentials are available.
    """
    try:
        result = subprocess.run(
            ["cmdkey", f"/delete:TERMSRV/{host}"], check=False
        )
    except OSError:
        return False
    return getattr(result, "returncode", 0) == 0


def _write_rdp_and_start_mstsc(
    ip: str,
    content: str,
    fullscreen: bool,
    width: int,
    height: int,
    device_name: str,
    cleanup_delay: float,
) -> tuple[str, object]:
    """Write the ``.rdp`` *content* for *ip* and launch ``mstsc`` on it.

    Shared machinery for :func:`launch_remote_desktop` and
    :func:`retry_remote_desktop_without_password`. The file lives in
    ``~/.wol_app/rdp/`` named after the device (falling back to *ip*) and is
    deleted *cleanup_delay* seconds later so credentials do not linger on
    disk. The geometry is forced on the command line because mstsc ignores
    ``fullscreen:i:0`` inside an .rdp file; the .rdp path is always the last
    argument and supplies the username (which mstsc cannot take via CLI).

    Returns:
        A ``(rdp_path, process)`` tuple.

    Raises:
        RuntimeError: if the file cannot be written even after an ACL repair.
        OSError: if mstsc cannot be started (the .rdp file is removed).
    """
    base_name = _sanitize_filename_part(device_name or ip)
    ensure_user_data_dir(_RDP_DIR)
    rdp_path = _RDP_DIR / f"{base_name}.rdp"
    try:
        with open(rdp_path, "w", encoding="utf-8") as f:
            f.write(content)
    except PermissionError:
        # The directory (or an old file in it) is not accessible for the
        # current user — typically because a previous elevated app start
        # created it with admin-only permissions. Try to repair the ACLs
        # (takeown + icacls, may trigger a UAC prompt) and retry once.
        _repair_dir_permissions(_RDP_DIR)
        try:
            with open(rdp_path, "w", encoding="utf-8") as f:
                f.write(content)
        except PermissionError as exc:
            raise RuntimeError(
                f"Cannot write remote desktop file to {_RDP_DIR}. "
                "The folder is not accessible for the current user. "
                "Repair it once from an elevated terminal with: "
                f'takeown /f "{_RDP_DIR}" /r /d y  and  '
                f'icacls "{_RDP_DIR}" /reset /t /c /q'
            ) from exc

    # Force the geometry on the command line (reliable) and let the .rdp
    # file supply the credentials. The .rdp path is always the last argument.
    # Even values only: gnome-remote-desktop rejects odd session dimensions
    # (see _even_size), and the CLI arguments override the .rdp file keys.
    if fullscreen:
        cmd = ["mstsc", f"/v:{ip}", "/f", rdp_path]
    else:
        cmd = [
            "mstsc",
            f"/v:{ip}",
            f"/w:{_even_size(width)}",
            f"/h:{_even_size(height)}",
            rdp_path,
        ]
    try:
        process = subprocess.Popen(cmd)
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
    return str(rdp_path), process


def _launch_remote_desktop_windows(
    ip: str,
    username: str = "",
    password: str = "",
    fullscreen: bool = True,
    width: int = 1920,
    height: int = 1080,
    cleanup_delay: float = 5.0,
    device_name: str = "",
    on_fast_exit=None,
    fast_exit_window: float = 10.0,
    auth_level: int = 1,
) -> str:
    """Launch Windows Remote Desktop (``mstsc``) to *ip*.

    A temporary ``.rdp`` file is written and passed to mstsc; it never
    contains the password (see :func:`_build_rdp_content`) and is deleted
    *cleanup_delay* seconds later.

    The session geometry is forced via **command-line arguments**, because
    mstsc is known to ignore ``fullscreen:i:0`` inside an .rdp file (it then
    falls back to full-screen). The .rdp file is still passed so that the
    username (which mstsc cannot take on the command line) is supplied.
    Because Windows 10/11 mstsc ignores an embedded password, the credentials
    are additionally registered with the Windows Credential Manager via
    ``cmdkey`` so the password does not have to be re-entered:

    * ``fullscreen=True``  → ``mstsc /v:<ip> /f <file>``
    * ``fullscreen=False`` → ``mstsc /v:<ip> /w:<width> /h:<height> <file>``

    The ``/w:``/``/h:``/``/f`` arguments have the highest precedence and
    reliably determine whether the session opens in a window or full-screen.

    **Fast-exit monitoring:** when a *password* is set and *on_fast_exit* is
    provided, the mstsc process is watched in a daemon thread. If it exits
    within *fast_exit_window* seconds — the black-screen-then-close pattern
    of a wrong password against an xrdp/Linux (Ubuntu) host — *on_fast_exit*
    is invoked **on that background thread**. The callback must be thread-safe
    and should marshal any UI work (e.g. via a Qt signal) to the main thread;
    :func:`retry_remote_desktop_without_password` is the intended follow-up.

    Args:
        ip: Target host (IPv4 address or name).
        username: Optional RDP user; empty leaves mstsc's default.
        password: Optional RDP password; empty makes mstsc prompt.
        fullscreen: Full-screen mode when True, windowed mode when False.
        width: Window width in pixels (windowed mode only).
        height: Window height in pixels (windowed mode only).
        cleanup_delay: Seconds to wait before deleting the temp file.
        device_name: Device name used for the temp file's basename; falls
            back to *ip* when empty or missing.
        on_fast_exit: Optional callable invoked (from a background thread)
            when mstsc exits within *fast_exit_window* seconds. Only watched
            when a password was supplied.
        fast_exit_window: Seconds below which an mstsc exit counts as fast.

    Returns:
        Path of the written ``.rdp`` file.

    Raises:
        ValueError: if *ip* is empty.
        OSError: if mstsc cannot be started (e.g. not found).
    """
    if not ip:
        raise ValueError("IP address is empty")

    # Register the credentials with the Windows Credential Manager so mstsc
    # can log in without re-prompting for the password. If that fails we must
    # NOT connect anyway: mstsc would then authenticate without a password,
    # which Windows hosts mask with a re-prompt but xrdp hosts answer by
    # closing the session immediately (window opens and vanishes again).
    credentials_ready = _register_rdp_credentials(ip, username, password)

    content = _build_rdp_content(
        ip, username, password, fullscreen, width, height,
        prompt_for_password=not credentials_ready, auth_level=auth_level,
    )

    # Take the timestamp before launching so the monitor measures the full
    # process lifetime (Popen setup included).
    started_at = time.monotonic()
    rdp_path, process = _write_rdp_and_start_mstsc(
        ip, content, fullscreen, width, height, device_name, cleanup_delay
    )

    if password and on_fast_exit is not None and fast_exit_window > 0:
        threading.Thread(
            target=_monitor_mstsc_fast_exit,
            args=(process, started_at, float(fast_exit_window), on_fast_exit),
            daemon=True,
        ).start()
    return rdp_path


def _retry_remote_desktop_windows(
    ip: str,
    username: str = "",
    fullscreen: bool = True,
    width: int = 1920,
    height: int = 1080,
    device_name: str = "",
    cleanup_delay: float = 30.0,
) -> str:
    """Second connection attempt in which the user types the password.

    Used after :func:`launch_remote_desktop` detected a fast mstsc exit —
    the signature of a rejected password on an xrdp/Linux host. The stored
    ``TERMSRV/<host>`` Credential Manager entry is deleted first (otherwise
    mstsc keeps authenticating with the wrong password automatically and
    never shows its prompt), then mstsc is started with the username but
    **without** a password so the user is asked for it directly in the mstsc
    dialog. The password stored in the device record is not modified.

    No fast-exit monitoring is armed for this attempt — the user is expected
    to type the correct password, and a retry loop is never desirable.

    Args:
        ip: Target host (IPv4 address or name).
        username: RDP user to pre-fill; empty leaves mstsc's default.
        fullscreen: Full-screen mode when True, windowed mode when False.
        width: Window width in pixels (windowed mode only).
        height: Window height in pixels (windowed mode only).
        device_name: Device name used for the temp file's basename.
        cleanup_delay: Seconds before the temp file is deleted; generous by
            default because the user needs time at the password prompt.

    Returns:
        Path of the written ``.rdp`` file.

    Raises:
        ValueError: if *ip* is empty.
        OSError: if mstsc cannot be started (e.g. not found).
    """
    if not ip:
        raise ValueError("IP address is empty")

    # Without this deletion mstsc would silently re-use the stored (wrong)
    # password from the Credential Manager and skip the prompt entirely.
    _delete_rdp_credentials(ip)

    content = _build_rdp_content(
        ip, username, "", fullscreen, width, height,
        prompt_for_password=True,
    )
    rdp_path, _process = _write_rdp_and_start_mstsc(
        ip, content, fullscreen, width, height, device_name, cleanup_delay
    )
    return rdp_path


# ── Remote Desktop: Linux (FreeRDP / xfreerdp) ──────────────────────────────

def xfreerdp_available() -> bool:
    """Return True when the FreeRDP client ``xfreerdp`` is on PATH."""
    return shutil.which("xfreerdp") is not None


def build_xfreerdp_args(
    ip: str,
    username: str = "",
    password: str = "",
    fullscreen: bool = True,
    width: int = 1920,
    height: int = 1080,
) -> list[str]:
    """Build the ``xfreerdp`` command line for *ip*.

    ``/v:`` takes the host, ``/u:``/``/p:`` the credentials (only when set),
    ``/f`` full-screen and ``/geometry:WxH`` a windowed session.
    ``+auto-reconnect`` mirrors the convenience of the Windows client.
    """
    args = ["xfreerdp", f"/v:{ip}"]
    if username:
        args.append(f"/u:{username}")
    if password:
        args.append(f"/p:{password}")
    if fullscreen:
        args.append("/f")
    else:
        args.append(f"/geometry:{int(width)}x{int(height)}")
    args.append("+auto-reconnect")
    return args


def _launch_remote_desktop_linux(
    ip: str,
    username: str = "",
    password: str = "",
    fullscreen: bool = True,
    width: int = 1920,
    height: int = 1080,
    device_name: str = "",
    on_fast_exit=None,
    fast_exit_window: float = 10.0,
    **_ignored,
) -> None:
    """Launch a FreeRDP (``xfreerdp``) Remote Desktop session to *ip*.

    Same fast-exit contract as the Windows path: when a *password* is set and
    *on_fast_exit* is given, the xfreerdp process is watched in a daemon
    thread and *on_fast_exit* fires if it dies within *fast_exit_window*
    seconds — the xrdp/Ubuntu wrong-password signature (a session that opens
    and vanishes immediately). The callback runs on that background thread and
    must marshal any UI work to the GUI thread (see ``remote_desktop``).

    Raises:
        ValueError: if *ip* is empty.
        RuntimeError: if ``xfreerdp`` is not installed.
        OSError: if xfreerdp cannot be started.
    """
    if not ip:
        raise ValueError("IP address is empty")
    if not xfreerdp_available():
        raise RuntimeError(
            "xfreerdp not found. Install it with: sudo apt install freerdp2-x11"
        )

    cmd = build_xfreerdp_args(
        ip, username, password, fullscreen=fullscreen, width=width, height=height
    )
    # Take the timestamp before launching so the monitor measures the full
    # process lifetime (Popen setup included). shell=False: no command injection.
    started_at = time.monotonic()
    process = subprocess.Popen(cmd)

    if password and on_fast_exit is not None and fast_exit_window > 0:
        threading.Thread(
            target=_monitor_mstsc_fast_exit,
            args=(process, started_at, float(fast_exit_window), on_fast_exit),
            daemon=True,
        ).start()


def _retry_remote_desktop_linux(
    ip: str,
    username: str = "",
    fullscreen: bool = True,
    width: int = 1920,
    height: int = 1080,
    device_name: str = "",
    **_ignored,
) -> None:
    """Second connection attempt in which the user types the password.

    Used after :func:`_launch_remote_desktop_linux` detected a fast xfreerdp
    exit — the signature of a rejected password on an xrdp/Linux host. xfreerdp
    is started with the username but **without** ``/p:`` so it prompts for the
    password directly. The password stored in the device record is not
    modified. No fast-exit monitoring is armed for this attempt.

    Raises:
        ValueError: if *ip* is empty.
        RuntimeError: if ``xfreerdp`` is not installed.
        OSError: if xfreerdp cannot be started.
    """
    if not ip:
        raise ValueError("IP address is empty")
    if not xfreerdp_available():
        raise RuntimeError(
            "xfreerdp not found. Install it with: sudo apt install freerdp2-x11"
        )
    cmd = build_xfreerdp_args(
        ip, username, "", fullscreen=fullscreen, width=width, height=height
    )
    subprocess.Popen(cmd)


# ── Remote Desktop: macOS (Microsoft Remote Desktop) ────────────────────────

#: Bundle id of the Microsoft Remote Desktop app on the Mac App Store.
MACOS_RD_BUNDLE_ID = "com.microsoft.rdc.macos"
#: Install pointer used in error messages when the app is missing.
MACOS_RD_INSTALL_URL = "https://aka.ms/rdmac/mac"


def macos_remote_desktop_available() -> bool:
    """True when the Microsoft Remote Desktop app is installed (macOS).

    Looks the app up by bundle id via Spotlight (``mdfind``); when Spotlight
    is disabled or has no index, falls back to the well-known install
    locations.
    """
    try:
        result = subprocess.run(
            ["mdfind", f"kMDItemCFBundleIdentifier == '{MACOS_RD_BUNDLE_ID}'"],
            capture_output=True, text=True, timeout=5,
        )
        if result.stdout.strip():
            return True
    except (OSError, subprocess.TimeoutExpired):
        pass
    for candidate in (
        "/Applications/Microsoft Remote Desktop.app",
        str(Path.home() / "Applications/Microsoft Remote Desktop.app"),
    ):
        if os.path.isdir(candidate):
            return True
    return False


def build_macos_rdp_url(ip: str, username: str = "") -> str:
    """Build the ``rdp://`` URI for the Microsoft Remote Desktop client.

    Uses the legacy RDP URI scheme (``rdp://key=type:value&...``) that the
    macOS client registers; the username is pre-filled when given. The
    password can never travel in the URL — the user types it into the
    Microsoft Remote Desktop prompt.
    """
    from urllib.parse import quote

    url = f"rdp://full%20address=s:{quote(ip, safe='')}"
    if username:
        url += f"&username=s:{quote(username, safe='')}"
    return url


def _launch_remote_desktop_macos(
    ip: str,
    username: str = "",
    password: str = "",  # noqa: ARG001 - the client never accepts a CLI password
    **_ignored,
) -> None:
    """Open a Remote Desktop session via the Microsoft Remote Desktop app.

    The app is launched through its ``rdp://`` URL scheme (username
    pre-filled). Passwords cannot be handed to the client, so the user types
    it into the Microsoft Remote Desktop prompt; fast-exit monitoring is not
    available for LaunchServices launches and is silently skipped.

    Raises:
        ValueError: if *ip* is empty.
        RuntimeError: if Microsoft Remote Desktop is not installed.
        OSError: if ``open`` could not run at all.
    """
    if not ip:
        raise ValueError("IP address is empty")
    if not macos_remote_desktop_available():
        raise RuntimeError(
            "Microsoft Remote Desktop not found. "
            f"Install it from {MACOS_RD_INSTALL_URL}"
        )
    url = build_macos_rdp_url(ip, username)
    result = subprocess.run(["open", url], capture_output=True, timeout=15)
    if result.returncode != 0:
        # URL scheme not registered (older/newer client builds vary) — at
        # least bring the app to the front so the user can connect manually.
        subprocess.run(
            ["open", "-b", MACOS_RD_BUNDLE_ID], capture_output=True, timeout=15,
        )


def _retry_remote_desktop_macos(
    ip: str,
    username: str = "",
    **_ignored,
) -> None:
    """Re-open the Microsoft Remote Desktop session for *ip*.

    The first attempt already prompts for the password on macOS (the client
    never receives it), so this is the same launch without credentials.
    """
    _launch_remote_desktop_macos(ip, username)


def launch_remote_desktop(
    ip: str,
    username: str = "",
    password: str = "",
    fullscreen: bool = True,
    width: int = 1920,
    height: int = 1080,
    cleanup_delay: float = 5.0,
    device_name: str = "",
    on_fast_exit=None,
    fast_exit_window: float = 10.0,
    auth_level: int = 1,
):
    """Launch a Remote Desktop session to *ip*.

    Backends: ``mstsc`` (Windows), ``xfreerdp`` (Linux) and the Microsoft
    Remote Desktop app via its ``rdp://`` URL scheme (macOS).

    *auth_level* (Windows) maps to mstsc's ``authentication level``: ``0``
    connect without verifying the server certificate, ``1`` warn on an
    unexpected certificate (default), ``2`` connect only on an exact match.
    It is ignored by the Linux/macOS backends.

    Platform dispatch over the shared fast-exit contract: the Windows and
    Linux backends watch the process when a *password* is set and invoke
    *on_fast_exit* (from a background thread) when the session dies within
    *fast_exit_window* seconds. macOS cannot watch a LaunchServices launch
    and always prompts for the password in the client.
    Returns the ``.rdp`` file path on Windows, ``None`` on Linux/macOS.
    """
    if sys.platform == "win32":
        return _launch_remote_desktop_windows(
            ip, username, password, fullscreen, width, height,
            cleanup_delay, device_name, on_fast_exit, fast_exit_window,
            auth_level=auth_level,
        )
    if sys.platform == "darwin":
        return _launch_remote_desktop_macos(
            ip, username, password, fullscreen=fullscreen,
            width=width, height=height, device_name=device_name,
        )
    return _launch_remote_desktop_linux(
        ip, username, password, fullscreen, width, height,
        device_name, on_fast_exit, fast_exit_window,
    )


def retry_remote_desktop_without_password(
    ip: str,
    username: str = "",
    fullscreen: bool = True,
    width: int = 1920,
    height: int = 1080,
    device_name: str = "",
    cleanup_delay: float = 30.0,
):
    """Second connection attempt where the user types the password.

    Windows: deletes the ``TERMSRV/<host>`` Credential Manager entry and
    re-launches mstsc without a password. Linux: re-launches xfreerdp without
    ``/p:`` so it prompts. macOS: re-opens the Microsoft Remote Desktop app
    (which always prompts for the password anyway). Returns the ``.rdp`` path
    on Windows, ``None`` on Linux/macOS.
    """
    if sys.platform == "win32":
        return _retry_remote_desktop_windows(
            ip, username, fullscreen, width, height, device_name, cleanup_delay,
        )
    if sys.platform == "darwin":
        return _retry_remote_desktop_macos(
            ip, username, fullscreen=fullscreen, width=width, height=height,
            device_name=device_name,
        )
    return _retry_remote_desktop_linux(
        ip, username, fullscreen, width, height, device_name,
    )


# ── VNC (TurboVNC) ─────────────────────────────────────────────────────────

# TurboVNC ships no native viewer binary on Windows: the viewer is a Java jar
# behind ``vncviewer.bat`` / ``vncviewerw.bat``. The "w" variant starts javaw
# (no console window) and is therefore preferred.
_VNC_WINDOWS_LAUNCHERS = ("vncviewerw.bat", "vncviewer.bat")
_VNC_WINDOWS_DIR_NAMES = ("TurboVNC", "Turbo VNC")
# Executable names looked up on the PATH (Linux/macOS installs, RealVNC-style
# viewers that also answer to "vncviewer").
_VNC_PATH_NAMES = ("vncviewer", "vncviewer.exe")


def _vnc_candidate_dirs() -> list[str]:
    """Install directories that may hold a Windows VNC viewer."""
    roots: list[str] = []
    for var in ("ProgramFiles", "ProgramW6432", "ProgramFiles(x86)"):
        root = os.environ.get(var, "")
        if root and root not in roots:
            roots.append(root)
    return [
        os.path.join(root, name)
        for root in roots
        for name in _VNC_WINDOWS_DIR_NAMES
    ]


def find_vnc_viewer() -> str:
    """Locate a VNC viewer executable ("" when none was found).

    Search order: the TurboVNC default install directories (Windows), then the
    ``PATH`` (Linux/macOS installs put ``vncviewer`` in ``/usr/local/bin`` or
    ``/opt/TurboVNC/bin``). Never raises — an empty result simply means the
    caller should tell the user to install or configure a client.
    """
    if sys.platform == "win32":
        for directory in _vnc_candidate_dirs():
            for launcher in _VNC_WINDOWS_LAUNCHERS:
                candidate = os.path.join(directory, launcher)
                if os.path.isfile(candidate):
                    return candidate
    for name in _VNC_PATH_NAMES:
        found = shutil.which(name)
        if found:
            return found
    return ""


def build_vnc_args(
    viewer: str,
    ip: str,
    port: int = 5900,
    fullscreen: bool = True,
) -> list[str]:
    """Command line that opens a direct VNC connection to *ip*:*port*.

    TurboVNC addresses a literal TCP port with the doubled-colon form
    ``host::port`` (``host:1`` would mean display 1, i.e. port 5901), and
    ``-FullScreen 1`` starts the viewer full-screen. No credentials are ever
    part of the command line — the viewer prompts for the password (the caller
    may pre-fill the clipboard).
    """
    args = [viewer]
    if fullscreen:
        args += ["-FullScreen", "1"]
    args.append(f"{ip}::{int(port)}")
    return args


def launch_vnc(
    ip: str,
    port: int = 5900,
    viewer_path: str = "",
    fullscreen: bool = True,
) -> list[str]:
    """Open a VNC session to *ip*:*port* with the installed TurboVNC viewer.

    *viewer_path* overrides the auto-detection (empty = :func:`find_vnc_viewer`).
    Returns the command line that was started so the caller can log it.

    Raises:
        ValueError: if *ip* is empty.
        RuntimeError: if no VNC viewer is installed or configured.
        OSError: if the viewer could not be started.
    """
    if not ip:
        raise ValueError("IP address is empty")
    viewer = (viewer_path or "").strip() or find_vnc_viewer()
    if not viewer:
        raise RuntimeError(
            "No VNC viewer found. Install TurboVNC or set its path in the "
            "remote access settings."
        )
    cmd = build_vnc_args(viewer, ip, port=port, fullscreen=fullscreen)
    # CREATE_NO_WINDOW hides the console of TurboVNC's .bat launcher (the Java
    # viewer itself is a GUI process). shell=False: no command injection.
    creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    subprocess.Popen(cmd, creationflags=creationflags)
    return cmd


# ── RustDesk ───────────────────────────────────────────────────────────────

# RustDesk ships one executable that is client *and* server; the installed
# client is what opens an outgoing session. Windows installs to
# "Program Files\RustDesk\RustDesk.exe", macOS keeps the binary inside the app
# bundle (the bundle name uses a capital R, the file inside historically a
# lower-case one, so both are probed for case-sensitive volumes), and Linux
# packages install to /usr/bin.
_RUSTDESK_WINDOWS_DIR_NAMES = ("RustDesk",)
_RUSTDESK_WINDOWS_EXES = ("RustDesk.exe", "rustdesk.exe")
_RUSTDESK_MACOS_BINARIES = (
    "/Applications/RustDesk.app/Contents/MacOS/RustDesk",
    "/Applications/RustDesk.app/Contents/MacOS/rustdesk",
)
_RUSTDESK_LINUX_BINARIES = ("/usr/bin/rustdesk", "/opt/rustdesk/rustdesk")
_RUSTDESK_PATH_NAMES = ("rustdesk", "rustdesk.exe")


def _rustdesk_candidate_dirs() -> list[str]:
    """Install directories that may hold the Windows RustDesk client."""
    roots: list[str] = []
    for var in ("ProgramFiles", "ProgramW6432", "ProgramFiles(x86)",
                "LOCALAPPDATA"):
        root = os.environ.get(var, "")
        if root and root not in roots:
            roots.append(root)
    dirs = [
        os.path.join(root, name)
        for root in roots
        for name in _RUSTDESK_WINDOWS_DIR_NAMES
    ]
    # Per-user installs ("install for this user only") live under LOCALAPPDATA.
    local = os.environ.get("LOCALAPPDATA", "")
    if local:
        dirs.extend(os.path.join(local, "Programs", name)
                    for name in _RUSTDESK_WINDOWS_DIR_NAMES)
    return dirs


def find_rustdesk_client() -> str:
    """Locate the RustDesk client executable ("" when none was found).

    Search order: the platform's default install location, then the ``PATH``
    (portable installs and custom prefixes). Never raises — an empty result
    simply means the caller should tell the user to install or configure
    RustDesk.
    """
    if sys.platform == "win32":
        for directory in _rustdesk_candidate_dirs():
            for name in _RUSTDESK_WINDOWS_EXES:
                candidate = os.path.join(directory, name)
                if os.path.isfile(candidate):
                    return candidate
    else:
        binaries = (
            _RUSTDESK_MACOS_BINARIES if sys.platform == "darwin"
            else _RUSTDESK_LINUX_BINARIES
        )
        for candidate in binaries:
            if os.path.isfile(candidate):
                return candidate
    for name in _RUSTDESK_PATH_NAMES:
        found = shutil.which(name)
        if found:
            return found
    return ""


def build_rustdesk_target(
    peer_id: str,
    ip: str,
    direct_port: int = 21118,
) -> str:
    """How a device is addressed in RustDesk: its id, else Direct IP Access.

    A RustDesk id cannot be discovered by scanning, so a device without a
    stored id is reached through Direct IP Access: the peer answers on TCP 21118
    and is addressed as ``ip:port``. That stays inside the LAN and skips the
    rendezvous server and any relay — the fast path, and the one that works
    without a RustDesk account.
    """
    peer_id = (peer_id or "").strip()
    if peer_id:
        return peer_id
    if not ip:
        raise ValueError("Neither a RustDesk id nor an IP address is set")
    return f"{ip}:{int(direct_port)}"


def build_rustdesk_args(client: str, target: str) -> list[str]:
    """Command line that opens a RustDesk session to *target*.

    ``--connect <id>`` is RustDesk's documented entry point: it opens the
    session window and connects straight away, and an already running RustDesk
    instance takes the request over instead of starting a second copy. The
    password is never part of the command line (it would show up in the process
    list) — RustDesk remembers it per peer after the first entry, and the
    caller may pre-fill the clipboard for that first one.
    """
    return [client, "--connect", target]


def launch_rustdesk(
    ip: str,
    peer_id: str = "",
    direct_port: int = 21118,
    client_path: str = "",
) -> list[str]:
    """Open a RustDesk session to a device with the installed client.

    *peer_id* wins over *ip*; without it the peer is addressed by Direct IP
    Access on *direct_port*. *client_path* overrides the auto-detection
    (empty = :func:`find_rustdesk_client`). Returns the command line that was
    started so the caller can log it.

    Raises:
        ValueError: if neither *peer_id* nor *ip* is set.
        RuntimeError: if no RustDesk client is installed or configured.
        OSError: if the client could not be started.
    """
    target = build_rustdesk_target(peer_id, ip, direct_port=direct_port)
    client = (client_path or "").strip() or find_rustdesk_client()
    if not client:
        raise RuntimeError(
            "No RustDesk client found. Install RustDesk or set its path in the "
            "remote access settings."
        )
    cmd = build_rustdesk_args(client, target)
    # RustDesk is a GUI process; CREATE_NO_WINDOW only matters when a portable
    # build is started from a console. shell=False: no command injection.
    creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    subprocess.Popen(cmd, creationflags=creationflags)
    return cmd


# ── Sorting helpers ────────────────────────────────────────────────────────

def ip_sort_key(ip: str) -> tuple:
    """Sort IPv4 addresses numerically (192.168.1.9 < 192.168.1.10).

    Anything that is not four dotted decimals sorts after the numeric
    addresses, still alphabetically among itself. Shared between the
    devices screen and the dashboard's prev/next device navigation.
    """
    parts = (ip or "").split(".")
    if len(parts) == 4 and all(p.isdigit() for p in parts):
        return (0, tuple(int(p) for p in parts), "")
    return (1, (), ip or "")


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


# Normalized platform ids stored per device ("os" key) and reported by the
# host service (protocol v8). Lives here so both config and the network
# scanner can use it without importing each other.
OS_WINDOWS = "windows"
OS_MACOS = "macos"
OS_LINUX = "linux"
VALID_OS_IDS = (OS_WINDOWS, OS_MACOS, OS_LINUX)

#: locale key for each platform id (used by the scan UIs)
OS_LABEL_KEYS = {
    OS_WINDOWS: "scan_dialog.os.windows",
    OS_MACOS: "scan_dialog.os.macos",
    OS_LINUX: "scan_dialog.os.linux",
}


def normalize_os(value: object) -> str:
    """Collapse a platform id to ``windows``/``macos``/``linux`` ("" = unknown).

    The host service reports the concrete distribution (``ubuntu``,
    ``debian``, …); the UI groups everything else under ``linux`` so the
    scan table and the stored device records stay consistent.
    """
    if not isinstance(value, str):
        return ""
    ident = value.strip().lower()
    if ident in VALID_OS_IDS:
        return ident
    if ident == "darwin" or ident.startswith("macos"):
        return OS_MACOS
    if ident == "win32" or ident.startswith("windows"):
        return OS_WINDOWS
    if ident and ident != "unknown":
        return OS_LINUX
    return ""


def os_display_text(os_id: str, confidence: str) -> str:
    """Platform label for a device/host ("" when unknown, ``~`` = estimated).

    Shared by the scan results and the platform pill on the device cards and
    rows: only a high-confidence reading (the host service answered) is shown
    as a bare label, everything derived from TTL/SMB/OUI hints gets a ``~``.
    """
    label_key = OS_LABEL_KEYS.get(os_id)
    if label_key is None:
        return ""
    text = Translations.tr(label_key)
    return text if confidence == "high" else f"~ {text}"


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
        # Also check project root (icons etc. live next to run.py)
        root_path = os.path.dirname(base_path)
        if not os.path.exists(os.path.join(base_path, filename)) \
                and os.path.exists(os.path.join(root_path, filename)):
            base_path = root_path
    return os.path.join(base_path, filename)


def app_icon_for_mode(mode: str) -> str:
    """Icon file name for a UI layout mode (modern -> green, classic -> blue)."""
    return "icon_modern.ico" if mode == "modern" else "icon.ico"


def set_app_user_model_id(app_id: str) -> bool:
    """Set the Windows AppUserModelID of the current process.

    Windows groups a taskbar button with a pinned/installed shortcut when
    the IDs match and then shows the SHORTCUT's icon instead of the
    window's own. Using a layout-specific ID keeps the button separate, so
    the window icon wins and the taskbar follows the active UI layout.
    """
    if os.name != "nt":
        return False
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
        return True
    except Exception:
        return False


def force_window_foreground(widget) -> bool:
    """Bring a top-level window to the foreground, bypassing the platform's
    "a background process may not steal focus" rule.

    That rule is what breaks the single-instance raise request: a second
    launch tells the running instance to show itself, but the running
    instance is a *background* application, so ``showNormal()`` + ``raise_()``
    + ``activateWindow()`` only un-minimise the window — it stays behind the
    other windows (Windows: the taskbar button just flashes; macOS: the Dock
    icon bounces once and the window stays miniaturised/unfocused).

    * Windows: attach our input thread to the current foreground thread (the
      classic Raymond Chen trick) so ``SetForegroundWindow`` is accepted.
    * macOS: deminiaturise the ``NSWindow`` and activate the application with
      ``activateIgnoringOtherApps`` (PyObjC, bundled by the macOS build; a
      ctypes ``objc_msgSend`` fallback covers environments without it). A
      second launch does not even reach the ``RAISE`` request there — see
      :func:`install_macos_reopen_handler`, which calls this from the Cocoa
      reopen event.

    No-op on other platforms; returns True when the foreground call was
    attempted.
    """
    if sys.platform == "darwin":
        return _force_window_foreground_macos(widget)
    if os.name != "nt":
        return False
    try:
        import ctypes

        hwnd = int(widget.winId())
        if not hwnd:
            return False
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        # Only un-minimise when the window is actually iconic — SW_RESTORE on
        # a maximized window would un-maximize it, which is not wanted here.
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        fg = user32.GetForegroundWindow()
        fg_tid = user32.GetWindowThreadProcessId(fg, None)
        cur_tid = kernel32.GetCurrentThreadId()
        attached = bool(fg_tid) and fg_tid != cur_tid
        if attached:
            user32.AttachThreadInput(cur_tid, fg_tid, True)
        try:
            user32.BringWindowToTop(hwnd)
            user32.SetForegroundWindow(hwnd)
            user32.SetActiveWindow(hwnd)
        finally:
            if attached:
                user32.AttachThreadInput(cur_tid, fg_tid, False)
        return True
    except Exception:
        return False


def _force_window_foreground_macos(widget) -> bool:
    """macOS counterpart of :func:`force_window_foreground`.

    A second launch of the app either asks the running process to show
    itself (``RAISE`` over the single-instance socket, e.g. ``open -n`` or a
    terminal launch) or, far more often, only re-activates it through
    LaunchServices — in that case :func:`install_macos_reopen_handler` calls
    this from the Cocoa reopen event. Either way the process is a
    background application at that moment, and Qt's
    ``raise_()``/``activateWindow()`` cannot cross the AppKit activation
    boundary, so the AppKit objects behind the Qt window are used directly:

    * ``deminiaturize:`` — a window sitting in the Dock stays there otherwise
      (``showNormal()`` un-hides but does not un-miniaturise it),
    * ``activateIgnoringOtherApps:`` — makes the app itself frontmost, which
      is what brings it "out of the Dock" for the user.

    Needs PyObjC (``pyobjc-framework-Cocoa``, pulled in by requirements.txt
    on macOS and bundled by the .app build); without it the same AppKit
    calls are made through the Objective-C runtime via ctypes, so the fix
    also works in a plain venv. Returns True when activation was attempted.
    """
    try:
        import objc  # noqa: F401  (fails first when PyObjC is not installed)
        from AppKit import NSApplication, NSRunningApplication  # type: ignore

        nswin = None
        win_id = int(widget.winId() or 0)
        if win_id:
            # winId() is the QNSView, the NSWindow hangs below it.
            view = objc.objc_object(c_void_p=win_id)
            candidate = view.window()
            if candidate is not None and candidate.respondsToSelector_(
                    "isMiniaturized"):
                nswin = candidate
            if nswin is not None and not nswin.isMiniaturized():
                nswin = None  # plain visible window — activation is enough
        if nswin is not None:
            nswin.deminiaturize_(None)
        app = NSApplication.sharedApplication()
        if app.isHidden():
            app.unhide_(None)
        # Deprecated since macOS 14 but still the only call that reliably
        # steals focus for a background app; NSRunningApplication.activateWithOptions_
        # is tried as well (no-op on older systems, honoured on newer ones).
        app.activateIgnoringOtherApps_(True)
        current = NSRunningApplication.currentApplication()
        if current is not None:
            current.activateWithOptions_(1 << 1)  # NSApplicationActivateIgnoringOtherApps
        if nswin is not None:
            nswin.makeKeyAndOrderFront_(None)
        return True
    except Exception:
        return _force_window_foreground_macos_ctypes(widget)


def _force_window_foreground_macos_ctypes(widget) -> bool:
    """PyObjC-free fallback: drive the Objective-C runtime with ctypes.

    ``winId()`` is the ``QNSView*`` on macOS (its ``window`` selector yields
    the ``NSWindow*``) and ``[NSApplication sharedApplication]`` returns the
    ``QNSApplication`` instance Qt created; everything else is plain
    ``objc_msgSend``. (``objc_getVariable("NSApp")`` would be the shorter
    route, but that symbol is not exported by the current runtime.)
    """
    import ctypes
    import ctypes.util

    objc_lib = ctypes.CDLL(ctypes.util.find_library("objc") or "libobjc.A.dylib")
    objc_lib.sel_registerName.restype = ctypes.c_void_p
    objc_lib.sel_registerName.argtypes = [ctypes.c_char_p]
    objc_lib.objc_getClass.restype = ctypes.c_void_p
    objc_lib.objc_getClass.argtypes = [ctypes.c_char_p]
    objc_lib.objc_msgSend.restype = ctypes.c_void_p

    def send(target: int, selector: str, *extra) -> int:
        # Extra args are BOOL/flag values; passing them as pointer-sized
        # arguments matches the arm64/x86_64 calling convention for both.
        objc_lib.objc_msgSend.argtypes = (
            [ctypes.c_void_p, ctypes.c_void_p] + [ctypes.c_void_p] * len(extra))
        return objc_lib.objc_msgSend(
            target, objc_lib.sel_registerName(selector.encode()), *extra) or 0

    view = int(widget.winId() or 0)
    win = send(view, "window") if view else 0
    minimized = bool(win) and bool(send(win, "isMiniaturized"))
    if minimized:
        send(win, "deminiaturize:", 0)
    # The shared application instance Qt created (autoreleased — not retained).
    nsapp = send(objc_lib.objc_getClass(b"NSApplication"), "sharedApplication")
    if not nsapp:
        return False
    if send(nsapp, "isHidden"):
        send(nsapp, "unhide:", 0)
    # Deprecated since macOS 14 but still effective; the modern
    # NSRunningApplication call is issued as well (harmless on older systems).
    send(nsapp, "activateIgnoringOtherApps:", 1)
    current = send(objc_lib.objc_getClass(b"NSRunningApplication"),
                   "currentApplication")
    if current:
        # NSApplicationActivateIgnoringOtherApps = 1 << 1
        send(current, "activateWithOptions:", 1 << 1)
    if minimized:
        send(win, "makeKeyAndOrderFront:", 0)
    return True


# Keeps the installed ObjC delegate alive: NSApplication holds its delegate
# weakly, and the callback must not be collected either.
_macos_reopen_state: dict = {}


def install_macos_reopen_handler(callback) -> bool:
    """macOS: run ``callback()`` when the user launches the app a second time.

    On macOS a second launch never creates a second process: LaunchServices
    activates the running instance and delivers a *reopen* Apple Event, so
    the local-socket ``RAISE`` handshake of :mod:`wol_app.single_instance`
    is bypassed and a miniaturised window stays miniaturised. Overriding
    ``applicationShouldHandleReopen:hasVisibleWindows:`` on Qt's Cocoa
    delegate restores the Windows/Linux behaviour.

    The delegate subclasses the class Qt already installed, so every other
    Cocoa callback (quit, file/URL opening, termination) keeps working.
    No-op on other platforms; returns True when the handler was installed.
    """
    if sys.platform != "darwin":
        return False
    try:
        import objc
        from AppKit import NSApplication
    except Exception:
        return False
    try:
        app = NSApplication.sharedApplication()
        previous = app.delegate()
        if previous is None:
            return False

        # Re-installing (e.g. after a settings reload) only swaps the callback;
        # the delegate must not be subclassed over and over.
        if _macos_reopen_state.get("delegate") is previous:
            _macos_reopen_state["callback"] = callback
            return True

        class _ReopenDelegate(type(previous)):
            def applicationShouldHandleReopen_hasVisibleWindows_(
                    self, sender, visible):
                handler = _macos_reopen_state.get("callback")
                if handler is not None:
                    try:
                        handler()
                    except Exception:
                        pass
                # Qt/AppKit implement reopen as well (de-hide, activate);
                # keep that behaviour on top of our own raise.
                try:
                    return bool(objc.super(
                        _ReopenDelegate, self
                    ).applicationShouldHandleReopen_hasVisibleWindows_(
                        sender, visible))
                except Exception:
                    return True

        delegate = _ReopenDelegate.alloc().init()
        if delegate is None:
            return False
        app.setDelegate_(delegate)
        _macos_reopen_state["delegate"] = delegate
        _macos_reopen_state["callback"] = callback
        return True
    except Exception:
        return False


def _app_icon_dir() -> str:
    """Directory holding icon.ico / icon_modern.ico (install dir or project root)."""
    import sys

    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def update_shortcut_icons(mode: str) -> int:
    """Point Desktop/Start-Menu shortcuts of this app at the icon of ``mode``.

    Mirrors the taskbar rule (modern -> green icon_modern.ico, classic ->
    blue icon.ico) for the shortcut icons themselves, so the Desktop and
    Start Menu entries match the layout the user selected in the settings.
    Only shortcuts whose target is this app's executable are touched; a
    shortcut is rewritten only when its icon actually differs. Returns the
    number of updated shortcuts (0 on non-Windows, in headless/test runs,
    or when no shortcut exists).
    """
    if os.name != "nt" or os.environ.get("WOL_HEADLESS", "").lower() in ("1", "true", "yes"):
        return 0
    # Only meaningful for an installed (frozen) build: in dev mode the app
    # lives in the source tree, where no Start Menu/Desktop shortcuts exist
    # and rewriting them would point at a non-installed icon path.
    import sys as _sys

    if not getattr(_sys, "frozen", False):
        return 0
    icon_name = app_icon_for_mode(mode)
    icon_path = os.path.join(_app_icon_dir(), icon_name)
    if not os.path.exists(icon_path):
        return 0
    exe_name = "Wake-on-LAN Manager.exe"
    start_menu_sub = r"Microsoft\Windows\Start Menu\Programs"
    search_roots = [
        os.path.join(os.environ.get("PROGRAMDATA", r"C:\ProgramData"), start_menu_sub),
        os.path.join(os.environ.get("APPDATA", ""), start_menu_sub),
        os.path.join(os.environ.get("USERPROFILE", ""), "Desktop"),
        os.path.join(os.environ.get("PUBLIC", r"C:\Users\Public"), "Desktop"),
    ]
    try:
        import pythoncom  # noqa: F401  (initialises COM for the current thread)
        from win32com.client import Dispatch
    except Exception:
        return 0
    updated = 0
    for root in search_roots:
        if not root or not os.path.isdir(root):
            continue
        try:
            lnks = [os.path.join(dirpath, f)
                    for dirpath, _, files in os.walk(root)
                    for f in files if f.lower().endswith(".lnk")]
        except OSError:
            continue
        for lnk_path in lnks:
            try:
                shell = Dispatch("WScript.Shell")
                shortcut = shell.CreateShortcut(lnk_path)
                target = (shortcut.TargetPath or "").lower()
                if os.path.basename(target) != exe_name.lower():
                    continue
                if os.path.normcase(shortcut.IconLocation or "") == \
                        os.path.normcase(f"{icon_path},0"):
                    continue
                shortcut.IconLocation = f"{icon_path},0"
                shortcut.Save()
                updated += 1
            except Exception:
                continue
    return updated
