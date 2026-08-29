"""Smoke tests for the modern control-center window (offscreen, headless)."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("WOL_HEADLESS", "1")

import pytest  # noqa: E402

pytest.importorskip("PyQt6")

from PyQt6.QtWidgets import QApplication  # noqa: E402

from wol_app.config import ConfigManager  # noqa: E402
from wol_app.translations import Translations  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(scope="module", autouse=True)
def _translations():
    Translations().load("en")


@pytest.fixture()
def config(tmp_path):
    cfg = ConfigManager(config_path=str(tmp_path / "config.json"))
    cfg.add_device("Workstation", "AA:BB:CC:00:11:22")
    cfg.update_device(cfg.get_devices()[0]["id"], ip="192.168.1.10")
    cfg.add_device("Media-Server", "AA:BB:CC:33:44:55")
    return cfg


class TestModernMainWindow:
    def test_instantiates_and_navigates(self, qapp, config):
        from wol_app.modern_main_window import ModernMainWindow

        window = ModernMainWindow(config, dark_mode=True)
        assert window.stack.count() == 4
        assert window.stack.currentIndex() == 0

        window._select_nav(1)
        assert window.stack.currentIndex() == 1
        assert window.nav_buttons[1].isChecked()
        assert not window.nav_buttons[0].isChecked()
        window.close()

    def test_manage_view_lists_devices(self, qapp, config):
        from wol_app.views.manage_view import DeviceRow, ManageView

        view = ManageView(config)
        rows = view._device_rows()
        assert len(rows) == 2
        # First row (name-sorted): Media-Server
        assert isinstance(rows[0], DeviceRow)
        assert rows[0].title.text() == "Media-Server"
        assert rows[0].device_id == config.get_devices()[1]["id"]
        # Fixed-height rows like the scan result list
        assert rows[0].height() == 64

    def test_manage_view_search_filter(self, qapp, config):
        from wol_app.views.manage_view import ManageView

        view = ManageView(config)
        view.search_input.setText("work")
        rows = view._device_rows()
        assert len(rows) == 1
        assert rows[0].title.text() == "Workstation"

    def test_device_row_status_tile(self, qapp, config):
        from wol_app.views.manage_view import ManageView

        view = ManageView(config)
        row = view._device_rows()[0]
        row.set_status("online")
        assert row.badge.objectName() == "badgeOnline"
        assert row.badge.text() == Translations.tr("status.online")
        row.set_status("offline")
        assert row.badge.objectName() == "badgeOffline"

    def test_retranslate_does_not_raise(self, qapp, config):
        from wol_app.modern_main_window import ModernMainWindow

        window = ModernMainWindow(config, dark_mode=True)
        Translations.set_language("de")
        try:
            window._retranslate()
            assert "Verwalten" in window.nav_buttons[1].text()
        finally:
            Translations.set_language("en")
        window.close()
