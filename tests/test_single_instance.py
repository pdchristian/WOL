"""Tests for the single-instance lock (wol_app/single_instance.py).

The lock itself (QLockFile + QLocalServer/QLocalSocket) works offscreen;
only the module-level HEADLESS_MODE shortcut is patched where needed.
Each test uses its own tmp config file, so lock/socket names never clash.
"""

import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("WOL_HEADLESS", "1")

import pytest  # noqa: E402

pytest.importorskip("PyQt6")

from PyQt6.QtCore import QLockFile  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

import wol_app.single_instance as single_instance  # noqa: E402
from wol_app.config import ConfigManager  # noqa: E402
from wol_app.single_instance import (  # noqa: E402
    SingleInstanceGuard,
    _NoopGuard,
    ensure_primary_instance,
    instance_key,
)


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture()
def config(tmp_path):
    return ConfigManager(config_path=str(tmp_path / "config.json"))


@pytest.fixture()
def locking(qapp, monkeypatch):
    """Disable the headless bypass so the real lock path runs."""
    monkeypatch.setattr(single_instance, "HEADLESS_MODE", False)
    yield


class TestInstanceKey:
    def test_stable_and_path_specific(self, tmp_path):
        a = tmp_path / "a.json"
        b = tmp_path / "b.json"
        assert instance_key(a) == instance_key(str(a))
        assert instance_key(a) != instance_key(b)
        assert len(instance_key(a)) == 16


class TestBypasses:
    def test_headless_returns_noop(self, qapp, config, monkeypatch):
        # Patch explicitly — other test modules may have imported app_core
        # before WOL_HEADLESS was set, making the import-time value False.
        monkeypatch.setattr(single_instance, "HEADLESS_MODE", True)
        guard = ensure_primary_instance(qapp, config)
        assert isinstance(guard, _NoopGuard)

    def test_allow_multiple_returns_noop(self, qapp, config, locking):
        config.set_allow_multiple_instances(True)
        guard = ensure_primary_instance(qapp, config)
        assert isinstance(guard, _NoopGuard)
        # Even repeatedly — no lock is ever taken.
        assert isinstance(ensure_primary_instance(qapp, config), _NoopGuard)


class TestPrimarySecondary:
    def test_first_launch_is_primary(self, qapp, config, locking):
        guard = ensure_primary_instance(qapp, config)
        try:
            assert isinstance(guard, SingleInstanceGuard)
            lock_path = config.config_path.parent / (
                f"instance-{instance_key(config.config_path)}.lock")
            assert lock_path.exists()
        finally:
            guard.release()

    def test_second_launch_defers_and_raises(
            self, qapp, config, locking):
        primary = ensure_primary_instance(qapp, config)
        try:
            fired: list[int] = []
            primary.set_raise_handler(lambda: fired.append(1))

            second = ensure_primary_instance(qapp, config)
            assert second is None  # caller must exit
            for _ in range(50):
                qapp.processEvents()
                if fired:
                    break
            assert fired == [1]
        finally:
            primary.release()

    def test_different_configs_run_in_parallel(
            self, qapp, config, tmp_path, locking):
        other = ConfigManager(config_path=str(tmp_path / "other" / "config.json"))
        g1 = ensure_primary_instance(qapp, config)
        g2 = ensure_primary_instance(qapp, other)
        try:
            assert isinstance(g1, SingleInstanceGuard)
            assert isinstance(g2, SingleInstanceGuard)
        finally:
            g1.release()
            g2.release()

    def test_release_frees_the_lock(self, qapp, config, locking):
        guard = ensure_primary_instance(qapp, config)
        lock_path = config.config_path.parent / (
            f"instance-{instance_key(config.config_path)}.lock")
        guard.release()
        # A fresh lock can be acquired immediately after release.
        probe = QLockFile(str(lock_path))
        assert probe.tryLock(0)
        probe.unlock()

    def test_release_is_idempotent(self, qapp, config, locking):
        guard = ensure_primary_instance(qapp, config)
        guard.release()
        guard.release()

    def test_about_to_quit_releases(self, qapp, config, locking):
        guard = ensure_primary_instance(qapp, config)
        lock_path = config.config_path.parent / (
            f"instance-{instance_key(config.config_path)}.lock")
        qapp.aboutToQuit.emit()
        probe = QLockFile(str(lock_path))
        assert probe.tryLock(0)
        probe.unlock()


class _FakeLock:
    """QLockFile stand-in with scripted tryLock behaviour."""

    def __init__(self, results, stale_clears=False):
        self._results = list(results)
        self._stale_clears = stale_clears
        self.unlocked = False

    def tryLock(self, timeout=-1):  # noqa: N802 (Qt naming)
        if self._results:
            return self._results.pop(0)
        return self._stale_clears

    def removeStaleLockFile(self):  # noqa: N802 (Qt naming)
        return True

    def unlock(self):
        self.unlocked = True


class TestSecondaryAlwaysExits:
    """Lock held by a live process → this launch exits, even if the holder
    never answers the raise request (old fail-open path allowed exactly
    two instances with the default setting — regression guard)."""

    def test_lock_holder_alive_exits_even_without_answer(
            self, qapp, config, monkeypatch):
        monkeypatch.setattr(single_instance, "HEADLESS_MODE", False)
        monkeypatch.setattr(
            single_instance, "QLockFile",
            lambda path: _FakeLock([False], stale_clears=True))

        # No local server is listening → notify fails → must still exit.
        assert ensure_primary_instance(qapp, config) is None

    def test_unreachable_lock_no_longer_fails_open(
            self, qapp, config, monkeypatch):
        monkeypatch.setattr(single_instance, "HEADLESS_MODE", False)
        monkeypatch.setattr(
            single_instance, "QLockFile",
            lambda path: _FakeLock([False, False], stale_clears=False))

        assert ensure_primary_instance(qapp, config) is None


class TestConfigDefaultWrittenToDisk:
    """First run after install/upgrade: the key is persisted explicitly."""

    def test_missing_key_is_persisted_as_false(self, tmp_path):
        cfg_file = tmp_path / "config.json"
        cfg_file.write_text(
            json.dumps({"ui": {"language": "de"}}), encoding="utf-8")

        config = ConfigManager(config_path=str(cfg_file))
        assert config.get_allow_multiple_instances() is False

        on_disk = json.loads(cfg_file.read_text(encoding="utf-8"))
        assert on_disk["ui"]["allow_multiple_instances"] is False

    def test_existing_true_is_not_overwritten(self, tmp_path):
        cfg_file = tmp_path / "config.json"
        cfg_file.write_text(
            json.dumps({"ui": {"allow_multiple_instances": True}}),
            encoding="utf-8")

        config = ConfigManager(config_path=str(cfg_file))
        assert config.get_allow_multiple_instances() is True
        on_disk = json.loads(cfg_file.read_text(encoding="utf-8"))
        assert on_disk["ui"]["allow_multiple_instances"] is True

