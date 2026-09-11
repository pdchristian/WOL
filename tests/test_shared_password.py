"""Tests for the shared-password feature (apply password to same-username devices).

Covers: ConfigManager.get_devices_by_username, the shared helper module, the
modern device dialog (ModernShutdownConfirmDialog Ja/Nein) and the classic
DeviceDialog (QMessageBox.question).
"""

import os

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
    apply_password,
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
