"""Tests for the UI layout mode (classic/modern) selection in ConfigManager."""

from unittest.mock import patch

from wol_app.config import ConfigManager, DEFAULT_CONFIG


def _make_config(tmp_path) -> ConfigManager:
    with patch("wol_app.config.read_ui_mode_from_registry", return_value=None):
        return ConfigManager(config_path=str(tmp_path / "config.json"))


class TestLayoutModeDefaults:
    def test_default_is_classic(self, tmp_path):
        config = _make_config(tmp_path)
        assert config.get_layout_mode() == "classic"

    def test_default_config_contains_layout_keys(self):
        assert DEFAULT_CONFIG["ui"]["layout_mode"] == "classic"
        assert DEFAULT_CONFIG["ui"]["layout_mode_user_set"] is False


class TestSetLayoutMode:
    def test_set_modern_persists(self, tmp_path):
        config = _make_config(tmp_path)
        config.set_layout_mode("modern")
        assert config.get_layout_mode() == "modern"

        # Reload: user choice sticks, registry is not consulted again
        with patch("wol_app.config.read_ui_mode_from_registry", return_value="classic"):
            reloaded = ConfigManager(config_path=str(tmp_path / "config.json"))
        assert reloaded.get_layout_mode() == "modern"

    def test_invalid_mode_raises(self, tmp_path):
        config = _make_config(tmp_path)
        try:
            config.set_layout_mode("hologram")
            raised = False
        except ValueError:
            raised = True
        assert raised


class TestInstallerRegistryHint:
    def test_registry_modern_adopted_on_first_start(self, tmp_path):
        with patch("wol_app.config.read_ui_mode_from_registry", return_value="modern"):
            config = ConfigManager(config_path=str(tmp_path / "config.json"))
        assert config.get_layout_mode() == "modern"

    def test_registry_value_persisted(self, tmp_path):
        with patch("wol_app.config.read_ui_mode_from_registry", return_value="modern"):
            ConfigManager(config_path=str(tmp_path / "config.json"))
        # Second load without registry: persisted value survives
        with patch("wol_app.config.read_ui_mode_from_registry", return_value=None):
            config = ConfigManager(config_path=str(tmp_path / "config.json"))
        assert config.get_layout_mode() == "modern"

    def test_no_registry_value_keeps_classic(self, tmp_path):
        config = _make_config(tmp_path)
        assert config.get_layout_mode() == "classic"

    def test_invalid_stored_mode_falls_back_to_classic(self, tmp_path):
        config = _make_config(tmp_path)
        config.config["ui"]["layout_mode"] = "bogus"
        assert config.get_layout_mode() == "classic"
