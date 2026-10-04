"""Tests for the shared-password feature (apply password to same-username devices).

Covers: ConfigManager.get_devices_by_username, the shared helper module, the
modern device dialog (ModernShutdownConfirmDialog Ja/Nein) and the classic
DeviceDialog (QMessageBox.question).
"""

import os
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("WOL_HEADLESS", "1")

import pytest  # noqa: E402

pytest.importorskip("PyQt6")

from PyQt6.QtWidgets import (  # noqa: E402
    QApplication,
    QDialog,
    QMessageBox,
)

from wol_app.config import ConfigManager  # noqa: E402
from wol_app.shared_password import (  # noqa: E402
    apply_api_key,
    apply_password,
    collect_api_key_share_targets,
    collect_share_targets,
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
    """Three devices: two share user 'shared' (different passwords), one has none."""
    cfg = ConfigManager(config_path=str(tmp_path / "config.json"))
    cfg.add_device("Alpha", "AA:BB:CC:00:00:01")
    cfg.add_device("Beta", "AA:BB:CC:00:00:02")
    cfg.add_device("Gamma", "AA:BB:CC:00:00:03")
    a, b, _ = cfg.get_devices()
    cfg.update_device(a["id"], username="shared", password="old-a")
    cfg.update_device(b["id"], username="Other", password="old-b")
    return cfg


class TestGetDevicesByUsername:
    def test_finds_matches_case_insensitive(self, config):
        matches = config.get_devices_by_username("SHARED")
        assert [d["name"] for d in matches] == ["Alpha"]

    def test_excludes_id(self, config):
        alpha = config.get_device_by_name("Alpha")
        assert config.get_devices_by_username("shared", exclude_id=alpha["id"]) == []

    def test_empty_username_never_matches(self, config):
        assert config.get_devices_by_username("") == []
        assert config.get_devices_by_username("   ") == []
        # Gamma has no username at all
        assert config.get_devices_by_username("Gamma") == []

    def test_case_sensitive_mode(self, config):
        assert config.get_devices_by_username("Shared", case_insensitive=False) == []
        assert len(config.get_devices_by_username("shared", case_insensitive=False)) == 1


class TestSharedPasswordHelper:
    def test_no_targets_without_password(self, config):
        assert collect_share_targets(config, "shared", "") == []

    def test_no_targets_without_username(self, config):
        assert collect_share_targets(config, "", "secret") == []

    def test_skips_devices_with_identical_password(self, config):
        alpha = config.get_device_by_name("Alpha")
        # Alpha already stores exactly this password -> only Beta could match,
        # but Beta uses a different username -> empty.
        targets = collect_share_targets(config, "shared", "old-a",
                                        exclude_id=alpha["id"])
        assert targets == []

    def test_collect_and_apply(self, config):
        alpha = config.get_device_by_name("Alpha")
        config.update_device(config.get_device_by_name("Gamma")["id"],
                             username="shared")
        targets = collect_share_targets(config, "shared", "new-pw",
                                        exclude_id=alpha["id"])
        assert {d["name"] for d in targets} == {"Gamma"}
        assert apply_password(config, targets, "new-pw") == 1
        assert config.get_device_by_name("Gamma")["password"] == "new-pw"


def _patch_confirm(monkeypatch, accept: bool):
    """Make ModernShutdownConfirmDialog.exec return Accepted/Rejected."""
    from wol_app.views.shutdown_confirm_dialog import ModernShutdownConfirmDialog

    calls: list = []
    code = QDialog.DialogCode.Accepted if accept else QDialog.DialogCode.Rejected
    monkeypatch.setattr(
        ModernShutdownConfirmDialog, "exec",
        lambda self: (calls.append(self), code)[1])
    return calls


class TestModernDialogSharedPassword:
    def _open_edit(self, config, name):
        from wol_app.views.device_edit_dialog import ModernDeviceDialog

        device = config.get_device_by_name(name)
        dialog = ModernDeviceDialog(config, device=device)
        return dialog

    def test_yes_applies_to_same_user_devices(self, qapp, config, monkeypatch):
        calls = _patch_confirm(monkeypatch, accept=True)
        config.update_device(config.get_device_by_name("Gamma")["id"],
                             username="shared")
        dialog = self._open_edit(config, "Alpha")
        dialog.username_input.setText("shared")
        dialog.password_input.setText("new-pw")
        dialog._save()
        assert len(calls) == 1
        assert dialog.result() == QDialog.DialogCode.Accepted
        assert config.get_device_by_name("Alpha")["password"] == "new-pw"
        assert config.get_device_by_name("Gamma")["password"] == "new-pw"
        # Beta keeps its password (different user)
        assert config.get_device_by_name("Beta")["password"] == "old-b"

    def test_no_keeps_other_passwords(self, qapp, config, monkeypatch):
        calls = _patch_confirm(monkeypatch, accept=False)
        # give Gamma the same username so there is a target
        config.update_device(config.get_device_by_name("Gamma")["id"],
                             username="shared")
        dialog = self._open_edit(config, "Alpha")
        dialog.username_input.setText("shared")
        dialog.password_input.setText("new-pw")
        dialog._save()
        assert len(calls) == 1
        assert dialog.result() == QDialog.DialogCode.Accepted
        assert config.get_device_by_name("Alpha")["password"] == "new-pw"
        assert config.get_device_by_name("Gamma").get("password", "") == ""

    def test_no_popup_without_password(self, qapp, config, monkeypatch):
        calls = _patch_confirm(monkeypatch, accept=True)
        dialog = self._open_edit(config, "Alpha")
        dialog.username_input.setText("shared")
        dialog.password_input.setText("")
        dialog._save()
        assert calls == []

    def test_no_popup_when_all_identical(self, qapp, config, monkeypatch):
        calls = _patch_confirm(monkeypatch, accept=True)
        dialog = self._open_edit(config, "Alpha")
        dialog.username_input.setText("shared")
        dialog.password_input.setText("old-a")  # same as stored, no other matches
        dialog._save()
        assert calls == []

    def test_add_branch_offers_popup(self, qapp, config, monkeypatch):
        calls = _patch_confirm(monkeypatch, accept=True)
        from wol_app.views.device_edit_dialog import ModernDeviceDialog

        dialog = ModernDeviceDialog(config)
        dialog.name_input.setText("Delta")
        dialog.mac_input.setText("AA:BB:CC:00:00:04")
        dialog.username_input.setText("shared")
        dialog.password_input.setText("brand-new")
        dialog._save()
        assert len(calls) == 1
        assert config.get_device_by_name("Alpha")["password"] == "brand-new"

    def test_confirm_dialog_uses_primary_style(self, qapp, config, monkeypatch):
        calls = _patch_confirm(monkeypatch, accept=False)
        config.update_device(config.get_device_by_name("Gamma")["id"],
                             username="shared")
        dialog = self._open_edit(config, "Alpha")
        dialog.username_input.setText("shared")
        dialog.password_input.setText("another-pw")
        dialog._save()
        confirm = calls[0]
        assert confirm.yes_btn.objectName() == "primaryButton"
        assert confirm._show_icon is False


class TestClassicDialogSharedPassword:
    def _patch_question(self, monkeypatch, answer):
        from wol_app import device_dialog

        calls: list = []

        def fake_question(parent, title, text, buttons, *a, **k):
            calls.append((title, text))
            return answer

        monkeypatch.setattr(QMessageBox, "question",
                            staticmethod(fake_question))
        return calls

    def test_yes_applies_password(self, qapp, config, monkeypatch):
        from wol_app.device_dialog import DeviceDialog

        calls = self._patch_question(
            monkeypatch, QMessageBox.StandardButton.Yes)
        config.update_device(config.get_device_by_name("Gamma")["id"],
                             username="shared")
        device = config.get_device_by_name("Alpha")
        dialog = DeviceDialog(config, device=device)
        dialog.username_input.setText("shared")
        dialog.password_input.setText("classic-pw")
        dialog._save()
        assert len(calls) == 1
        assert "shared" in calls[0][1]
        assert config.get_device_by_name("Alpha")["password"] == "classic-pw"
        assert config.get_device_by_name("Gamma")["password"] == "classic-pw"

    def test_no_keeps_others(self, qapp, config, monkeypatch):
        from wol_app.device_dialog import DeviceDialog

        config.update_device(config.get_device_by_name("Gamma")["id"],
                             username="shared")
        self._patch_question(monkeypatch, QMessageBox.StandardButton.No)
        device = config.get_device_by_name("Alpha")
        dialog = DeviceDialog(config, device=device)
        dialog.username_input.setText("shared")
        dialog.password_input.setText("classic-pw")
        dialog._save()
        assert config.get_device_by_name("Alpha")["password"] == "classic-pw"
        assert config.get_device_by_name("Gamma").get("password", "") == ""

    def test_no_question_without_matches(self, qapp, config, monkeypatch):
        from wol_app.device_dialog import DeviceDialog

        calls = self._patch_question(
            monkeypatch, QMessageBox.StandardButton.Yes)
        device = config.get_device_by_name("Beta")  # user Other, no twin
        dialog = DeviceDialog(config, device=device)
        dialog.username_input.setText("Other")
        dialog.password_input.setText("solo-pw")
        dialog._save()
        assert calls == []
        assert config.get_device_by_name("Beta")["password"] == "solo-pw"


class TestApiKeyShareHelper:
    """The dashboard API key is offered to *every* other device.

    Unlike the password it is not scoped by username: the key belongs to the
    inference server (e.g. Strata started with ``API_Key dummy``), and the
    dashboard can only measure activity when the host service probes
    ``/metrics`` with it.
    """

    def test_no_targets_without_key(self, config):
        assert collect_api_key_share_targets(config, "") == []
        assert collect_api_key_share_targets(config, "   ") == []

    def test_targets_are_all_other_devices(self, config):
        alpha = config.get_device_by_name("Alpha")
        targets = collect_api_key_share_targets(config, "dummy",
                                                exclude_id=alpha["id"])
        assert {d["name"] for d in targets} == {"Beta", "Gamma"}

    def test_skips_devices_already_storing_the_key(self, config):
        config.set_device_api_key(config.get_device_by_name("Beta")["id"],
                                  "dummy")
        targets = collect_api_key_share_targets(config, "dummy")
        assert {d["name"] for d in targets} == {"Alpha", "Gamma"}

    def test_apply_api_key(self, config):
        targets = collect_api_key_share_targets(config, "dummy")
        assert apply_api_key(config, targets, "dummy") == 3
        for dev in config.get_devices():
            assert ConfigManager.get_device_api_key(dev) == "dummy"


class TestModernDialogApiKey:
    def _add_dialog(self, config, key):
        from wol_app.views.device_edit_dialog import ModernDeviceDialog

        dialog = ModernDeviceDialog(config)
        dialog.name_input.setText("Blade-18")
        dialog.mac_input.setText("AA:BB:CC:00:00:09")
        dialog.api_key_input.setText(key)
        return dialog

    def test_yes_applies_key_to_all_other_devices(self, qapp, config,
                                                  monkeypatch):
        calls = _patch_confirm(monkeypatch, accept=True)
        dialog = self._add_dialog(config, "dummy")
        dialog._save()
        assert len(calls) == 1
        blade = config.get_device_by_name("Blade-18")
        assert ConfigManager.get_device_api_key(blade) == "dummy"
        for name in ("Alpha", "Beta", "Gamma"):
            assert ConfigManager.get_device_api_key(
                config.get_device_by_name(name)) == "dummy"

    def test_no_keeps_other_keys_untouched(self, qapp, config, monkeypatch):
        calls = _patch_confirm(monkeypatch, accept=False)
        dialog = self._add_dialog(config, "dummy")
        dialog._save()
        assert len(calls) == 1
        assert ConfigManager.get_device_api_key(
            config.get_device_by_name("Blade-18")) == "dummy"
        assert ConfigManager.get_device_api_key(
            config.get_device_by_name("Alpha")) == ""

    def test_no_popup_without_key(self, qapp, config, monkeypatch):
        calls = _patch_confirm(monkeypatch, accept=True)
        self._add_dialog(config, "")._save()
        assert calls == []

    def test_no_popup_when_every_device_matches(self, qapp, config,
                                                monkeypatch):
        for dev in config.get_devices():
            config.set_device_api_key(dev["id"], "dummy")
        calls = _patch_confirm(monkeypatch, accept=True)
        dialog = self._add_dialog(config, "dummy")
        dialog._save()
        assert calls == []

    def test_edit_prefills_key_and_unchanged_save_stays_quiet(
            self, qapp, config, monkeypatch):
        from wol_app.views.device_edit_dialog import ModernDeviceDialog

        config.set_device_api_key(config.get_device_by_name("Alpha")["id"],
                                  "dummy")
        calls = _patch_confirm(monkeypatch, accept=True)
        dialog = ModernDeviceDialog(
            config, device=config.get_device_by_name("Alpha"))
        assert dialog.api_key_input.text() == "dummy"
        dialog._save()
        assert calls == []
        assert ConfigManager.get_device_api_key(
            config.get_device_by_name("Alpha")) == "dummy"

    def test_edit_new_key_prompts_for_other_devices(self, qapp, config,
                                                    monkeypatch):
        from wol_app.views.device_edit_dialog import ModernDeviceDialog

        calls = _patch_confirm(monkeypatch, accept=True)
        dialog = ModernDeviceDialog(
            config, device=config.get_device_by_name("Alpha"))
        dialog.api_key_input.setText("dummy")
        dialog._save()
        assert len(calls) == 1
        for name in ("Alpha", "Beta", "Gamma"):
            assert ConfigManager.get_device_api_key(
                config.get_device_by_name(name)) == "dummy"

    def test_edit_clearing_key_removes_it(self, qapp, config, monkeypatch):
        from wol_app.views.device_edit_dialog import ModernDeviceDialog

        config.set_device_api_key(config.get_device_by_name("Alpha")["id"],
                                  "dummy")
        calls = _patch_confirm(monkeypatch, accept=True)
        dialog = ModernDeviceDialog(
            config, device=config.get_device_by_name("Alpha"))
        dialog.api_key_input.clear()
        dialog._save()
        assert calls == []
        assert ConfigManager.get_device_api_key(
            config.get_device_by_name("Alpha")) == ""

    def test_edit_prefills_and_clears_field(self, qapp, config, monkeypatch):
        from wol_app.views.device_edit_dialog import ModernDeviceDialog

        _patch_confirm(monkeypatch, accept=False)
        d1 = config.add_device("Keyed", "AA:BB:CC:00:00:0A")
        config.set_device_api_key(d1["id"], "s3cret-key")
        edit = ModernDeviceDialog(config,
                                  device=config.get_device_by_id(d1["id"]))
        assert edit.api_key_input.text() == "s3cret-key"
        edit.api_key_input.setText("new-key")
        edit._save()
        assert ConfigManager.get_device_api_key(
            config.get_device_by_id(d1["id"])) == "new-key"
        # Secrets must not linger in the dialog after saving
        assert edit.api_key_input.text() == ""

    def test_edit_clearing_removes_key(self, qapp, config, monkeypatch):
        """Clearing the prefilled field is an explicit removal (like watch)."""
        from wol_app.views.device_edit_dialog import ModernDeviceDialog

        _patch_confirm(monkeypatch, accept=False)
        d1 = config.add_device("Keyed", "AA:BB:CC:00:00:0B")
        config.set_device_api_key(d1["id"], "keep-me")
        edit = ModernDeviceDialog(config,
                                  device=config.get_device_by_id(d1["id"]))
        edit.api_key_input.setText("")
        edit._save()
        assert ConfigManager.get_device_api_key(
            config.get_device_by_id(d1["id"])) == ""
        assert "api_key" not in config.get_device_by_id(d1["id"])

    def test_invalid_key_is_rejected(self, qapp, config, monkeypatch):
        from wol_app.views.device_edit_dialog import ModernDeviceDialog

        _patch_confirm(monkeypatch, accept=True)
        dialog = ModernDeviceDialog(config)
        dialog.name_input.setText("Nope")
        dialog.mac_input.setText("AA:BB:CC:00:00:0C")
        dialog.api_key_input.setText("x" * 200)
        with mock.patch("wol_app.views.device_edit_dialog.QMessageBox.warning"):
            dialog._save()
        assert config.get_device_by_name("Nope") is None
