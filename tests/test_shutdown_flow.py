"""Regression tests for the remote-shutdown subprocess calls.

Covers the exact command strings built by ``wol_app.shutdown_flow.execute_shutdown``
and ``wol_app.schedule_runner.scheduled_shutdown`` plus their success/failure log
paths. ``subprocess.run`` is monkeypatched so nothing is executed on the host.

NOTE: these tests assert the *command strings* as-is. The ``shell=True`` usage is
deliberately left in place (out of scope) — the regression here is that the
commands and the log/status side effects stay correct.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("WOL_HEADLESS", "1")

from unittest.mock import MagicMock  # noqa: E402

import pytest  # noqa: E402

pytest.importorskip("PyQt6")

from PyQt6.QtWidgets import QApplication  # noqa: E402

import wol_app.shutdown_flow as shutdown_flow  # noqa: E402
import wol_app.schedule_runner as schedule_runner  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


class _FakeConfig:
    """Minimal config stub exposing just what the shutdown code touches."""

    def __init__(self, device):
        self._device = device
        self.logs = []

    def get_device_by_id(self, device_id):
        if self._device and self._device.get("id") == device_id:
            return self._device
        return None

    def add_log(self, name, action, status, message):
        self.logs.append((name, action, status, message))

    def get_device_shutdown_method(self, device):
        # Force the classic SMB path (not the host service).
        return "smb"


def _recorder():
    calls = []

    def fn(msg, timeout=0):
        calls.append((msg, timeout))

    fn.calls = calls
    return fn


def _completed(rc=0, stderr=""):
    from subprocess import CompletedProcess

    return CompletedProcess(args="", returncode=rc, stdout="", stderr=stderr)


# --- execute_shutdown (wol_app.shutdown_flow) --------------------------------

class TestExecuteShutdownSmb:
    def test_success_connect_and_shutdown(self, qapp, monkeypatch):
        device = {
            "id": "d1", "name": "PC1", "ip": "192.168.1.10",
            "username": "admin", "password": "pw123",
        }
        cfg = _FakeConfig(device)
        status = _recorder()
        commands = []
        results = [_completed(0), _completed(0), _completed(0)]

        def fake_run(cmd, *args, **kwargs):
            commands.append(cmd)
            return results.pop(0)

        monkeypatch.setattr(shutdown_flow.subprocess, "run", fake_run)
        mock_qmb = MagicMock()
        monkeypatch.setattr(shutdown_flow, "QMessageBox", mock_qmb)

        shutdown_flow.execute_shutdown(None, cfg, device, None, status)

        assert commands == [
            "net use \\\\192.168.1.10 /delete /y",
            "net use \\\\192.168.1.10\\IPC$ /user:admin pw123",
            "shutdown /m \\\\192.168.1.10 /s /t 0 /f",
        ]
        assert any(log[2] == "SUCCESS" for log in cfg.logs)
        mock_qmb.information.assert_called_once()

    def test_connect_failure_logs_error_and_aborts(self, qapp, monkeypatch):
        device = {
            "id": "d1", "name": "PC1", "ip": "192.168.1.10",
            "username": "admin", "password": "pw123",
        }
        cfg = _FakeConfig(device)
        status = _recorder()
        commands = []
        # delete ok, connect fails (rc=1)
        results = [_completed(0), _completed(1, stderr="Access is denied")]

        def fake_run(cmd, *args, **kwargs):
            commands.append(cmd)
            return results.pop(0)

        monkeypatch.setattr(shutdown_flow.subprocess, "run", fake_run)
        mock_qmb = MagicMock()
        monkeypatch.setattr(shutdown_flow, "QMessageBox", mock_qmb)

        shutdown_flow.execute_shutdown(None, cfg, device, None, status)

        # Only delete + connect ran; the shutdown command was never issued.
        assert commands == [
            "net use \\\\192.168.1.10 /delete /y",
            "net use \\\\192.168.1.10\\IPC$ /user:admin pw123",
        ]
        assert any(log[2] == "ERROR" for log in cfg.logs)
        mock_qmb.critical.assert_called_once()


# --- scheduled_shutdown (wol_app.schedule_runner) --------------------------

class TestScheduledShutdownSmb:
    def test_success_two_commands_and_logs(self, qapp, monkeypatch):
        device = {
            "id": "d2", "name": "Server", "ip": "10.0.0.5",
            "username": "svc", "password": "s3cret",
        }
        cfg = _FakeConfig(device)
        status = _recorder()
        commands = []
        results = [_completed(0), _completed(0)]

        def fake_run(cmd, *args, **kwargs):
            commands.append(cmd)
            return results.pop(0)

        monkeypatch.setattr(schedule_runner.subprocess, "run", fake_run)

        schedule_runner.scheduled_shutdown(cfg, "d2", status)

        assert commands == [
            'net use \\\\10.0.0.5\\IPC$ "s3cret" /user:"svc"',
            "shutdown /m \\\\10.0.0.5 /s /t 0 /f",
        ]
        statuses = [log[2] for log in cfg.logs]
        assert "IN_PROGRESS" in statuses
        assert "SUCCESS" in statuses

    def test_connect_failure_logs_failed_and_aborts(self, qapp, monkeypatch):
        device = {
            "id": "d2", "name": "Server", "ip": "10.0.0.5",
            "username": "svc", "password": "s3cret",
        }
        cfg = _FakeConfig(device)
        status = _recorder()
        commands = []
        # connect fails (rc=1) -> no shutdown command
        results = [_completed(1, stderr="denied")]

        def fake_run(cmd, *args, **kwargs):
            commands.append(cmd)
            return results.pop(0)

        monkeypatch.setattr(schedule_runner.subprocess, "run", fake_run)

        schedule_runner.scheduled_shutdown(cfg, "d2", status)

        assert commands == ['net use \\\\10.0.0.5\\IPC$ "s3cret" /user:"svc"']
        statuses = [log[2] for log in cfg.logs]
        assert "IN_PROGRESS" in statuses
        assert "FAILED" in statuses

    def test_missing_device_short_circuits(self, qapp, monkeypatch):
        cfg = _FakeConfig(None)
        status = _recorder()
        ran = {"called": False}

        def fake_run(cmd, *args, **kwargs):
            ran["called"] = True
            return _completed(0)

        monkeypatch.setattr(schedule_runner.subprocess, "run", fake_run)

        schedule_runner.scheduled_shutdown(cfg, "does-not-exist", status)

        assert not ran["called"]
        assert cfg.logs == []  # No log written for a missing device
