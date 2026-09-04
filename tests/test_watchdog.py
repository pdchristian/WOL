"""Tests for the opt-in GUI freeze watchdog (wol_app.watchdog)."""

import time
from pathlib import Path

import pytest

from wol_app.watchdog import (
    DEFAULT_TIMEOUT_S,
    GuiWatchdog,
    _env_flag,
    maybe_start_watchdog,
)


class TestEnvFlag:
    def test_disabled_by_default(self, monkeypatch):
        monkeypatch.delenv("WOL_WATCHDOG", raising=False)
        assert _env_flag() is None

    @pytest.mark.parametrize("value", ["", "0", "false", "no", "off"])
    def test_disabled_values(self, monkeypatch, value):
        monkeypatch.setenv("WOL_WATCHDOG", value)
        assert _env_flag() is None

    @pytest.mark.parametrize("value", ["1", "true", "YES", "on"])
    def test_enabled_default_timeout(self, monkeypatch, value):
        monkeypatch.setenv("WOL_WATCHDOG", value)
        assert _env_flag() == DEFAULT_TIMEOUT_S

    def test_numeric_timeout(self, monkeypatch):
        monkeypatch.setenv("WOL_WATCHDOG", "2.5")
        assert _env_flag() == 2.5

    def test_invalid_falls_back_to_default(self, monkeypatch):
        monkeypatch.setenv("WOL_WATCHDOG", "blubb")
        assert _env_flag() == DEFAULT_TIMEOUT_S


class TestGuiWatchdog:
    def test_dumps_when_gui_thread_stalls(self, tmp_path: Path):
        log = tmp_path / "wd.log"
        wd = GuiWatchdog(timeout_s=0.4, log_path=log)
        wd.start()
        time.sleep(1.2)  # no beat -> hang must be dumped
        wd.stop()
        wd.join(timeout=2)
        text = log.read_text(encoding="utf-8")
        assert "GUI freeze" in text
        # The dump contains this test module's frames (all_threads dump)
        assert "watchdog" in text.lower()
        assert wd.hangs == 1

    def test_no_dump_while_beating(self, tmp_path: Path):
        log = tmp_path / "wd.log"
        wd = GuiWatchdog(timeout_s=0.6, log_path=log)
        wd.start()
        for _ in range(8):
            wd.beat()
            time.sleep(0.1)
        wd.stop()
        wd.join(timeout=2)
        assert not log.exists() or "GUI freeze" not in log.read_text(
            encoding="utf-8")
        assert wd.hangs == 0

    def test_dump_once_per_hang_and_rearm(self, tmp_path: Path):
        log = tmp_path / "wd.log"
        wd = GuiWatchdog(timeout_s=0.4, log_path=log)
        wd.start()
        time.sleep(1.5)  # one long hang -> exactly one dump
        assert wd.hangs == 1
        wd.beat()        # recovered
        time.sleep(1.2)  # hangs again -> second dump
        wd.stop()
        wd.join(timeout=2)
        assert wd.hangs == 2
        text = log.read_text(encoding="utf-8")
        assert text.count("GUI freeze") == 2


class TestMaybeStartWatchdog:
    def test_noop_without_env(self, monkeypatch, qapp):
        monkeypatch.delenv("WOL_WATCHDOG", raising=False)
        assert maybe_start_watchdog(qapp) is None

    def test_noop_without_app(self, monkeypatch):
        monkeypatch.setenv("WOL_WATCHDOG", "1")
        assert maybe_start_watchdog(None) is None

    def test_starts_with_env(self, monkeypatch, qapp, tmp_path):
        monkeypatch.setenv("WOL_WATCHDOG", "1")
        monkeypatch.setattr("wol_app.watchdog.LOG_FILE",
                            tmp_path / "sub" / "wd.log")
        wd = maybe_start_watchdog(qapp)
        try:
            assert wd is not None
            assert wd.is_alive()
            assert (tmp_path / "sub" / "wd.log").exists()
        finally:
            wd.stop()
            wd.join(timeout=2)
