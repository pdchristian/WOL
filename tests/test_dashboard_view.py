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


def view_status_creds(view) -> bool:
    """Status line shows the credential hint (popup regression helper)."""
    return view.status_line.text() == \
        Translations.tr("modern.dashboard.creds.message")


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

    def test_header_shows_host_service_version_after_metrics(self, view, tmp_config):
        _, dev_id = tmp_config
        view.set_device(dev_id)
        # No version in the header before the first metrics response.
        assert "Host Service" not in view.mono.text()
        view._on_metrics(dict(METRICS))
        assert "192.168.1.10" in view.mono.text()
        assert "AA:BB:CC:00:11:22" in view.mono.text()
        assert "Host Service v2" in view.mono.text()
        # Offline: the version hint disappears with the connection.
        view._on_metrics_failed("Connection timed out")
        assert "Host Service" not in view.mono.text()

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

    def test_run_reenabled_after_going_online(self, view, tmp_config):
        """Regression: run_btn must not stay disabled after an offline phase.

        Toggling the opt-in before the host answered (or while it was down)
        used to leave the button dead until the checkbox was toggled again.
        """
        _, dev_id = tmp_config
        view.set_device(dev_id)
        view.allow_batch_check.setChecked(True)
        # Host not reachable yet -> run disabled
        view._on_metrics_failed("Connection refused")
        assert not view.run_btn.isEnabled()
        # Host answers -> run becomes available without touching the checkbox
        view._on_metrics(dict(METRICS))
        assert view.run_btn.isEnabled()
        # And offline again -> disabled
        view._on_metrics_failed("Connection refused")
        assert not view.run_btn.isEnabled()

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

    def test_missing_credentials_popup_once(self, qapp, tmp_path, monkeypatch):
        """No stored credentials -> offline status + warning popup (once)."""
        cfg = ConfigManager(config_path=str(tmp_path / "creds.json"))
        cfg.add_device("NoCreds", "AA:BB:CC:00:11:33")
        dev_id = cfg.get_devices()[0]["id"]
        cfg.update_device(dev_id, ip="192.168.1.11")
        monkeypatch.setattr("wol_app.views.dashboard_view.HEADLESS_MODE", False)
        calls = []
        monkeypatch.setattr(
            "wol_app.views.dashboard_view.QMessageBox.warning",
            lambda *a, **k: calls.append(a))
        v = DeviceDashboardView(cfg)
        v.set_device(dev_id)
        assert len(calls) == 1
        assert Translations.tr("modern.dashboard.creds.message") in calls[0][2]
        assert view_status_creds(v)
        # Polling again must not spam the popup …
        v._poll_metrics()
        assert len(calls) == 1
        # … but switching devices arms it again.
        v.set_device(dev_id)
        assert len(calls) == 2
        v.cancel_workers()

    def test_auth_failure_shows_credential_message(self, view, tmp_config):
        """Host rejects credentials -> credential text (not "unreachable")."""
        _, dev_id = tmp_config
        view.set_device(dev_id)
        calls = []
        import wol_app.views.dashboard_view as dv
        orig_warning = dv.QMessageBox.warning
        dv.QMessageBox.warning = staticmethod(lambda *a, **k: calls.append(a))
        try:
            view._on_metrics_failed("Authentication failed")
        finally:
            dv.QMessageBox.warning = orig_warning
        assert view.status_line.text() == \
            Translations.tr("modern.dashboard.creds.message")
        assert len(calls) == 1
        # A later transport error falls back to the normal offline text
        view._on_metrics_failed("Connection timed out")
        assert "timed out" in view.status_line.text()

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


class TestWatchedProcesses:
    """Service chips + services panel for watched processes (v3)."""

    def _view_with_watch(self, qapp, tmp_path, monkeypatch, entries):
        cfg = ConfigManager(config_path=str(tmp_path / "watch.json"))
        cfg.add_device("AIServer", "AA:BB:CC:00:11:99")
        dev_id = cfg.get_devices()[0]["id"]
        cfg.update_device(dev_id, ip="192.168.1.50",
                          username="user", password="pass")
        cfg.set_device_watch_processes(dev_id, entries)
        monkeypatch.setattr(DeviceDashboardView, "_poll_metrics", lambda self: None)
        v = DeviceDashboardView(cfg)
        v.set_device(dev_id)
        return v

    def test_no_watch_no_chips(self, view, tmp_config):
        _, dev_id = tmp_config
        view.set_device(dev_id)
        view._on_metrics(dict(METRICS))
        assert view._chip_widgets == {}
        assert view.svc_panel.isHidden()

    def test_chip_running_ready(self, qapp, tmp_path, monkeypatch):
        v = self._view_with_watch(qapp, tmp_path, monkeypatch,
                                  ["llama-server.exe:8080"])
        assert "llama-server.exe:8080" in v._chip_widgets
        v._on_metrics(dict(METRICS, processes={
            "llama-server.exe:8080": {"running": True, "pid": 4711, "cpu": 3.0,
                                       "ram": 5 * 1024**3, "uptime": 3600,
                                       "api_port": 8080, "api_port_open": True,
                                       "model": "qwen2.5-coder-14b-q4.gguf"}}))
        chip = v._chip_widgets["llama-server.exe:8080"]
        assert chip.objectName() == "svcChipRunning"
        assert not chip.isHidden()
        assert not v.svc_panel.isHidden()

    def test_chip_and_row_list_loaded_models(self, qapp, tmp_path, monkeypatch):
        """Host v4 "models" list: chip shows first + "+N", row one line each."""
        v = self._view_with_watch(qapp, tmp_path, monkeypatch,
                                  ["llama-server.exe:8080"])
        v._on_metrics(dict(METRICS, processes={
            "llama-server.exe:8080": {
                "running": True, "pid": 4711, "cpu": 3.0,
                "ram": 5 * 1024**3, "uptime": 3600,
                "api_port": 8080, "api_port_open": True,
                "models": ["Qwen3.8-Flash-256k-50", "glm-4.7-air"]}}))
        chip = v._chip_widgets["llama-server.exe:8080"]
        assert "Qwen3.8-Flash-256k-50 +1" in chip.text()
        row = v._svc_row_widgets["llama-server.exe:8080"]
        row_models = [lbl.text() for lbl in row._model_labels
                      if not lbl.isHidden()]
        assert any("Qwen3.8-Flash-256k-50" in t for t in row_models)
        assert any("glm-4.7-air" in t for t in row_models)

    def test_row_falls_back_to_argv_model(self, qapp, tmp_path, monkeypatch):
        """Hosts without "models" (v3) keep showing the argv-derived name;

        dots inside the name are NOT truncated (regression: "Qwen3.8-…"
        was cut to "Qwen3" by a split(".") on the dashboard).
        """
        v = self._view_with_watch(qapp, tmp_path, monkeypatch,
                                  ["llama-server.exe"])
        v._on_metrics(dict(METRICS, processes={
            "llama-server.exe": {"running": True, "pid": 9, "cpu": 1.0,
                                  "ram": 1024, "uptime": 10,
                                  "model": "Qwen3.8-Flash-256k-62"}}))
        row = v._svc_row_widgets["llama-server.exe"]
        texts = [lbl.text() for lbl in row._model_labels if not lbl.isHidden()]
        assert texts == ["🧠 Qwen3.8-Flash-256k-62"]

    def test_chip_starting_when_port_closed(self, qapp, tmp_path, monkeypatch):
        v = self._view_with_watch(qapp, tmp_path, monkeypatch,
                                  ["llama-server.exe:8080"])
        v._on_metrics(dict(METRICS, processes={
            "llama-server.exe:8080": {"running": True, "pid": 1, "cpu": 0.0,
                                       "ram": 1024, "uptime": 5,
                                       "api_port": 8080, "api_port_open": False}}))
        chip = v._chip_widgets["llama-server.exe:8080"]
        assert chip.objectName() == "svcChipProbing"

    def test_chip_inactive_when_stopped(self, qapp, tmp_path, monkeypatch):
        v = self._view_with_watch(qapp, tmp_path, monkeypatch,
                                  ["llama-server.exe"])
        v._on_metrics(dict(METRICS, processes={
            "llama-server.exe": {"running": False}}))
        chip = v._chip_widgets["llama-server.exe"]
        assert chip.objectName() == "svcChipInactive"

    def test_chip_green_without_port(self, qapp, tmp_path, monkeypatch):
        """No port in the entry -> running alone is the green state."""
        v = self._view_with_watch(qapp, tmp_path, monkeypatch,
                                  ["ollama.exe"])
        v._on_metrics(dict(METRICS, processes={
            "ollama.exe": {"running": True, "pid": 7, "cpu": 1.0,
                            "ram": 1024, "uptime": 10}}))
        assert v._chip_widgets["ollama.exe"].objectName() == "svcChipRunning"

    def test_chips_hidden_when_host_offline(self, qapp, tmp_path, monkeypatch):
        v = self._view_with_watch(qapp, tmp_path, monkeypatch,
                                  ["llama-server.exe"])
        v._on_metrics(dict(METRICS, processes={
            "llama-server.exe": {"running": True, "pid": 1, "cpu": 0.0,
                                  "ram": 1, "uptime": 1}}))
        assert not v._chip_widgets["llama-server.exe"].isHidden()
        v._on_metrics_failed("Connection refused")
        assert v._chip_widgets["llama-server.exe"].isHidden()
        assert v.svc_panel.isHidden()

    def test_no_process_field_hides_services(self, qapp, tmp_path, monkeypatch):
        """Old host service (no processes map) -> chips hidden, no error."""
        v = self._view_with_watch(qapp, tmp_path, monkeypatch,
                                  ["llama-server.exe"])
        v._on_metrics(dict(METRICS))  # protocol 2, no "processes"
        assert v._chip_widgets["llama-server.exe"].isHidden()
        assert v.svc_panel.isHidden()

    def test_inference_badge_after_consecutive_high_gpu(self, qapp, tmp_path, monkeypatch):
        v = self._view_with_watch(qapp, tmp_path, monkeypatch,
                                  ["llama-server.exe:8080"])
        proc = {"llama-server.exe:8080": {"running": True, "pid": 1, "cpu": 1.0,
                "ram": 1024, "uptime": 1, "api_port": 8080, "api_port_open": True}}
        row = v._svc_row_widgets["llama-server.exe:8080"]
        v._on_metrics(dict(METRICS, gpu=90.0, processes=proc))
        assert row.live.isHidden()          # 1 sample: not yet
        v._on_metrics(dict(METRICS, gpu=90.0, processes=proc))
        assert not row.live.isHidden()      # 2 consecutive: inference active
        v._on_metrics(dict(METRICS, gpu=5.0, processes=proc))
        assert row.live.isHidden()          # low sample resets the counter

    def test_watch_list_edit_refreshes_header(self, qapp, tmp_path, monkeypatch):
        cfg = ConfigManager(config_path=str(tmp_path / "edit.json"))
        cfg.add_device("D", "AA:BB:CC:00:11:AA")
        dev_id = cfg.get_devices()[0]["id"]
        cfg.update_device(dev_id, ip="1.2.3.4", username="u", password="p")
        monkeypatch.setattr(DeviceDashboardView, "_poll_metrics", lambda self: None)
        v = DeviceDashboardView(cfg)
        v.set_device(dev_id)
        assert v._chip_widgets == {}
        # Watch list added while the dashboard is open -> header refresh picks it up
        cfg.set_device_watch_processes(dev_id, ["llama-server.exe"])
        v.refresh_device_header()
        assert "llama-server.exe" in v._chip_widgets
        v.cancel_workers()
