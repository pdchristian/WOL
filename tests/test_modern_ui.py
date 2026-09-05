"""Smoke tests for the modern control-center window (offscreen, headless)."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("WOL_HEADLESS", "1")

import pytest  # noqa: E402

pytest.importorskip("PyQt6")

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
    cfg = ConfigManager(config_path=str(tmp_path / "config.json"))
    cfg.add_device("Workstation", "AA:BB:CC:00:11:22")
    cfg.update_device(cfg.get_devices()[0]["id"], ip="192.168.1.10")
    cfg.add_device("Media-Server", "AA:BB:CC:33:44:55")
    return cfg


class TestModernMainWindow:
    def test_instantiates_and_navigates(self, qapp, config):
        from wol_app.modern_main_window import ModernMainWindow

        window = ModernMainWindow(config, dark_mode=True)
        # 6 sidebar screens + the per-device dashboard (no sidebar entry)
        assert window.stack.count() == 7
        assert window.stack.currentIndex() == 0

        window._select_nav(1)
        assert window.stack.currentIndex() == 1
        assert window.nav_buttons[1].isChecked()
        assert not window.nav_buttons[0].isChecked()
        window.close()

    def test_open_dashboard_switches_stack_without_nav_entry(self, qapp, config, monkeypatch):
        from wol_app.modern_main_window import DASHBOARD_NAV_INDEX, ModernMainWindow
        from wol_app.views.dashboard_view import DeviceDashboardView

        # No real network polling from tests (set_device starts a poll).
        monkeypatch.setattr(DeviceDashboardView, "_poll_metrics", lambda self: None)

        window = ModernMainWindow(config, dark_mode=True)
        device_id = config.get_devices()[0]["id"]
        window.open_device_dashboard(device_id)
        assert window.stack.currentIndex() == DASHBOARD_NAV_INDEX
        # The dashboard is not a sidebar entry: no nav button stays checked
        assert not any(btn.isChecked() for btn in window.nav_buttons)
        assert not window.settings_btn.isChecked()
        assert not window.about_btn.isChecked()
        # Back returns to the devices screen
        window.dashboard_view.back_requested.emit()
        assert window.stack.currentIndex() == 0
        window.dashboard_view.cancel_workers()
        window.close()

    def test_manage_view_lists_devices(self, qapp, config):
        from wol_app.views.manage_view import DeviceRow, ManageView

        view = ManageView(config)
        rows = view._device_rows()
        assert len(rows) == 2
        # First row (name-sorted): Media-Server
        assert isinstance(rows[0], DeviceRow)
        assert rows[0].title.text() == "Media-Server"
        assert rows[0].device_id == config.get_devices()[1]["id"]
        # Fixed-height rows like the scan result list
        assert rows[0].height() == 64

    def test_manage_view_search_filter(self, qapp, config):
        from wol_app.views.manage_view import ManageView

        view = ManageView(config)
        view.search_input.setText("work")
        rows = view._device_rows()
        assert len(rows) == 1
        assert rows[0].title.text() == "Workstation"

    def test_device_row_status_dot(self, qapp, config):
        from wol_app.views.manage_view import ManageView

        view = ManageView(config)
        row = view._device_rows()[0]
        row.set_status("online")
        assert row.dot.objectName() == "dotOnline"
        row.set_status("offline")
        assert row.dot.objectName() == "dotOffline"
        row.set_status("unknown")
        assert row.dot.objectName() == "dotUnknown"

    def test_retranslate_does_not_raise(self, qapp, config):
        from wol_app.modern_main_window import ModernMainWindow

        window = ModernMainWindow(config, dark_mode=True)
        Translations.set_language("de")
        try:
            window._retranslate()
            assert "Verwalten" in window.nav_buttons[1].text()
        finally:
            Translations.set_language("en")
        window.close()

    def test_settings_nav_opens_native_screen(self, qapp, config):
        from wol_app.modern_main_window import SETTINGS_NAV_INDEX, ModernMainWindow

        window = ModernMainWindow(config, dark_mode=True)
        window.settings_btn.click()
        assert window.stack.currentIndex() == SETTINGS_NAV_INDEX
        assert window.settings_btn.isChecked()
        assert not any(btn.isChecked() for btn in window.nav_buttons)
        # Selecting an area un-checks the settings button again
        window._select_nav(1)
        assert not window.settings_btn.isChecked()
        window.close()


class TestSettingsView:
    def test_loads_current_values(self, qapp, config):
        from wol_app.views.settings_view import SettingsView

        config.update_network_settings(broadcast_ip="192.168.1.255",
                                       broadcast_port=7)
        view = SettingsView(config)
        assert view.broadcast_ip_input.text() == "192.168.1.255"
        assert view.broadcast_port_input.value() == 7
        assert view.language_combo.currentData() == "en"

    def test_save_persists_settings(self, qapp, config, monkeypatch):
        from PyQt6.QtWidgets import QMessageBox

        from wol_app.views.settings_view import SettingsView

        monkeypatch.setattr(QMessageBox, "information",
                            staticmethod(lambda *a, **k: None))
        view = SettingsView(config)
        view.broadcast_ip_input.setText("10.0.0.255")
        view.broadcast_port_input.setValue(19)
        view.max_logs_input.setValue(500)
        saved: list[bool] = []
        view.settings_saved.connect(lambda: saved.append(True))
        view._save()

        net = config.get_network_settings()
        assert net["broadcast_ip"] == "10.0.0.255"
        assert net["broadcast_port"] == 19
        assert config.get_max_logs() == 500
        assert saved == [True]

    def test_save_rejects_invalid_ip(self, qapp, config, monkeypatch):
        from PyQt6.QtWidgets import QMessageBox

        from wol_app.views.settings_view import SettingsView

        warnings: list[str] = []
        monkeypatch.setattr(
            QMessageBox, "warning",
            staticmethod(lambda *a, **k: warnings.append(a[1])))
        view = SettingsView(config)
        view.broadcast_ip_input.setText("999.1.1.1")
        view._save()
        assert warnings  # invalid IP rejected, nothing persisted
        assert config.get_network_settings()["broadcast_ip"] == "255.255.255.255"

    def test_reset_keeps_devices_clears_settings(self, qapp, config, monkeypatch):
        from PyQt6.QtWidgets import QMessageBox

        from wol_app.views.settings_view import SettingsView

        monkeypatch.setattr(QMessageBox, "question",
                            staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
        config.update_network_settings(broadcast_ip="10.0.0.255", broadcast_port=19)
        config.set_max_logs(500)
        view = SettingsView(config)
        view._reset_to_defaults()

        net = config.get_network_settings()
        assert net["broadcast_ip"] == "255.255.255.255"
        assert config.get_max_logs() == 100
        # Devices are kept
        assert len(config.get_devices()) == 2

    def test_reset_declined_changes_nothing(self, qapp, config, monkeypatch):
        from PyQt6.QtWidgets import QMessageBox

        from wol_app.views.settings_view import SettingsView

        monkeypatch.setattr(QMessageBox, "question",
                            lambda *a, **k: QMessageBox.StandardButton.No)
        config.update_network_settings(broadcast_ip="10.0.0.255")
        view = SettingsView(config)
        view._reset_to_defaults()
        assert config.get_network_settings()["broadcast_ip"] == "10.0.0.255"


class TestUpdateView:
    def test_shows_app_name_and_version(self, qapp, config):
        from wol_app import __version__
        from wol_app.views.update_view import UpdateView

        view = UpdateView(config)
        assert view.app_name.text() == Translations.tr("app.name")
        assert __version__ in view.version_label.text()
        assert view.check_btn.isEnabled()

    def test_check_result_up_to_date(self, qapp, config):
        from wol_app.views.update_view import UpdateView

        view = UpdateView(config)
        view._on_check_finished(({"tag_name": "v99.0.0"}, False))
        assert view.status_label.text() == Translations.tr("modern.update.up_to_date")

    def test_check_result_error(self, qapp, config):
        from wol_app.views.update_view import UpdateView

        view = UpdateView(config)
        view._on_check_finished(None)
        assert Translations.tr("update_error.check_failed") in view.status_label.text()

    def test_about_nav_opens_native_screen(self, qapp, config, monkeypatch):
        from wol_app import modern_main_window
        from wol_app.views.update_view import UpdateView

        # No network / no threads in headless mode
        window = modern_main_window.ModernMainWindow(config, dark_mode=True)
        assert isinstance(window.update_view, UpdateView)
        # The "Updates prüfen" sidebar entry was removed — the update check
        # lives on the native "Über" screen.
        assert not hasattr(window, "update_btn")

        window.about_btn.click()
        assert window.stack.currentIndex() == modern_main_window.UPDATE_NAV_INDEX
        assert window.about_btn.isChecked()
        assert not window.settings_btn.isChecked()
        assert not any(btn.isChecked() for btn in window.nav_buttons)

        # Selecting an area un-checks the footer entry again
        window._select_nav(0)
        assert not window.about_btn.isChecked()
        window.close()

    def test_retranslate_does_not_raise(self, qapp, config):
        from wol_app.views.update_view import UpdateView

        view = UpdateView(config)
        Translations.set_language("de")
        try:
            view.retranslate()
            assert Translations.tr("modern.update.button.check") == \
                view.check_btn.text()
        finally:
            Translations.set_language("en")


class TestToggleSwitch:
    def test_toggle_emits_and_flips_state(self, qapp):
        from wol_app.widgets.toggle_switch import ToggleSwitch

        toggle = ToggleSwitch(checked=False)
        seen: list[bool] = []
        toggle.toggled.connect(seen.append)

        toggle.toggle()
        assert toggle.isChecked() is True
        assert seen == [True]

        toggle.toggle()
        assert toggle.isChecked() is False
        assert seen == [True, False]

    def test_set_checked_does_not_emit(self, qapp):
        from wol_app.widgets.toggle_switch import ToggleSwitch

        toggle = ToggleSwitch(checked=False)
        seen: list[bool] = []
        toggle.toggled.connect(seen.append)
        toggle.setChecked(True)
        assert toggle.isChecked() is True
        assert seen == []


class TestScheduleView:
    @pytest.fixture()
    def schedule_config(self, config):
        dev = config.get_devices()[0]
        config.add_schedule(dev["id"], 8, 30, ["Mon", "Tue", "Wed", "Thu", "Fri"])
        dev2 = config.get_devices()[1]
        config.add_schedule(dev2["id"], 20, 0, [], action="shutdown", enabled=False)
        return config

    def test_lists_schedules_sorted_by_time(self, qapp, schedule_config):
        from wol_app.views.schedule_view import ScheduleView

        view = ScheduleView(schedule_config)
        rows = view._schedule_rows()
        assert len(rows) == 2
        # Sorted by time: 08:30 before 20:00
        assert "08:30" in rows[0].mono.text()
        assert "20:00" in rows[1].mono.text()
        assert rows[0].height() == 64

    def test_subtitle_contains_days_and_action(self, qapp, schedule_config):
        from wol_app.views.schedule_view import ScheduleView

        view = ScheduleView(schedule_config)
        rows = view._schedule_rows()
        assert Translations.tr("modern.schedule.days.weekdays") in rows[0].mono.text()
        assert Translations.tr("modern.schedule.action.wake") in rows[0].mono.text()
        assert Translations.tr("modern.schedule.days.every") in rows[1].mono.text()
        assert Translations.tr("modern.schedule.action.shutdown") in rows[1].mono.text()

    def test_search_filter(self, qapp, schedule_config):
        from wol_app.views.schedule_view import ScheduleView

        view = ScheduleView(schedule_config)
        view.search_input.setText("server")
        rows = view._schedule_rows()
        assert len(rows) == 1
        assert rows[0].title.text() == "Media-Server"

    def test_toggle_updates_config(self, qapp, schedule_config):
        from wol_app.views.schedule_view import ScheduleView

        view = ScheduleView(schedule_config)
        row = view._schedule_rows()[0]
        assert row.toggle.isChecked() is True
        row.toggle.toggle()
        schedules = schedule_config.get_schedules()
        target = next(s for s in schedules if s["id"] == row.schedule_id)
        assert target["enabled"] is False

    def test_disabled_schedule_title_style(self, qapp, schedule_config):
        from wol_app.views.schedule_view import ScheduleView

        view = ScheduleView(schedule_config)
        # Second schedule was created with enabled=False
        row = view._schedule_rows()[1]
        assert row.title.objectName() == "rowTitleDisabled"
        assert row.toggle.isChecked() is False

    def test_delete_removes_schedule(self, qapp, schedule_config, monkeypatch):
        from PyQt6.QtWidgets import QMessageBox

        from wol_app.views.schedule_view import ScheduleView

        monkeypatch.setattr(QMessageBox, "question",
                            staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
        view = ScheduleView(schedule_config)
        row = view._schedule_rows()[0]
        view._delete_schedule(row.schedule_id)
        assert len(schedule_config.get_schedules()) == 1
        assert len(view._schedule_rows()) == 1

    def test_empty_state_visible_without_schedules(self, qapp, config):
        from wol_app.views.schedule_view import ScheduleView

        view = ScheduleView(config)
        assert len(view._schedule_rows()) == 0
        assert view.empty_label.isVisibleTo(view)

    def test_retranslate_does_not_raise(self, qapp, schedule_config):
        from wol_app.views.schedule_view import ScheduleView

        view = ScheduleView(schedule_config)
        Translations.set_language("de")
        try:
            view.retranslate()
            assert view.title.text() == "Zeitplan"
        finally:
            Translations.set_language("en")

    def test_modern_window_uses_native_schedule_page(self, qapp, config):
        from wol_app.modern_main_window import ModernMainWindow
        from wol_app.views.schedule_view import ScheduleView

        window = ModernMainWindow(config, dark_mode=True)
        assert isinstance(window.schedule_view, ScheduleView)
        window._select_nav(2)
        assert window.stack.currentWidget() is window.schedule_view
        window.close()


class TestScheduleRunner:
    def test_wake_dispatches_to_engine(self, config):
        from wol_app.schedule_runner import dispatch_schedule_action

        calls: list[tuple] = []

        class FakeEngine:
            def send_wake_packet(self, device_id):
                calls.append(("wake", device_id))

        dev = config.get_devices()[0]
        dispatch_schedule_action(config, FakeEngine(), dev["id"], "wake")
        assert calls == [("wake", dev["id"])]

    def test_shutdown_unknown_device_logs_status(self, config):
        from wol_app.schedule_runner import dispatch_schedule_action

        msgs: list[str] = []
        dispatch_schedule_action(
            config, None, "missing-id", "shutdown",
            lambda msg, _ms=0: msgs.append(msg),
        )
        assert msgs
        assert Translations.tr("status.device_not_found", device_id="missing-id") == msgs[0]


class TestModernDeviceDialog:
    def test_add_device_persists_and_emits(self, qapp, config):
        from wol_app.views.device_edit_dialog import ModernDeviceDialog

        dialog = ModernDeviceDialog(config)
        saved: list[dict] = []
        dialog.device_saved.connect(saved.append)
        dialog.name_input.setText("Gaming-PC")
        dialog.mac_input.setText("AA:BB:CC:66:77:88")
        dialog.ip_input.setText("192.168.1.15")
        dialog._save()
        assert dialog.result() == QDialog.DialogCode.Accepted
        assert len(saved) == 1
        assert saved[0]["name"] == "Gaming-PC"
        assert saved[0]["ip"] == "192.168.1.15"
        assert len(config.get_devices()) == 3

    def test_edit_device_updates_config(self, qapp, config):
        from wol_app.views.device_edit_dialog import ModernDeviceDialog

        device = config.get_devices()[0]
        dialog = ModernDeviceDialog(config, device=device)
        assert dialog.name_input.text() == "Workstation"
        assert dialog.enabled_toggle.isChecked() is True
        dialog.name_input.setText("Workstation 2")
        dialog.enabled_toggle.setChecked(False)
        dialog._save()
        updated = config.get_device_by_id(device["id"])
        assert updated["name"] == "Workstation 2"
        assert updated["enabled"] is False

    def test_missing_name_rejected(self, qapp, config, monkeypatch):
        from PyQt6.QtWidgets import QMessageBox

        from wol_app.views.device_edit_dialog import ModernDeviceDialog

        monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))
        dialog = ModernDeviceDialog(config)
        dialog.mac_input.setText("AA:BB:CC:DD:EE:FF")
        dialog._save()
        assert dialog.result() != QDialog.DialogCode.Accepted
        assert len(config.get_devices()) == 2

    def test_invalid_mac_rejected(self, qapp, config, monkeypatch):
        from PyQt6.QtWidgets import QMessageBox

        from wol_app.views.device_edit_dialog import ModernDeviceDialog

        monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))
        dialog = ModernDeviceDialog(config)
        dialog.name_input.setText("Rig")
        dialog.mac_input.setText("not-a-mac")
        dialog._save()
        assert dialog.result() != QDialog.DialogCode.Accepted
        assert len(config.get_devices()) == 2

    def test_preset_prefills_fields(self, qapp, config):
        from wol_app.views.device_edit_dialog import ModernDeviceDialog

        dialog = ModernDeviceDialog(
            config, preset={"name": "NAS", "mac": "11:22:33:44:55:66",
                            "ip": "192.168.1.30"},
        )
        assert dialog.name_input.text() == "NAS"
        assert dialog.mac_input.text() == "11:22:33:44:55:66"
        assert dialog.ip_input.text() == "192.168.1.30"

    def test_watch_processes_roundtrip(self, qapp, config):
        """The watched-processes field persists on save and prefills on edit."""
        from wol_app.views.device_edit_dialog import ModernDeviceDialog

        dialog = ModernDeviceDialog(config)
        dialog.name_input.setText("AI-Server")
        dialog.mac_input.setText("AA:BB:CC:11:22:33")
        dialog.watch_input.setText("llama-server.exe:8080, ollama.exe")
        dialog._save()
        device = next(d for d in config.get_devices()
                      if d["name"] == "AI-Server")
        assert config.get_device_watch_processes(device) == [
            "llama-server.exe:8080", "ollama.exe"]
        # Reopen for editing -> prefilled, and clearing it persists as empty
        edit = ModernDeviceDialog(config, device=device)
        assert edit.watch_input.text() == "llama-server.exe:8080, ollama.exe"
        edit.watch_input.setText("")
        edit._save()
        assert config.get_device_watch_processes(
            config.get_device_by_id(device["id"])) == []

    def test_uses_modern_dialog_in_views(self, qapp, config):
        """The modern manage/devices views open the modern dialog."""
        from wol_app.views import devices_view, manage_view

        assert manage_view.ModernDeviceDialog is devices_view.ModernDeviceDialog
        assert not hasattr(manage_view, "DeviceDialog")


class TestModernScheduleEditDialog:
    def test_day_labels_are_translated(self, qapp, config):
        from wol_app.views.schedule_edit_dialog import ModernScheduleEditDialog

        Translations.set_language("de")
        try:
            dialog = ModernScheduleEditDialog(config, config.get_devices())
            labels = [cb.text() for cb in dialog.day_checks.values()]
            assert labels == ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
        finally:
            Translations.set_language("en")

    def test_day_data_keys_stay_english(self, qapp, config):
        from wol_app.views.schedule_edit_dialog import DAYS, ModernScheduleEditDialog

        dialog = ModernScheduleEditDialog(config, config.get_devices())
        assert list(dialog.day_checks.keys()) == DAYS
        assert DAYS == ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    def test_save_creates_schedule(self, qapp, config):
        from wol_app.views.schedule_edit_dialog import ModernScheduleEditDialog

        dev = config.get_devices()[0]
        dialog = ModernScheduleEditDialog(config, config.get_devices())
        dialog.device_combo.setCurrentIndex(
            dialog.device_combo.findData(dev["id"])
        )
        dialog.hour_spin.setValue(7)
        dialog.minute_spin.setValue(15)
        for day, cb in dialog.day_checks.items():
            cb.setChecked(day in ("Mon", "Wed"))
        dialog._save()
        assert dialog.result() == QDialog.DialogCode.Accepted
        sched = config.get_schedules()[0]
        assert sched["device_id"] == dev["id"]
        assert (sched["hour"], sched["minute"]) == (7, 15)
        assert sched["days"] == ["Mon", "Wed"]
        assert sched["enabled"] is True

    def test_no_days_shows_warning(self, qapp, config, monkeypatch):
        from PyQt6.QtWidgets import QMessageBox

        from wol_app.views.schedule_edit_dialog import ModernScheduleEditDialog

        monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))
        dialog = ModernScheduleEditDialog(config, config.get_devices())
        for cb in dialog.day_checks.values():
            cb.setChecked(False)
        dialog._save()
        assert dialog.result() != QDialog.DialogCode.Accepted
        assert len(config.get_schedules()) == 0
