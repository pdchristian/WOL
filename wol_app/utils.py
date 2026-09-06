"""Wake-on-LAN Application - Shared Utilities.

Central location for validation helpers, subprocess wrappers, and common
utility functions used across multiple modules.
"""

import base64
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

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
    prompt_for_password: bool = False,
) -> str:
    """Build the content of a temporary ``.rdp`` file for *ip*.

    mstsc cannot take credentials on the command line, so the username and
    password are embedded in the file. ``password:54:`` is base64-encoded
    UTF-16LE — the exact format mstsc expects.

    *prompt_for_password* forces mstsc's credential prompt even when a
    password is set. Used as a fallback when the password could not be
    registered with the Credential Manager: connecting without credentials
    is not a graceful failure — Windows hosts re-prompt, but xrdp hosts
    (Linux) drop the connection immediately.
    """
    prompt = (not password) or prompt_for_password
    lines = [
        f"full address:s:{ip}",
        # Use the embedded password instead of prompting when one is set.
        f"prompt for password:i:{1 if prompt else 0}",
        # Self-signed server certificates (typical for xrdp/Linux hosts) would
        # otherwise trigger the "unknown publisher" security dialog on every
        # connect. Level 0 connects without verifying the server certificate.
        "authentication level:i:0",
        # Keep the address we connected to as the server identity after an
        # RDP redirection/broker hop. Required for xrdp (Ubuntu) hosts, which
        # otherwise present a redirection name the client cannot match or
        # resolve; harmless for plain Windows hosts.
        "use redirection server name:i:1",
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
        # Position the window at 10,10 (winposstr = left,top,right,bottom).
        lines.append(
            f"winposstr:s:0,1,10,10,{int(width) + 10},{int(height) + 10}"
        )
    return "\r\n".join(lines) + "\r\n"


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
        A (width, height) 16:9 pair that fits the given screen.
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
    return (target_width, target_height)


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
) -> str:
    """Launch Windows Remote Desktop (``mstsc``) to *ip*.

    A temporary ``.rdp`` file carrying the credentials is written and passed
    to mstsc; it is deleted *cleanup_delay* seconds later so the password
    does not linger on disk.

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
        prompt_for_password=not credentials_ready,
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
):
    """Launch a Remote Desktop session to *ip* (mstsc on Windows, xfreerdp on Linux).

    Platform dispatch over the shared fast-exit contract: both backends watch
    the process when a *password* is set and invoke *on_fast_exit* (from a
    background thread) when the session dies within *fast_exit_window* seconds.
    Returns the ``.rdp`` file path on Windows, ``None`` on Linux.
    """
    if sys.platform == "win32":
        return _launch_remote_desktop_windows(
            ip, username, password, fullscreen, width, height,
            cleanup_delay, device_name, on_fast_exit, fast_exit_window,
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
    ``/p:`` so it prompts. Returns the ``.rdp`` path on Windows, ``None`` on
    Linux.
    """
    if sys.platform == "win32":
        return _retry_remote_desktop_windows(
            ip, username, fullscreen, width, height, device_name, cleanup_delay,
        )
    return _retry_remote_desktop_linux(
        ip, username, fullscreen, width, height, device_name,
    )


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
