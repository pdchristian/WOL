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
                             watch=None):
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
