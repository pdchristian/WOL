"""Fast-exit retry flow of wol_app.remote_desktop (offscreen, headless).

A wrong password against an xrdp/Ubuntu host makes mstsc close immediately
(black screen). ``start_remote_desktop`` must then watch the process and, on
a fast exit, ask the user whether to reconnect without the stored password.
"""

import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("WOL_HEADLESS", "1")

import pytest  # noqa: E402
from unittest.mock import MagicMock, patch  # noqa: E402

pytest.importorskip("PyQt6")

from PyQt6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from wol_app import remote_desktop  # noqa: E402
from wol_app.config import ConfigManager  # noqa: E402
from wol_app.remote_desktop import (  # noqa: E402
    _handle_fast_exit,
    _make_fast_exit_callback,
    _pending_fast_exit,
    start_remote_desktop,
)
from wol_app.translations import Translations  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(scope="module", autouse=True)
def _translations():
    Translations().load("en")


@pytest.fixture()
def config(tmp_path):
    return ConfigManager(config_path=str(tmp_path / "config.json"))


@pytest.fixture(autouse=True)
def _clear_pending():
    _pending_fast_exit.clear()
    yield
    _pending_fast_exit.clear()


DEVICE = {
    "id": "d1", "name": "Ubuntu PC", "mac": "AA:BB:CC:DD:EE:FF",
    "ip": "10.0.0.42", "username": "max", "password": "secret",
    "enabled": True,
}


@pytest.fixture()
def parent(qapp):
    """A real (hidden) QWidget to act as dialog parent."""
    from PyQt6.QtWidgets import QWidget

    widget = QWidget()
    yield widget
    widget.setParent(None)


class TestStartRemoteDesktopWiring:
    def test_password_arms_fast_exit_watch(self, qapp, config, parent):
        with patch.object(remote_desktop, "launch_remote_desktop") as mock_launch, \
             patch.object(remote_desktop, "_make_fast_exit_callback",
                          return_value="cb") as mock_cb:
            start_remote_desktop(parent, config, DEVICE, fullscreen=True)
        kwargs = mock_launch.call_args.kwargs
        assert kwargs["on_fast_exit"] == "cb"
        assert kwargs["password"] == "secret"

    def test_no_password_disables_watch(self, qapp, config, parent):
        device = dict(DEVICE, password="")
        with patch.object(remote_desktop, "launch_remote_desktop") as mock_launch, \
             patch.object(remote_desktop, "_make_fast_exit_callback") as mock_cb:
            start_remote_desktop(parent, config, device, fullscreen=True)
        mock_cb.assert_not_called()
        assert mock_launch.call_args.kwargs["on_fast_exit"] is None


class TestHandleFastExit:
    def test_yes_retries_without_password(self, qapp, config, parent):
        with patch.object(QMessageBox, "question",
                          return_value=QMessageBox.StandardButton.Yes), \
             patch.object(remote_desktop,
                          "retry_remote_desktop_without_password") as mock_retry:
            _handle_fast_exit(parent, config, "Ubuntu PC", "10.0.0.42",
                              "max", True, 1920, 1080)
        kwargs = mock_retry.call_args.kwargs
        assert kwargs["ip"] == "10.0.0.42"
        assert kwargs["username"] == "max"
        assert kwargs["fullscreen"] is True
        # The password is never passed on — the user types it in mstsc.
        assert "password" not in kwargs
        # A warning entry lands in the app log.
        logs = config.config.get("logs", [])
        assert any(e["action"] == "RDP" and e["status"] == "WARNING"
                   for e in logs)
        assert "10.0.0.42" not in _pending_fast_exit

    def test_no_does_not_retry(self, qapp, config, parent):
        with patch.object(QMessageBox, "question",
                          return_value=QMessageBox.StandardButton.No), \
             patch.object(remote_desktop,
                          "retry_remote_desktop_without_password") as mock_retry:
            _handle_fast_exit(parent, config, "Ubuntu PC", "10.0.0.42",
                              "max", True, 1920, 1080)
        mock_retry.assert_not_called()
        assert "10.0.0.42" not in _pending_fast_exit

    def test_retry_failure_shows_error(self, qapp, config, parent):
        with patch.object(QMessageBox, "question",
                          return_value=QMessageBox.StandardButton.Yes), \
             patch.object(remote_desktop,
                          "retry_remote_desktop_without_password",
                          side_effect=OSError("mstsc missing")), \
             patch.object(QMessageBox, "critical") as mock_critical:
            _handle_fast_exit(parent, config, "Ubuntu PC", "10.0.0.42",
                              "max", True, 1920, 1080)
        mock_critical.assert_called_once()


class TestFastExitCallback:
    def test_callback_marks_pending_and_opens_dialog(self, qapp, config, parent):
        cb = _make_fast_exit_callback(parent, config, "Ubuntu PC",
                                      "10.0.0.42", "max", True, 1920, 1080)
        with patch.object(QMessageBox, "question",
                          return_value=QMessageBox.StandardButton.No) as q, \
             patch.object(remote_desktop,
                          "retry_remote_desktop_without_password") as mock_retry:
            cb()  # same thread -> direct signal connection, runs synchronously
        q.assert_called_once()
        mock_retry.assert_not_called()

    def test_pending_host_blocks_second_prompt(self, qapp, config, parent):
        cb = _make_fast_exit_callback(parent, config, "Ubuntu PC",
                                      "10.0.0.42", "max", True, 1920, 1080)
        _pending_fast_exit.add("10.0.0.42")
        with patch.object(QMessageBox, "question") as q:
            cb()
        q.assert_not_called()

    def test_callback_opens_dialog_via_relay(self, qapp, config, parent):
        """Signal-based marshalling: emitting from a worker thread works."""
        import threading

        cb = _make_fast_exit_callback(parent, config, "Ubuntu PC",
                                      "10.0.0.42", "max", True, 1920, 1080)
        opened = []

        def fake_question(*args, **kwargs):
            opened.append(True)
            return QMessageBox.StandardButton.No

        thread = threading.Thread(target=cb)
        with patch.object(QMessageBox, "question", side_effect=fake_question), \
             patch.object(remote_desktop,
                          "retry_remote_desktop_without_password"):
            thread.start()
            thread.join(timeout=2.0)
            # Queued cross-thread delivery needs the event loop.
            for _ in range(200):
                if opened:
                    break
                qapp.processEvents()
                time.sleep(0.005)
        assert opened, "dialog was not opened on the GUI thread"


# ── Platform routing: RDP vs VNC ─────────────────────────────────────────

LINUX_DEVICE = dict(DEVICE, os="linux")
WINDOWS_DEVICE = dict(DEVICE, os="windows")


def test_resolve_protocol_follows_device_platform(config):
    assert remote_desktop.resolve_remote_protocol(config, WINDOWS_DEVICE) == "rdp"
    assert remote_desktop.resolve_remote_protocol(config, LINUX_DEVICE) == "vnc"
    # never-detected platform keeps the historical RDP path
    assert remote_desktop.resolve_remote_protocol(config, DEVICE) == "rdp"


def test_resolve_protocol_survives_stub_config():
    class Stub:
        pass

    assert remote_desktop.resolve_remote_protocol(Stub(), LINUX_DEVICE) == "rdp"


def test_resolve_protocol_ignores_invalid_stored_value(config):
    # a hand-edited, invalid value falls back to the platform default
    config.config["remote"]["protocol_by_os"]["linux"] = "telnet"
    config.config["remote"]["protocol_by_os"]["windows"] = "telnet"
    assert remote_desktop.resolve_remote_protocol(config, LINUX_DEVICE) == "vnc"
    assert remote_desktop.resolve_remote_protocol(config, WINDOWS_DEVICE) == "rdp"


def test_linux_device_opens_vnc_not_mstsc(parent, config):
    with patch.object(remote_desktop, "launch_vnc", return_value=["vncviewer", "x"]) as vnc, \
            patch.object(remote_desktop, "launch_remote_desktop") as rdp, \
            patch.object(QMessageBox, "information"), \
            patch.object(QApplication, "clipboard", return_value=MagicMock()):
        start_remote_desktop(parent, config, LINUX_DEVICE, True)
    rdp.assert_not_called()
    vnc.assert_called_once_with(
        "10.0.0.42", port=5900, viewer_path="", fullscreen=True)


def test_windows_device_still_opens_mstsc(parent, config):
    with patch.object(remote_desktop, "launch_vnc") as vnc, \
            patch.object(remote_desktop, "launch_remote_desktop") as rdp:
        start_remote_desktop(parent, config, WINDOWS_DEVICE, True)
    vnc.assert_not_called()
    rdp.assert_called_once()


def test_vnc_uses_configured_viewer_path_and_port(parent, config):
    config.set_vnc_viewer_path(r"C:\Tools\vncviewerw.bat")
    config.set_vnc_port(5901)
    with patch.object(remote_desktop, "launch_vnc", return_value=["v"]) as vnc, \
            patch.object(QMessageBox, "information"), \
            patch.object(QApplication, "clipboard", return_value=MagicMock()):
        start_remote_desktop(parent, config, LINUX_DEVICE, False)
    vnc.assert_called_once_with(
        "10.0.0.42", port=5901, viewer_path=r"C:\Tools\vncviewerw.bat",
        fullscreen=False)


def test_vnc_password_goes_to_clipboard_not_command_line(parent, config):
    clipboard = MagicMock()
    with patch.object(remote_desktop, "launch_vnc", return_value=["v"]) as vnc, \
            patch.object(QMessageBox, "information") as info, \
            patch.object(QApplication, "clipboard", return_value=clipboard):
        start_remote_desktop(parent, config, LINUX_DEVICE, True)
    clipboard.setText.assert_called_once_with("secret")
    info.assert_called_once()
    assert "secret" not in str(vnc.call_args)


def test_vnc_logs_started_session(parent, config):
    with patch.object(remote_desktop, "launch_vnc",
                      return_value=["v", "10.0.0.42::5900"]), \
            patch.object(QMessageBox, "information"), \
            patch.object(QApplication, "clipboard", return_value=MagicMock()):
        start_remote_desktop(parent, config, LINUX_DEVICE, True)
    messages = [entry.get("message", "") for entry in config.get_logs()]
    assert any("Started VNC session to 10.0.0.42::5900" in m for m in messages)


def test_vnc_without_viewer_warns_where_to_configure(parent, config):
    with patch.object(remote_desktop, "launch_vnc",
                      side_effect=RuntimeError("no viewer")), \
            patch.object(QMessageBox, "warning") as warn:
        start_remote_desktop(parent, config, LINUX_DEVICE, True)
    assert warn.call_args.args[1] == Translations.tr("dialog.vnc_missing.title")
    assert not config.get_logs()


def test_vnc_launch_failure_shows_generic_error(parent, config):
    with patch.object(remote_desktop, "launch_vnc",
                      side_effect=OSError("boom")), \
            patch.object(QMessageBox, "critical") as critical:
        start_remote_desktop(parent, config, LINUX_DEVICE, True)
    assert critical.call_args.args[1] == \
        Translations.tr("dialog.remote_desktop_error.title")
