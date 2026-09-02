"""Regression tests for wol_app.updater.UpdateChecker.run() network flow."""

import os
import json
import contextlib
from urllib.error import URLError

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("WOL_HEADLESS", "1")

import pytest  # noqa: E402

pytest.importorskip("PyQt6")

from PyQt6.QtWidgets import QApplication  # noqa: E402

import wol_app.updater as updater  # noqa: E402
from wol_app.updater import UpdateChecker  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _capture(checker):
    results = []
    checker.finished.connect(lambda rel, upd: results.append((rel, upd)))
    return results


def _fake_urlopen_releasing(payload):
    @contextlib.contextmanager
    def _fake(req, *args, **kwargs):
        class _Resp:
            def read(self):
                return payload
        yield _Resp()
    return _fake


class TestUpdateCheckerRun:
    def test_newer_release_reports_update(self, qapp, monkeypatch):
        monkeypatch.setattr(
            updater, "urlopen",
            _fake_urlopen_releasing(json.dumps({"tag_name": "v2.1.0"}).encode("utf-8")),
        )
        checker = UpdateChecker(current_version="2.0.0")
        results = _capture(checker)
        checker.run()
        assert len(results) == 1
        release, has_update = results[0]
        assert has_update is True
        assert release["tag_name"] == "v2.1.0"

    def test_same_version_reports_no_update(self, qapp, monkeypatch):
        monkeypatch.setattr(
            updater, "urlopen",
            _fake_urlopen_releasing(json.dumps({"tag_name": "v2.0.0"}).encode("utf-8")),
        )
        checker = UpdateChecker(current_version="2.0.0")
        results = _capture(checker)
        checker.run()
        assert results[0][1] is False

    def test_older_release_reports_no_update(self, qapp, monkeypatch):
        monkeypatch.setattr(
            updater, "urlopen",
            _fake_urlopen_releasing(json.dumps({"tag_name": "v1.9.0"}).encode("utf-8")),
        )
        checker = UpdateChecker(current_version="2.0.0")
        results = _capture(checker)
        checker.run()
        assert results[0][1] is False

    def test_network_error_reports_no_update(self, qapp, monkeypatch):
        def _raise(req, *args, **kwargs):
            raise URLError("no network")

        monkeypatch.setattr(updater, "urlopen", _raise)
        checker = UpdateChecker(current_version="2.0.0")
        results = _capture(checker)
        checker.run()
        assert results == [(None, False)]
