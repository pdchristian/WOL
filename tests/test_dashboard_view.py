"""Tests for the device dashboard view (metrics display + batch library)."""

import pytest

from wol_app.config import ConfigManager
from wol_app.translations import Translations

pytest.importorskip("PyQt6")

from PyQt6.QtWidgets import QApplication  # noqa: E402

from wol_app.views.dashboard_view import (  # noqa: E402
    DeviceDashboardView,
    MetricCard,
    RingGauge,
    Sparkline,
    _fmt_bytes_gb,
    _fmt_uptime,
)


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(scope="module", autouse=True)
def _translations():
    Translations().load("de")


@pytest.fixture
def tmp_config(tmp_path):
    cfg = ConfigManager(config_path=str(tmp_path / "dash.json"))
    cfg.add_device("Workstation", "AA:BB:CC:00:11:22")
    dev_id = cfg.get_devices()[0]["id"]
    cfg.update_device(dev_id, ip="192.168.1.10", username="user", password="pass")
    return cfg, dev_id


@pytest.fixture
def view(qapp, tmp_config, monkeypatch):
    cfg, _ = tmp_config
    # No real network polling from tests.
    monkeypatch.setattr(DeviceDashboardView, "_poll_metrics", lambda self: None)
    v = DeviceDashboardView(cfg)
    yield v
    v.cancel_workers()


METRICS = {
    "status": "ok", "protocol": 2, "hostname": "WS-07",
    "cpu": 42.0, "cpu_count": 8, "ram_used": 8 * 1024**3,
    "ram_total": 32 * 1024**3, "gpu": 66.0, "vram_used": 3 * 1024**3,
    "vram_total": 12 * 1024**3, "gpu_name": "NVIDIA RTX 4070", "uptime": 3600,
}


class TestFormatting:
    def test_bytes_gb(self):
        assert _fmt_bytes_gb(12 * 1024**3) == "12.0"
        assert _fmt_bytes_gb(None) == ""

    def test_uptime(self):
        assert _fmt_uptime(90) == "1 m"
        assert _fmt_uptime(3700) == "1 h 1 m"
        assert _fmt_uptime(3 * 86400 + 4 * 3600) == "3 d 4 h"
        assert _fmt_uptime(None) == ""


class TestWidgets:
    def test_ring_gauge_accepts_none_and_clamps(self, qapp):
        gauge = RingGauge("gauge_cpu")
        gauge.set_value(None)
        assert gauge._value.text() == "–"
        gauge.set_value(150)
        assert gauge._pct == 100.0
        gauge.set_value(-5)
        assert gauge._pct == 0.0
        gauge.grab()  # paintEvent must not raise

    def test_sparkline_paints_with_gaps(self, qapp):
        spark = Sparkline("gauge_ram")
        spark.push(None)
        spark.push(50.0)
        spark.push(70.0)
        spark.grab()
        spark.reset()
        assert all(v is None for v in spark._values)


class TestDashboardView:
    def test_set_device_updates_header(self, view, tmp_config):
        _, dev_id = tmp_config
        view.set_device(dev_id)
        assert view.title.text() == "Workstation"
        assert "192.168.1.10" in view.mono.text()

    def test_apply_metrics_updates_cards(self, view, tmp_config):
        _, dev_id = tmp_config
        view.set_device(dev_id)
        view._on_metrics(dict(METRICS))
        assert view.cards["cpu"].gauge._pct == 42.0
        assert view.cards["gpu"].gauge._pct == 66.0
        assert "RTX 4070" in view.cards["gpu"].detail.text()
        assert "12.0" in view.cards["vram"].detail.text()
        assert view.badge.objectName() == "badgeOnline"

    def test_apply_metrics_without_gpu(self, view, tmp_config):
        _, dev_id = tmp_config
        view.set_device(dev_id)
        data = dict(METRICS, gpu=None, vram_used=None, vram_total=None, gpu_name=None)
        view._on_metrics(data)
        assert view.cards["gpu"].gauge._pct is None
        assert view.cards["gpu"].detail.text() == Translations.tr("modern.dashboard.metric.na")

    def test_failure_shows_offline_badge(self, view, tmp_config):
        _, dev_id = tmp_config
        view.set_device(dev_id)
        view._on_metrics(dict(METRICS))
        view._on_metrics_failed("Connection timed out")
        assert view.badge.objectName() == "badgeOffline"
        assert "timed out" in view.status_line.text()

    def test_run_disabled_without_allow_batch(self, view, tmp_config):
        _, dev_id = tmp_config
        view.set_device(dev_id)
        view._on_metrics(dict(METRICS))
        assert not view.run_btn.isEnabled()
        # With the per-device opt-in (and metrics online) it becomes enabled
        view.allow_batch_check.setChecked(True)
        assert view.run_btn.isEnabled()

    def test_batch_crud_persists(self, qapp, tmp_config, monkeypatch):
        cfg, dev_id = tmp_config
        monkeypatch.setattr(DeviceDashboardView, "_poll_metrics", lambda self: None)
        v = DeviceDashboardView(cfg)
        v.set_device(dev_id)
        v._new_batch()
        batches = ConfigManager.get_device_batches(cfg.get_device_by_id(dev_id))
        assert len(batches) == 1
        # Edit + save through the editor
        v.name_edit.setText("Cleanup")
        v.script_edit.setPlainText("@echo off\necho hi")
        v.timeout_spin.setValue(30)
        v._commit_editor()
        batches = ConfigManager.get_device_batches(cfg.get_device_by_id(dev_id))
        assert batches[0]["name"] == "Cleanup"
        assert batches[0]["timeout"] == 30
        assert "echo hi" in batches[0]["script"]
        # Duplicate
        v._duplicate_batch()
        assert len(ConfigManager.get_device_batches(cfg.get_device_by_id(dev_id))) == 2
        v.cancel_workers()

    def test_batch_survives_reopen(self, qapp, tmp_config, monkeypatch):
        cfg, dev_id = tmp_config
        cfg.set_device_batches(dev_id, [{"id": "b1", "name": "Ping",
                                         "script": "ping 1.2.3.4", "timeout": 10}])
        monkeypatch.setattr(DeviceDashboardView, "_poll_metrics", lambda self: None)
        v = DeviceDashboardView(cfg)
        v.set_device(dev_id)
        assert v.batch_list.count() == 1
        assert v.script_edit.toPlainText() == "ping 1.2.3.4"
        v.cancel_workers()

    def test_allow_batch_persists(self, view, tmp_config):
        cfg, dev_id = tmp_config
        view.set_device(dev_id)
        view.allow_batch_check.setChecked(True)
        assert cfg.get_device_by_id(dev_id).get("allow_batch") is True
        view.allow_batch_check.setChecked(False)
        assert cfg.get_device_by_id(dev_id).get("allow_batch") is False

    def test_retranslate_does_not_raise(self, view, tmp_config):
        _, dev_id = tmp_config
        view.set_device(dev_id)
        view._on_metrics(dict(METRICS))
        view.retranslate()
        assert view.cards["cpu"].title.text() == \
            Translations.tr("modern.dashboard.metric.cpu").upper()

    def test_metric_card_reset(self, qapp):
        card = MetricCard("cpu", "CPU")
        card.set_value(50.0, "8 Kerne")
        assert card.gauge._pct == 50.0
        card.reset_display()
        assert card.gauge._pct is None
        assert card.detail.text() == ""
