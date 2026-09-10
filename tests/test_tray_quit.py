"""Tests for the "keep running in the notification area" feature (tray).

Covers the config round-trip (ui.close_to_tray), the optional third
"Minimieren" button on the quit confirmation dialog, the window's
hide-to-tray / quit routing, and the modern settings toggle.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("WOL_HEADLESS", "1")

import pytest  # noqa: E402

pytest.importorskip("PyQt6")

from PyQt6.QtCore import QTimer  # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog  # noqa: E402

from wol_app.config import ConfigManager  # noqa: E402
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


class TestCloseToTrayConfig:
    def test_default_is_on(self, config):
        assert config.get_close_to_tray() is True

    def test_roundtrip(self, config):
        config.set_close_to_tray(True)
        assert config.get_close_to_tray() is True
        config.set_close_to_tray(False)
        assert config.get_close_to_tray() is False


class TestQuitDialogMinimizeButton:
    def _buttons(self, dialog):
        from PyQt6.QtWidgets import QPushButton

        return dialog.findChildren(QPushButton)

    def test_without_min_key_two_buttons(self, qapp):
        from wol_app.views.shutdown_confirm_dialog import (
            ModernShutdownConfirmDialog,
        )

        dialog = ModernShutdownConfirmDialog(
            "", None,
            title_key="modern.quit_confirm.title",
            message_key="modern.quit_confirm.message",
            yes_key="modern.quit_confirm.yes",
            no_key="modern.quit_confirm.no",
        )
        assert dialog.min_btn is None
        assert len(self._buttons(dialog)) == 2

    def test_with_min_key_three_buttons_and_order(self, qapp):
        from wol_app.views.shutdown_confirm_dialog import (
            ModernShutdownConfirmDialog,
        )

        dialog = ModernShutdownConfirmDialog(
            "", None,
            title_key="modern.quit_confirm.title",
            message_key="modern.quit_confirm.message",
            yes_key="modern.quit_confirm.yes",
            no_key="modern.quit_confirm.no",
            min_key="modern.quit_confirm.minimize",
        )
        assert dialog.min_btn is not None
        assert len(self._buttons(dialog)) == 3
        # Order: Ja / Minimieren / Nein (left to right).
        texts = [b.text() for b in self._buttons(dialog)]
        assert texts == [
            Translations.tr("modern.quit_confirm.yes"),
            Translations.tr("modern.quit_confirm.minimize"),
            Translations.tr("modern.quit_confirm.no"),
        ]

    def test_minimize_button_returns_code(self, qapp):
        from wol_app.views.shutdown_confirm_dialog import (
            MINIMIZE_RESULT_CODE,
            ModernShutdownConfirmDialog,
        )

        dialog = ModernShutdownConfirmDialog(
            "", None,
            title_key="modern.quit_confirm.title",
            message_key="modern.quit_confirm.message",
            yes_key="modern.quit_confirm.yes",
            no_key="modern.quit_confirm.no",
            min_key="modern.quit_confirm.minimize",
        )
        QTimer.singleShot(0, dialog.min_btn.click)
        assert dialog.exec() == MINIMIZE_RESULT_CODE

    def test_yes_and_no_results_unchanged(self, qapp):
        from wol_app.views.shutdown_confirm_dialog import (
            ModernShutdownConfirmDialog,
        )

        for btn, expected in (
            ("yes_btn", QDialog.DialogCode.Accepted),
            ("no_btn", QDialog.DialogCode.Rejected),
        ):
            dialog = ModernShutdownConfirmDialog(
                "", None,
                title_key="modern.quit_confirm.title",
                message_key="modern.quit_confirm.message",
                yes_key="modern.quit_confirm.yes",
                no_key="modern.quit_confirm.no",
                min_key="modern.quit_confirm.minimize",
            )
            QTimer.singleShot(0, getattr(dialog, btn).click)
            assert dialog.exec() == expected


class TestCloseToTrayWindow:
    @pytest.fixture()
    def window(self, qapp, config, monkeypatch):
        """Modern window with a simulated tray (offscreen has none)."""
        from wol_app.modern_main_window import ModernMainWindow

        monkeypatch.setattr(
            ModernMainWindow, "_tray_supported", staticmethod(lambda: True))
        window = ModernMainWindow(config, dark_mode=True)
        window.show()
        yield window
        # Never let a test quit the app or leave the tray icon behind.
        window._quitting = True
        if window._tray is not None:
            window._tray.hide()
        window.close()

    def test_inactive_when_setting_off(self, window, config):
        config.set_close_to_tray(False)
        assert window._close_to_tray_active() is False

    def test_active_when_setting_on(self, window, config):
        config.set_close_to_tray(True)
        assert window._close_to_tray_active() is True

    def test_close_hides_instead_of_closing(self, window, config, monkeypatch):
        config.set_close_to_tray(True)
        window._apply_tray_mode()
        stopped: list[bool] = []
        monkeypatch.setattr(
            window.engine, "stop_scheduler",
            lambda: stopped.append(True))

        window.close()

        assert window.isHidden()
        assert window._tray is not None and window._tray.isVisible()
        # Cleanup must NOT have run — the app keeps working in the tray.
        assert stopped == []

    def test_show_from_tray_restores_window(self, window, config):
        config.set_close_to_tray(True)
        window._hide_to_tray()
        assert window.isHidden()
        window._show_from_tray()
        assert not window.isHidden()

    def test_show_from_tray_hides_the_icon_again(self, window, config):
        """While the window is visible there is exactly one app symbol."""
        config.set_close_to_tray(True)
        window._hide_to_tray()
        assert window._tray is not None and window._tray.isVisible()
        window._show_from_tray()
        assert not window._tray.isVisible()

    def test_about_to_quit_hides_the_icon(self, window, config, monkeypatch):
        """Every exit path (incl. the update flow) removes the tray icon."""
        config.set_close_to_tray(True)
        window._hide_to_tray()
        assert window._tray is not None and window._tray.isVisible()

        # Simulate the process ending (QApplication.aboutToQuit) without
        # routing through _quit_application — the update-install path.
        monkeypatch.setattr(window, "close", lambda: None)
        qapp = QApplication.instance()
        qapp.aboutToQuit.emit()
        assert not window._tray.isVisible()

    def test_quit_bypasses_tray_and_closes(self, window, config, monkeypatch):
        config.set_close_to_tray(True)
        window._apply_tray_mode()
        stopped: list[bool] = []
        monkeypatch.setattr(
            window.engine, "stop_scheduler",
            lambda: stopped.append(True))
        quit_calls: list[bool] = []
        monkeypatch.setattr(
            QApplication, "quit", lambda self: quit_calls.append(True))

        window._quit_application()

        assert stopped == [True]
        assert quit_calls == [True]
        assert not window._tray.isVisible()

    def test_close_still_closes_when_setting_off(self, window, config, monkeypatch):
        config.set_close_to_tray(False)
        window._apply_tray_mode()
        stopped: list[bool] = []
        monkeypatch.setattr(
            window.engine, "stop_scheduler",
            lambda: stopped.append(True))
        window.close()
        assert stopped == [True]
        assert window._tray is None

    def test_confirm_quit_routing(self, window, config, monkeypatch):
        """Dialog result 1/2/0 routes to quit / hide / nothing."""
        import wol_app.modern_main_window as mmw
        from wol_app.views.shutdown_confirm_dialog import MINIMIZE_RESULT_CODE

        config.set_close_to_tray(True)

        actions: list[str] = []
        monkeypatch.setattr(
            window, "_quit_application", lambda: actions.append("quit"))
        monkeypatch.setattr(
            window, "_hide_to_tray", lambda: actions.append("minimize"))

        results = iter([
            QDialog.DialogCode.Accepted,
            MINIMIZE_RESULT_CODE,
            QDialog.DialogCode.Rejected,
        ])

        class _StubDialog:
            def __init__(self, *a, **k):
                self.min_key = k.get("min_key")

            def exec(self):
                assert self.min_key == "modern.quit_confirm.minimize"
                return next(results)

        monkeypatch.setattr(mmw, "ModernShutdownConfirmDialog", _StubDialog)
        window._confirm_quit()
        window._confirm_quit()
        window._confirm_quit()
        assert actions == ["quit", "minimize"]

    def test_confirm_quit_without_tray_has_no_min_button(
            self, window, config, monkeypatch):
        """Setting off → dialog is created without min_key (plain Ja/Nein)."""
        import wol_app.modern_main_window as mmw

        config.set_close_to_tray(False)

        seen: list = []

        class _StubDialog:
            def __init__(self, *a, **k):
                seen.append(k.get("min_key"))

            def exec(self):
                return QDialog.DialogCode.Rejected

        monkeypatch.setattr(mmw, "ModernShutdownConfirmDialog", _StubDialog)
        window._confirm_quit()
        assert seen == [None]


class TestSettingsViewCloseToTray:
    def test_toggle_loads_and_saves(self, qapp, config, monkeypatch):
        from PyQt6.QtWidgets import QMessageBox

        from wol_app.views.settings_view import SettingsView

        monkeypatch.setattr(QMessageBox, "information",
                            staticmethod(lambda *a, **k: None))
        config.set_close_to_tray(True)
        view = SettingsView(config)
        assert view.close_to_tray_toggle.isChecked() is True

        view.close_to_tray_toggle.setChecked(False)
        view._save()
        assert config.get_close_to_tray() is False

    def test_save_does_not_require_restart(self, qapp, config, monkeypatch):
        from PyQt6.QtWidgets import QMessageBox

        from wol_app.views.settings_view import SettingsView

        monkeypatch.setattr(QMessageBox, "information",
                            staticmethod(lambda *a, **k: None))
        view = SettingsView(config)
        view.close_to_tray_toggle.setChecked(True)
        view._save()
        assert view.restart_required is False

    def test_reset_restores_default_on(self, qapp, config, monkeypatch):
        from PyQt6.QtWidgets import QMessageBox

        from wol_app.views.settings_view import SettingsView

        monkeypatch.setattr(QMessageBox, "question",
                            staticmethod(
                                lambda *a, **k: QMessageBox.StandardButton.Yes))
        config.set_close_to_tray(False)
        view = SettingsView(config)
        view._reset_to_defaults()
        assert config.get_close_to_tray() is True
