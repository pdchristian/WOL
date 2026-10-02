"""Tests for the modern devices screen (DevicesView / DeviceCard)."""

import json
import os
from pathlib import Path

# Grid tests show() the view — keep those windows offscreen so no real
# windows flash during the suite (same pattern as test_sidebar.py).
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("WOL_HEADLESS", "1")

import pytest

from wol_app.config import ConfigManager
from wol_app.translations import Translations

pytest.importorskip("PyQt6")

from PyQt6.QtWidgets import QApplication  # noqa: E402

from wol_app.config import DEVICES_VIEW_LIST  # noqa: E402
from wol_app.views.devices_view import (  # noqa: E402
    CARD_MIN_WIDTH,
    GRID_SPACING,
    PAGE_MARGIN_H,
    DeviceCard,
    DeviceListRow,
    DevicesView,
)

# Translation keys asserted below — must exist in every locale so the
# locale-synchronous assertions never fall back to the raw key string.
_ACTION_KEYS = ("modern.devices.button.wake", "button.shutdown")
_NAME_KEYS = ("device.me", "device.disabled")


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(scope="module", autouse=True)
def _translations():
    from wol_app.translations import Translations

    Translations().load("de")


@pytest.fixture
def tmp_config(tmp_path):
    cfg_path = tmp_path / "devices.json"
    return ConfigManager(str(cfg_path))


@pytest.fixture
def config_with_devices(tmp_config):
    tmp_config.config["devices"] = [
        {"id": "d1", "name": "Desktop", "mac": "AA:BB:CC:DD:EE:01", "ip": "192.168.1.10", "enabled": True},
        {"id": "d2", "name": "Server", "mac": "AA:BB:CC:DD:EE:02", "ip": "192.168.1.20", "enabled": True},
        {"id": "d3", "name": "Laptop", "mac": "AA:BB:CC:DD:EE:03", "ip": "192.168.1.30", "enabled": False},
    ]
    return tmp_config


class TestDeviceCard:
    def test_offline_card_shows_wake_button(self, qapp, config_with_devices):
        card = DeviceCard(config_with_devices.config["devices"][0], "offline", set())
        assert card.action_btn.text() == Translations.tr("modern.devices.button.wake")
        assert card.action_btn.objectName() == "wakeButton"
        assert card.pill.dot.objectName() == "pillDotOffline"

    def test_online_card_shows_shutdown_button(self, qapp, config_with_devices):
        card = DeviceCard(config_with_devices.config["devices"][0], "online", set())
        assert card.action_btn.text() == Translations.tr("button.shutdown")
        assert card.action_btn.objectName() == "shutdownButton"
        assert card.pill.dot.objectName() == "pillDotOnline"

    def test_status_swap_updates_button(self, qapp, config_with_devices):
        card = DeviceCard(config_with_devices.config["devices"][0], "offline", set())
        card.set_status("online")
        assert card.action_btn.objectName() == "shutdownButton"
        card.set_status("unknown")
        assert card.action_btn.objectName() == "wakeButton"
        assert card.pill.dot.objectName() == "pillDotUnknown"

    def test_action_click_emits_wake_or_shutdown(self, qapp, config_with_devices):
        card = DeviceCard(config_with_devices.config["devices"][0], "offline", set())
        fired = []
        card.wake_requested.connect(lambda did: fired.append(("wake", did)))
        card.shutdown_requested.connect(lambda did: fired.append(("shutdown", did)))
        card._action_clicked()  # offline -> wake
        card.set_status("online")
        card._action_clicked()  # online -> shutdown
        assert fired == [("wake", "d1"), ("shutdown", "d1")]

    def test_local_device_marked_with_me(self, qapp, config_with_devices):
        card = DeviceCard(
            config_with_devices.config["devices"][0], "unknown", {"192.168.1.10"})
        assert Translations.tr("device.me") in card.title.text()

    def test_disabled_device_buttons_disabled(self, qapp, config_with_devices):
        card = DeviceCard(config_with_devices.config["devices"][2], "unknown", set())
        assert not card.action_btn.isEnabled()
        assert not card.remote_fs_btn.isEnabled()
        assert not card.remote_win_btn.isEnabled()
        assert Translations.tr("device.disabled") in card.title.text()

    def test_remote_buttons_emit_signal(self, qapp, config_with_devices):
        card = DeviceCard(config_with_devices.config["devices"][0], "unknown", set())
        fired = []
        card.remote_requested.connect(lambda did, fs: fired.append((did, fs)))
        card.remote_fs_btn.click()
        card.remote_win_btn.click()
        assert fired == [("d1", True), ("d1", False)]


class TestDeviceListRow:
    """List row: power icon button (wake ↔ shutdown) at the far right."""

    def test_offline_row_shows_wake_icon_button(self, qapp, config_with_devices):
        row = DeviceListRow(config_with_devices.config["devices"][0], "offline", set())
        assert row.action_btn.objectName() == "wakeIconButton"
        assert row.action_btn.toolTip() == Translations.tr("modern.devices.button.wake")
        assert row.dot.objectName() == "dotOffline"

    def test_online_row_shows_shutdown_icon_button(self, qapp, config_with_devices):
        row = DeviceListRow(config_with_devices.config["devices"][0], "online", set())
        assert row.action_btn.objectName() == "shutdownIconButton"
        assert row.action_btn.toolTip() == Translations.tr("button.shutdown")
        assert row.dot.objectName() == "dotOnline"

    def test_status_swap_updates_icon_button(self, qapp, config_with_devices):
        row = DeviceListRow(config_with_devices.config["devices"][0], "offline", set())
        row.set_status("online")
        assert row.action_btn.objectName() == "shutdownIconButton"
        row.set_status("unknown")
        assert row.action_btn.objectName() == "wakeIconButton"
        assert row.dot.objectName() == "dotUnknown"

    def test_action_click_emits_wake_or_shutdown(self, qapp, config_with_devices):
        row = DeviceListRow(config_with_devices.config["devices"][0], "offline", set())
        fired = []
        row.wake_requested.connect(lambda did: fired.append(("wake", did)))
        row.shutdown_requested.connect(lambda did: fired.append(("shutdown", did)))
        row._action_clicked()  # offline -> wake
        row.set_status("online")
        row._action_clicked()  # online -> shutdown
        assert fired == [("wake", "d1"), ("shutdown", "d1")]

    def test_disabled_device_action_button_disabled(self, qapp, config_with_devices):
        row = DeviceListRow(config_with_devices.config["devices"][2], "unknown", set())
        assert not row.action_btn.isEnabled()

    def test_view_rows_wired_to_wake_and_shutdown(self, qapp, config_with_devices):
        """DeviceListRow signals are connected to the same flows as the cards."""
        view = DevicesView(config_with_devices)
        row = view._rows["d1"]
        fired = []
        # Disconnect the real flows for this assertion and watch the signal.
        row.wake_requested.disconnect()
        row.shutdown_requested.disconnect()
        row.wake_requested.connect(lambda did: fired.append(("wake", did)))
        row.shutdown_requested.connect(lambda did: fired.append(("shutdown", did)))
        row.set_status("offline")
        row._action_clicked()
        row.set_status("online")
        row._action_clicked()
        assert fired == [("wake", "d1"), ("shutdown", "d1")]
        view.cancel_workers()
        view.deleteLater()


class TestDevicesView:
    def test_cards_built_for_all_devices(self, qapp, config_with_devices):
        view = DevicesView(config_with_devices)
        assert set(view._cards) == {"d1", "d2", "d3"}

    def test_summary_counts_devices_and_online(self, qapp, config_with_devices):
        view = DevicesView(config_with_devices)
        view._statuses = {"d1": "online", "d2": "offline", "d3": "unknown"}
        view._update_summary()
        assert "3" in view.subtitle.text()
        assert "1" in view.subtitle.text()

    def test_search_filters_cards(self, qapp, config_with_devices):
        view = DevicesView(config_with_devices)
        view.search_input.setText("Server")
        assert set(view._cards) == {"d2"}
        view.search_input.setText("")
        assert set(view._cards) == {"d1", "d2", "d3"}

    def test_statuses_finished_updates_cards(self, qapp, config_with_devices):
        view = DevicesView(config_with_devices)
        results = [("d1", "Desktop", "online", ""), ("d2", "Server", "offline", "")]
        view._on_statuses_finished(results)
        assert view._cards["d1"].action_btn.objectName() == "shutdownButton"
        assert view._cards["d2"].action_btn.objectName() == "wakeButton"

    def test_empty_state_visible_without_devices(self, qapp, tmp_config):
        view = DevicesView(tmp_config)
        assert view.empty_label.isVisibleTo(view)

    def test_retranslate_keeps_status_text(self, qapp, config_with_devices):
        view = DevicesView(config_with_devices)
        view._on_statuses_finished([("d1", "Desktop", "online", "")])
        view.retranslate()
        assert view._cards["d1"].action_btn.text() == Translations.tr("button.shutdown")


class TestGridColumnCount:
    """Column count comes from the *real* viewport width — never a pre-layout guess.

    Regression: measuring in the constructor (before Qt lays the widget out)
    produced a bogus column count that visibly "jumped" to more/other columns
    on the first window resize.
    """

    @staticmethod
    def _expected_cols(viewport_w: int) -> int:
        avail = max(viewport_w - 2 * PAGE_MARGIN_H, CARD_MIN_WIDTH)
        return max(1, (avail + GRID_SPACING) // (CARD_MIN_WIDTH + GRID_SPACING))

    @pytest.fixture()
    def shown_view(self, qapp, config_with_devices, monkeypatch):
        """DevicesView factory: shown at a given width with pings silenced."""
        views = []

        def _make(width: int) -> DevicesView:
            view = DevicesView(config_with_devices)
            # showEvent triggers refresh_statuses → skip real ICMP pings in tests
            monkeypatch.setattr(view, "refresh_statuses", lambda: None)
            view.resize(width, 700)
            view.show()
            qapp.processEvents()  # includes the deferred singleShot reflow
            views.append(view)
            return view

        yield _make
        for v in views:
            v.cancel_workers()
            v.deleteLater()

    def test_unmeasured_view_uses_placeholder_not_bogus_count(self, qapp, config_with_devices):
        # Not shown yet → viewport has no width: cards stack in one column and
        # the sentinel stays 0 so the first real layout reflows.
        view = DevicesView(config_with_devices)
        assert view._grid_cols == 0
        # All 3 cards placed in a single column (rows 0, 1, 2 / col 0).
        # getItemPosition returns (row, column, rowspan, colspan).
        positions = [view.grid.getItemPosition(i) for i in range(3)]
        assert [p[0] for p in positions] == [0, 1, 2]
        assert all(p[1] == 0 for p in positions)
        view.cancel_workers()
        view.deleteLater()

    def test_show_without_resize_reflows_to_real_width(self, shown_view):
        view = shown_view(930)
        assert view._grid_cols == self._expected_cols(view._scroll.viewport().width())
        assert view._grid_cols >= 2

    @pytest.mark.parametrize("width", [620, 930, 1080, 1500])
    def test_columns_track_width(self, shown_view, width):
        view = shown_view(width)
        assert view._grid_cols == self._expected_cols(view._scroll.viewport().width())
        # Cards fill exactly the computed columns: no card beyond the last one
        max_col = max(
            view.grid.getItemPosition(i)[1] for i in range(view.grid.count()))
        assert max_col < view._grid_cols

    def test_three_columns_at_default_window_width(self, shown_view):
        """With CARD_MIN_WIDTH=300 three columns start at ≈ 1004 px viewport.

        3 columns need 3·300 + 2·16 = 932 px of grid width; plus the 2·36 px
        page margins the viewport must be ≥ 1004 px — e.g. a 1230 px window
        behind the 230 px sidebar. Below that the row drops to two wider
        cards (never narrower than 300 px, so "Herunterfahren" always fits).
        """
        view = shown_view(1020)
        assert view._grid_cols == 3
        view_2col = shown_view(935)
        assert view_2col._grid_cols == 2

    def test_list_mode_resize_does_not_reflow(self, qapp, config_with_devices, monkeypatch):
        config_with_devices.set_devices_view_mode(DEVICES_VIEW_LIST)
        view = DevicesView(config_with_devices)
        monkeypatch.setattr(view, "refresh_statuses", lambda: None)
        view.resize(935, 700)
        view.show()
        qapp.processEvents()
        before = view._grid_cols
        view.resize(1500, 700)
        qapp.processEvents()
        assert view._grid_cols == before  # early-return while the list is shown
        view.cancel_workers()
        view.deleteLater()

    def test_refresh_while_hidden_restores_columns_on_show(self, qapp, config_with_devices, monkeypatch):
        """Hidden rebuild (device edited on "Verwalten") must not keep a 1-col placeholder.

        Regression: refresh_devices() while the view is hidden lays out with
        the cols=1 placeholder but left _grid_cols at the old column count,
        so showEvent's `if _grid_cols == 0` guard skipped the reflow and the
        cards stayed one-per-row very wide after switching back to "Geräte".
        """
        view = DevicesView(config_with_devices)
        monkeypatch.setattr(view, "refresh_statuses", lambda: None)
        view.resize(1020, 700)
        view.show()
        qapp.processEvents()
        assert view._grid_cols == 3

        # Simulate leaving the view, editing a device there, coming back.
        view.hide()
        qapp.processEvents()
        view.refresh_devices()  # fires while hidden → placeholder layout
        assert view._grid_cols == 0  # sentinel reset, not stale 3
        view.show()
        qapp.processEvents()
        assert view._grid_cols == 3
        positions = [view.grid.getItemPosition(i) for i in range(3)]
        assert sorted(p[1] for p in positions) == [0, 1, 2]
        view.cancel_workers()
        view.deleteLater()


class TestGridRightEdgeFlush:
    """The right edge of the last card is flush with the search field.

    Regression (2026-09-06): two separate bugs left a dead margin on the
    right of the card grid:

    1. "ratchet" — a plain QScrollArea never makes its content narrower
       than the layout minimum (fixed toolbar widths), so shrinking the
       window never delivered a smaller resizeEvent and the column formula
       saw a stale, too-large width.
    2. phantom columns — QGridLayout keeps columnStretch permanently, so a
       column left over from a wider layout kept stretch=1 and split the
       row into an extra narrow column.
    """

    @pytest.fixture()
    def many_devices_config(self, tmp_path, monkeypatch):
        """6 devices: enough that every tested width's row ends in a real card."""
        cfg = ConfigManager(str(tmp_path / "flush.json"))
        cfg.config["devices"] = [
            {
                "id": f"f{i}",
                "name": f"Flush{i}",
                "mac": f"AA:BB:CC:DD:EE:{i:02X}",
                "ip": f"192.168.1.{i}",
                "enabled": True,
            }
            for i in range(1, 7)
        ]
        return cfg

    @pytest.fixture()
    def shown_view(self, qapp, many_devices_config, monkeypatch):
        views = []

        def _make(width: int) -> DevicesView:
            view = DevicesView(many_devices_config)
            monkeypatch.setattr(view, "refresh_statuses", lambda: None)
            view.resize(width, 700)
            view.show()
            qapp.processEvents()
            views.append(view)
            return view

        yield _make
        for v in views:
            v.cancel_workers()
            v.deleteLater()

    @staticmethod
    def _settle(qapp, view: DevicesView, width: int) -> None:
        view.resize(width, 700)
        for _ in range(5):
            qapp.processEvents()

    def test_content_width_tracks_viewport(self, qapp, shown_view):
        """No ratchet: pageContent follows the viewport when shrinking."""
        view = shown_view(1400)
        for width in (1100, 900, 760, 620, 900, 1400):
            self._settle(qapp, view, width)
            vp = view._scroll.viewport().width()
            assert view._scroll.widget().width() <= vp + 1

    def test_last_card_flush_with_search_field(self, qapp, shown_view):
        """Right card edge == search field right edge at every width."""
        view = shown_view(1400)
        content = view._scroll.widget()
        for width in (1400, 1200, 1000, 900, 760, 700, 600, 900, 1400):
            self._settle(qapp, view, width)
            cards = list(view._cards.values())
            assert cards, f"no cards at width {width}"
            rightmost = max(
                c.mapTo(content, c.rect().topRight()).x() for c in cards)
            search_right = view.search_input.mapTo(
                content, view.search_input.rect().topRight()).x()
            assert abs(rightmost - search_right) <= 2, (
                f"width {width}: card edge {rightmost} vs search {search_right}")

    def test_no_phantom_column_after_shrinking(self, qapp, shown_view):
        """Cards fill the row after a wide→narrow step (stretch reset)."""
        view = shown_view(1400)
        self._settle(qapp, view, 1400)
        wide_cols = view._grid_cols
        self._settle(qapp, view, 900)
        assert view._grid_cols < wide_cols
        # Every card is (near) as wide as the formula promises — a leftover
        # stretch column would leave the cards much narrower.
        avail = view._grid_host.width()
        expected = (avail - (view._grid_cols - 1) * GRID_SPACING) // view._grid_cols
        for card in view._cards.values():
            assert card.width() >= expected - 2

    def test_search_field_right_edge_at_content_edge(self, qapp, shown_view):
        """FlexToolbar keeps the search field right-aligned when shrinking."""
        view = shown_view(1400)
        content = view._scroll.widget()
        for width in (1400, 900, 760, 620, 1400):
            self._settle(qapp, view, width)
            right = view.search_input.mapTo(
                content, view.search_input.rect().topRight()).x()
            assert abs(right - (content.width() - PAGE_MARGIN_H)) <= 2


class TestLocaleKeyConsistency:
    """Guard against one-sided locale maintenance (C5).

    ``test_devices_view`` (de) and ``test_modern_ui`` (en) drive the same
    ``DevicesView``/``DeviceCard`` widgets. The keys they exercise must exist
    in BOTH English and German; otherwise a missing key silently falls back
    to the raw key string and the UI shows untranslated keys.
    """

    def _locale_keys(self, lang: str) -> set:
        path = Path(__file__).resolve().parent.parent / "wol_app" / "locales" / f"{lang}.json"
        with open(path, encoding="utf-8") as fh:
            return set(json.load(fh).keys())

    @pytest.mark.parametrize("lang", ["en", "de"])
    def test_action_keys_present_in_both_locales(self, lang):
        keys = self._locale_keys(lang)
        missing = [k for k in _ACTION_KEYS if k not in keys]
        assert not missing, f"Keys missing from {lang}.json: {missing}"

    @pytest.mark.parametrize("lang", ["en", "de"])
    def test_name_marker_keys_present_in_both_locales(self, lang):
        keys = self._locale_keys(lang)
        missing = [k for k in _NAME_KEYS if k not in keys]
        assert not missing, f"Keys missing from {lang}.json: {missing}"


class TestPlatformPill:
    """Status + platform chip on cards and rows, and the client tooltips."""

    def test_card_pill_shows_detected_platform(self, qapp, config_with_devices):
        device = dict(config_with_devices.config["devices"][0], os="ubuntu")
        card = DeviceCard(device, "online", set())
        assert "Linux" in card.pill.text.text()
        assert card.pill.dot.objectName() == "pillDotOnline"

    def test_card_pill_marks_unknown_platform(self, qapp, config_with_devices):
        card = DeviceCard(config_with_devices.config["devices"][0], "online", set())
        assert Translations.tr("scan_dialog.os.unknown") in card.pill.text.text()

    def test_list_row_keeps_dot_and_adds_pill(self, qapp, config_with_devices):
        device = dict(config_with_devices.config["devices"][0], os="windows")
        row = DeviceListRow(device, "online", set())
        assert row.dot.objectName() == "dotOnline"
        assert "Windows" in row.pill.text.text()
        assert row.pill.dot.objectName() == "pillDotOnline"

    def test_status_update_moves_pill_dot(self, qapp, config_with_devices):
        card = DeviceCard(config_with_devices.config["devices"][0], "offline", set())
        card.set_status("online")
        assert card.pill.dot.objectName() == "pillDotOnline"

    def test_estimate_and_service_show_platform_without_tilde(self, qapp):
        from wol_app.widgets.status_pill import StatusPill

        estimated = StatusPill("windows", "ttl", "online")
        assert "Windows" in estimated.text.text()
        assert not estimated.text.text().startswith("~")
        service = StatusPill("windows", "high", "online")
        assert "Windows" in service.text.text()
        assert not service.text.text().startswith("~")
        # the confidence is still spelled out in the tooltip, not the label
        assert Translations.tr("scan_dialog.os.tip_estimate") in estimated.toolTip()
        assert Translations.tr("scan_dialog.os.tip_service") in service.toolTip()

    def test_pill_tooltip_combines_status_and_platform(self, qapp):
        from wol_app.widgets.status_pill import StatusPill

        pill = StatusPill("linux", "", "online")
        tip = pill.toolTip()
        assert Translations.tr("status.online") in tip
        assert Translations.tr("modern.devices.pill_detected") in tip
        pill.set_platform("", "")
        assert Translations.tr("modern.devices.pill_unknown") in pill.toolTip()

    def test_remote_tooltips_name_the_client_for_the_protocol(
            self, qapp, config_with_devices):
        from wol_app.config import REMOTE_PROTOCOL_VNC

        device = dict(config_with_devices.config["devices"][0], os="linux")
        card = DeviceCard(
            device, "online", set(), remote_protocol=REMOTE_PROTOCOL_VNC)
        assert card.remote_fs_btn.toolTip().endswith(
            Translations.tr("modern.devices.client_vnc"))
        assert card.remote_win_btn.toolTip().endswith(
            Translations.tr("modern.devices.client_vnc"))
        # default (windows / unknown) keeps the RDP client in the tooltip
        plain = DeviceCard(config_with_devices.config["devices"][0], "online", set())
        assert plain.remote_fs_btn.toolTip().endswith(
            Translations.tr("modern.devices.client_rdp"))

    def test_view_routes_protocol_per_device(self, qapp, config_with_devices):
        config_with_devices.config["devices"][0]["os"] = "linux"
        view = DevicesView(config_with_devices)
        assert view._cards["d1"].remote_fs_btn.toolTip().endswith(
            Translations.tr("modern.devices.client_vnc"))
        assert view._cards["d2"].remote_fs_btn.toolTip().endswith(
            Translations.tr("modern.devices.client_rdp"))


class TestPlatformDetection:
    """Automatic platform fingerprinting for devices without a stored platform."""

    def test_probe_targets_resolves_hostnames(self, monkeypatch):
        from wol_app.app_core import OsDetectWorker

        monkeypatch.setattr(
            "wol_app.utils.resolve_ipv4_all",
            lambda v: ["10.0.0.9", "10.0.0.10"])
        targets, hint = OsDetectWorker.probe_targets(
            {"ip": "ubuntu-mercury.fritz.box", "name": "mercury"})
        assert targets == ["10.0.0.9", "10.0.0.10"]
        assert hint == "ubuntu-mercury.fritz.box"

    def test_probe_targets_keeps_plain_ipv4(self):
        from wol_app.app_core import OsDetectWorker

        assert OsDetectWorker.probe_targets(
            {"ip": "10.0.0.5", "name": "PC"}) == (["10.0.0.5"], "PC")

    def test_probe_targets_unresolvable_name_is_tried_as_is(self, monkeypatch):
        from wol_app.app_core import OsDetectWorker

        monkeypatch.setattr("wol_app.utils.resolve_ipv4_all", lambda v: [])
        assert OsDetectWorker.probe_targets({"ip": "gone.local"}) == (
            ["gone.local"], "gone.local")

    def test_worker_tries_further_addresses_until_one_answers(
            self, config_with_devices, monkeypatch):
        from wol_app.app_core import OsDetectWorker

        config_with_devices.config["devices"][0]["ip"] = "pc.fritz.box"
        monkeypatch.setattr(
            "wol_app.utils.resolve_ipv4_all",
            lambda v: ["10.0.0.1", "10.0.0.2"])

        def fake_fingerprint(ip, hostname="", mac="", **_kw):
            if ip == "10.0.0.1":
                return "", "", ""       # stale lease, no signal at all
            return "windows", "medium", "fingerprint"

        monkeypatch.setattr("wol_app.os_detect.fingerprint_host",
                            fake_fingerprint)
        worker = OsDetectWorker(config_with_devices)
        results: list = []
        worker.finished.connect(results.extend)
        worker.run()

        d1 = next(r for r in results if r[0] == "d1")
        assert d1[1:3] == ("windows", "medium")

    def test_worker_probes_only_devices_without_platform(
            self, config_with_devices, monkeypatch):
        from wol_app.app_core import OsDetectWorker
        from wol_app.os_detect import CONFIDENCE_MEDIUM

        config_with_devices.config["devices"][0]["os"] = "windows"
        probed: list[str] = []

        def fake_fingerprint(ip, hostname="", mac="", **_kw):
            probed.append(hostname or ip)
            return "linux", CONFIDENCE_MEDIUM, "fingerprint"

        monkeypatch.setattr("wol_app.os_detect.fingerprint_host",
                            fake_fingerprint)
        worker = OsDetectWorker(config_with_devices)
        results: list = []
        worker.finished.connect(results.extend)
        worker.run()

        # d1 already has a platform and d3 is disabled -> only d2 is probed.
        assert sorted(r[0] for r in results) == ["d2"]
        assert all(r[1] == "linux" for r in results)
        assert len(probed) == 1

    def test_worker_survives_probe_errors(self, config_with_devices, monkeypatch):
        from wol_app.app_core import OsDetectWorker

        def boom(*_a, **_kw):
            raise OSError("network down")

        monkeypatch.setattr("wol_app.os_detect.fingerprint_host", boom)
        worker = OsDetectWorker(config_with_devices)
        results: list = []
        worker.finished.connect(results.extend)
        worker.run()
        assert results
        assert all(r[1] == "" for r in results)

    def test_headless_mode_skips_detection(self, qapp, config_with_devices):
        view = DevicesView(config_with_devices)
        assert view._os_thread is None

    def test_results_persist_and_update_the_cards(self, qapp, config_with_devices):
        view = DevicesView(config_with_devices)
        view._on_platforms_finished([("d1", "linux", "low", "fingerprint")])

        stored = config_with_devices.get_device_by_id("d1")
        assert stored["os"] == "linux"
        assert stored["os_confidence"] == "low"
        # Rebuilt cards show the platform and route the Remote buttons to VNC.
        card = view._cards["d1"]
        assert "Linux" in card.pill.text.text()
        assert not card.pill.text.text().startswith("~")
        assert card.remote_fs_btn.toolTip().endswith(
            Translations.tr("modern.devices.client_vnc"))

    def test_unknown_result_leaves_device_untouched(self, qapp, config_with_devices):
        view = DevicesView(config_with_devices)
        view._on_platforms_finished([("d1", "", "", "")])
        stored = config_with_devices.get_device_by_id("d1")
        assert "os" not in stored or not stored["os"]
        assert "d1" in view._os_probed

    def test_manual_refresh_forgets_missing_platforms(self, qapp,
                                                       config_with_devices,
                                                       monkeypatch):
        view = DevicesView(config_with_devices)
        view._os_probed = {"d1", "d2", "d3"}
        started: list[bool] = []
        monkeypatch.setattr(view, "refresh_statuses", lambda: started.append(True))
        monkeypatch.setattr(view, "detect_missing_platforms", lambda: None)
        view._on_refresh_clicked()
        assert started == [True]
        # All three devices lack a platform -> the memory is cleared again.
        assert view._os_probed == set()
