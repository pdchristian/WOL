"""Tests for wol_app.config ConfigManager."""

import base64
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


class TestInferenceInterval(ConfigManagerTestBase):
    """ui.inference_interval_ms — devices-view inference badge poll cadence."""

    def test_default_is_10_seconds(self):
        cm = ConfigManager(config_path=str(self.config_path))
        self.assertEqual(cm.get_inference_interval_ms(), 10_000)

    def test_set_and_persist(self):
        cm = ConfigManager(config_path=str(self.config_path))
        cm.set_inference_interval_ms(15_000)
        self.assertEqual(cm.get_inference_interval_ms(), 15_000)
        with open(self.config_path) as f:
            saved = json.load(f)
        self.assertEqual(saved["ui"]["inference_interval_ms"], 15_000)

    def test_clamped_to_range(self):
        cm = ConfigManager(config_path=str(self.config_path))
        cm.set_inference_interval_ms(1_000)
        self.assertEqual(cm.get_inference_interval_ms(), 5_000)
        cm.set_inference_interval_ms(120_000)
        self.assertEqual(cm.get_inference_interval_ms(), 30_000)

    def test_garbage_falls_back_to_default(self):
        self._write_raw({"ui": {"inference_interval_ms": "not-a-number"}})
        cm = ConfigManager(config_path=str(self.config_path))
        self.assertEqual(cm.get_inference_interval_ms(), 10_000)


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

    def test_update_device_persists_rdp_auth_level(self):
        # Regression: rdp_auth_level used to be silently dropped by
        # update_device, so the certificate-validation dropdown never saved.
        cm = ConfigManager(config_path=str(self.config_path))
        device = cm.add_device("PC", "AA:BB:CC:DD:EE:FF")
        cm.update_device(device["id"], rdp_auth_level=0)
        self.assertEqual(cm.get_device_rdp_auth_level(device), 0)
        cm.update_device(device["id"], rdp_auth_level=2)
        self.assertEqual(cm.get_device_rdp_auth_level(device), 2)
        # Reload from disk to confirm it was actually written.
        reloaded = ConfigManager(config_path=str(self.config_path))
        dev2 = reloaded.get_device_by_id(device["id"])
        self.assertEqual(reloaded.get_device_rdp_auth_level(dev2), 2)

    def test_update_device_rdp_auth_level_invalid_falls_back(self):
        cm = ConfigManager(config_path=str(self.config_path))
        device = cm.add_device("PC", "AA:BB:CC:DD:EE:FF")
        cm.update_device(device["id"], rdp_auth_level=7)
        self.assertEqual(cm.get_device_rdp_auth_level(device), 1)
        cm.update_device(device["id"], rdp_auth_level="bogus")
        self.assertEqual(cm.get_device_rdp_auth_level(device), 1)


class TestDeviceOs(ConfigManagerTestBase):
    def test_normalize_os_collapses_distributions(self):
        self.assertEqual(ConfigManager.normalize_os("ubuntu"), "linux")
        self.assertEqual(ConfigManager.normalize_os("Debian"), "linux")
        self.assertEqual(ConfigManager.normalize_os("Windows"), "windows")
        self.assertEqual(ConfigManager.normalize_os("win32"), "windows")
        self.assertEqual(ConfigManager.normalize_os("darwin"), "macos")
        self.assertEqual(ConfigManager.normalize_os("macOS"), "macos")
        self.assertEqual(ConfigManager.normalize_os(""), "")
        self.assertEqual(ConfigManager.normalize_os("unknown"), "")
        self.assertEqual(ConfigManager.normalize_os(None), "")

    def test_get_device_os_empty_for_legacy_device(self):
        # Devices created before the "os" key exist report "" and are never
        # migrated — the value is re-detectable at any time.
        cm = ConfigManager(config_path=str(self.config_path))
        device = cm.add_device("PC", "AA:BB:CC:DD:EE:FF")
        self.assertNotIn("os", device)
        self.assertEqual(cm.get_device_os(device), "")

    def test_set_device_os_persists_normalized_value(self):
        cm = ConfigManager(config_path=str(self.config_path))
        device = cm.add_device("PC", "AA:BB:CC:DD:EE:FF")
        self.assertTrue(cm.set_device_os(device["id"], "ubuntu"))
        self.assertEqual(cm.get_device_os(device), "linux")
        self.assertEqual(device["os"], "linux")
        reloaded = ConfigManager(config_path=str(self.config_path))
        self.assertEqual(
            cm.get_device_os(reloaded.get_device_by_id(device["id"])), "linux")

    def test_set_device_os_clears_with_empty_value(self):
        cm = ConfigManager(config_path=str(self.config_path))
        device = cm.add_device("PC", "AA:BB:CC:DD:EE:FF")
        cm.set_device_os(device["id"], "macos")
        cm.set_device_os(device["id"], "")
        self.assertEqual(cm.get_device_os(device), "")

    def test_os_confidence_roundtrip(self):
        cm = ConfigManager(config_path=str(self.config_path))
        device = cm.add_device("PC", "AA:BB:CC:DD:EE:FF")
        cm.set_device_os(device["id"], "ubuntu", "medium")
        reloaded = ConfigManager(config_path=str(self.config_path))
        stored = reloaded.get_device_by_id(device["id"])
        self.assertEqual(stored["os"], "linux")
        self.assertEqual(stored["os_confidence"], "medium")
        self.assertEqual(reloaded.get_device_os_confidence(stored), "medium")

    def test_invalid_os_confidence_is_dropped(self):
        cm = ConfigManager(config_path=str(self.config_path))
        device = cm.add_device("PC", "AA:BB:CC:DD:EE:FF")
        cm.set_device_os(device["id"], "windows", "guessed")
        self.assertEqual(
            cm.get_device_os_confidence(cm.get_device_by_id(device["id"])), "")

    def test_confidence_cleared_with_the_platform(self):
        cm = ConfigManager(config_path=str(self.config_path))
        device = cm.add_device("PC", "AA:BB:CC:DD:EE:FF")
        cm.set_device_os(device["id"], "windows", "high")
        cm.set_device_os(device["id"], "")
        stored = cm.get_device_by_id(device["id"])
        self.assertEqual(stored.get("os"), "")
        self.assertNotIn("os_confidence", stored)

    def test_get_device_os_confidence_defaults_to_empty(self):
        self.assertEqual(ConfigManager.get_device_os_confidence({}), "")
        self.assertEqual(
            ConfigManager.get_device_os_confidence({"os_confidence": "bogus"}), "")


class TestRemoteSection(ConfigManagerTestBase):
    """Platform -> protocol routing and the VNC / RustDesk client settings."""

    def test_defaults_materialised_for_old_config(self):
        self._write_raw({"devices": []})
        cm = ConfigManager(config_path=str(self.config_path))
        self.assertEqual(cm.get_remote_protocol("windows"), "rdp")
        self.assertEqual(cm.get_remote_protocol("macos"), "rustdesk")
        self.assertEqual(cm.get_remote_protocol("linux"), "vnc")
        self.assertEqual(cm.get_vnc_port(), 5900)
        self.assertEqual(cm.get_vnc_viewer_path(), "")
        self.assertEqual(cm.get_rustdesk_direct_port(), 21118)
        self.assertEqual(cm.get_rustdesk_path(), "")

    def test_protocol_roundtrip_persists(self):
        cm = ConfigManager(config_path=str(self.config_path))
        cm.set_remote_protocol("windows", "vnc")
        cm.set_remote_protocol("linux", "rdp")
        reloaded = ConfigManager(config_path=str(self.config_path))
        self.assertEqual(reloaded.get_remote_protocol("windows"), "vnc")
        self.assertEqual(reloaded.get_remote_protocol("linux"), "rdp")
        # untouched platforms keep their default
        self.assertEqual(reloaded.get_remote_protocol("macos"), "rustdesk")

    def test_unknown_platform_and_distro_ids_fall_back(self):
        cm = ConfigManager(config_path=str(self.config_path))
        # "" / "unknown" = never detected -> historical RDP
        self.assertEqual(cm.get_remote_protocol(""), "rdp")
        self.assertEqual(cm.get_remote_protocol("unknown"), "rdp")
        # concrete distributions collapse to linux (normalize_os)
        self.assertEqual(cm.get_remote_protocol("ubuntu"), "vnc")
        self.assertEqual(cm.get_remote_protocol("darwin"), "rustdesk")

    def test_old_macos_vnc_default_switches_to_rustdesk_once(self):
        # Configs written before RustDesk became the macOS default still carry
        # "vnc". The first load switches the entry and persists it, so the
        # switch never repeats on later starts.
        self._write_raw({
            "devices": [],
            "remote": {"protocol_by_os": {
                "windows": "rdp", "macos": "vnc", "linux": "vnc"}},
        })
        cm = ConfigManager(config_path=str(self.config_path))
        self.assertEqual(cm.get_remote_protocol("macos"), "rustdesk")
        self.assertEqual(cm.get_remote_protocol("linux"), "vnc")
        reloaded = ConfigManager(config_path=str(self.config_path))
        self.assertEqual(reloaded.get_remote_protocol("macos"), "rustdesk")

    def test_explicit_macos_vnc_choice_survives_the_switch(self):
        # protocol_user_set marks a routing edited in the settings: the default
        # switch must not overwrite a deliberate decision for TurboVNC.
        self._write_raw({
            "devices": [],
            "remote": {
                "protocol_by_os": {"macos": "vnc"},
                "protocol_user_set": True,
            },
        })
        cm = ConfigManager(config_path=str(self.config_path))
        self.assertEqual(cm.get_remote_protocol("macos"), "vnc")

    def test_setting_a_protocol_marks_it_user_chosen(self):
        self._write_raw({
            "devices": [],
            "remote": {"protocol_by_os": {"macos": "vnc"}},
        })
        cm = ConfigManager(config_path=str(self.config_path))
        cm.set_remote_protocol("macos", "vnc")
        reloaded = ConfigManager(config_path=str(self.config_path))
        self.assertEqual(reloaded.get_remote_protocol("macos"), "vnc")

    def test_invalid_stored_value_falls_back_to_default(self):
        cm = ConfigManager(config_path=str(self.config_path))
        cm.config["remote"]["protocol_by_os"]["windows"] = "telnet"
        self.assertEqual(cm.get_remote_protocol("windows"), "rdp")

    def test_missing_mapping_uses_defaults(self):
        cm = ConfigManager(config_path=str(self.config_path))
        cm.config["remote"] = {}
        self.assertEqual(cm.get_remote_protocol("linux"), "vnc")

    def test_set_rejects_unknown_platform_and_protocol(self):
        cm = ConfigManager(config_path=str(self.config_path))
        with self.assertRaises(ValueError):
            cm.set_remote_protocol("unknown", "vnc")
        with self.assertRaises(ValueError):
            cm.set_remote_protocol("windows", "telnet")

    def test_vnc_port_roundtrip_and_validation(self):
        cm = ConfigManager(config_path=str(self.config_path))
        cm.set_vnc_port(5901)
        self.assertEqual(
            ConfigManager(config_path=str(self.config_path)).get_vnc_port(), 5901)
        for bad in (0, -1, 70000):
            with self.assertRaises(ValueError):
                cm.set_vnc_port(bad)

    def test_vnc_port_repairs_hand_edited_value(self):
        cm = ConfigManager(config_path=str(self.config_path))
        cm.config["remote"]["vnc_port"] = 99999
        self.assertEqual(cm.get_vnc_port(), 65535)
        cm.config["remote"]["vnc_port"] = "unsinn"
        self.assertEqual(cm.get_vnc_port(), 5900)

    def test_vnc_viewer_path_roundtrip(self):
        cm = ConfigManager(config_path=str(self.config_path))
        cm.set_vnc_viewer_path(r"C:\Tools\vncviewer.bat")
        self.assertEqual(
            ConfigManager(config_path=str(self.config_path)).get_vnc_viewer_path(),
            r"C:\Tools\vncviewer.bat")
        cm.set_vnc_viewer_path("   ")
        self.assertEqual(cm.get_vnc_viewer_path(), "")

    def test_rustdesk_port_roundtrip_and_validation(self):
        cm = ConfigManager(config_path=str(self.config_path))
        cm.set_rustdesk_direct_port(21119)
        self.assertEqual(
            ConfigManager(
                config_path=str(self.config_path)).get_rustdesk_direct_port(),
            21119)
        for bad in (0, -1, 70000):
            with self.assertRaises(ValueError):
                cm.set_rustdesk_direct_port(bad)

    def test_rustdesk_port_repairs_hand_edited_value(self):
        cm = ConfigManager(config_path=str(self.config_path))
        cm.config["remote"]["rustdesk_direct_port"] = 99999
        self.assertEqual(cm.get_rustdesk_direct_port(), 65535)
        cm.config["remote"]["rustdesk_direct_port"] = "unsinn"
        self.assertEqual(cm.get_rustdesk_direct_port(), 21118)

    def test_rustdesk_path_roundtrip(self):
        cm = ConfigManager(config_path=str(self.config_path))
        cm.set_rustdesk_path(r"C:\Program Files\RustDesk\RustDesk.exe")
        self.assertEqual(
            ConfigManager(config_path=str(self.config_path)).get_rustdesk_path(),
            r"C:\Program Files\RustDesk\RustDesk.exe")
        cm.set_rustdesk_path("   ")
        self.assertEqual(cm.get_rustdesk_path(), "")


class TestDeviceRustDeskId(ConfigManagerTestBase):
    """The optional per-device RustDesk peer id."""

    def test_getter_defaults_to_empty(self):
        self.assertEqual(ConfigManager.get_device_rustdesk_id({}), "")

    def test_getter_accepts_ids_uuids_and_host_port(self):
        for value in ("123456789", "550e8400-e29b-41d4-a716-446655440000",
                      "mac-mini.local", "192.168.1.20:21118"):
            self.assertEqual(
                ConfigManager.get_device_rustdesk_id({"rustdesk_id": value}),
                value)

    def test_getter_rejects_unusable_values(self):
        for value in ("", "  ", "12345 6789", "a/b", "rm -rf /", "id;ls",
                      "x" * 65, 42, None):
            self.assertEqual(
                ConfigManager.get_device_rustdesk_id({"rustdesk_id": value}),
                "")

    def test_update_device_stores_and_clears_the_id(self):
        cm = ConfigManager(config_path=str(self.config_path))
        device = cm.add_device("Mac", "AA:BB:CC:DD:EE:FF")
        cm.update_device(device["id"], rustdesk_id=" 123456789 ")
        self.assertEqual(
            cm.get_device_by_id(device["id"]).get("rustdesk_id"), "123456789")
        cm.update_device(device["id"], rustdesk_id="")
        self.assertNotIn("rustdesk_id", cm.get_device_by_id(device["id"]))

    def test_set_device_rustdesk_id_roundtrip(self):
        cm = ConfigManager(config_path=str(self.config_path))
        device = cm.add_device("Mac", "AA:BB:CC:DD:EE:FF")
        self.assertTrue(cm.set_device_rustdesk_id(device["id"], "987654321"))
        self.assertEqual(
            ConfigManager(config_path=str(self.config_path))
            .get_device_rustdesk_id(cm.get_device_by_id(device["id"])),
            "987654321")
        self.assertTrue(cm.set_device_rustdesk_id(device["id"], ""))
        self.assertNotIn(
            "rustdesk_id",
            ConfigManager(config_path=str(self.config_path))
            .get_device_by_id(device["id"]))


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


class TestDeviceApiKey(ConfigManagerTestBase):
    """Dashboard API key (host protocol v10) storage rules."""

    def test_set_and_get_roundtrip(self):
        cm = ConfigManager(config_path=str(self.config_path))
        cm.add_device("Blade-18", "AA:BB:CC:DD:EE:01")
        dev_id = cm.config["devices"][0]["id"]
        self.assertTrue(cm.set_device_api_key(dev_id, "dummy"))
        self.assertEqual(
            ConfigManager.get_device_api_key(cm.get_device_by_id(dev_id)),
            "dummy")

    def test_stored_encrypted_on_disk(self):
        cm = ConfigManager(config_path=str(self.config_path))
        cm.add_device("Blade-18", "AA:BB:CC:DD:EE:01")
        dev_id = cm.config["devices"][0]["id"]
        cm.set_device_api_key(dev_id, "sk-abcdef0123456789" * 4)
        with open(self.config_path) as f:
            saved = json.load(f)
        raw = saved["devices"][0]["api_key"]
        # Explicit "enc:" marker — the base64 heuristic alone would misread a
        # long alphanumeric key as ciphertext and lose it on the next load.
        self.assertTrue(raw.startswith("enc:"))
        self.assertNotIn("sk-abcdef", raw)
        # Reload must hand back the plaintext key
        cm2 = ConfigManager(config_path=str(self.config_path))
        self.assertEqual(
            ConfigManager.get_device_api_key(cm2.get_device_by_id(dev_id)),
            "sk-abcdef0123456789" * 4)

    def test_empty_key_removes_field(self):
        cm = ConfigManager(config_path=str(self.config_path))
        cm.add_device("PC", "AA:BB:CC:DD:EE:01")
        dev_id = cm.config["devices"][0]["id"]
        cm.set_device_api_key(dev_id, "dummy")
        cm.set_device_api_key(dev_id, "")
        self.assertNotIn("api_key", cm.get_device_by_id(dev_id))
        with open(self.config_path) as f:
            saved = json.load(f)
        self.assertNotIn("api_key", saved["devices"][0])

    def test_invalid_values_degrade_to_empty(self):
        for bad in ("", "   ", "x" * 129, "line1\nline2", "tab\there",
                    "emoji\U0001f600", 42, None):
            self.assertEqual(ConfigManager.get_device_api_key(
                {"api_key": bad}), "", msg=f"bad value: {bad!r}")

    def test_legacy_plaintext_key_reencrypted(self):
        self._write_raw({"devices": [{
            "id": "1", "name": "PC", "mac": "AA:BB:CC:DD:EE:FF",
            "api_key": "plaintext-key"}]})
        cm = ConfigManager(config_path=str(self.config_path))
        self.assertEqual(cm.config["devices"][0]["api_key"], "plaintext-key")
        with open(self.config_path) as f:
            saved = json.load(f)
        self.assertTrue(saved["devices"][0]["api_key"].startswith("enc:"))

    def test_undecryptable_key_does_not_break_load(self):
        # Valid base64, long enough to attempt decryption, but not our
        # ciphertext -> decrypt_password() raises and the field is dropped.
        bogus = base64.b64encode(b"\x00" * 24).decode()
        self._write_raw({"devices": [{
            "id": "1", "name": "PC", "mac": "AA:BB:CC:DD:EE:FF",
            "api_key": f"enc:{bogus}"}]})
        cm = ConfigManager(config_path=str(self.config_path))
        self.assertEqual(ConfigManager.get_device_api_key(
            cm.config["devices"][0]), "")


if __name__ == "__main__":
    unittest.main()
