"""Wake-on-LAN Manager - Main Entry Point (Windows + Linux).

On Windows the classic single-window layout and the modern "Control Center"
layout are both available; the choice is made via ``ui.layout_mode`` (see
:func:`wol_app.main_window.main`).

On Linux (the Ubuntu/GNOME port) only the Modern UI ships - the classic
window and its dialogs are never imported, so no Windows-only code is loaded.
The WOL Host Service (``wol_host_service_linux.py``, systemd, TCP 8765) is
installed alongside the app and provides remote shutdown/reboot, dashboard
metrics and (opt-in) remote script execution.
"""

from __future__ import annotations

import sys


def _main_linux():
    """Modern-UI-only entry for Linux/GNOME (never imports main_window)."""
    import os
    from typing import NoReturn

    from PyQt6.QtGui import QIcon
    from PyQt6.QtWidgets import QApplication

    from wol_app.config import ConfigManager
    from wol_app.theme import _system_uses_dark, apply_display_mode
    from wol_app.translations import Translations
    from wol_app.utils import get_resource_path
    from wol_app.watchdog import maybe_start_watchdog

    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # Consistent modern look on Linux/GNOME
    app.setApplicationName("Wake-on-LAN Manager")
    app.setOrganizationName("WakeOnLAN")

    # Diagnostics: set WOL_WATCHDOG=1 (or seconds) to dump all thread stacks
    # to ~/.wol_app/wol_watchdog.log when the GUI thread hangs.
    maybe_start_watchdog(app)

    # Initialize config and translations.
    config = ConfigManager()
    trans = Translations()
    language = config.config.get("ui", {}).get("language", "en")
    trans.load(language)

    # Apply display mode (auto / light / dark) as the base palette.
    display_mode = config.config.get("ui", {}).get("display_mode", "auto")
    apply_display_mode(app, display_mode)

    # Application window icon (modern icon preferred).
    icon_path: str = get_resource_path("icon_modern.png")
    if not os.path.exists(icon_path):
        icon_path = get_resource_path("icon.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    dark = display_mode == "dark" or (
        display_mode == "auto" and _system_uses_dark()
    )

    from wol_app.modern_main_window import run_modern_window

    run_modern_window(config, dark_mode=dark)
    raise SystemExit(0)  # unreachable: run_modern_window calls sys.exit


def main():
    """Platform-dispatching entry point.

    Windows keeps the full feature set (classic + modern UI); Linux runs the
    Modern UI only and never imports the classic ``main_window`` module.
    """
    if sys.platform == "win32":
        from wol_app.main_window import main as _main_windows

        return _main_windows()
    return _main_linux()


if __name__ == "__main__":
    main()
