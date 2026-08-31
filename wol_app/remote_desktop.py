"""Shared Remote Desktop launch flow for the classic and modern layouts.

Extracted from ``MainWindow._remote_desktop_selected`` so both UIs start
``mstsc`` with identical behaviour: IP validation, credential passthrough
and resolution selection (fixed value or "auto" from the primary screen's
physical pixels).
"""

from typing import Any

from PyQt6.QtWidgets import QMessageBox, QWidget

from wol_app.config import (
    REMOTE_DESKTOP_AUTO_FRACTION,
    REMOTE_DESKTOP_RESOLUTION_AUTO,
)
from wol_app.translations import Translations
from wol_app.utils import auto_rdp_resolution, launch_remote_desktop


def start_remote_desktop(
    parent: QWidget, config: Any, device: dict, fullscreen: bool
) -> None:
    """Start a Remote Desktop session for *device*.

    *fullscreen* selects full-screen mode (True) or a window of the
    user-configured resolution (False). Errors are reported via message
    boxes on *parent*; the function never raises.
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

    try:
        launch_remote_desktop(
            ip=device_ip,
            username=username,
            password=password,
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
