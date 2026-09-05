"""Window geometry persistence for the modern main window (offscreen)."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("WOL_HEADLESS", "1")

import pytest  # noqa: E402

pytest.importorskip("PyQt6")

from PyQt6.QtWidgets import QApplication  # noqa: E402

from wol_app.config import ConfigManager  # noqa: E402
from wol_app.translations import Translations  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(scope="module", autouse=True)
def _translations():
    Translations().load("en")


@pytest.fixture()
def config(tmp_path):
    return ConfigManager(config_path=str(tmp_path / "config.json"))


def _make_window(config):
    from wol_app.modern_main_window import ModernMainWindow

    return ModernMainWindow(config, dark_mode=True)


class TestGeometryRestore:
    def test_default_size_without_saved_geometry(self, config):
        win = _make_window(config)
        assert win.width() == 1180
        assert win.height() == 740
        win.close()

    def test_saved_geometry_restores_size(self, config):
        config.set_window_geometry(50, 40, 1300, 820)
        win = _make_window(config)
        assert (win.width(), win.height()) == (1300, 820)
        win.close()

    def test_offscreen_geometry_falls_back_to_default(self, config):
        # Far outside every virtual desktop (unplugged monitor scenario):
        # the saved rect must NOT be applied.
        config.set_window_geometry(99999, 99999, 1280, 800)
        win = _make_window(config)
        assert (win.width(), win.height()) == (1180, 740)
        win.close()

    def test_malformed_geometry_falls_back_to_default(self, config):
        config.config.setdefault("ui", {})["window_geometry"] = [10, 20, 30]
        win = _make_window(config)
        assert (win.width(), win.height()) == (1180, 740)
        win.close()


class TestGeometrySave:
    def test_close_persists_normal_geometry(self, qapp, config):
        win = _make_window(config)
        win.show()
        qapp.processEvents()
        win.resize(1234, 678)
        qapp.processEvents()
        win.close()
        assert config.get_window_geometry() == [
            win.normalGeometry().x(),
            win.normalGeometry().y(),
            1234,
            678,
        ]

    def test_maximized_close_keeps_normal_size(self, qapp, config):
        win = _make_window(config)
        win.show()
        qapp.processEvents()
        win.resize(1180, 740)
        win.showMaximized()
        qapp.processEvents()
        win.close()
        saved = config.get_window_geometry()
        assert saved is not None
        # The saved size is the normal (restored) size, not the maximized one.
        assert saved[2] == 1180
        assert saved[3] == 740
