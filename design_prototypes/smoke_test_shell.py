"""Offscreen smoke test for Phase 2 (MainShell + sidebar navigation)."""

import os
import sys

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication

from wol_app.config import ConfigManager
from wol_app.main_shell import KEY_MANAGE, KEY_SETTINGS, MainShell
from wol_app.theme import apply_display_mode
from wol_app.translations import Translations
from wol_app.wol_engine import WOLEngine


def main() -> None:
    app = QApplication([])
    apply_display_mode(app, "dark")
    Translations()  # init singleton
    Translations.set_language("en")

    cfg = ConfigManager()
    if not cfg.get_devices():
        cfg.add_device("Demo", "AA:BB:CC:00:11:22")
    eng = WOLEngine(cfg)

    shell = MainShell(cfg, eng)
    print("MainShell built OK")

    # Devices screen is the default and registered.
    devices = shell.devices_screen()
    assert devices is not None
    assert shell.stack.currentWidget() is devices
    print("default screen is devices OK")

    # Navigate to another screen.
    shell._on_navigate(KEY_MANAGE)
    assert shell.stack.currentWidget() is shell._screens[KEY_MANAGE]
    shell._on_navigate(KEY_SETTINGS)
    assert shell.stack.currentWidget() is shell._screens[KEY_SETTINGS]
    print("navigation OK")

    # All expected screens registered.
    expected = {"devices", "manage", "schedule", "logs", "settings", "about"}
    assert expected <= set(shell._screens.keys()), shell._screens.keys()
    print("all screens registered OK")

    print("ALL PHASE-2 SMOKE TESTS PASSED")


if __name__ == "__main__":
    main()
