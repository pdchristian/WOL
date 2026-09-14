"""macOS-only: install / update / remove the bundled WOL Host Service.

The desktop app embeds the frozen host-service bundle (onedir) at
``Contents/Resources/WOL Host Service`` (see build_macos.sh + the macOS
PyInstaller spec). This module installs that payload system-wide to
``/usr/local/lib/wol-host-service`` and registers the LaunchDaemon — all
without a Developer ID: privilege escalation goes through the built-in
``osascript ... with administrator privileges`` dialog (password or Touch ID).

Design notes:
* The heavy lifting stays inside the *service binary itself*
  (``--install`` / ``--uninstall`` write the plist, bootstrap launchd and
  touch the firewall). This module only copies files, clears the quarantine
  xattr and stamps the version marker — so the root script is small and the
  logic is shared with ``packaging/macos/install_host_service.command``.
* The shell payload runs as root from a temp file: avoids AppleScript
  escaping problems for paths with spaces and keeps the osascript one-liner
  constant. Output is teed to a fixed log file for readable error messages.
* Every public Qt-free function is unit-testable; the ``QObject`` worker is
  a thin wrapper so the UI never blocks on the admin prompt.
"""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
import tempfile

# Install layout — mirrors wol_host_service_macos.py (kept as literals here
# so importing this module never pulls in the service modules at app start).
SERVICE_NAME = "WOL Host Service"
INSTALL_DIR = "/usr/local/lib/wol-host-service"
INSTALL_BIN = os.path.join(INSTALL_DIR, SERVICE_NAME)
VERSION_MARKER = os.path.join(INSTALL_DIR, "service_version.txt")
PLIST_PATH = "/Library/LaunchDaemons/de.wolmanager.hostservice.plist"
INSTALL_LOG = "/tmp/wol-host-service-install.log"


def is_macos() -> bool:
    return sys.platform == "darwin"


# ── Payload discovery (pure functions, unit-testable) ──────────────────────

def _payload_dir_ok(path: str) -> bool:
    """True when *path* looks like the embedded onedir service bundle."""
    return os.path.isfile(os.path.join(path, SERVICE_NAME)) and os.path.isdir(
        os.path.join(path, "_internal"))


def service_payload_path(get_resource=None) -> str | None:
    """Absolute path of the bundled service payload, or None when absent.

    In a frozen .app the payload lives in ``Contents/Resources/WOL Host
    Service``; ``sys._MEIPASS`` is checked as a fallback. The path is
    derived from ``sys.executable`` so no Qt-backed helper is imported at
    module load. In a source checkout, build_macos.sh output under
    ``dist/WOL Host Service`` is used - handy for smoke tests without
    re-packaging. Without a payload the install UI stays hidden.
    """
    if not is_macos():
        return None
    candidates = []
    if get_resource is not None:
        candidates.append(get_resource(SERVICE_NAME))
    if getattr(sys, "frozen", False):
        contents = os.path.dirname(os.path.dirname(sys.executable))
        candidates.append(os.path.join(contents, "Resources", SERVICE_NAME))
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(os.path.join(meipass, SERVICE_NAME))
    else:
        # Source checkout: <repo>/wol_app/host_service_installer.py -> <repo>
        root = os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)))
        candidates.append(os.path.join(root, "dist", SERVICE_NAME))
    for candidate in candidates:
        if candidate and _payload_dir_ok(candidate):
            return candidate
    return None


def payload_version(payload_dir: str) -> str:
    """Version stamped next to the payload binary (build_macos.sh)."""
    try:
        with open(os.path.join(payload_dir, "service_version.txt"),
                  encoding="utf-8") as fh:
            version = fh.read().strip()
        if version:
            return version
    except OSError:
        pass
    from wol_app import __version__  # payload built together with the app
    return __version__


def installed_version() -> str | None:
    """Version of the system-wide installed service (None = not installed).

    A pre-marker manual install (install_host_service.command before this
    feature) counts as version "0.0.0" so the app offers an update.
    """
    if not os.path.exists(INSTALL_BIN):
        return None
    try:
        with open(VERSION_MARKER, encoding="utf-8") as fh:
            version = fh.read().strip()
        return version or "0.0.0"
    except OSError:
        return "0.0.0"


def service_state(payload: str | None,
                  installed: str | None) -> str:
    """One of "none" | "install" | "update" | "current".

    "current" also covers an installed service without a comparable payload
    (app run from source): the UI then just reports the installed version.
    """
    if installed is None:
        return "install" if payload else "none"
    if payload is None:
        return "current"  # cannot compare, keep it quiet
    return "update" if payload != installed else "current"


def describe_state() -> tuple[str, str | None, str | None]:
    """(state, payload_version, installed_version) for the current system."""
    payload_dir = service_payload_path()
    payload = payload_version(payload_dir) if payload_dir else None
    installed = installed_version()
    return service_state(payload, installed), payload, installed


def should_prompt(prompted_version: str | None,
                  state: str,
                  payload: str | None) -> bool:
    """Pure prompt-gating: ask at most once per bundled service version.

    Only "install" and "update" prompt; an answer is remembered for the
    *payload* version, so the next app release asks again about its newer
    service. "current" never asks, "none" has nothing to offer.
    """
    if state not in ("install", "update") or not payload:
        return False
    return (prompted_version or "") != payload


# ── Privileged scripts (pure builders + osascript runner) ──────────────────

def build_install_script(payload_dir: str, version: str) -> str:
    """Bash script (run as root): copy payload -> install -> register."""
    p = shlex.quote(payload_dir)
    d = shlex.quote(INSTALL_DIR)
    b = shlex.quote(INSTALL_BIN)
    v = shlex.quote(version)
    return f"""set -e
rm -rf {d}
mkdir -p {d}
cp -R {p}/. {d}/
chmod +x {b}
# A copied .app payload may still carry the download quarantine flag -
# launchd would refuse to keep the daemon alive without clearing it.
/usr/bin/xattr -dr com.apple.quarantine {d} 2>/dev/null || true
{b} --install
printf '%s\\n' {v} > {shlex.quote(VERSION_MARKER)}
"""


def build_uninstall_script() -> str:
    """Bash script (run as root): unregister daemon + drop install dir."""
    b = shlex.quote(INSTALL_BIN)
    d = shlex.quote(INSTALL_DIR)
    return f"""{b} --uninstall || true
rm -rf {d}
true
"""


def _applescript_quote(text: str) -> str:
    """Escape a string for embedding in AppleScript double quotes."""
    return text.replace("\\", "\\\\").replace('"', '\\"')


def run_privileged(script: str, prompt: str,
                   runner=subprocess.run) -> tuple[bool, str]:
    """Run a bash *script* as root via the macOS admin dialog.

    *runner* is injectable for tests. Returns ``(ok, message)``; a cancelled
    dialog (OSStatus -128) is reported as ``(False, "cancelled")`` so callers
    can stay silent. Script output lands in :data:`INSTALL_LOG` because
    ``do shell script`` swallows it otherwise.
    """
    fd, script_path = tempfile.mkstemp(suffix=".sh", prefix="wol-hs-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write("{\n")
            fh.write(script)
            # Tee all output (incl. stderr) - do shell script swallows it.
            fh.write(f"}} > {shlex.quote(INSTALL_LOG)} 2>&1\n")
        os.chmod(script_path, 0o700)
        wrapped = (
            "with timeout of 3600 seconds\n"
            f'do shell script "/bin/bash {_applescript_quote(script_path)}" '
            f'with prompt "{_applescript_quote(prompt)}" '
            "with administrator privileges\n"
            "end timeout"
        )
        result = runner(["osascript", "-e", wrapped],
                        capture_output=True, text=True, timeout=3700)
    finally:
        try:
            os.unlink(script_path)
        except OSError:
            pass
    if result.returncode == 0:
        return True, ""
    stderr = (result.stderr or "").strip()
    if "-128" in stderr or "User canceled" in stderr:
        return False, "cancelled"
    detail = ""
    try:
        with open(INSTALL_LOG, encoding="utf-8") as fh:
            detail = fh.read().strip()
    except OSError:
        pass
    return False, (detail or stderr or
                   f"osascript exit {result.returncode}")


# ── High-level operations (Qt-free; used by the worker below) ──────────────

def install_or_update_host_service(
        prompt_install: str, prompt_update: str,
        runner=subprocess.run) -> tuple[bool, str, str]:
    """Install/update the bundled service. (ok, outcome, message)."""
    payload_dir = service_payload_path()
    if not payload_dir:
        return False, "no_payload", "payload missing"
    version = payload_version(payload_dir)
    prompt = prompt_update if installed_version() else prompt_install
    script = build_install_script(payload_dir, version)
    ok, message = run_privileged(script, prompt, runner=runner)
    if ok:
        return True, version, ""
    if message == "cancelled":
        return False, "cancelled", ""
    return False, "failed", message


def remove_host_service(prompt: str,
                        runner=subprocess.run) -> tuple[bool, str]:
    """Unregister + delete the installed service (needs the install dir)."""
    if installed_version() is None:
        return False, "not_installed"
    ok, message = run_privileged(build_uninstall_script(), prompt,
                                 runner=runner)
    if ok:
        return True, ""
    return False, message


# ── Qt worker (imported lazily, keeps the admin prompt off the UI thread) ──

def make_worker_class():
    """Build the worker class once, with its Qt signals wired."""
    from PyQt6.QtCore import QObject, pyqtSignal

    class HostServiceWorker(QObject):
        """Runs one privileged service action in a worker thread.

        Signals: ``finished(outcome, message)`` where *outcome* is the new
        installed version on success, or "cancelled" / "failed" /
        "no_payload" / "not_installed".
        """

        finished = pyqtSignal(str, str)

        def __init__(self, action: str, texts: dict) -> None:
            super().__init__()
            self.action = action          # "install" | "remove"
            self.texts = texts            # localized prompt strings

        def run(self) -> None:
            try:
                if self.action == "remove":
                    ok, message = remove_host_service(
                        self.texts["prompt_remove"])
                    if ok:
                        self.finished.emit("removed", "")
                    elif message == "cancelled":
                        self.finished.emit("cancelled", "")
                    elif message == "not_installed":
                        self.finished.emit("not_installed", "")
                    else:
                        self.finished.emit("failed", message)
                    return
                ok, outcome, message = install_or_update_host_service(
                    self.texts["prompt_install"],
                    self.texts["prompt_update"])
                if ok:
                    self.finished.emit(outcome, "")
                else:
                    self.finished.emit(outcome, message)
            except Exception as e:  # never kill the QThread silently
                self.finished.emit("failed", str(e))

    return HostServiceWorker


def run_privileged_action(action: str, texts: dict, on_result,
                          holder: dict) -> None:
    """Run "install"/"remove" off the UI thread; call on_result when done.

    Follows the ScanWorker pattern (QObject moved to a QThread). *holder*
    is a caller-owned dict keeping strong references to thread and worker
    alive while running (Qt would otherwise garbage-collect them mid-run);
    entries are removed again once the thread has finished.
    """
    from PyQt6.QtCore import QThread

    thread = QThread()
    worker = make_worker_class()(action, texts)
    worker.moveToThread(thread)
    thread.started.connect(worker.run)

    def _finish(outcome: str, message: str) -> None:
        thread.quit()
        holder.pop("thread", None)
        holder.pop("worker", None)
        on_result(outcome, message)

    worker.finished.connect(_finish)
    holder["thread"] = thread
    holder["worker"] = worker
    thread.start()
