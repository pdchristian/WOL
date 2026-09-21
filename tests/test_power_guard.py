"""Safety guard: the host service must never power off the test machine.

The host service's shutdown/reboot path runs the real OS command
(``shutdown /s`` / ``systemctl poweroff``). To make it impossible for a test
that drives the handler in-process to shut down the developer workstation,
``_execute_power`` short-circuits when ``WOL_TEST_NO_POWER`` is set — and
``tests/conftest.py`` sets it for the whole session.

These tests assert the guard directly. ``subprocess.run`` is always mocked,
so even the "guard disabled" cases never touch the OS.
"""

import os

import pytest
from unittest import mock

# The Windows service module imports ctypes at module level but only touches
# ctypes.windll inside functions; importing is safe on every platform.
wol_host_service = pytest.importorskip(
    "wol_host_service", reason="Windows service module")
wol_linux = pytest.importorskip(
    "wol_host_service_linux", reason="Linux service module")


class TestWindowsPowerGuard:
    def test_conftest_sets_guard(self):
        # The session-wide guard is the primary line of defence.
        assert os.environ.get("WOL_TEST_NO_POWER") == "1"

    def test_guard_blocks_shutdown(self, monkeypatch):
        monkeypatch.setenv("WOL_TEST_NO_POWER", "1")
        with mock.patch.object(wol_host_service.subprocess, "run") as run:
            wol_host_service._execute_power("shutdown")
        run.assert_not_called()

    def test_guard_blocks_reboot(self, monkeypatch):
        monkeypatch.setenv("WOL_TEST_NO_POWER", "1")
        with mock.patch.object(wol_host_service.subprocess, "run") as run:
            wol_host_service._execute_power("reboot")
        run.assert_not_called()

    def test_without_guard_runs_shutdown(self, monkeypatch):
        # Guard disabled -> the real argv is used (still mocked, never run).
        monkeypatch.delenv("WOL_TEST_NO_POWER", raising=False)
        with mock.patch.object(wol_host_service.subprocess, "run") as run:
            wol_host_service._execute_power("shutdown")
        run.assert_called_once()
        assert run.call_args.args[0] == ["shutdown", "/s", "/t", "0", "/f"]

    def test_without_guard_runs_reboot(self, monkeypatch):
        monkeypatch.delenv("WOL_TEST_NO_POWER", raising=False)
        with mock.patch.object(wol_host_service.subprocess, "run") as run:
            wol_host_service._execute_power("reboot")
        run.assert_called_once()
        assert run.call_args.args[0] == ["shutdown", "/r", "/t", "0", "/f"]


class TestLinuxPowerGuard:
    def test_guard_blocks_shutdown(self, monkeypatch):
        monkeypatch.setenv("WOL_TEST_NO_POWER", "1")
        with mock.patch.object(wol_linux.subprocess, "run") as run:
            wol_linux._execute_power("shutdown")
        run.assert_not_called()

    def test_guard_blocks_reboot(self, monkeypatch):
        monkeypatch.setenv("WOL_TEST_NO_POWER", "1")
        with mock.patch.object(wol_linux.subprocess, "run") as run:
            wol_linux._execute_power("reboot")
        run.assert_not_called()

    def test_without_guard_uses_module_cmds(self, monkeypatch):
        # SHUTDOWN_CMD/REBOOT_CMD are read at call time (macOS overrides them).
        monkeypatch.delenv("WOL_TEST_NO_POWER", raising=False)
        monkeypatch.setattr(wol_linux, "SHUTDOWN_CMD", ["poweroff"])
        monkeypatch.setattr(wol_linux, "REBOOT_CMD", ["reboot"])
        with mock.patch.object(wol_linux.subprocess, "run") as run:
            wol_linux._execute_power("shutdown")
        run.assert_called_once_with(["poweroff"], capture_output=True)
