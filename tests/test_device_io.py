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


class TestBatchImportExport:
    """Dashboard batches travel with the device through export/import."""

    def _export(self, config, path):
        with patch("wol_app.device_io.QFileDialog.getSaveFileName",
                   return_value=(str(path), "")), \
             patch("wol_app.device_io.QMessageBox.information"):
            assert export_devices(config) is True

    def _import(self, config, path):
        with patch("wol_app.device_io.QFileDialog.getOpenFileName",
                   return_value=(str(path), "")), \
             patch("wol_app.device_io.QMessageBox.information"):
            return import_devices(config)

    def test_roundtrip_with_batches(self, config, tmp_path):
        d1 = config.add_device("PC1", "AA:BB:CC:DD:EE:01")
        config.set_device_batches(d1["id"], [
            {"id": "b1", "name": "Ping", "script": "ping 1.2.3.4",
             "timeout": 10},
            {"id": "b2", "name": "Maint", "script": "@echo off\r\necho hi",
             "timeout": 60},
        ])
        config.set_device_allow_batch(d1["id"], True)
        src = tmp_path / "dev.json"
        self._export(config, src)
        data = json.loads(src.read_text(encoding="utf-8"))
        assert len(data[0]["batches"]) == 2
        assert data[0]["allow_batch"] is True

        config2 = ConfigManager(config_path=str(tmp_path / "config2.json"))
        assert self._import(config2, src) is True
        imported = config2.get_device_by_name("PC1")
        batches = ConfigManager.get_device_batches(imported)
        assert [b["name"] for b in batches] == ["Ping", "Maint"]
        assert batches[1]["timeout"] == 60
        assert imported.get("allow_batch") is True

    def test_export_omits_empty_batches(self, config, tmp_path):
        config.add_device("Plain", "AA:BB:CC:DD:EE:02")
        src = tmp_path / "dev.json"
        self._export(config, src)
        data = json.loads(src.read_text(encoding="utf-8"))
        assert "batches" not in data[0]

    def test_import_sanitizes_batches(self, config, tmp_path):
        src = tmp_path / "dev.json"
        src.write_text(json.dumps([{
            "name": "PC", "mac": "AA:BB:CC:DD:EE:03",
            "allow_batch": True,
            "batches": [
                {"name": "OK", "script": "echo ok", "timeout": 10},
                {"name": "Empty", "script": "   ", "timeout": 10},
                {"name": "NoScript"},
                "not-a-dict",
                {"name": "Timeout", "script": "echo t", "timeout": 999999},
            ],
        }]), encoding="utf-8")
        assert self._import(config, src) is True
        dev = config.get_device_by_name("PC")
        batches = ConfigManager.get_device_batches(dev)
        assert [b["name"] for b in batches] == ["OK", "Timeout"]
        assert all(b["id"] for b in batches)
        assert batches[1]["timeout"] == 3600
        assert dev.get("allow_batch") is True

    def test_import_without_batches_keeps_existing(self, config, tmp_path):
        d1 = config.add_device("PC1", "AA:BB:CC:DD:EE:01")
        config.set_device_batches(d1["id"], [
            {"id": "b1", "name": "Keep", "script": "echo keep", "timeout": 7}])
        src = tmp_path / "dev.json"
        src.write_text(json.dumps([
            {"name": "PC1", "mac": "AA:BB:CC:DD:EE:01", "ip": "10.0.0.9"},
        ]), encoding="utf-8")
        assert self._import(config, src) is True
        dev = config.get_device_by_name("PC1")
        assert dev.get("ip") == "10.0.0.9"
        batches = ConfigManager.get_device_batches(dev)
        assert [b["name"] for b in batches] == ["Keep"]
