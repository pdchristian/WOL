"""Shared Remote Desktop launch flow for the classic and modern layouts.

Extracted from ``MainWindow._remote_desktop_selected`` so both UIs start
``mstsc`` with identical behaviour: IP validation, credential passthrough
and resolution selection (fixed value or "auto" from the primary screen's
physical pixels).

Fast-exit retry: a wrong password against an xrdp/Linux host (typical for
Ubuntu) shows as a black screen and mstsc closes again immediately. The
launch therefore watches the mstsc process and, when it dies within a few
seconds, asks the user whether to reconnect **without the stored password**
so the password can be typed directly into the mstsc prompt.
"""

import threading
from typing import Any

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QMessageBox, QWidget

from wol_app.config import (
    REMOTE_DESKTOP_AUTO_FRACTION,
    REMOTE_DESKTOP_RESOLUTION_AUTO,
)
from wol_app.translations import Translations
from wol_app.utils import (
    auto_rdp_resolution,
    launch_remote_desktop,
    retry_remote_desktop_without_password,
)

# Hosts whose fast-exit prompt has been requested but not answered yet.
# Prevents a second prompt (or retry) while one is still open for the same
# host, e.g. after a double click on the remote desktop menu entry.
_pending_fast_exit: set[str] = set()
_pending_lock = threading.Lock()


class _FastExitRelay(QObject):
    """Relays the monitor thread's fast-exit notice onto the GUI thread.

    ``launch_remote_desktop`` invokes its callback on a background thread
    without a Qt event loop, where ``QTimer.singleShot`` would never fire.
    Emitting a signal from that thread is the documented-safe way: Qt queues
    the emission to the GUI thread the relay object belongs to.
    """

    triggered = pyqtSignal()


def _handle_fast_exit(
    parent: QWidget,
    config: Any,
    device_name: str,
    ip: str,
    username: str,
    fullscreen: bool,
    width: int,
    height: int,
) -> None:
    """Ask the user whether to reconnect without the stored password.

    Runs on the GUI thread (via :class:`_FastExitRelay`). The pending mark
    for *ip* is always cleared, whichever button is pressed.
    """
    try:
        answer = QMessageBox.question(
            parent,
            Translations.tr("dialog.rdp_retry.title"),
            Translations.tr("dialog.rdp_retry.message", name=device_name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
    finally:
        with _pending_lock:
            _pending_fast_exit.discard(ip)
    if answer != QMessageBox.StandardButton.Yes:
        return

    # English log text by convention (all add_log callers log English) and
    # because the log sanitizer strips non-ASCII characters anyway.
    if config is not None:
        try:
            config.add_log(
                device_name,
                "RDP",
                "WARNING",
                "Session closed immediately (likely wrong password); "
                "reconnecting without the stored password",
            )
        except Exception:  # noqa: BLE001 - logging must never block the retry
            pass
    try:
        retry_remote_desktop_without_password(
            ip=ip,
            username=username,
            fullscreen=fullscreen,
            width=width,
            height=height,
            device_name=device_name,
        )
    except Exception:
        QMessageBox.critical(
            parent,
            Translations.tr("dialog.remote_desktop_error.title"),
            Translations.tr("dialog.remote_desktop_error.message"),
        )


def _make_fast_exit_callback(
    parent: QWidget,
    config: Any,
    device_name: str,
    ip: str,
    username: str,
    fullscreen: bool,
    width: int,
    height: int,
):
    """Build the ``on_fast_exit`` callback passed to ``launch_remote_desktop``.

    The returned callable runs on the monitor's background thread. It marks
    *ip* as pending (so concurrent fast exits cannot stack prompts) and
    marshals the dialog onto the GUI thread through :class:`_FastExitRelay`.
    The relay is parented to *parent* so it is destroyed together with the UI.
    """
    relay = _FastExitRelay()
    relay.setParent(parent)
    relay.triggered.connect(
        lambda: _handle_fast_exit(
            parent, config, device_name, ip, username,
            fullscreen, width, height,
        )
    )

    def _on_fast_exit() -> None:
        with _pending_lock:
            if ip in _pending_fast_exit:
                return
            _pending_fast_exit.add(ip)
        try:
            relay.triggered.emit()
        except RuntimeError:
            # Relay destroyed (window or app closing) — nothing to prompt on.
            with _pending_lock:
                _pending_fast_exit.discard(ip)

    return _on_fast_exit


def start_remote_desktop(
    parent: QWidget, config: Any, device: dict, fullscreen: bool
) -> None:
    """Start a Remote Desktop session for *device*.

    *fullscreen* selects full-screen mode (True) or a window of the
    user-configured resolution (False). When a stored password is used and
    mstsc exits within a few seconds — the xrdp/Ubuntu black-screen pattern
    of a rejected password — the user is asked whether to reconnect without
    the stored password so it can be entered in the mstsc prompt directly.
    Errors are reported via message boxes on *parent*; the function never
    raises.
    """
    device_name = device.get("name", "")
    device_ip = device.get("ip", "")

    if not device_ip:
        QMessageBox.warning(
            parent,
            Translations.tr("dialog.no_ip.title"),
            Translations.tr("dialog.no_ip.message", name=device_name),
        )
        return

    username: str = device.get("username", "") or ""
    password: str = device.get("password", "") or ""

    width: int = 1920
    height: int = 1080
    if not fullscreen:
        resolution = config.get_remote_desktop_resolution()
        if resolution == REMOTE_DESKTOP_RESOLUTION_AUTO:
            # "Optimized 16:9": size the window from the primary screen's
            # current resolution (physical pixels) so it fits without scroll.
            # QScreen.size() returns *logical* pixels, which are DPI-scaled
            # (e.g. 2048x1152 at 125% on a 2560x1440 display). Multiply by
            # devicePixelRatio() to recover the physical resolution.
            from PyQt6.QtWidgets import QApplication

            screen = QApplication.primaryScreen()
            if screen is not None:
                scale = screen.devicePixelRatio()
                size = screen.size()
                width, height = auto_rdp_resolution(
                    round(size.width() * scale),
                    round(size.height() * scale),
                    fraction=REMOTE_DESKTOP_AUTO_FRACTION,
                )
        else:
            try:
                w, h = resolution.split("x")
                width, height = int(w), int(h)
            except (ValueError, AttributeError):
                pass  # keep 1920x1080 fallback

    # Watch the process only when a password was supplied: without one mstsc
    # prompts anyway, so a fast exit cannot be a credential problem.
    on_fast_exit = None
    if password:
        on_fast_exit = _make_fast_exit_callback(
            parent, config, device_name, device_ip, username,
            fullscreen, width, height,
        )

    try:
        launch_remote_desktop(
            ip=device_ip,
            username=username,
            password=password,
            fullscreen=fullscreen,
            width=width,
            height=height,
            device_name=device_name,
            on_fast_exit=on_fast_exit,
        )
    except Exception:
        QMessageBox.critical(
            parent,
            Translations.tr("dialog.remote_desktop_error.title"),
            Translations.tr("dialog.remote_desktop_error.message"),
        )
