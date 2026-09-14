#!/usr/bin/env python3
"""WOL Host Service - macOS variant (launchd) for remote control via TCP.

This service runs on the *target* macOS machine and listens on TCP port
8765. It reuses the battle-tested core of ``wol_host_service_linux.py``
unchanged (single-line JSON protocol, PAM credential authentication,
metrics/watch/llama.cpp probes, opt-in batch execution) and only replaces
the two platform-specific pieces:

* power commands: ``shutdown -h now`` / ``shutdown -r now`` instead of
  ``systemctl`` (the BSD shutdown tool, works for a root launchd daemon),
* service management: a LaunchDaemon plist in /Library/LaunchDaemons
  instead of a systemd unit in /etc/systemd/system.

Authentication goes through PAM exactly like the Linux variant (``pamela``,
service ``login``). On macOS ``/etc/pam.d/login`` routes to
``pam_opendirectory``, which validates local accounts (and directory
accounts) — so no password ever touches the process command line.

Commands and the wire protocol are identical to the Windows/Linux services
and the Android client; see ``wol_host_service_linux.py`` for the full
protocol documentation (protocol version is defined there).

CLI usage (run with sudo for install/uninstall/start/stop):

    wol_host_service_macos.py --install        Install + load the LaunchDaemon
    wol_host_service_macos.py --uninstall      Remove the LaunchDaemon
    wol_host_service_macos.py --start          Start / restart the service
    wol_host_service_macos.py --stop           Stop the service
    wol_host_service_macos.py --status         Show service status
    wol_host_service_macos.py --version        Print installed service version
    wol_host_service_macos.py --enable-batch   Allow run_batch on this machine
    wol_host_service_macos.py --disable-batch  Forbid run_batch (default)
    wol_host_service_macos.py --run            Run in the foreground (debugging)
    wol_host_service_macos.py --port N         Port override for --run (default 8765)

The PyInstaller macOS build packages this module as the standalone
"WOL Host Service" executable; ``--install`` then points the plist at the
installed copy under /usr/local/lib/wol-host-service (see
packaging/macos/install_host_service.command).
"""

import os
import plistlib
import shutil
import subprocess
import sys

import wol_host_service_linux as core

# ── Platform overrides for the shared core ─────────────────────────────────
# The core's TCP handler looks these up as module globals at request time.
core.SHUTDOWN_CMD = ["/usr/sbin/shutdown", "-h", "now"]
core.REBOOT_CMD = ["/usr/sbin/shutdown", "-r", "now"]

LABEL = "de.wolmanager.hostservice"
PLIST_PATH = f"/Library/LaunchDaemons/{LABEL}.plist"
# Where the install script places the built service binary (onedir bundle:
# the folder also contains _internal/ and must be copied as a whole).
INSTALL_DIR = "/usr/local/lib/wol-host-service"
INSTALL_BIN = os.path.join(INSTALL_DIR, "WOL Host Service")
# Written by the installer (app or install_host_service.command) after a
# successful --install: plain version string of the shipped service build.
# The desktop app compares it against its own bundled payload to offer
# updates; --version prints it. Missing marker = pre-marker install ("0.0.0").
VERSION_MARKER = os.path.join(INSTALL_DIR, "service_version.txt")
FIREWALL_TOOL = "/usr/libexec/ApplicationFirewall/socketfilterfw"


def is_root() -> bool:
    """True when the current process may manage the LaunchDaemon."""
    return hasattr(os, "geteuid") and os.geteuid() == 0


def _exec_args() -> list[str]:
    """ProgramArguments for the plist (frozen binary or venv python + script)."""
    if getattr(sys, "frozen", False):
        return [os.path.abspath(sys.executable), "--run"]
    return [sys.executable, os.path.abspath(__file__), "--run"]


def build_plist() -> dict:
    """LaunchDaemon property list (run at boot, keep-alive, log to files)."""
    return {
        "Label": LABEL,
        "ProgramArguments": _exec_args(),
        "RunAtLoad": True,
        "KeepAlive": True,
        "ThrottleInterval": 10,
        "WorkingDirectory": "/",
        "StandardOutPath": "/var/log/wol-host-service.log",
        "StandardErrorPath": "/var/log/wol-host-service.log",
    }


def _launchctl(*args: str, timeout: float = 30.0) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["launchctl", *args], capture_output=True, text=True, timeout=timeout
    )


def add_firewall_rule() -> bool:
    """Unblock the service binary in the macOS application firewall.

    Skipped (success) when the firewall is inactive or the tool is missing.
    Best effort otherwise: a GUI consent dialog may still appear on first
    listen when the binary is not signed — the daemon logs that case.
    """
    if not os.path.exists(FIREWALL_TOOL):
        return True
    try:
        state = _launchctl_firmware_state()
        if not state:
            return True  # firewall off (or unknown) - ports are reachable anyway
        target = _exec_args()[0]
        _launchctl_firewall("--add", target)
        _launchctl_firewall("--unblockapp", target)
        return True
    except Exception:
        return False


def _launchctl_firmware_state() -> bool:
    """True when the application firewall is globally enabled."""
    try:
        result = subprocess.run(
            [FIREWALL_TOOL, "--getglobalstate"],
            capture_output=True, text=True, timeout=15,
        )
        return "enabled" in (result.stdout or "").lower()
    except Exception:
        return False


def _launchctl_firewall(*args: str) -> None:
    try:
        subprocess.run(
            [FIREWALL_TOOL, *args], capture_output=True, text=True, timeout=15,
        )
    except Exception:
        pass


def remove_firewall_rule() -> bool:
    """Remove the firewall exception for the service binary (best effort)."""
    if not os.path.exists(FIREWALL_TOOL):
        return True
    try:
        _launchctl_firewall("--remove", _exec_args()[0])
        return True
    except Exception:
        return False


def install_service() -> bool:
    """Write + bootstrap the LaunchDaemon (root) and configure the firewall."""
    if not is_root():
        print("ERROR: Root privileges required for --install (use sudo).")
        return False

    # A previous copy may be running (upgrade): unload first, idempotently.
    _launchctl("bootout", f"system/{LABEL}")

    plist = build_plist()
    try:
        with open(PLIST_PATH, "wb") as fh:
            plistlib.dump(plist, fh)
    except OSError as e:
        print(f"ERROR: Could not write {PLIST_PATH}: {e}")
        return False
    os.chmod(PLIST_PATH, 0o644)

    result = _launchctl("bootstrap", "system", PLIST_PATH)
    if result.returncode != 0:
        # Older macOS: fall back to load -w.
        result = _launchctl("load", "-w", PLIST_PATH)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        print(f"ERROR: Could not start the service: {detail}")
        return False

    if not add_firewall_rule():
        print("WARNING: Could not configure the application firewall.")
        print(f"         Allow inbound TCP port {core.DEFAULT_PORT} manually.")

    print("Service 'WOL Host Service' installed (launchd, auto-start at boot).")
    print(f"LaunchDaemon: {PLIST_PATH}")
    print(f"Batch execution is disabled by default "
          f"(enable: sudo {os.path.basename(sys.argv[0])} --enable-batch).")
    return True


def uninstall_service() -> bool:
    """Remove the LaunchDaemon and its firewall exception."""
    if not is_root():
        print("ERROR: Root privileges required for --uninstall (use sudo).")
        return False

    remove_firewall_rule()
    _launchctl("bootout", f"system/{LABEL}")
    _launchctl("unload", PLIST_PATH)
    if os.path.exists(PLIST_PATH):
        try:
            os.remove(PLIST_PATH)
        except OSError as e:
            print(f"ERROR: Could not remove {PLIST_PATH}: {e}")
            return False
    if os.path.isdir(INSTALL_DIR):
        shutil.rmtree(INSTALL_DIR, ignore_errors=True)
    print("Service 'WOL Host Service' removed.")
    return True


def start_service() -> bool:
    if not is_root():
        print("ERROR: Root privileges required for --start (use sudo).")
        return False
    if os.path.exists(PLIST_PATH):
        # Already loaded? kickstart restarts it; otherwise bootstrap starts fresh.
        if _launchctl("kickstart", "-k", f"system/{LABEL}").returncode != 0:
            result = _launchctl("bootstrap", "system", PLIST_PATH)
            if result.returncode != 0:
                print("ERROR: Could not start the service "
                      f"(exit {result.returncode}). Is it installed?")
                return False
        print("Service 'WOL Host Service' started.")
        return True
    print("ERROR: Service not installed (run --install first).")
    return False


def stop_service() -> bool:
    if not is_root():
        print("ERROR: Root privileges required for --stop (use sudo).")
        return False
    result = _launchctl("bootout", f"system/{LABEL}")
    if result.returncode != 0:
        result = _launchctl("unload", PLIST_PATH)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        print(f"ERROR: Could not stop the service: {detail or 'not running?'}")
        return False
    print("Service 'WOL Host Service' stopped (re-run --start or --install).")
    return True


def show_status() -> bool:
    result = _launchctl("print", f"system/{LABEL}")
    if result.returncode != 0:
        print("Service 'WOL Host Service' is not installed or not loaded.")
        return True
    out = result.stdout or ""
    state = "unknown"
    for line in out.splitlines():
        stripped = line.strip()
        if stripped.startswith("state ="):
            state = stripped.split("=", 1)[1].strip().upper()
            break
    batch = "enabled" if core.is_batch_allowed() else "disabled"
    print(f"Service 'WOL Host Service': {state} (batch execution {batch})")
    return True


def show_version() -> bool:
    """Print this binary's version (build_macos.sh stamps the marker).

    The marker sits next to the executable both in the .app payload and in
    the installed directory; the system-wide marker is the fallback for
    installs from before the payload marker existed.
    """
    candidates = [
        os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])),
                     "service_version.txt"),
        VERSION_MARKER,
    ]
    version = ""
    for candidate in candidates:
        try:
            with open(candidate, encoding="utf-8") as fh:
                version = fh.read().strip()
        except OSError:
            continue
        if version:
            break
    print(f"{version or '0.0.0'} (protocol v{core.PROTOCOL_VERSION})")
    return True


def main() -> int:
    args = sys.argv[1:]

    # CLI mode (port override shared with the core's foreground runner).
    port = core.DEFAULT_PORT
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
    if "--version" in args:
        return 0 if show_version() else 1
    if "--enable-batch" in args:
        if core.set_batch_allowed(True):
            print("Batch execution ENABLED on this machine.")
            return 0
        print("ERROR: Could not write the service config file "
              f"({core._CONFIG_FILE}). Run with sudo when the service runs as root.")
        return 1
    if "--disable-batch" in args:
        if core.set_batch_allowed(False):
            print("Batch execution DISABLED on this machine (default).")
            return 0
        print("ERROR: Could not write the service config file "
              f"({core._CONFIG_FILE}). Run with sudo when the service runs as root.")
        return 1
    if "--run" in args:
        core.run_foreground(port)
        return 0

    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
