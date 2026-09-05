"""Sidebar collapse/resize tests for the modern window (offscreen, headless)."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("WOL_HEADLESS", "1")

import pytest  # noqa: E402

pytest.importorskip("PyQt6")

from PyQt6.QtWidgets import QApplication  # noqa: E402

from wol_app.config import (  # noqa: E402
    SIDEBAR_COLLAPSED_WIDTH,
    SIDEBAR_SNAP_WIDTH,
    SIDEBAR_WIDTH_DEFAULT,
    SIDEBAR_WIDTH_MAX,
    SIDEBAR_WIDTH_MIN,
    ConfigManager,
)
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
    return ConfigManager(config_path=str(tmp_path / "config.json"))


@pytest.fixture()
def window(qapp, config):
    from wol_app.modern_main_window import ModernMainWindow

    win = ModernMainWindow(config, dark_mode=True)
    # The splitter only emits splitterMoved / reports real sizes once it
    # has a geometry — show it on the offscreen platform.
    win.show()
    qapp.processEvents()
    yield win
    win.dashboard_view.cancel_workers()
    win.close()


class TestSidebarConfig:
    def test_defaults(self, config):
        assert config.get_sidebar_width() == SIDEBAR_WIDTH_DEFAULT
        assert config.get_sidebar_collapsed() is False

    def test_width_roundtrip_and_clamp(self, config):
        config.set_sidebar_width(300)
        assert config.get_sidebar_width() == 300
        config.set_sidebar_width(50)  # below MIN
        assert config.get_sidebar_width() == SIDEBAR_WIDTH_MIN
        config.set_sidebar_width(9999)  # above MAX
        assert config.get_sidebar_width() == SIDEBAR_WIDTH_MAX

    def test_collapsed_roundtrip(self, config):
        config.set_sidebar_collapsed(True)
        assert config.get_sidebar_collapsed() is True
        config.set_sidebar_collapsed(False)
        assert config.get_sidebar_collapsed() is False

    def test_invalid_width_falls_back(self, config):
        config.config.setdefault("ui", {})["sidebar_width"] = "not-a-number"
        assert config.get_sidebar_width() == SIDEBAR_WIDTH_DEFAULT


class TestSidebarCollapse:
    def test_start_expanded_by_default(self, window):
        assert not window._sidebar_collapsed
        assert window.sidebar.maximumWidth() == SIDEBAR_WIDTH_MAX
        assert "  " in window.nav_buttons[0].text()  # icon + label

    def test_toggle_collapses_to_icons_only(self, window):
        window._toggle_sidebar()
        assert window._sidebar_collapsed
        assert window.sidebar.maximumWidth() == SIDEBAR_COLLAPSED_WIDTH
        # Icon-only: the button text is just the emoji (no label)
        assert window.nav_buttons[0].text() == "💻"
        assert window.nav_buttons[0].property("collapsed") == "true"
        assert not window.logo_text.isVisibleTo(window)
        assert not window.lbl_areas.isVisibleTo(window)

    def test_toggle_restores_last_width(self, window):
        window._sidebar_last_width = 300
        window._apply_sidebar_mode()
        window._toggle_sidebar()
        assert window.splitter.sizes()[0] == SIDEBAR_COLLAPSED_WIDTH
        window._toggle_sidebar()
        assert not window._sidebar_collapsed
        assert window.splitter.sizes()[0] == 300
        assert "💻" in window.nav_buttons[0].text()
        assert window.nav_buttons[0].property("collapsed") is None

    def test_state_persisted_on_toggle(self, window, config):
        window._toggle_sidebar()
        assert config.get_sidebar_collapsed() is True
        window._toggle_sidebar()
        assert config.get_sidebar_collapsed() is False

    def _drag_to(self, window, qapp, width: int):
        """Simulate an interactive drag: setSizes() does not emit splitterMoved."""
        total = sum(window.splitter.sizes())
        window.splitter.setSizes([width, max(total - width, 100)])
        qapp.processEvents()
        window.splitter.splitterMoved.emit(width, 1)
        qapp.processEvents()

    def test_splitter_moved_snaps_shut(self, window, qapp):
        # Drag down to the snap threshold → collapse (no in-between width).
        self._drag_to(window, qapp, SIDEBAR_SNAP_WIDTH)
        assert window._sidebar_collapsed is True
        assert window.sidebar.maximumWidth() == SIDEBAR_COLLAPSED_WIDTH

    def test_splitter_moved_tracks_width(self, window, qapp):
        self._drag_to(window, qapp, 280)
        assert window._sidebar_last_width == 280
        assert window._sidebar_collapsed is False

    def test_splitter_moved_bounces_between_snap_and_min(self, window, qapp):
        # Between the snap threshold and the minimum: bounce back to MIN.
        mid = (SIDEBAR_SNAP_WIDTH + SIDEBAR_WIDTH_MIN) // 2
        self._drag_to(window, qapp, mid)
        assert not window._sidebar_collapsed
        assert window.splitter.sizes()[0] == SIDEBAR_WIDTH_MIN

    def test_collapsed_start_from_config(self, qapp, config):
        from wol_app.modern_main_window import ModernMainWindow

        config.set_sidebar_collapsed(True)
        win = ModernMainWindow(config, dark_mode=True)
        try:
            assert win._sidebar_collapsed
            assert win.sidebar.maximumWidth() == SIDEBAR_COLLAPSED_WIDTH
            assert win.nav_buttons[0].text() == "💻"
        finally:
            win.dashboard_view.cancel_workers()
            win.close()


class TestToggleViaNavClicks:
    def test_click_active_button_toggles(self, window):
        # Devices is active (index 0); a second click on it toggles the
        # sidebar instead of re-selecting the screen.
        assert window.stack.currentIndex() == 0
        window.nav_buttons[0].click()
        assert window._sidebar_collapsed is True
        assert window.stack.currentIndex() == 0
        window.nav_buttons[0].click()
        assert window._sidebar_collapsed is False

    def test_click_other_button_navigates_without_toggle(self, window):
        window.nav_buttons[1].click()
        assert window.stack.currentIndex() == 1
        assert not window._sidebar_collapsed
        # Now "Verwalten" is active → clicking it toggles
        window.nav_buttons[1].click()
        assert window._sidebar_collapsed is True
        assert window.stack.currentIndex() == 1

    def test_active_button_stays_checked_after_toggle(self, window):
        window.nav_buttons[0].click()  # toggle (was active)
        assert window.nav_buttons[0].isChecked()
        # In collapsed mode the same button is still the toggle target
        window.nav_buttons[0].click()
        assert not window._sidebar_collapsed

    def test_footer_button_toggles_when_active(self, window):
        window.settings_btn.click()
        assert window.stack.currentIndex() == 4
        window.settings_btn.click()  # already active → toggle
        assert window._sidebar_collapsed is True

    def test_dashboard_open_clears_active_nav(self, window, monkeypatch):
        from wol_app.views.dashboard_view import DeviceDashboardView

        monkeypatch.setattr(DeviceDashboardView, "_poll_metrics", lambda self: None)
        device_id = "does-not-exist"
        window.open_device_dashboard(device_id)
        assert window._active_nav_btn is None
        # With no active entry, a nav click navigates instead of toggling
        window.nav_buttons[0].click()
        assert not window._sidebar_collapsed
        assert window.stack.currentIndex() == 0


class TestRetranslateKeepsCollapse:
    def test_retranslate_stays_icon_only(self, window):
        window._toggle_sidebar()
        window._retranslate()
        assert window._sidebar_collapsed
        assert window.nav_buttons[0].text() == "💻"
        assert window.settings_btn.text() == "⚙"
        # Tooltips keep the full translated label
        assert "Devices" in window.nav_buttons[0].toolTip()
