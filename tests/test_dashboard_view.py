"""Tests for the device dashboard view (metrics display + batch library)."""

import pytest

from wol_app.config import ConfigManager
from wol_app.translations import Translations

pytest.importorskip("PyQt6")

from PyQt6.QtCore import Qt  # noqa: E402
from PyQt6.QtWidgets import (  # noqa: E402
    QAbstractItemView,
    QApplication,
    QMessageBox,
)

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
        # New batches start at the product default of 10 s (not the old 120).
        assert batches[0]["timeout"] == 10
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

    def test_row_shows_model_throughput(self, qapp, tmp_path, monkeypatch):
        """Host v5 "model_metrics": the model line gains a t/s suffix."""
        v = self._view_with_watch(qapp, tmp_path, monkeypatch,
                                  ["llama-server.exe:8080"])
        v._on_metrics(dict(METRICS, processes={
            "llama-server.exe:8080": {
                "running": True, "pid": 4711, "cpu": 3.0,
                "ram": 5 * 1024**3, "uptime": 3600,
                "api_port": 8080, "api_port_open": True,
                "models": ["Qwen3.8-Flash-256k-62", "glm-4.7-air"],
                "model_metrics": {
                    "Qwen3.8-Flash-256k-62": {"prompt_tps": 261.15,
                                              "predicted_tps": 26.65}}}}))
        row = v._svc_row_widgets["llama-server.exe:8080"]
        texts = [lbl.text() for lbl in row._model_labels if not lbl.isHidden()]
        assert len(texts) == 2
        # Model with metrics: prompt/predicted t/s appended (2 decimals).
        qwen = next(t for t in texts if "Qwen3.8-Flash-256k-62" in t)
        assert "261.15" in qwen and "26.65" in qwen
        assert "t/s" in qwen
        # Model without metrics stays a plain model line.
        glm = next(t for t in texts if "glm-4.7-air" in t)
        assert "t/s" not in glm

    def test_row_no_throughput_without_metrics(self, qapp, tmp_path,
                                               monkeypatch):
        """Older hosts (v4) report no model_metrics -> plain model line."""
        v = self._view_with_watch(qapp, tmp_path, monkeypatch,
                                  ["llama-server.exe:8080"])
        v._on_metrics(dict(METRICS, processes={
            "llama-server.exe:8080": {
                "running": True, "pid": 4711, "cpu": 3.0,
                "ram": 5 * 1024**3, "uptime": 3600,
                "api_port": 8080, "api_port_open": True,
                "models": ["Qwen3.8-Flash-256k-62"]}}))
        row = v._svc_row_widgets["llama-server.exe:8080"]
        texts = [lbl.text() for lbl in row._model_labels if not lbl.isHidden()]
        assert texts == ["🧠 Qwen3.8-Flash-256k-62"]

    def test_model_tps_suffix_ignores_bad_values(self):
        """Non-numeric / non-finite / missing values never produce a suffix."""
        from wol_app.views.dashboard_view import _model_tps_suffix
        good = {"model_metrics": {"m": {"prompt_tps": 1.5,
                                        "predicted_tps": 2.5}}}
        assert _model_tps_suffix(good, "m") != ""
        assert _model_tps_suffix({}, "m") == ""
        assert _model_tps_suffix(good, "other") == ""
        assert _model_tps_suffix(
            {"model_metrics": {"m": {"prompt_tps": "x",
                                     "predicted_tps": 1}}}, "m") == ""
        assert _model_tps_suffix(
            {"model_metrics": {"m": {"prompt_tps": float("nan"),
                                     "predicted_tps": 1}}}, "m") == ""
        assert _model_tps_suffix(
            {"model_metrics": {"m": {"prompt_tps": 1}}}, "m") == ""

    def test_model_tps_suffix_total_tokens(self):
        """total_tokens renders as its own part; t/s part is independent."""
        from wol_app.views.dashboard_view import _model_tps_suffix
        both = {"model_metrics": {"m": {"prompt_tps": 1.5,
                                        "predicted_tps": 2.5,
                                        "total_tokens": 131072}}}
        suffix = _model_tps_suffix(both, "m")
        assert "1.50" in suffix and "2.50" in suffix
        # Thousands are grouped with a non-breaking space (131\u00a0072).
        assert "131\u00a0072" in suffix
        assert suffix.count(" · ") == 2  # " · " prefix + one join
        # Only total_tokens (host has nothing latched yet) -> total alone.
        only_total = {"model_metrics": {"m": {"total_tokens": 42}}}
        total_suffix = _model_tps_suffix(only_total, "m")
        assert "42" in total_suffix and "t/s" not in total_suffix
        # total_tokens 0 / non-numeric is dropped.
        assert _model_tps_suffix(
            {"model_metrics": {"m": {"total_tokens": 0}}}, "m") == ""
        assert _model_tps_suffix(
            {"model_metrics": {"m": {"total_tokens": "x"}}}, "m") == ""

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


class TestDeviceNavigation:
    """Prev/next arrows + position badge (x / n) in the dashboard header."""

    def _view_multi(self, qapp, tmp_path, monkeypatch, n=3):
        cfg = ConfigManager(config_path=str(tmp_path / "nav.json"))
        for i in range(n):
            cfg.add_device(f"Dev{i}", f"AA:BB:CC:00:11:{i:02X}")
        ids = [d["id"] for d in cfg.get_devices()]
        monkeypatch.setattr(DeviceDashboardView, "_poll_metrics", lambda self: None)
        v = DeviceDashboardView(cfg)
        return v, ids

    def test_single_device_hides_nav(self, view, tmp_config):
        _, dev_id = tmp_config
        view.set_device(dev_id)
        assert view.prev_btn.isHidden()
        assert view.next_btn.isHidden()
        assert view.pos_label.isHidden()

    def test_first_device_prev_disabled_next_enabled(self, qapp, tmp_path, monkeypatch):
        v, ids = self._view_multi(qapp, tmp_path, monkeypatch)
        v.set_device(ids[0])  # name sort: Dev0 first
        assert not v.prev_btn.isHidden()
        assert not v.next_btn.isHidden()
        assert not v.prev_btn.isEnabled()
        assert v.next_btn.isEnabled()
        assert v.pos_label.text() == Translations.tr(
            "modern.dashboard.position", index=1, total=3)

    def test_last_device_next_disabled(self, qapp, tmp_path, monkeypatch):
        v, ids = self._view_multi(qapp, tmp_path, monkeypatch)
        v.set_device(ids[-1])  # name sort: DevN last
        assert v.prev_btn.isEnabled()
        assert not v.next_btn.isEnabled()
        assert v.pos_label.text() == Translations.tr(
            "modern.dashboard.position", index=3, total=3)

    def test_neighbour_device_id_clamps_at_borders(self, qapp, tmp_path, monkeypatch):
        v, ids = self._view_multi(qapp, tmp_path, monkeypatch)
        v.set_device(ids[0])
        assert v.neighbour_device_id(-1) is None
        assert v.neighbour_device_id(1) == ids[1]
        v.set_device(ids[-1])
        assert v.neighbour_device_id(1) is None
        assert v.neighbour_device_id(-1) == ids[-2]

    def test_nav_follows_sort_key(self, qapp, tmp_path, monkeypatch):
        """Ordering follows the persisted devices-screen sort key (IP)."""
        cfg = ConfigManager(config_path=str(tmp_path / "navip.json"))
        cfg.add_device("A", "AA:BB:CC:00:00:01")
        cfg.add_device("B", "AA:BB:CC:00:00:02")
        ids = [d["id"] for d in cfg.get_devices()]
        cfg.update_device(ids[0], ip="192.168.1.20")
        cfg.update_device(ids[1], ip="192.168.1.3")
        cfg.set_devices_sort_key("ip")
        monkeypatch.setattr(DeviceDashboardView, "_poll_metrics", lambda self: None)
        v = DeviceDashboardView(cfg)
        v.set_device(ids[1])  # .3 sorts before .20 → first
        assert v.neighbour_device_id(1) == ids[0]
        assert v.neighbour_device_id(-1) is None
        v.cancel_workers()

    def test_offline_devices_are_skipped(self, qapp, tmp_path, monkeypatch):
        """Prev/next jumps over devices whose last ping said "offline"."""
        v, ids = self._view_multi(qapp, tmp_path, monkeypatch)
        v.set_nav_statuses({ids[0]: "online", ids[1]: "offline",
                            ids[2]: "online"})
        v.set_device(ids[0])
        assert v.neighbour_device_id(1) == ids[2]  # Dev1 (offline) skipped
        v.set_device(ids[2])
        assert v.neighbour_device_id(-1) == ids[0]
        # Badge/limits count only reachable devices: 1/2 and 2/2.
        assert v.pos_label.text() == Translations.tr(
            "modern.dashboard.position", index=2, total=2)
        assert not v.next_btn.isEnabled()

    def test_offline_current_device_stays_in_sequence(self, qapp, tmp_path,
                                                      monkeypatch):
        """An opened device that went offline keeps its place (badge/limits)."""
        v, ids = self._view_multi(qapp, tmp_path, monkeypatch, n=2)
        v.set_nav_statuses({ids[0]: "online", ids[1]: "offline"})
        v.set_device(ids[1])  # opened while offline
        assert v.pos_label.text() == Translations.tr(
            "modern.dashboard.position", index=2, total=2)
        assert v.neighbour_device_id(-1) == ids[0]
        assert v.neighbour_device_id(1) is None

    def test_all_offline_except_current_hides_nav(self, qapp, tmp_path,
                                                  monkeypatch):
        v, ids = self._view_multi(qapp, tmp_path, monkeypatch)
        v.set_nav_statuses({ids[0]: "online", ids[1]: "offline",
                            ids[2]: "offline"})
        v.set_device(ids[0])
        assert v.prev_btn.isHidden()
        assert v.next_btn.isHidden()
        assert v.pos_label.isHidden()

    def test_live_metrics_update_nav_statuses(self, qapp, tmp_path, monkeypatch):
        """A device going offline/online in the dashboard updates the cache."""
        v, ids = self._view_multi(qapp, tmp_path, monkeypatch)
        v.set_nav_statuses({i: "online" for i in ids})
        v.set_device(ids[1])
        v._on_metrics(dict(METRICS))
        assert v.neighbour_device_id(1) == ids[2]
        v._on_metrics_failed("Connection timed out")  # → offline badge
        assert v.neighbour_device_id(1) == ids[2]
        v.set_device(ids[0])
        # Dev1 is now known offline → next from Dev0 skips it.
        assert v.neighbour_device_id(1) == ids[2]


class _FakeCopyDialog:
    """Stand-in for BatchCopyDialog with a scripted selection/exec result."""

    class DialogCode:
        Accepted = 1
        Rejected = 0

    def __init__(self, source_device, batches, targets, statuses=None,
                 parent=None):
        self.source = source_device
        self.batches = batches
        self.targets = targets
        self.accept = True
        self.target_index = 0
        self.target_indexes = None  # None = only target_index, else list
        self.pick = None      # None = all batches, else set of names
        self.allow = False

    def exec(self):
        return self.DialogCode.Accepted if self.accept else self.DialogCode.Rejected

    @property
    def target_device_ids(self):
        if self.target_indexes is None:
            return [self.targets[self.target_index].get("id")]
        return [self.targets[i].get("id") for i in self.target_indexes]

    def selected_batches(self):
        if self.pick is None:
            return [dict(b) for b in self.batches]
        return [dict(b) for b in self.batches if b.get("name") in self.pick]

    def allow_batch_enabled(self):
        return self.allow


def _patch_copy_dialog(monkeypatch, configure=None):
    """Replace the dialog class in dashboard_view; returns an instances list."""
    created: list[_FakeCopyDialog] = []

    def factory(*args, **kwargs):
        dlg = _FakeCopyDialog(*args, **kwargs)
        if configure:
            configure(dlg)
        created.append(dlg)
        return dlg

    factory.DialogCode = _FakeCopyDialog.DialogCode
    monkeypatch.setattr("wol_app.views.dashboard_view.BatchCopyDialog", factory)
    return created


class TestBatchCopy:
    """Copying stored batches from the open device to another device."""

    def _copy_config(self, qapp, tmp_path, monkeypatch, target_batches=None):
        cfg = ConfigManager(config_path=str(tmp_path / "copy.json"))
        cfg.add_device("Src", "AA:BB:CC:00:22:01")
        cfg.add_device("Tgt", "AA:BB:CC:00:22:02")
        ids = {d["name"]: d["id"] for d in cfg.get_devices()}
        cfg.set_device_batches(ids["Src"], [
            {"id": "s1", "name": "A", "script": "echo a", "timeout": 10},
            {"id": "s2", "name": "B", "script": "echo b", "timeout": 20},
        ])
        if target_batches:
            cfg.set_device_batches(ids["Tgt"], target_batches)
        monkeypatch.setattr(DeviceDashboardView, "_poll_metrics",
                            lambda self: None)
        v = DeviceDashboardView(cfg)
        return v, cfg, ids["Src"], ids["Tgt"]

    def _confirm(self, monkeypatch, answer):
        monkeypatch.setattr(
            "wol_app.views.dashboard_view.QMessageBox.question",
            staticmethod(lambda *a, **k: answer))

    def test_copy_btn_disabled_without_other_devices(self, view, tmp_config):
        _, dev_id = tmp_config  # single-device config
        view.set_device(dev_id)
        assert not view.copy_btn.isEnabled()

    def test_copy_btn_disabled_without_batches(self, qapp, tmp_path, monkeypatch):
        v, cfg, src_id, _ = self._copy_config(qapp, tmp_path, monkeypatch)
        cfg.set_device_batches(src_id, [])
        v.set_device(src_id)
        assert not v.copy_btn.isEnabled()
        v.cancel_workers()

    def test_copy_btn_enabled_with_batches_and_target(self, qapp, tmp_path,
                                                      monkeypatch):
        v, _, src_id, _ = self._copy_config(qapp, tmp_path, monkeypatch)
        v.set_device(src_id)
        assert v.copy_btn.isEnabled()
        v.cancel_workers()

    def test_full_copy_merges_into_target_list(self, qapp, tmp_path, monkeypatch):
        """Different names are appended — existing batches are kept."""
        v, cfg, src_id, tgt_id = self._copy_config(
            qapp, tmp_path, monkeypatch,
            target_batches=[{"id": "t1", "name": "Old", "script": "x",
                             "timeout": 5}])
        self._confirm(monkeypatch, QMessageBox.StandardButton.Yes)
        _patch_copy_dialog(monkeypatch)
        v.set_device(src_id)
        v._copy_batches()
        tgt = ConfigManager.get_device_batches(cfg.get_device_by_id(tgt_id))
        assert [b["name"] for b in tgt] == ["Old", "A", "B"]  # "Old" kept
        # Fresh ids: no collision with the source batches
        assert all(b["id"] not in ("s1", "s2") for b in tgt)
        # Source untouched
        src = ConfigManager.get_device_batches(cfg.get_device_by_id(src_id))
        assert [b["id"] for b in src] == ["s1", "s2"]
        v.cancel_workers()

    def test_same_name_overwrites_only_that_batch(self, qapp, tmp_path,
                                                  monkeypatch):
        """Example 2: copying C+D onto A,B,C keeps A and B, replaces C, adds D."""
        v, cfg, src_id, tgt_id = self._copy_config(qapp, tmp_path, monkeypatch)
        cfg.set_device_batches(src_id, [
            {"id": "s1", "name": "C", "script": "echo new-c", "timeout": 30},
            {"id": "s2", "name": "D", "script": "echo d", "timeout": 10},
        ])
        cfg.set_device_batches(tgt_id, [
            {"id": "t1", "name": "A", "script": "echo a", "timeout": 10},
            {"id": "t2", "name": "B", "script": "echo b", "timeout": 10},
            {"id": "t3", "name": "C", "script": "echo old-c", "timeout": 10},
        ])
        self._confirm(monkeypatch, QMessageBox.StandardButton.Yes)
        _patch_copy_dialog(monkeypatch)
        v.set_device(src_id)
        v._copy_batches()
        tgt = ConfigManager.get_device_batches(cfg.get_device_by_id(tgt_id))
        assert [b["name"] for b in tgt] == ["A", "B", "C", "D"]
        by_name = {b["name"]: b for b in tgt}
        assert by_name["C"]["script"] == "echo new-c"  # C overwritten
        assert by_name["A"]["script"] == "echo a"      # A untouched
        assert by_name["B"]["script"] == "echo b"      # B untouched
        # The replaced batch keeps its target id (stable reference)
        assert by_name["C"]["id"] == "t3"
        v.cancel_workers()

    def test_partial_selection_copies_only_checked(self, qapp, tmp_path,
                                                   monkeypatch):
        v, cfg, src_id, tgt_id = self._copy_config(qapp, tmp_path, monkeypatch)
        _patch_copy_dialog(monkeypatch,
                           configure=lambda d: setattr(d, "pick", {"B"}))
        v.set_device(src_id)
        v._copy_batches()
        tgt = ConfigManager.get_device_batches(cfg.get_device_by_id(tgt_id))
        assert [b["name"] for b in tgt] == ["B"]
        v.cancel_workers()

    def test_cancel_keeps_target_untouched(self, qapp, tmp_path, monkeypatch):
        v, cfg, src_id, tgt_id = self._copy_config(
            qapp, tmp_path, monkeypatch,
            target_batches=[{"id": "t1", "name": "Old", "script": "x",
                             "timeout": 5}])
        _patch_copy_dialog(monkeypatch,
                           configure=lambda d: setattr(d, "accept", False))
        v.set_device(src_id)
        v._copy_batches()
        tgt = ConfigManager.get_device_batches(cfg.get_device_by_id(tgt_id))
        assert [b["id"] for b in tgt] == ["t1"]
        v.cancel_workers()

    def test_replace_confirm_declined_aborts(self, qapp, tmp_path, monkeypatch):
        v, cfg, src_id, tgt_id = self._copy_config(
            qapp, tmp_path, monkeypatch,
            target_batches=[{"id": "t1", "name": "A", "script": "x",
                             "timeout": 5}])  # name collides with source "A"
        self._confirm(monkeypatch, QMessageBox.StandardButton.No)
        _patch_copy_dialog(monkeypatch)
        v.set_device(src_id)
        v._copy_batches()
        tgt = ConfigManager.get_device_batches(cfg.get_device_by_id(tgt_id))
        assert [b["id"] for b in tgt] == ["t1"]
        v.cancel_workers()

    def test_allow_batch_checkbox_sets_target_opt_in(self, qapp, tmp_path,
                                                     monkeypatch):
        v, cfg, src_id, tgt_id = self._copy_config(qapp, tmp_path, monkeypatch)
        _patch_copy_dialog(monkeypatch,
                           configure=lambda d: setattr(d, "allow", True))
        v.set_device(src_id)
        v._copy_batches()
        assert cfg.get_device_by_id(tgt_id).get("allow_batch") is True
        # Source opt-in untouched
        assert not cfg.get_device_by_id(src_id).get("allow_batch")
        v.cancel_workers()

    def test_no_allow_batch_leaves_target_opt_in_off(self, qapp, tmp_path,
                                                     monkeypatch):
        v, cfg, src_id, tgt_id = self._copy_config(qapp, tmp_path, monkeypatch)
        _patch_copy_dialog(monkeypatch)
        v.set_device(src_id)
        v._copy_batches()
        assert not cfg.get_device_by_id(tgt_id).get("allow_batch")
        v.cancel_workers()

    def test_oversized_source_hits_limit_message(self, qapp, tmp_path,
                                                 monkeypatch):
        """Hand-edited source with > MAX batches: target stays untouched."""
        v, cfg, src_id, tgt_id = self._copy_config(qapp, tmp_path, monkeypatch)
        dev = cfg.get_device_by_id(src_id)
        dev["batches"] = [{"id": f"s{i}", "name": f"N{i}", "script": "x",
                           "timeout": 10}
                          for i in range(51)]
        cfg.save()
        _patch_copy_dialog(monkeypatch)
        v.set_device(src_id)
        v._copy_batches()
        assert ConfigManager.get_device_batches(cfg.get_device_by_id(tgt_id)) == []
        assert Translations.tr("modern.dashboard.batch.copy.limit_target",
                               name="Tgt", limit=50) in v.console_edit.toPlainText()
        v.cancel_workers()

    def test_copy_to_multiple_targets_at_once(self, qapp, tmp_path,
                                              monkeypatch):
        """Both checked targets receive the batches independently."""
        cfg = ConfigManager(config_path=str(tmp_path / "multi.json"))
        cfg.add_device("Src", "AA:BB:CC:00:22:11")
        cfg.add_device("Tgt1", "AA:BB:CC:00:22:12")
        cfg.add_device("Tgt2", "AA:BB:CC:00:22:13")
        ids = {d["name"]: d["id"] for d in cfg.get_devices()}
        cfg.set_device_batches(ids["Src"], [
            {"id": "s1", "name": "A", "script": "echo a", "timeout": 10}])
        cfg.set_device_batches(ids["Tgt2"], [
            {"id": "t9", "name": "Keep", "script": "x", "timeout": 5}])
        monkeypatch.setattr(DeviceDashboardView, "_poll_metrics",
                            lambda self: None)
        v = DeviceDashboardView(cfg)
        _patch_copy_dialog(monkeypatch,
                           configure=lambda d: setattr(
                               d, "target_indexes", [0, 1]))
        v.set_device(ids["Src"])
        v._copy_batches()
        for name in ("Tgt1", "Tgt2"):
            tgt = ConfigManager.get_device_batches(cfg.get_device_by_id(ids[name]))
            assert "A" in [b["name"] for b in tgt]
        # Tgt2's untouched batch stays
        tgt2 = ConfigManager.get_device_batches(cfg.get_device_by_id(ids["Tgt2"]))
        assert "Keep" in [b["name"] for b in tgt2]
        v.cancel_workers()

    def test_copy_logs_done_message(self, qapp, tmp_path, monkeypatch):
        v, cfg, src_id, tgt_id = self._copy_config(qapp, tmp_path, monkeypatch)
        _patch_copy_dialog(monkeypatch)
        v.set_device(src_id)
        v._copy_batches()
        done = Translations.tr("modern.dashboard.batch.copy.done",
                               name="Tgt", count=2)
        assert done in v.console_edit.toPlainText()
        assert v.status_line.text() == done
        v.cancel_workers()


class TestBatchCopyDialog:
    """The real BatchCopyDialog widget (target list, warnings, selection)."""

    def _make(self, qapp, tmp_path):
        from wol_app.views.batch_copy_dialog import BatchCopyDialog
        cfg = ConfigManager(config_path=str(tmp_path / "dlg.json"))
        cfg.add_device("Src", "AA:BB:CC:00:33:01")
        cfg.add_device("Tgt", "AA:BB:CC:00:33:02")
        cfg.add_device("Empty", "AA:BB:CC:00:33:03")
        ids = {d["name"]: d["id"] for d in cfg.get_devices()}
        cfg.set_device_batches(ids["Tgt"], [
            {"id": "t1", "name": "A", "script": "x", "timeout": 5},
            {"id": "t2", "name": "Old", "script": "x", "timeout": 5}])
        cfg.set_device_allow_batch(ids["Tgt"], True)
        source = cfg.get_device_by_id(ids["Src"])
        targets = [d for d in cfg.get_devices() if d["id"] != ids["Src"]]
        batches = ConfigManager.get_device_batches(source) or [
            {"id": "s1", "name": "A", "script": "echo a\necho b", "timeout": 10},
            {"id": "s2", "name": "B", "script": "echo b", "timeout": 20},
        ]
        return BatchCopyDialog(source, batches, targets, None), cfg, ids

    def test_target_list_lists_all_other_devices(self, qapp, tmp_path):
        dlg, _, ids = self._make(qapp, tmp_path)
        rows = {r.device.get("id"): r for r in dlg._target_rows}
        assert set(rows) == {ids["Tgt"], ids["Empty"]}
        dlg.close()

    def test_no_target_preselected_and_copy_disabled(self, qapp, tmp_path):
        """The dialog opens with nothing checked so nothing is copied
        accidentally; the copy button stays disabled until a target is set."""
        dlg, _, _ = self._make(qapp, tmp_path)
        assert dlg.target_device_ids == []
        assert not dlg.copy_btn.isEnabled()
        assert dlg.selected_count() == 2  # batches preselected, targets not
        dlg.close()

    def test_multiple_targets_can_be_checked(self, qapp, tmp_path):
        dlg, _, ids = self._make(qapp, tmp_path)
        for row in dlg._target_rows:
            row.check.setChecked(True)
        assert set(dlg.target_device_ids) == {ids["Tgt"], ids["Empty"]}
        assert dlg.copy_btn.isEnabled()
        # Unchecking again disables the button (no target left).
        for row in dlg._target_rows:
            row.check.setChecked(False)
        assert dlg.target_device_ids == []
        assert not dlg.copy_btn.isEnabled()
        dlg.close()

    def test_replace_warning_only_for_checked_targets_with_batches(
            self, qapp, tmp_path):
        dlg, _, ids = self._make(qapp, tmp_path)
        rows = {r.device.get("id"): r for r in dlg._target_rows}
        # No target checked → no warning
        assert not dlg.warn_label.isVisibleTo(dlg)
        rows[ids["Empty"]].check.setChecked(True)
        assert not dlg.warn_label.isVisibleTo(dlg)
        # "A" collides with a target batch, "B" does not → warning counts 1
        rows[ids["Tgt"]].check.setChecked(True)
        assert dlg.warn_label.isVisibleTo(dlg)
        assert "1" in dlg.warn_label.text()
        # Unchecking the colliding batch makes the warning disappear
        dlg._rows[0].check.setChecked(False)  # row 0 = "A"
        assert not dlg.warn_label.isVisibleTo(dlg)
        dlg._rows[0].check.setChecked(True)
        assert dlg.warn_label.isVisibleTo(dlg)
        rows[ids["Tgt"]].check.setChecked(False)
        assert not dlg.warn_label.isVisibleTo(dlg)
        dlg.close()

    def test_selection_defaults_to_all_and_updates_count(self, qapp, tmp_path):
        dlg, _, _ = self._make(qapp, tmp_path)
        # A target has to be checked before copying is possible at all.
        dlg._target_rows[0].check.setChecked(True)
        assert dlg.selected_count() == 2
        assert dlg.copy_btn.isEnabled()
        dlg._rows[0].check.setChecked(False)
        assert dlg.selected_count() == 1
        assert Translations.tr("modern.dashboard.batch.copy.action",
                               count=1) == dlg.copy_btn.text()
        for row in dlg._rows:
            row.check.setChecked(False)
        assert dlg.selected_count() == 0
        assert not dlg.copy_btn.isEnabled()
        dlg.close()

    def test_select_all_toggles_every_row(self, qapp, tmp_path):
        dlg, _, _ = self._make(qapp, tmp_path)
        dlg.all_check.setChecked(False)  # clicked-equivalent via setChecked? no:
        # setChecked does not emit clicked; call the handler directly:
        dlg._on_all_clicked(False)
        assert dlg.selected_count() == 0
        dlg._on_all_clicked(True)
        assert dlg.selected_count() == 2
        dlg.close()

    def test_selected_batches_are_copies_in_source_order(self, qapp, tmp_path):
        dlg, _, _ = self._make(qapp, tmp_path)
        sel = dlg.selected_batches()
        assert [b["name"] for b in sel] == ["A", "B"]
        sel[0]["name"] = "mutated"
        assert dlg._rows[0].batch["name"] == "A"  # original untouched
        dlg.close()


class TestBatchReorder:
    """Drag & drop reordering of the batch list (config write-back).

    A real mouse drag cannot be synthesised offscreen, so the tests drive
    the same code path the widget uses: the view's drag hooks around the
    (source, target) pair that BatchListWidget.dropEvent() reports
    (drop indicator index against the list BEFORE the source row is
    removed — Qt's moveRow convention). The view then re-syncs the list
    through a singleShot _load_batches, which processEvents() runs.
    """

    def _view_with_batches(self, qapp, tmp_path, monkeypatch, names):
        cfg = ConfigManager(config_path=str(tmp_path / "reorder.json"))
        cfg.add_device("WS", "AA:BB:CC:00:44:01")
        dev_id = cfg.get_devices()[0]["id"]
        cfg.set_device_batches(dev_id, [
            {"id": f"b{i}", "name": n, "script": f"echo {n}", "timeout": 10}
            for i, n in enumerate(names)])
        monkeypatch.setattr(DeviceDashboardView, "_poll_metrics",
                            lambda self: None)
        v = DeviceDashboardView(cfg)
        v.set_device(dev_id)
        return v, cfg, dev_id

    def _move_row(self, v, source, dest_final):
        """Simulate one InternalMove drop exactly like the widget does.

        dropEvent reports the drop indicator's insertion index against the
        list BEFORE the source row is removed, so the final visual position
        needs +1 when moving downwards. processEvents() then runs the
        singleShot _load_batches that re-syncs the list with the config.
        """
        v._begin_batch_drag()
        target = dest_final + 1 if dest_final > source else dest_final
        v._record_batch_move(source, target)
        v._commit_batch_reorder()
        v._end_batch_drag()
        QApplication.processEvents()

    def _names(self, cfg, dev_id):
        return [b["name"] for b in
                ConfigManager.get_device_batches(cfg.get_device_by_id(dev_id))]

    def test_list_is_configured_for_internal_move(self, view, tmp_config):
        _, dev_id = tmp_config
        view.set_device(dev_id)
        assert view.batch_list.dragDropMode() == \
            QAbstractItemView.DragDropMode.InternalMove
        # Copy drops would duplicate batch ids — must be MoveAction.
        assert view.batch_list.defaultDropAction() == Qt.DropAction.MoveAction
        assert not view.batch_list.dragDropOverwriteMode()

    def test_record_batch_move_needs_active_drag(self, qapp, tmp_path,
                                                 monkeypatch):
        # _record_batch_move only arms while _begin_batch_drag ran (a
        # stray drop outside a drag must never touch the config).
        v, cfg, dev_id = self._view_with_batches(qapp, tmp_path, monkeypatch,
                                                 ["One", "Two", "Three"])
        v._record_batch_move(0, 2)
        v._commit_batch_reorder()
        assert self._names(cfg, dev_id) == ["One", "Two", "Three"]
        v.cancel_workers()

    def test_move_row_persists_new_order(self, qapp, tmp_path, monkeypatch):
        v, cfg, dev_id = self._view_with_batches(
            qapp, tmp_path, monkeypatch, ["One", "Two", "Three"])
        self._move_row(v, 0, 2)  # first batch dropped after the last
        assert self._names(cfg, dev_id) == ["Two", "Three", "One"]
        assert [v.batch_list.item(i).text()
                for i in range(v.batch_list.count())] == \
            ["Two", "Three", "One"]
        v.cancel_workers()

    def test_move_middle_to_top_persists(self, qapp, tmp_path, monkeypatch):
        v, cfg, dev_id = self._view_with_batches(
            qapp, tmp_path, monkeypatch, ["A", "B", "C", "D"])
        self._move_row(v, 2, 0)
        assert self._names(cfg, dev_id) == ["C", "A", "B", "D"]
        v.cancel_workers()

    def test_editor_follows_moved_selection(self, qapp, tmp_path, monkeypatch):
        v, _, _ = self._view_with_batches(qapp, tmp_path, monkeypatch,
                                          ["One", "Two", "Three"])
        v.batch_list.setCurrentRow(0)
        assert v.script_edit.toPlainText() == "echo One"
        self._move_row(v, 0, 2)
        # The selection travels with the batch (now row 2) and the editor
        # keeps showing the moved batch's script across the re-sync.
        assert v.batch_list.currentRow() == 2
        assert v._batch_active == 2
        assert v.script_edit.toPlainText() == "echo One"
        v.cancel_workers()

    def test_title_stays_paired_with_script_after_reorder(
            self, qapp, tmp_path, monkeypatch):
        # Regression: reordering must move name AND script as one unit —
        # selecting any visible row has to show exactly that batch's script.
        v, cfg, dev_id = self._view_with_batches(qapp, tmp_path, monkeypatch,
                                                 ["One", "Two", "Three"])
        self._move_row(v, 0, 2)
        names = self._names(cfg, dev_id)
        assert names == ["Two", "Three", "One"]
        # Visible list matches the persisted order...
        assert [v.batch_list.item(i).text()
                for i in range(v.batch_list.count())] == names
        # ...and every row's editor shows its own script.
        for row, name in enumerate(names):
            v.batch_list.setCurrentRow(row)
            assert v.script_edit.toPlainText() == f"echo {name}"
        v.cancel_workers()

    def test_drop_in_place_changes_nothing(self, qapp, tmp_path, monkeypatch):
        v, cfg, dev_id = self._view_with_batches(qapp, tmp_path, monkeypatch,
                                                 ["One", "Two", "Three"])
        self._move_row(v, 0, 0)  # no-op move
        assert self._names(cfg, dev_id) == ["One", "Two", "Three"]
        v.cancel_workers()

    def test_stale_source_resyncs_without_write(self, qapp, tmp_path,
                                                monkeypatch):
        # Simulate a config reload during the drag: the recorded source row
        # is out of range -> nothing is written, the list re-syncs instead.
        v, cfg, dev_id = self._view_with_batches(qapp, tmp_path, monkeypatch,
                                                 ["One", "Two", "Three"])
        v._apply_batch_move(7, 0)
        QApplication.processEvents()
        assert self._names(cfg, dev_id) == ["One", "Two", "Three"]
        assert v.batch_list.count() == 3
        v.cancel_workers()

    def test_pending_editor_edits_committed_before_drag(self, qapp, tmp_path,
                                                        monkeypatch):
        v, cfg, dev_id = self._view_with_batches(qapp, tmp_path, monkeypatch,
                                                 ["One", "Two"])
        v.batch_list.setCurrentRow(0)
        v.name_edit.setText("Renamed")
        self._move_row(v, 0, 1)
        assert self._names(cfg, dev_id) == ["Two", "Renamed"]
        v.cancel_workers()

    def test_second_reorder_after_resync(self, qapp, tmp_path, monkeypatch):
        v, cfg, dev_id = self._view_with_batches(
            qapp, tmp_path, monkeypatch, ["One", "Two", "Three"])
        self._move_row(v, 0, 2)
        v._load_batches()  # e.g. device switch / retranslate
        # A second reorder maps onto the fresh config order again:
        self._move_row(v, 2, 0)
        assert self._names(cfg, dev_id) == ["One", "Two", "Three"]
        v.cancel_workers()

    def test_grip_hidden_without_hover(self, qapp, tmp_path, monkeypatch):
        # The 6-dot handle only appears on the row under the mouse, so a
        # freshly loaded list carries no icons at all.
        v, _, _ = self._view_with_batches(qapp, tmp_path, monkeypatch,
                                          ["One", "Two", "Three"])
        for i in range(v.batch_list.count()):
            assert v.batch_list.item(i).icon().isNull()
        v.cancel_workers()

    def test_grip_shown_only_on_hovered_row(self, qapp, tmp_path,
                                            monkeypatch):
        # _set_hover_row is what the viewport MouseMove/Leave filter calls
        # with the row under the pointer (-1 over empty space or on leave) —
        # driving it directly simulates a hover move offscreen.
        v, _, _ = self._view_with_batches(qapp, tmp_path, monkeypatch,
                                          ["One", "Two", "Three"])
        lst = v.batch_list
        lst._set_hover_row(1)
        assert not lst.item(1).icon().isNull()
        assert lst.item(0).icon().isNull() and lst.item(2).icon().isNull()
        # Moving to another row clears the previous one.
        lst._set_hover_row(0)
        assert not lst.item(0).icon().isNull()
        assert lst.item(1).icon().isNull()
        # Pointer over the empty area below the rows (or leaving the list):
        # itemAt() returns None → row -1 → every grip disappears.
        lst._set_hover_row(-1)
        for i in range(lst.count()):
            assert lst.item(i).icon().isNull()
        v.cancel_workers()

    def test_grip_state_reset_after_reorder(self, qapp, tmp_path,
                                            monkeypatch):
        v, _, _ = self._view_with_batches(qapp, tmp_path, monkeypatch,
                                          ["One", "Two", "Three"])
        v.batch_list._set_hover_row(0)
        assert not v.batch_list.item(0).icon().isNull()
        self._move_row(v, 0, 2)
        # The post-drag sync (startDrag's finally) clears every grip;
        # offscreen no row is hovered.
        v.batch_list.sync_hover_after_move()
        for i in range(v.batch_list.count()):
            assert v.batch_list.item(i).icon().isNull()
        v.cancel_workers()
