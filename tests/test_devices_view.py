"""Tests for the modern devices screen (DevicesView / DeviceCard)."""

import pytest

from wol_app.config import ConfigManager

pytest.importorskip("PyQt6")

from PyQt6.QtWidgets import QApplication  # noqa: E402

from wol_app.views.devices_view import DeviceCard, DevicesView  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(scope="module", autouse=True)
def _translations():
    from wol_app.translations import Translations

    Translations().load("de")


@pytest.fixture
def tmp_config(tmp_path):
    cfg_path = tmp_path / "devices.json"
    return ConfigManager(str(cfg_path))


@pytest.fixture
def config_with_devices(tmp_config):
    tmp_config.config["devices"] = [
        {"id": "d1", "name": "Desktop", "mac": "AA:BB:CC:DD:EE:01", "ip": "192.168.1.10", "enabled": True},
        {"id": "d2", "name": "Server", "mac": "AA:BB:CC:DD:EE:02", "ip": "192.168.1.20", "enabled": True},
        {"id": "d3", "name": "Laptop", "mac": "AA:BB:CC:DD:EE:03", "ip": "192.168.1.30", "enabled": False},
    ]
    return tmp_config


class TestDeviceCard:
    def test_offline_card_shows_wake_button(self, qapp, config_with_devices):
        card = DeviceCard(config_with_devices.config["devices"][0], "offline", set())
        assert card.action_btn.text() == "Aufwecken"
        assert card.action_btn.objectName() == "wakeButton"
        assert card.dot.objectName() == "dotOffline"

    def test_online_card_shows_shutdown_button(self, qapp, config_with_devices):
        card = DeviceCard(config_with_devices.config["devices"][0], "online", set())
        assert card.action_btn.text() == "Herunterfahren"
        assert card.action_btn.objectName() == "shutdownButton"
        assert card.dot.objectName() == "dotOnline"

    def test_status_swap_updates_button(self, qapp, config_with_devices):
        card = DeviceCard(config_with_devices.config["devices"][0], "offline", set())
        card.set_status("online")
        assert card.action_btn.objectName() == "shutdownButton"
        card.set_status("unknown")
        assert card.action_btn.objectName() == "wakeButton"
        assert card.dot.objectName() == "dotUnknown"

    def test_action_click_emits_wake_or_shutdown(self, qapp, config_with_devices):
        card = DeviceCard(config_with_devices.config["devices"][0], "offline", set())
        fired = []
        card.wake_requested.connect(lambda did: fired.append(("wake", did)))
        card.shutdown_requested.connect(lambda did: fired.append(("shutdown", did)))
        card._action_clicked()  # offline -> wake
        card.set_status("online")
        card._action_clicked()  # online -> shutdown
        assert fired == [("wake", "d1"), ("shutdown", "d1")]

    def test_local_device_marked_with_me(self, qapp, config_with_devices):
        card = DeviceCard(
            config_with_devices.config["devices"][0], "unknown", {"192.168.1.10"})
        assert "(ich)" in card.title.text()

    def test_disabled_device_buttons_disabled(self, qapp, config_with_devices):
        card = DeviceCard(config_with_devices.config["devices"][2], "unknown", set())
        assert not card.action_btn.isEnabled()
        assert not card.remote_fs_btn.isEnabled()
        assert not card.remote_win_btn.isEnabled()
        assert "Deaktiviert" in card.title.text()

    def test_remote_buttons_emit_signal(self, qapp, config_with_devices):
        card = DeviceCard(config_with_devices.config["devices"][0], "unknown", set())
        fired = []
        card.remote_requested.connect(lambda did, fs: fired.append((did, fs)))
        card.remote_fs_btn.click()
        card.remote_win_btn.click()
        assert fired == [("d1", True), ("d1", False)]


class TestDevicesView:
    def test_cards_built_for_all_devices(self, qapp, config_with_devices):
        view = DevicesView(config_with_devices)
        assert set(view._cards) == {"d1", "d2", "d3"}

    def test_summary_counts_devices_and_online(self, qapp, config_with_devices):
        view = DevicesView(config_with_devices)
        view._statuses = {"d1": "online", "d2": "offline", "d3": "unknown"}
        view._update_summary()
        assert "3" in view.subtitle.text()
        assert "1" in view.subtitle.text()

    def test_search_filters_cards(self, qapp, config_with_devices):
        view = DevicesView(config_with_devices)
        view.search_input.setText("Server")
        assert set(view._cards) == {"d2"}
        view.search_input.setText("")
        assert set(view._cards) == {"d1", "d2", "d3"}

    def test_statuses_finished_updates_cards(self, qapp, config_with_devices):
        view = DevicesView(config_with_devices)
        results = [("d1", "Desktop", "online", ""), ("d2", "Server", "offline", "")]
        view._on_statuses_finished(results)
        assert view._cards["d1"].action_btn.objectName() == "shutdownButton"
        assert view._cards["d2"].action_btn.objectName() == "wakeButton"

    def test_empty_state_visible_without_devices(self, qapp, tmp_config):
        view = DevicesView(tmp_config)
        assert view.empty_label.isVisibleTo(view)

    def test_retranslate_keeps_status_text(self, qapp, config_with_devices):
        view = DevicesView(config_with_devices)
        view._on_statuses_finished([("d1", "Desktop", "online", "")])
        view.retranslate()
        assert view._cards["d1"].action_btn.text() == "Herunterfahren"
