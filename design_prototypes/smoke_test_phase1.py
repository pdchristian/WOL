"""Offscreen smoke test for Phase 1 (theme + DevicesScreen)."""

import os
import sys

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication

from wol_app.config import ConfigManager
from wol_app.screens.devices_screen import DevicesScreen
from wol_app.theme import apply_display_mode
from wol_app.translations import Translations
from wol_app.wol_engine import WOLEngine


def main() -> None:
    app = QApplication([])
    apply_display_mode(app, "dark")
    Translations()  # init singleton
    Translations.set_language("en")

    cfg = ConfigManager()
    cfg.set_device_view_mode("cards")
    assert cfg.get_device_view_mode() == "cards"

    if not cfg.get_devices():
        cfg.add_device("Demo", "AA:BB:CC:00:11:22")

    eng = WOLEngine(cfg)
    scr = DevicesScreen(cfg, eng)
    print("DevicesScreen built OK")

    # Toggle to list and back, checking persistence.
    scr._set_view_mode("list")
    assert not scr.table.isHidden() and scr.cards_scroll.isHidden()
    assert cfg.get_device_view_mode() == "list"
    print("list view OK")

    scr._set_view_mode("cards")
    assert not scr.cards_scroll.isHidden() and scr.table.isHidden()
    assert cfg.get_device_view_mode() == "cards"
    print("cards view OK")

    # Responsive column count: wide viewport -> multiple columns, narrow -> 1.
    scr._cards = []
    for i in range(6):
        cfg.add_device(f"Demo{i}", "AA:BB:CC:00:11:22")
    scr.refresh()
    wide_columns = scr._column_count()
    scr.cards_scroll.viewport().resize(1000, 600)
    columns_wide = scr._column_count()
    scr.cards_scroll.viewport().resize(200, 600)
    columns_narrow = scr._column_count()
    print(f"columns wide (1000px)={columns_wide}, narrow (200px)={columns_narrow}")
    assert columns_wide >= 2, "Expected multiple cards side-by-side on a wide viewport"
    assert columns_narrow == 1, "Expected a single column on a narrow viewport"
    assert wide_columns >= 1

    print("ALL PHASE-1 SMOKE TESTS PASSED")


if __name__ == "__main__":
    main()
