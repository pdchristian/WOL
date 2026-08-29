"""Tests for the shared device import/export helpers (wol_app.device_io)."""

import json
from unittest.mock import patch

import pytest

pytest.importorskip("PyQt6")

from wol_app.config import ConfigManager  # noqa: E402
from wol_app.device_io import export_devices, import_devices  # noqa: E402
from wol_app.translations import Translations  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _translations():
    Translations().load("en")


@pytest.fixture()
def config(tmp_path):
    return ConfigManager(config_path=str(tmp_path / "config.json"))


def _export_import_roundtrip(config, tmp_path):
    export_file = tmp_path / "devices.json"

    # Two devices
    d1 = config.add_device("PC1", "AA:BB:CC:DD:EE:01")
    config.update_device(d1["id"], ip="192.168.1.10", username="user1", password="secret")
    config.add_device("PC2", "AA:BB:CC:DD:EE:02")

    with patch("wol_app.device_io.QFileDialog.getSaveFileName",
               return_value=(str(export_file), "")), \
         patch("wol_app.device_io.QMessageBox.information"):
        assert export_devices(config) is True
    assert export_file.exists()

    # Import into a fresh config
    config2 = ConfigManager(config_path=str(tmp_path / "config2.json"))
    with patch("wol_app.device_io.QFileDialog.getOpenFileName",
               return_value=(str(export_file), "")), \
         patch("wol_app.device_io.QMessageBox.information"):
        assert import_devices(config2) is True

    devices = {d["name"]: d for d in config2.get_devices()}
    assert set(devices) == {"PC1", "PC2"}
    assert devices["PC1"]["mac"] == "AA:BB:CC:DD:EE:01"
    assert devices["PC1"]["ip"] == "192.168.1.10"
    assert devices["PC1"]["username"] == "user1"
    # Password survives the encrypted round-trip
    assert devices["PC1"]["password"] == "secret"


class TestDeviceIO:
    def test_roundtrip(self, config, tmp_path):
        _export_import_roundtrip(config, tmp_path)

    def test_export_cancelled(self, config):
        with patch("wol_app.device_io.QFileDialog.getSaveFileName", return_value=("", "")):
            assert export_devices(config) is False

    def test_import_invalid_format(self, config, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text('{"not": "a list"}', encoding="utf-8")
        with patch("wol_app.device_io.QFileDialog.getOpenFileName",
                   return_value=(str(bad), "")), \
             patch("wol_app.device_io.QMessageBox.critical"):
            assert import_devices(config) is False

    def test_import_skips_invalid_mac(self, config, tmp_path):
        src = tmp_path / "devices.json"
        src.write_text(json.dumps([
            {"name": "Good", "mac": "AA:BB:CC:DD:EE:FF"},
            {"name": "Bad", "mac": "not-a-mac"},
        ]), encoding="utf-8")
        with patch("wol_app.device_io.QFileDialog.getOpenFileName",
                   return_value=(str(src), "")), \
             patch("wol_app.device_io.QMessageBox.information"):
            assert import_devices(config) is True
        names = [d["name"] for d in config.get_devices()]
        assert names == ["Good"]
