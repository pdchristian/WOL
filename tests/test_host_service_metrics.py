"""Tests for the WOL Host Service dashboard features (metrics + run_batch).

wol_host_service imports ctypes at module level but only touches
ctypes.windll inside functions, so importing is safe on Windows; on other
platforms the tests that need Windows-only behaviour are skipped.
"""

import os
import subprocess
import sys
from unittest import mock

import pytest

wol_host_service = pytest.importorskip(
    "wol_host_service", reason="Windows service module")


class TestCollectMetrics:
    def test_metrics_with_mocked_psutil_and_gpu(self, monkeypatch):
        class _VM:
            used = 8 * 1024**3
            total = 32 * 1024**3

        fake_psutil = mock.MagicMock()
        fake_psutil.cpu_percent.return_value = 42.0
        fake_psutil.cpu_count.return_value = 8
        fake_psutil.virtual_memory.return_value = _VM()
        fake_psutil.boot_time.return_value = 0
        monkeypatch.setitem(sys.modules, "psutil", fake_psutil)
        monkeypatch.setattr(
            wol_host_service, "_gpu_metrics_cached",
            lambda: {"gpu": 30.0, "vram_used": 1024, "vram_total": 4096,
                     "gpu_name": "FakeGPU"})

        metrics = wol_host_service.collect_metrics()
        assert metrics["status"] == "ok"
        assert metrics["protocol"] == wol_host_service.PROTOCOL_VERSION
        assert metrics["cpu"] == 42.0
        assert metrics["cpu_count"] == 8
        assert metrics["ram_used"] == 8 * 1024**3
        assert metrics["vram_total"] == 4096
        assert metrics["gpu_name"] == "FakeGPU"
        assert metrics["uptime"] >= 0

    def test_metrics_survive_psutil_failure(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "psutil", None)  # import fails
        monkeypatch.setattr(wol_host_service, "_gpu_metrics_cached",
                            lambda: {"gpu": None, "vram_used": None,
                                     "vram_total": None, "gpu_name": None})
        metrics = wol_host_service.collect_metrics()
        assert metrics["status"] == "ok"
        assert metrics["cpu"] is None
        assert metrics["hostname"] != ""

    def test_nvidia_query_parses_csv(self):
        completed = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout=b"25, 2048, 8192, NVIDIA GeForce RTX 4070\n")
        with mock.patch.object(wol_host_service.subprocess, "run",
                               return_value=completed):
            data = wol_host_service._query_nvidia_smi()
        assert data["gpu"] == 25.0
        assert data["vram_used"] == 2048 * 1024 * 1024
        assert data["vram_total"] == 8192 * 1024 * 1024
        assert "RTX 4070" in data["gpu_name"]

    def test_nvidia_query_multi_gpu_aggregates(self):
        completed = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout=b"10, 1000, 4000, A\n30, 3000, 8000, B\n")
        with mock.patch.object(wol_host_service.subprocess, "run",
                               return_value=completed):
            data = wol_host_service._query_nvidia_smi()
        assert data["gpu"] == 20.0
        assert data["vram_used"] == 4000 * 1024 * 1024
        assert data["vram_total"] == 12000 * 1024 * 1024

    def test_nvidia_query_missing_binary(self):
        with mock.patch.object(
                wol_host_service.subprocess, "run",
                side_effect=FileNotFoundError("nvidia-smi")):
            data = wol_host_service._query_nvidia_smi()
        assert data == {"gpu": None, "vram_used": None, "vram_total": None,
                        "gpu_name": None}

    def test_gpu_cache_reuses_sample(self, monkeypatch):
        calls = {"n": 0}

        def _fake_query():
            calls["n"] += 1
            return {"gpu": 1.0, "vram_used": 1, "vram_total": 2, "gpu_name": "X"}

        monkeypatch.setattr(wol_host_service, "_query_nvidia_smi", _fake_query)
        monkeypatch.setattr(wol_host_service, "_gpu_cache", (0.0, {}))
        wol_host_service._gpu_metrics_cached()
        wol_host_service._gpu_metrics_cached()
        assert calls["n"] == 1  # second call hits the cache


class TestBatchGating:
    def test_default_is_disabled(self, tmp_path, monkeypatch):
        monkeypatch.setattr(wol_host_service, "_CONFIG_FILE",
                            str(tmp_path / "service.json"))
        assert wol_host_service.is_batch_allowed() is False

    def test_enable_and_disable(self, tmp_path, monkeypatch):
        monkeypatch.setattr(wol_host_service, "_CONFIG_FILE",
                            str(tmp_path / "service.json"))
        assert wol_host_service.set_batch_allowed(True) is True
        assert wol_host_service.is_batch_allowed() is True
        wol_host_service.set_batch_allowed(False)
        assert wol_host_service.is_batch_allowed() is False


@pytest.mark.skipif(os.name != "nt", reason="cmd.exe required")
class TestRunBatchScript:
    def test_exit_code_and_output(self):
        result = wol_host_service.run_batch_script("@echo off\r\necho hello\r\n")
        assert result["status"] == "ok"
        assert result["exit_code"] == 0
        assert "hello" in result["stdout"]
        assert result["duration_ms"] >= 0

    def test_nonzero_exit_code(self):
        result = wol_host_service.run_batch_script("@echo off\r\nexit /b 3\r\n")
        assert result["status"] == "ok"
        assert result["exit_code"] == 3

    def test_timeout(self):
        result = wol_host_service.run_batch_script(
            "@echo off\r\nping -n 30 127.0.0.1 >nul\r\n", timeout=1)
        assert result["status"] == "error"
        assert "timed out" in result["message"]

    def test_empty_script_rejected(self):
        result = wol_host_service.run_batch_script("   ")
        assert result["status"] == "error"

    def test_too_long_script_rejected(self):
        result = wol_host_service.run_batch_script("x" * (
            wol_host_service.MAX_SCRIPT_CHARS + 1))
        assert result["status"] == "error"
        assert "too long" in result["message"]


class TestCommandDispatch:
    """_CommandHandler.handle routing for the new commands (mocked auth)."""

    class _Sock:
        def __init__(self, request: bytes):
            self._request = request
            self.sent = b""

        def recv(self, _size):
            data, self._request = self._request, b""
            return data

        def sendall(self, data):
            self.sent += data

    def _handle(self, request: bytes, **patches):
        import contextlib
        import json

        handler = wol_host_service._CommandHandler.__new__(
            wol_host_service._CommandHandler)
        handler.request = self._Sock(request)
        ctx = (mock.patch.multiple(wol_host_service, **patches)
               if patches else contextlib.nullcontext())
        with ctx:
            handler.handle()
        return json.loads(handler.request.sent.decode("utf-8").strip())

    def test_metrics_requires_auth(self):
        response = self._handle(
            b'{"command":"metrics","username":"u","password":"p"}\n',
            validate_credentials=lambda u, p: False,
            collect_metrics=lambda: {"status": "ok"},
        )
        assert response["status"] == "error"
        assert "Authentication failed" in response["message"]

    def test_metrics_ok(self):
        response = self._handle(
            b'{"command":"metrics","username":"u","password":"p"}\n',
            validate_credentials=lambda u, p: True,
            collect_metrics=lambda: {"status": "ok", "cpu": 1.0,
                                     "protocol": 2},
        )
        assert response["cpu"] == 1.0

    def test_run_batch_gated(self):
        response = self._handle(
            b'{"command":"run_batch","username":"u","password":"p","script":"echo"}\n',
            validate_credentials=lambda u, p: True,
            is_batch_allowed=lambda: False,
        )
        assert response["status"] == "error"
        assert "disabled" in response["message"]

    def test_run_batch_executes_when_allowed(self):
        response = self._handle(
            b'{"command":"run_batch","username":"u","password":"p","script":"echo hi"}\n',
            validate_credentials=lambda u, p: True,
            is_batch_allowed=lambda: True,
            run_batch_script=lambda script, timeout: {
                "status": "ok", "exit_code": 0, "stdout": "hi",
                "stderr": "", "duration_ms": 1, "truncated": False},
        )
        assert response["exit_code"] == 0

    def test_unknown_command(self):
        response = self._handle(b'{"command":"nuke"}\n')
        assert response["status"] == "error"
        assert "Unknown command" in response["message"]
