"""Tests for wol_app.config ConfigManager."""

import json
import tempfile
import unittest
from pathlib import Path

from wol_app.config import ConfigManager
from wol_app.crypto import is_encrypted


class ConfigManagerTestBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.config_path = Path(self._tmp.name) / "config.json"

    def tearDown(self):
        self._tmp.cleanup()

    def _write_raw(self, data: dict):
        with open(self.config_path, "w") as f:
            json.dump(data, f)


class TestConfigLoad(ConfigManagerTestBase):
    def test_load_creates_defaults_when_missing(self):
        cm = ConfigManager(config_path=str(self.config_path))
        self.assertEqual(cm.config["devices"], [])
        self.assertEqual(cm.config["max_logs"], 100)

    def test_load_merges_with_defaults(self):
        self._write_raw({"devices": []})
        cm = ConfigManager(config_path=str(self.config_path))
        # Missing keys filled from defaults
        self.assertEqual(cm.config["network"]["broadcast_port"], 9)
        self.assertEqual(cm.config["ui"]["language"], "en")

    def test_load_legacy_plaintext_password_reencrypted(self):
        self._write_raw({"devices": [{"id": "1", "name": "PC", "mac": "AA:BB:CC:DD:EE:FF", "password": "plaintext"}]})
        cm = ConfigManager(config_path=str(self.config_path))
        # In-memory is decrypted back to plaintext for use
        self.assertEqual(cm.config["devices"][0]["password"], "plaintext")
        # But the persisted file must now be encrypted
        with open(self.config_path) as f:
            saved = json.load(f)
        self.assertTrue(is_encrypted(saved["devices"][0]["password"]))


class TestConfigSave(ConfigManagerTestBase):
    def test_save_encrypts_passwords(self):
        cm = ConfigManager(config_path=str(self.config_path))
        cm.add_device("PC", "AA:BB:CC:DD:EE:FF")
        cm.update_device(cm.config["devices"][0]["id"], password="secret")
        with open(self.config_path) as f:
            saved = json.load(f)
        self.assertTrue(is_encrypted(saved["devices"][0]["password"]))

    def test_logs_trimmed_to_max(self):
        cm = ConfigManager(config_path=str(self.config_path))
        cm.config["max_logs"] = 5
        for i in range(10):
            cm.add_log("PC", "WAKE", "SUCCESS", f"msg {i}")
        self.assertEqual(len(cm.config["logs"]), 5)


class TestConfigNetwork(ConfigManagerTestBase):
    def test_network_settings_default(self):
        cm = ConfigManager(config_path=str(self.config_path))
        self.assertEqual(cm.get_network_settings()["broadcast_port"], 9)

    def test_update_network_settings(self):
        cm = ConfigManager(config_path=str(self.config_path))
        cm.update_network_settings(broadcast_ip="192.168.1.255", broadcast_port=7)
        self.assertEqual(cm.get_network_settings()["broadcast_ip"], "192.168.1.255")
        self.assertEqual(cm.get_network_settings()["broadcast_port"], 7)


class TestConfigShutdownMethod(ConfigManagerTestBase):
    def test_default_shutdown_method_is_host_service(self):
        cm = ConfigManager(config_path=str(self.config_path))
        self.assertEqual(cm.get_default_shutdown_method(), "host_service")

    def test_set_default_shutdown_method(self):
        cm = ConfigManager(config_path=str(self.config_path))
        cm.set_default_shutdown_method("smb")
        self.assertEqual(cm.get_default_shutdown_method(), "smb")

    def test_set_default_rejects_invalid(self):
        cm = ConfigManager(config_path=str(self.config_path))
        with self.assertRaises(ValueError):
            cm.set_default_shutdown_method("bogus")

    def test_add_device_uses_default_method(self):
        cm = ConfigManager(config_path=str(self.config_path))
        cm.set_default_shutdown_method("smb")
        device = cm.add_device("PC", "AA:BB:CC:DD:EE:FF")
        self.assertEqual(device["shutdown_method"], "smb")

    def test_add_device_enabled_flag(self):
        cm = ConfigManager(config_path=str(self.config_path))
        # Default stays enabled
        device = cm.add_device("PC1", "AA:BB:CC:DD:EE:FF")
        self.assertTrue(device["enabled"])
        # Explicit disabled flag is persisted
        disabled = cm.add_device("PC2", "AA:BB:CC:DD:EE:02", enabled=False)
        self.assertFalse(disabled["enabled"])
        self.assertFalse(
            cm.get_device_by_id(disabled["id"])["enabled"]
        )

    def test_legacy_device_defaults_to_smb(self):
        cm = ConfigManager(config_path=str(self.config_path))
        # Simulate a device created before v1.7.0 (no shutdown_method key).
        # Assign a fresh list to avoid mutating the shared DEFAULT_CONFIG.
        cm.config["devices"] = [{
            "id": "legacy", "name": "Old", "mac": "AA:BB:CC:DD:EE:FF",
            "username": "", "password": "", "enabled": True,
        }]
        method = cm.get_device_shutdown_method(cm.config["devices"][0])
        self.assertEqual(method, "smb")

    def test_update_device_sets_shutdown_method(self):
        cm = ConfigManager(config_path=str(self.config_path))
        device = cm.add_device("PC", "AA:BB:CC:DD:EE:FF")
        cm.update_device(device["id"], shutdown_method="smb")
        self.assertEqual(cm.get_device_shutdown_method(device), "smb")

    def test_update_device_rejects_invalid_method(self):
        cm = ConfigManager(config_path=str(self.config_path))
        device = cm.add_device("PC", "AA:BB:CC:DD:EE:FF")
        cm.update_device(device["id"], shutdown_method="bogus")
        # Invalid value is ignored; default stays
        self.assertEqual(cm.get_device_shutdown_method(device), "host_service")

    def test_update_device_keeps_hostname_longer_than_ipv4(self):
        cm = ConfigManager(config_path=str(self.config_path))
        device = cm.add_device("Mercury", "AA:BB:CC:DD:EE:FF")
        cm.update_device(device["id"], ip="ubuntu-mercury.lan.fritz.box")
        # Host names must not be truncated to the old 15-char IPv4 limit.
        self.assertEqual(
            device["ip"], "ubuntu-mercury.lan.fritz.box")

    def test_update_device_strips_and_caps_ip(self):
        cm = ConfigManager(config_path=str(self.config_path))
        device = cm.add_device("PC", "AA:BB:CC:DD:EE:FF")
        cm.update_device(device["id"], ip="  192.168.1.10  ")
        self.assertEqual(device["ip"], "192.168.1.10")
        cm.update_device(device["id"], ip="a" * 300)
        self.assertEqual(len(device["ip"]), 253)


class TestRemoteDesktopResolution(ConfigManagerTestBase):
    def test_default_resolution(self):
        cm = ConfigManager(config_path=str(self.config_path))
        self.assertEqual(cm.get_remote_desktop_resolution(), "1920x1080")

    def test_legacy_config_gets_default(self):
        # Config without the ui.remote_desktop_resolution key (older version)
        self._write_raw({"devices": [], "ui": {"language": "de"}})
        cm = ConfigManager(config_path=str(self.config_path))
        self.assertEqual(cm.get_remote_desktop_resolution(), "1920x1080")

    def test_all_resolutions_persist(self):
        cm = ConfigManager(config_path=str(self.config_path))
        for resolution in ("1280x720", "1600x900", "1920x1080", "1920x1200",
                           "2400x1350", "2560x1440", "3440x1440", "3840x2160",
                           "auto"):
            cm.set_remote_desktop_resolution(resolution)
            self.assertEqual(cm.get_remote_desktop_resolution(), resolution)
            with open(self.config_path) as f:
                saved = json.load(f)
            self.assertEqual(saved["ui"]["remote_desktop_resolution"], resolution)

    def test_set_rejects_invalid_resolution(self):
        cm = ConfigManager(config_path=str(self.config_path))
        with self.assertRaises(ValueError):
            cm.set_remote_desktop_resolution("800x600")

    def test_invalid_stored_value_falls_back_to_default(self):
        self._write_raw({"ui": {"remote_desktop_resolution": "bogus"}})
        cm = ConfigManager(config_path=str(self.config_path))
        self.assertEqual(cm.get_remote_desktop_resolution(), "1920x1080")


class TestWindowGeometry(ConfigManagerTestBase):
    """ui.window_geometry: [x, y, w, h] of the modern main window."""

    def test_default_is_none(self):
        cm = ConfigManager(config_path=str(self.config_path))
        self.assertIsNone(cm.get_window_geometry())

    def test_roundtrip_and_persist(self):
        cm = ConfigManager(config_path=str(self.config_path))
        cm.set_window_geometry(120, 80, 1280, 800)
        self.assertEqual(cm.get_window_geometry(), [120, 80, 1280, 800])
        with open(self.config_path) as f:
            saved = json.load(f)
        self.assertEqual(saved["ui"]["window_geometry"], [120, 80, 1280, 800])

    def test_negative_position_allowed(self):
        # Multi-monitor setups place secondary screens at negative coords.
        cm = ConfigManager(config_path=str(self.config_path))
        cm.set_window_geometry(-1920, 0, 1280, 800)
        self.assertEqual(cm.get_window_geometry(), [-1920, 0, 1280, 800])

    def test_malformed_values_fall_back_to_none(self):
        for bad in (
            "not-a-list",                      # wrong type
            [10, 20, 30],                      # too few entries
            [10, 20, 30, 40, 50],              # too many entries
            [10, "x", 30, 40],                 # non-numeric entry
            [10, 20, 0, 40],                   # zero width
            [10, 20, 30, -5],                  # negative height
            {"x": 1},                          # dict instead of list
        ):
            self._write_raw({"ui": {"window_geometry": bad}})
            cm = ConfigManager(config_path=str(self.config_path))
            self.assertIsNone(cm.get_window_geometry(), msg=f"bad value: {bad!r}")


if __name__ == "__main__":
    unittest.main()
