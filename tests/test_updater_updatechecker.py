"""Regression tests for wol_app.updater.UpdateChecker.run() network flow."""

import os
import json
import contextlib
from urllib.error import HTTPError, URLError

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("WOL_HEADLESS", "1")

import pytest  # noqa: E402

pytest.importorskip("PyQt6")

from PyQt6.QtWidgets import QApplication  # noqa: E402

import wol_app.updater as updater  # noqa: E402
from wol_app.updater import UpdateChecker, normalize_tag  # noqa: E402


class TestNormalizeTag:
    """GitHub-Tags können 'v2.3.5' ODER 'v.2.3.5' lauten (Release v.2.3.5 real)."""

    def test_plain(self):
        assert normalize_tag("2.3.5") == "2.3.5"

    def test_v_prefix(self):
        assert normalize_tag("v2.3.5") == "2.3.5"

    def test_v_dot_prefix(self):
        assert normalize_tag("v.2.3.5") == "2.3.5"

    def test_uppercase_v(self):
        assert normalize_tag("V2.3.5") == "2.3.5"

    def test_whitespace(self):
        assert normalize_tag("  v.2.3.5  ") == "2.3.5"

    def test_empty(self):
        assert normalize_tag("") == ""


class TestParseVersionDotTag:
    def test_dot_tag_parses_correctly(self):
        assert updater._parse_version(normalize_tag("v.2.3.5")) == (2, 3, 5)

    def test_dot_tag_newer_than_current(self):
        assert updater._parse_version(normalize_tag("v.2.3.5")) > updater._parse_version("2.3.0")


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

    def test_dot_tag_release_reports_update(self, qapp, monkeypatch):
        monkeypatch.setattr(
            updater, "urlopen",
            _fake_urlopen_releasing(json.dumps({"tag_name": "v.2.3.5"}).encode("utf-8")),
        )
        checker = UpdateChecker(current_version="2.3.0")
        results = _capture(checker)
        checker.run()
        assert results[0][1] is True

    def test_network_error_reports_no_update(self, qapp, monkeypatch):
        def _raise(req, *args, **kwargs):
            raise URLError("no network")

        monkeypatch.setattr(updater, "urlopen", _raise)
        checker = UpdateChecker(current_version="2.0.0")
        results = _capture(checker)
        checker.run()
        assert results == [(None, False)]


class TestCheckForUpdatesSync:
    """Manual checks must tell "no update" and "check failed" apart.

    Regression: ``check_for_updates_sync`` used to swallow failures as
    ``(None, False)``, so a blocked/rate-limited ``api.github.com`` was shown
    to the user as "You are using the latest version".
    """

    def test_newer_release_reports_update(self, monkeypatch):
        monkeypatch.setattr(
            updater, "urlopen",
            _fake_urlopen_releasing(json.dumps({"tag_name": "v2.5.3"}).encode("utf-8")),
        )
        result = updater.check_for_updates_sync("2.5.2")
        assert result is not None
        release, has_update = result
        assert has_update is True
        assert release["tag_name"] == "v2.5.3"

    def test_same_release_reports_no_update(self, monkeypatch):
        monkeypatch.setattr(
            updater, "urlopen",
            _fake_urlopen_releasing(json.dumps({"tag_name": "v2.5.3"}).encode("utf-8")),
        )
        result = updater.check_for_updates_sync("2.5.3")
        assert result is not None
        assert result[1] is False

    def test_network_error_returns_none(self, monkeypatch):
        def _raise(req, *args, **kwargs):
            raise URLError("no network")

        monkeypatch.setattr(updater, "urlopen", _raise)
        assert updater.check_for_updates_sync("2.5.2") is None

    def test_rate_limited_http_error_returns_none(self, monkeypatch):
        def _raise(req, *args, **kwargs):
            raise HTTPError(
                "https://api.github.com/repos/pdchristian/WOL/releases/latest",
                403, "rate limit exceeded", {}, None,
            )

        monkeypatch.setattr(updater, "urlopen", _raise)
        assert updater.check_for_updates_sync("2.5.2") is None

    def test_malformed_payload_returns_none(self, monkeypatch):
        monkeypatch.setattr(updater, "urlopen", _fake_urlopen_releasing(b"not json"))
        assert updater.check_for_updates_sync("2.5.2") is None
