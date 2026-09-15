"""macOS platform-support tests (run on every OS, host-independent).

Covers the darwin branches added with the macOS port:

* build_ping_args -> BSD ping argv (-c / -W ms, no -4)
* launch_remote_desktop / retry -> Microsoft Remote Desktop via rdp:// URL
* update dialogs -> .dmg artifacts on macOS
* theme -> AppleInterfaceStyle dark-mode detection
* SMB shutdown -> guarded error off Windows

All platform checks are patched, so these tests behave identically on
Windows, macOS and Linux.
"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("WOL_HEADLESS", "1")

import pytest  # noqa: E402
from unittest.mock import MagicMock, patch  # noqa: E402

pytest.importorskip("PyQt6")

import wol_app.shutdown_flow as shutdown_flow  # noqa: E402
import wol_app.utils as utils  # noqa: E402
from wol_app.utils import (  # noqa: E402
    build_macos_rdp_url,
    build_ping_args,
    launch_remote_desktop,
    retry_remote_desktop_without_password,
)


class TestBuildPingArgs:
    def test_windows_forces_ipv4_and_ms_wait(self):
        with patch.object(utils.sys, "platform", "win32"):
            args = build_ping_args("1.2.3.4", 1, 5000)
        assert args == ["ping", "-4", "-n", "1", "-w", "5000", "1.2.3.4"]

    def test_macos_bsd_flags(self):
        with patch.object(utils.sys, "platform", "darwin"):
            args = build_ping_args("1.2.3.4", 1, 1000)
        # No -4 (BSD ping rejects it), -W takes milliseconds.
        assert args == ["ping", "-c", "1", "-W", "1000", "1.2.3.4"]

    def test_linux_second_flags(self):
        with patch.object(utils.sys, "platform", "linux"):
            args = build_ping_args("1.2.3.4", 1, 1500)
        # Linux -w is a seconds-granularity total deadline.
        assert args == ["ping", "-c", "1", "-w", "1", "1.2.3.4"]


class TestMacOSRemoteDesktop:
    def test_rdp_url_encodes_host_and_user(self):
        assert build_macos_rdp_url("10.0.0.5") == \
            "rdp://full%20address=s:10.0.0.5"
        url = build_macos_rdp_url("10.0.0.5", "max mu")
        assert url.endswith("username=s:max%20mu")

    def test_launch_opens_rdp_uri(self):
        with patch.object(utils.sys, "platform", "darwin"), \
             patch.object(utils, "macos_remote_desktop_available", return_value=True), \
             patch("wol_app.utils.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = launch_remote_desktop("10.0.0.5", "user", "pw")
        assert result is None
        cmd = mock_run.call_args.args[0]
        assert cmd == ["open", "rdp://full%20address=s:10.0.0.5&username=s:user"]

    def test_launch_without_app_raises_runtime_error(self):
        with patch.object(utils.sys, "platform", "darwin"), \
             patch.object(utils, "macos_remote_desktop_available", return_value=False):
            with pytest.raises(RuntimeError, match="Microsoft Remote Desktop"):
                launch_remote_desktop("10.0.0.5")

    def test_empty_ip_raises_value_error(self):
        with patch.object(utils.sys, "platform", "darwin"):
            with pytest.raises(ValueError):
                launch_remote_desktop("")

    def test_retry_reattempts_passwordless(self):
        with patch.object(utils.sys, "platform", "darwin"), \
             patch.object(utils, "macos_remote_desktop_available", return_value=True), \
             patch("wol_app.utils.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            retry_remote_desktop_without_password("10.0.0.5", "user")
        url = mock_run.call_args.args[0][1]
        assert "username=s:user" in url
        # Passwords never travel in the URL.
        assert "password" not in url.lower()

    def test_scheme_failure_falls_back_to_bundle_open(self):
        def fake_run(cmd, *a, **k):
            res = MagicMock()
            res.returncode = 1 if cmd[1].startswith("rdp://") else 0
            return res

        with patch.object(utils.sys, "platform", "darwin"), \
             patch.object(utils, "macos_remote_desktop_available", return_value=True), \
             patch("wol_app.utils.subprocess.run", side_effect=fake_run) as mock_run:
            launch_remote_desktop("10.0.0.5")
        # Second call must bring the app to the front via its bundle id.
        assert mock_run.call_args_list[-1].args[0] == [
            "open", "-b", utils.MACOS_RD_BUNDLE_ID]


class TestInstallerSuffixDispatch:
    def test_macos_prefers_dmg(self):
        from wol_app.update_dialog import _installer_suffix

        with patch.object(sys, "platform", "darwin"):
            assert _installer_suffix() == ".dmg"

    def test_windows_prefers_exe(self):
        from wol_app.update_dialog import _installer_suffix

        with patch.object(sys, "platform", "win32"):
            assert _installer_suffix() == ".exe"


class TestMacOSInstallerLaunch:
    def test_open_used_on_macos(self):
        import subprocess as sp

        from wol_app.update_dialog import _launch_installer_safe

        with patch.object(sys, "platform", "darwin"), \
             patch.object(sp, "run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            assert _launch_installer_safe("/tmp/Wol.dmg") is True
        assert mock_run.call_args.args[0] == ["open", "/tmp/Wol.dmg"]


class TestThemeDarwinDarkDetection:
    """theme._system_uses_dark() consults the AppleInterfaceStyle default."""

    def _run_mock(self, returncode, stdout):
        def fake(cmd, *a, **k):
            assert cmd == ["defaults", "read", "-g", "AppleInterfaceStyle"]
            return MagicMock(returncode=returncode, stdout=stdout)

        return fake

    def test_dark_when_key_present(self):
        from wol_app.theme import _system_uses_dark

        import wol_app.theme as theme

        with patch.object(theme.sys, "platform", "darwin"), \
             patch("subprocess.run", self._run_mock(0, "Dark\n")):
            assert _system_uses_dark() is True

    def test_light_when_key_absent(self):
        from wol_app.theme import _system_uses_dark

        import wol_app.theme as theme

        with patch.object(theme.sys, "platform", "darwin"), \
             patch("subprocess.run", self._run_mock(1, "")):
            assert _system_uses_dark() is False


class TestModernUiFontStackOrder:
    """Emoji fonts must never precede a family available on the platform.

    Qt picks the first family containing a glyph; the color-emoji fonts
    contain letters/digits too, which renders huge letter gaps (seen on
    macOS as "Apple Color Emoji", on Ubuntu as Noto Color Emoji before a
    macOS-only font was added to the stack).
    """

    def _families(self):
        from wol_app.modern_theme import _UI_FONT_STACK

        return [f.strip().strip('"') for f in _UI_FONT_STACK.split(",")]

    def test_emoji_fonts_come_after_platform_text_fonts(self):
        families = self._families()
        text = [f for f in families if "Emoji" not in f and f != "sans-serif"]
        emoji_first = next(
            i for i, f in enumerate(families) if "Emoji" in f)
        # At least one text family before the first emoji font on every OS:
        # Windows (Segoe UI), macOS (SF Pro / .AppleSystemUIFont /
        # Helvetica Neue), Ubuntu (Noto Sans / Ubuntu).
        assert {"Segoe UI", "SF Pro Text", ".AppleSystemUIFont",
                "Helvetica Neue", "Noto Sans", "Ubuntu"} & set(
                    text[:emoji_first])

    def test_macos_system_font_in_stack(self):
        families = self._families()
        assert ".AppleSystemUIFont" in families
        assert families.index(".AppleSystemUIFont") < families.index(
            "Apple Color Emoji")


class _FakeConfig:
    def __init__(self, device):
        self._device = device
        self.logs = []

    def get_device_by_id(self, device_id):
        return self._device if self._device and self._device.get("id") == device_id else None

    def add_log(self, name, action, status, message):
        self.logs.append((name, action, status, message))

    def get_device_shutdown_method(self, device):
        return "smb"


class TestSmbShutdownGuard:
    def test_non_windows_reports_unsupported(self, monkeypatch):
        device = {"id": "d1", "name": "NAS", "ip": "10.0.0.9",
                  "username": "", "password": ""}
        cfg = _FakeConfig(device)
        monkeypatch.setattr(shutdown_flow.sys, "platform", "darwin")
        mock_qmb = MagicMock()
        monkeypatch.setattr(shutdown_flow, "QMessageBox", mock_qmb)
        mock_run = MagicMock()
        monkeypatch.setattr(shutdown_flow.subprocess, "run", mock_run)

        shutdown_flow.execute_shutdown(None, cfg, device, None)

        mock_run.assert_not_called()  # no net use / shutdown commands
        mock_qmb.critical.assert_called_once()
        assert any(log[2] == "ERROR" for log in cfg.logs)


# ── Bundled host-service installer (macOS first-start / settings row) ─────

import shlex  # noqa: E402

import wol_app.host_service_installer as hsi  # noqa: E402
from wol_app.config import ConfigManager  # noqa: E402


class TestServiceStateMatrix:
    """Pure state decision over (payload, installed) versions."""

    def test_nothing_anywhere_is_none(self):
        assert hsi.service_state(None, None) == "none"

    def test_payload_without_install_offers_install(self):
        assert hsi.service_state("2.3.5", None) == "install"

    def test_newer_payload_offers_update(self):
        assert hsi.service_state("2.4.0", "2.3.5") == "update"

    def test_equal_versions_are_current(self):
        assert hsi.service_state("2.3.5", "2.3.5") == "current"

    def test_installed_without_payload_is_current(self):
        # Dev checkout with a manually installed service: stay quiet.
        assert hsi.service_state(None, "0.0.0") == "current"

    def test_older_payload_still_offers_update(self):
        # The bundled service always tracks the shipping app version, so a
        # version mismatch (even a downgrade) is offered as an update.
        assert hsi.service_state("2.3.5", "2.4.0") == "update"


class TestShouldPrompt:
    def test_install_prompts(self):
        assert hsi.should_prompt(None, "install", "2.3.5") is True

    def test_update_prompts(self):
        assert hsi.should_prompt(None, "update", "2.3.5") is True

    @pytest.mark.parametrize("state", ["current", "none"])
    def test_current_or_none_never_prompts(self, state):
        assert hsi.should_prompt(None, state, "2.3.5") is False

    def test_same_version_already_asked(self):
        assert hsi.should_prompt("2.3.5", "update", "2.3.5") is False

    def test_new_release_asks_again(self):
        assert hsi.should_prompt("2.3.4", "update", "2.3.5") is True

    def test_no_payload_never_prompts(self):
        assert hsi.should_prompt(None, "update", None) is False


def _make_fake_payload(tmp_path, version: str | None = None):
    """Create a minimal onedir bundle + optional version marker."""
    payload = tmp_path / hsi.SERVICE_NAME
    (payload / "_internal").mkdir(parents=True)
    (payload / hsi.SERVICE_NAME).write_text("#!/bin/sh\n")
    if version is not None:
        (payload / "service_version.txt").write_text(version + "\n")
    return str(payload)


class TestPayloadDiscovery:
    def test_payload_dir_ok_requires_binary_and_internal(self, tmp_path):
        good = _make_fake_payload(tmp_path)
        assert hsi._payload_dir_ok(good) is True
        assert hsi._payload_dir_ok(str(tmp_path / "missing")) is False
        (tmp_path / "no-internal" / hsi.SERVICE_NAME).parent.mkdir()
        (tmp_path / "no-internal" / hsi.SERVICE_NAME).write_text("x")
        assert hsi._payload_dir_ok(str(tmp_path / "no-internal")) is False

    def test_non_macos_has_no_payload(self, monkeypatch, tmp_path):
        monkeypatch.setattr(hsi.sys, "platform", "linux")
        fake = _make_fake_payload(tmp_path)
        assert hsi.service_payload_path(get_resource=lambda name: fake) is None

    def test_get_resource_hook_finds_bundle(self, monkeypatch, tmp_path):
        monkeypatch.setattr(hsi.sys, "platform", "darwin")
        monkeypatch.setattr(hsi.sys, "frozen", False, raising=False)
        fake = _make_fake_payload(tmp_path)
        assert hsi.service_payload_path(
            get_resource=lambda name: fake) == fake

    def test_frozen_app_uses_resources_dir(self, monkeypatch, tmp_path):
        # Simulate the packaged layout: <app>/Contents/MacOS/<exe>
        exe = tmp_path / "Wake-on-LAN Manager.app" / "Contents" / "MacOS" \
            / "Wake-on-LAN Manager"
        exe.parent.mkdir(parents=True)
        exe.write_text("")
        resources = exe.parent.parent / "Resources"
        fake = _make_fake_payload(resources)
        monkeypatch.setattr(hsi.sys, "platform", "darwin")
        monkeypatch.setattr(hsi.sys, "frozen", True, raising=False)
        monkeypatch.setattr(hsi.sys, "executable", str(exe), raising=False)
        monkeypatch.delattr(hsi.sys, "_MEIPASS", raising=False)
        assert hsi.service_payload_path() == fake


class TestVersions:
    def test_payload_version_marker(self, tmp_path):
        payload = _make_fake_payload(tmp_path, "9.9.9")
        assert hsi.payload_version(payload) == "9.9.9"

    def test_payload_version_falls_back_to_app(self, tmp_path):
        from wol_app import __version__
        payload = _make_fake_payload(tmp_path)  # no marker file
        assert hsi.payload_version(payload) == __version__

    def test_empty_marker_falls_back_to_app(self, tmp_path):
        from wol_app import __version__
        payload = _make_fake_payload(tmp_path, "")
        assert hsi.payload_version(payload) == __version__

    def test_installed_none_without_binary(self, monkeypatch, tmp_path):
        monkeypatch.setattr(hsi, "INSTALL_BIN", str(tmp_path / "nope"))
        assert hsi.installed_version() is None

    def test_installed_reads_marker(self, monkeypatch, tmp_path):
        binary = tmp_path / hsi.SERVICE_NAME
        binary.write_text("x")
        marker = tmp_path / "service_version.txt"
        marker.write_text("1.2.3\n")
        monkeypatch.setattr(hsi, "INSTALL_BIN", str(binary))
        monkeypatch.setattr(hsi, "VERSION_MARKER", str(marker))
        assert hsi.installed_version() == "1.2.3"

    def test_legacy_install_without_marker_is_zero(self, monkeypatch, tmp_path):
        binary = tmp_path / hsi.SERVICE_NAME
        binary.write_text("x")
        monkeypatch.setattr(hsi, "INSTALL_BIN", str(binary))
        monkeypatch.setattr(hsi, "VERSION_MARKER",
                            str(tmp_path / "missing.txt"))
        assert hsi.installed_version() == "0.0.0"


class TestScriptBuilders:
    def test_install_script_quotes_and_registers(self, monkeypatch):
        monkeypatch.setattr(hsi, "INSTALL_DIR", "/usr/local/lib/x y")
        monkeypatch.setattr(hsi, "INSTALL_BIN", "/usr/local/lib/x y/svc")
        monkeypatch.setattr(hsi, "VERSION_MARKER",
                            "/usr/local/lib/x y/service_version.txt")
        script = hsi.build_install_script("/tmp/pay load", "2.3.5")
        assert "'/usr/local/lib/x y'" in script
        assert "'/tmp/pay load'/." in script
        assert "--install" in script
        assert "xattr -dr com.apple.quarantine" in script
        assert "service_version.txt" in script
        assert "2.3.5" in script
        # shlex quote order: script must start defensively
        assert script.startswith("set -e")

    def test_uninstall_script_removes_dir(self):
        script = hsi.build_uninstall_script()
        assert "--uninstall" in script
        assert hsi.INSTALL_DIR in script or shlex.quote(hsi.INSTALL_DIR) \
            in script


class _FakeResult:
    def __init__(self, rc=0, stderr=""):
        self.returncode = rc
        self.stdout = ""
        self.stderr = stderr


class TestRunPrivileged:
    def test_success(self, monkeypatch, tmp_path):
        monkeypatch.setattr(hsi, "INSTALL_LOG", str(tmp_path / "log"))
        seen = {}

        def runner(argv, **kwargs):
            seen["argv"] = argv
            return _FakeResult(0)

        ok, message = hsi.run_privileged("echo hi", "Prompt", runner=runner)
        assert (ok, message) == (True, "")
        argv = seen["argv"]
        assert argv[0] == "osascript"
        assert "with administrator privileges" in argv[2]
        assert "with prompt \"Prompt\"" in argv[2]
        # Temp script is cleaned up again after the call.
        import re
        tmp = re.search(r'(/\S*wol-hs-\S*\.sh)', argv[2]).group(1)
        assert not os.path.exists(tmp)

    def test_cancel_detected_from_stderr(self, monkeypatch, tmp_path):
        monkeypatch.setattr(hsi, "INSTALL_LOG", str(tmp_path / "log"))

        def runner(argv, **kwargs):
            return _FakeResult(1, "0:9: execution error: User canceled. "
                               "(-128)")

        ok, message = hsi.run_privileged("x", "p", runner=runner)
        assert (ok, message) == (False, "cancelled")

    def test_failure_prefers_log_content(self, monkeypatch, tmp_path):
        log = tmp_path / "log"
        log.write_text("launchctl bootstrap failed")
        monkeypatch.setattr(hsi, "INSTALL_LOG", str(log))

        def runner(argv, **kwargs):
            return _FakeResult(1, "osascript exit noise")

        ok, message = hsi.run_privileged("x", "p", runner=runner)
        assert ok is False
        assert message == "launchctl bootstrap failed"

    def test_failure_falls_back_to_stderr(self, monkeypatch, tmp_path):
        monkeypatch.setattr(hsi, "INSTALL_LOG", str(tmp_path / "nolog"))

        def runner(argv, **kwargs):
            return _FakeResult(2, "boom")

        ok, message = hsi.run_privileged("x", "p", runner=runner)
        assert (ok, message) == (False, "boom")

    def test_special_characters_survive_quoting(self, monkeypatch, tmp_path):
        monkeypatch.setattr(hsi, "INSTALL_LOG", str(tmp_path / "log"))
        captured = {}

        def runner(argv, **kwargs):
            captured["wrapped"] = argv[2]
            return _FakeResult(0)

        hsi.run_privileged('echo "hi"', 'He said "yes" & \\no',
                           runner=runner)
        # The AppleScript literal must have every quote / backslash escaped.
        assert 'with prompt "He said \\"yes\\" & \\\\no"' \
            in captured["wrapped"]


class TestInstallOrUpdateFlow:
    def _patch_state(self, monkeypatch, payload, installed):
        monkeypatch.setattr(hsi, "service_payload_path",
                            lambda: payload)
        monkeypatch.setattr(hsi, "payload_version", lambda d: "2.4.0")
        monkeypatch.setattr(hsi, "installed_version", lambda: installed)
        monkeypatch.setattr(hsi, "INSTALL_LOG", "/tmp/pytest-wol-hs.log")

    def test_no_payload(self, monkeypatch):
        monkeypatch.setattr(hsi, "service_payload_path", lambda: None)
        ok, outcome, message = hsi.install_or_update_host_service(
            "i", "u", runner=lambda *a, **k: _FakeResult(0))
        assert (ok, outcome) == (False, "no_payload")

    def test_success_returns_version(self, monkeypatch, tmp_path):
        payload = _make_fake_payload(tmp_path, "2.4.0")
        self._patch_state(monkeypatch, payload, None)
        ok, outcome, message = hsi.install_or_update_host_service(
            "install now", "update now", runner=lambda *a, **k:
            _FakeResult(0))
        assert (ok, outcome, message) == (True, "2.4.0", "")

    def test_update_prompt_used_when_installed(self, monkeypatch, tmp_path):
        payload = _make_fake_payload(tmp_path, "2.4.0")
        self._patch_state(monkeypatch, payload, "2.3.5")
        prompts = []

        def runner(argv, **kwargs):
            prompts.append(argv[2])
            return _FakeResult(0)

        hsi.install_or_update_host_service("IIII", "UUUU", runner=runner)
        assert "UUUU" in prompts[0]
        assert "IIII" not in prompts[0]

    def test_cancelled_maps_to_outcome(self, monkeypatch, tmp_path):
        payload = _make_fake_payload(tmp_path, "2.4.0")
        self._patch_state(monkeypatch, payload, None)

        def runner(argv, **kwargs):
            return _FakeResult(1, "User canceled. (-128)")

        ok, outcome, message = hsi.install_or_update_host_service(
            "i", "u", runner=runner)
        assert (ok, outcome, message) == (False, "cancelled", "")

    def test_failure_maps_to_outcome(self, monkeypatch, tmp_path):
        payload = _make_fake_payload(tmp_path, "2.4.0")
        self._patch_state(monkeypatch, payload, None)

        def runner(argv, **kwargs):
            return _FakeResult(1, "kaboom")

        ok, outcome, message = hsi.install_or_update_host_service(
            "i", "u", runner=runner)
        assert (ok, outcome) == (False, "failed")
        assert message == "kaboom"


class TestRemoveFlow:
    def test_not_installed_short_circuits(self, monkeypatch):
        monkeypatch.setattr(hsi, "installed_version", lambda: None)
        called = []
        ok, message = hsi.remove_host_service(
            "p", runner=lambda *a, **k: called.append(1) or _FakeResult(0))
        assert (ok, message) == (False, "not_installed")
        assert not called

    def test_remove_success(self, monkeypatch, tmp_path):
        monkeypatch.setattr(hsi, "installed_version", lambda: "2.3.5")
        monkeypatch.setattr(hsi, "INSTALL_LOG", str(tmp_path / "log"))
        ok, message = hsi.remove_host_service(
            "p", runner=lambda *a, **k: _FakeResult(0))
        assert (ok, message) == (True, "")

    def test_remove_cancelled(self, monkeypatch, tmp_path):
        monkeypatch.setattr(hsi, "installed_version", lambda: "2.3.5")
        monkeypatch.setattr(hsi, "INSTALL_LOG", str(tmp_path / "log"))

        def runner(argv, **kwargs):
            return _FakeResult(1, "User canceled. (-128)")

        ok, message = hsi.remove_host_service("p", runner=runner)
        assert (ok, message) == (False, "cancelled")


class TestConfigPromptedVersion:
    """Round-trip of the ui.hostservice_prompted_version marker."""

    def _config(self, tmp_path):
        with patch("wol_app.config.read_ui_mode_from_registry",
                   return_value=None):
            return ConfigManager(config_path=str(tmp_path / "config.json"))

    def test_default_none(self, tmp_path):
        assert self._config(tmp_path).get_hostservice_prompted_version() \
            is None

    def test_set_and_reload(self, tmp_path):
        config = self._config(tmp_path)
        config.set_hostservice_prompted_version("2.3.5")
        reloaded = self._config(tmp_path)
        assert reloaded.get_hostservice_prompted_version() == "2.3.5"

    def test_empty_string_reads_as_none(self, tmp_path):
        config = self._config(tmp_path)
        config.config["ui"]["hostservice_prompted_version"] = ""
        assert config.get_hostservice_prompted_version() is None
