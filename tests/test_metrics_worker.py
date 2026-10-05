"""Tests for the dashboard background workers (metrics polling).

The QThread plumbing is exercised by the view tests; here the worker
objects run() directly on the calling thread (like the StatusWorker tests
in test_devices_view do) so no event loop is needed.
"""

import os
from unittest import mock

os.environ.setdefault("WOL_HEADLESS", "1")

import pytest

pytest.importorskip("PyQt6")

from wol_app.metrics_worker import InferenceSweepWorker  # noqa: E402


def _device(device_id: str, **extra) -> dict:
    base = {"id": device_id, "ip": f"10.0.0.{ord(device_id[-1]) % 100}",
            "username": "u", "password": "p",
            "watch": ["llama-server.exe:8080"]}
    base.update(extra)
    return base


class TestInferenceSweepWorker:
    def test_empty_device_list_emits_empty_result(self):
        worker = InferenceSweepWorker([])
        results = []
        worker.finished.connect(results.append)
        worker.run()
        assert results == [[]]

    def test_collects_metrics_response_per_device(self, monkeypatch):
        responses = {
            "10.0.0.49": (True, {"protocol": 9, "processes": {}}),
            "10.0.0.50": (False, "auth failed"),
        }
        monkeypatch.setattr(
            "wol_app.metrics_worker.get_metrics",
            lambda ip, *_a, **_k: responses[ip])
        worker = InferenceSweepWorker([_device("d1"), _device("d2")])
        results = []
        worker.finished.connect(results.append)
        worker.run()
        assert len(results) == 1
        by_id = dict(results[0])
        assert by_id["d1"] == {"protocol": 9, "processes": {}}
        assert by_id["d2"] is None  # failed request -> None verdict

    def test_watch_list_is_forwarded(self, monkeypatch):
        seen = {}

        def fake_get_metrics(ip, user, pw, timeout=5.0, sock_sink=None,
                             watch=None, api_key=""):
            seen["watch"] = watch
            return True, {"protocol": 9}

        monkeypatch.setattr(
            "wol_app.metrics_worker.get_metrics", fake_get_metrics)
        worker = InferenceSweepWorker(
            [_device("d1", watch=["a.exe:1", ":8081"])])
        worker.run()
        assert seen["watch"] == ["a.exe:1", ":8081"]

    def test_cancel_suppresses_the_result(self, monkeypatch):
        monkeypatch.setattr(
            "wol_app.metrics_worker.get_metrics",
            lambda *a, **k: (True, {"protocol": 9}))
        worker = InferenceSweepWorker([_device("d1")])
        results = []
        worker.finished.connect(results.append)
        worker.cancel()
        worker.run()
        # Cancelled before run: the early-out emits [] (nothing to apply).
        assert results in ([], [[]])

    def test_transport_exception_becomes_none(self, monkeypatch):
        def boom(*_a, **_k):
            raise OSError("connection refused")

        monkeypatch.setattr("wol_app.metrics_worker.get_metrics", boom)
        worker = InferenceSweepWorker([_device("d1")])
        results = []
        worker.finished.connect(results.append)
        worker.run()
        assert results == [[("d1", None)]]

    def test_api_key_is_forwarded(self, monkeypatch):
        """v10: the device's dashboard key reaches the metrics request."""
        seen = {}

        def fake_get_metrics(ip, user, pw, timeout=5.0, sock_sink=None,
                             watch=None, api_key=""):
            seen["api_key"] = api_key
            return True, {"protocol": 10}

        monkeypatch.setattr("wol_app.metrics_worker.get_metrics",
                            fake_get_metrics)
        worker = InferenceSweepWorker([_device("d1", api_key="dummy")])
        worker.run()
        assert seen["api_key"] == "dummy"

    def test_device_without_key_sends_empty_string(self, monkeypatch):
        seen = {}

        def fake_get_metrics(ip, user, pw, timeout=5.0, sock_sink=None,
                             watch=None, api_key=""):
            seen["api_key"] = api_key
            return True, {"protocol": 10}

        monkeypatch.setattr("wol_app.metrics_worker.get_metrics",
                            fake_get_metrics)
        worker = InferenceSweepWorker([_device("d1")])
        worker.run()
        assert seen["api_key"] == ""


class TestMetricsWorker:
    def test_api_key_reaches_the_client(self, monkeypatch):
        from wol_app.metrics_worker import MetricsWorker

        seen = {}

        def fake_get_metrics(ip, user, pw, timeout=5.0, sock_sink=None,
                             watch=None, api_key=""):
            seen["api_key"] = api_key
            return True, {"protocol": 10, "cpu": 1.0}

        monkeypatch.setattr("wol_app.metrics_worker.get_metrics",
                            fake_get_metrics)
        worker = MetricsWorker("10.0.0.1", "u", "p",
                               watch=["strata:8080"], api_key="dummy")
        got = []
        worker.metrics_ready.connect(got.append)
        worker.run()
        assert seen["api_key"] == "dummy"
        assert got and got[0]["cpu"] == 1.0
