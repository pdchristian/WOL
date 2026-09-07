"""Tests for wol_app.wol_engine magic packet creation and scheduling."""

import locale
import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

from wol_app.wol_engine import WOLEngine, day_in_schedule, _DAYS_EN


class TestMagicPacket(unittest.TestCase):
    def test_valid_mac_creates_packet(self):
        packet = WOLEngine._create_magic_packet("AA:BB:CC:DD:EE:FF")
        # 6 bytes of FF + 16 copies of the 6-byte MAC
        expected = b"\xff" * 6 + bytes.fromhex("AABBCCDDEEFF") * 16
        self.assertEqual(packet, expected)
        self.assertEqual(len(packet), 102)

    def test_hyphen_separated_mac(self):
        packet = WOLEngine._create_magic_packet("AA-BB-CC-DD-EE-FF")
        expected = b"\xff" * 6 + bytes.fromhex("AABBCCDDEEFF") * 16
        self.assertEqual(packet, expected)

    def test_invalid_mac_raises(self):
        with self.assertRaises(ValueError):
            WOLEngine._create_magic_packet("not-a-mac")
        with self.assertRaises(ValueError):
            WOLEngine._create_magic_packet("AA:BB:CC")
        with self.assertRaises(ValueError):
            WOLEngine._create_magic_packet("")

    def test_lowercase_mac(self):
        packet = WOLEngine._create_magic_packet("aa:bb:cc:dd:ee:ff")
        expected = b"\xff" * 6 + bytes.fromhex("AABBCCDDEEFF") * 16
        self.assertEqual(packet, expected)


class TestDayInSchedule(unittest.TestCase):
    """Regression: scheduler day-matching must be locale-independent.

    Uses the week 2026-09-07 (Mon) .. 2026-09-13 (Sun) as fixed references,
    so weekday expectations are deterministic regardless of the host locale.
    """

    # Fixed reference week (2026-09-07 is a Monday).
    MON = datetime(2026, 9, 7, 12, 0)
    TUE = datetime(2026, 9, 8, 12, 0)
    WED = datetime(2026, 9, 9, 12, 0)
    THU = datetime(2026, 9, 10, 12, 0)
    FRI = datetime(2026, 9, 11, 12, 0)
    SAT = datetime(2026, 9, 12, 12, 0)
    SUN = datetime(2026, 9, 13, 12, 0)

    def _assert_matches(self, now: datetime, days: list) -> None:
        self.assertTrue(day_in_schedule(days, now), f"{now:%a} should match {days}")

    def _assert_not(self, now: datetime, days: list) -> None:
        self.assertFalse(day_in_schedule(days, now), f"{now:%a} should NOT match {days}")

    def test_weekday_index_is_monday_first(self):
        # _DAYS_EN index must align with datetime.weekday() (Monday=0).
        self.assertEqual(_DAYS_EN[0], "Mon")
        self.assertEqual(_DAYS_EN[6], "Sun")

    def test_each_weekday_matches_its_own_entry(self):
        self._assert_matches(self.MON, ["Mon"])
        self._assert_matches(self.TUE, ["Tue"])
        self._assert_matches(self.WED, ["Wed"])
        self._assert_matches(self.THU, ["Thu"])
        self._assert_matches(self.FRI, ["Fri"])
        self._assert_matches(self.SAT, ["Sat"])
        self._assert_matches(self.SUN, ["Sun"])

    def test_weekday_does_not_match_other_entries(self):
        self._assert_not(self.MON, ["Tue"])
        self._assert_not(self.MON, ["Sun"])
        self._assert_not(self.SUN, ["Mon"])
        self._assert_not(self.SAT, ["Fri"])

    def test_multiple_days_match(self):
        self._assert_matches(self.MON, ["Mon", "Wed", "Fri"])
        self._assert_matches(self.WED, ["Mon", "Wed", "Fri"])
        self._assert_not(self.SAT, ["Mon", "Wed", "Fri"])

    def test_empty_day_list_matches_nothing(self):
        # Both schedule dialogs reject empty selections, so a schedule always
        # has >=1 day; an empty list only guards against malformed configs and
        # must never fire (preserves pre-fix behavior of `current_day in days`).
        for day in (self.MON, self.TUE, self.WED, self.THU,
                    self.FRI, self.SAT, self.SUN):
            self._assert_not(day, [])

    def test_stored_days_are_canonical_english(self):
        # The dialogs store English abbreviations; ensure the helper only
        # matches those (a stray lowercase/other token must not match).
        self._assert_not(self.MON, ["mon"])
        self._assert_not(self.MON, ["Mo"])

    def test_matching_is_locale_independent(self):
        """The fix must hold even if the OS LC_TIME locale is non-English.

        The old code used ``strftime("%a")``, which yields e.g. "Mo" under a
        German locale and silently never matched the stored "Mon". This test
        switches the locale (if available) and asserts the helper still maps
        to the canonical English weekday, i.e. it no longer depends on locale.
        """
        original = locale.getlocale(locale.LC_TIME)
        try:
            switched = None
            for candidate in ("de_DE.UTF-8", "de_DE", "German", "de-DE"):
                try:
                    locale.setlocale(locale.LC_TIME, candidate)
                    switched = candidate
                    break
                except locale.Error:
                    continue
            if switched is None:
                self.skipTest("No non-English LC_TIME locale available")
            else:
                # Even under a German locale the canonical mapping is stable.
                self._assert_matches(self.MON, ["Mon"])
                self._assert_not(self.MON, ["Tue"])
                # strftime("%a") would NOT equal "Mon" here — proof the helper
                # does not rely on it.
                self.assertNotEqual(self.MON.strftime("%a"), _DAYS_EN[self.MON.weekday()])
        finally:
            locale.setlocale(locale.LC_TIME, original)


class TestCheckDeviceStatusHostname(unittest.TestCase):
    """Regression: host names must be resolved to IPv4 before pinging.

    Two real-world failure modes are covered:

    * Windows ``ping`` prefers the AAAA record when the DNS server (e.g. a
      Fritz!Box) also publishes IPv6. Windows IPv6 replies contain no
      ``TTL=`` token, so the reply detector reported online hosts offline.
    * A name may resolve to several A records (a stale DHCP lease next to
      the current one) and the resolver order is not deterministic, so a
      single unreachable candidate must not decide the status.
    """

    def _engine(self, device: dict) -> WOLEngine:
        config = MagicMock()
        config.get_device_by_id.return_value = device
        engine = WOLEngine(config)
        return engine

    @staticmethod
    def _completed(text: str):
        res = MagicMock()
        res.stdout = text.encode("utf-8")
        return res

    def test_hostname_is_resolved_and_ping_forced_to_ipv4(self):
        engine = self._engine(
            {"id": "d1", "name": "blade-18", "ip": "blade-18.fritz.box"})
        with patch("wol_app.wol_engine.resolve_ipv4_all",
                   return_value=["192.168.2.150"]) as resolve, \
             patch("wol_app.wol_engine.run_subprocess_safe",
                   return_value=self._completed(
                       "Antwort von 192.168.2.150: Bytes=32 Zeit=1ms TTL=128")) as run:
            status, _msg = engine.check_device_status("d1")
        resolve.assert_called_once_with("blade-18.fritz.box")
        self.assertEqual(status, "online")
        cmd = run.call_args.args[0]
        # The resolved IPv4 is pinged, and IPv4 is enforced via "-4"
        self.assertEqual(cmd[-1], "192.168.2.150")
        self.assertIn("-4", cmd)

    def test_second_address_rescues_stale_first_record(self):
        engine = self._engine(
            {"id": "d1", "name": "blade-18", "ip": "blade-18"})
        outputs = [
            self._completed("Antwort von 192.168.2.62: Zielhost nicht erreichbar."),
            self._completed("Antwort von 192.168.2.150: Bytes=32 Zeit=1ms TTL=128"),
        ]
        with patch("wol_app.wol_engine.resolve_ipv4_all",
                   return_value=["192.168.2.172", "192.168.2.150"]), \
             patch("wol_app.wol_engine.run_subprocess_safe",
                   side_effect=outputs) as run:
            status, _msg = engine.check_device_status("d1")
        self.assertEqual(status, "online")
        self.assertEqual(run.call_count, 2)

    def test_offline_when_no_address_answers(self):
        engine = self._engine({"id": "d1", "name": "nas", "ip": "nas01"})
        with patch("wol_app.wol_engine.resolve_ipv4_all",
                   return_value=["192.168.2.9"]), \
             patch("wol_app.wol_engine.run_subprocess_safe",
                   return_value=self._completed("Zeitueberschreitung")):
            status, _msg = engine.check_device_status("d1")
        self.assertEqual(status, "offline")

    def test_unresolvable_name_reports_unknown(self):
        engine = self._engine({"id": "d1", "name": "ghost", "ip": "ghost.invalid"})
        with patch("wol_app.wol_engine.resolve_ipv4_all", return_value=[]), \
             patch("wol_app.wol_engine.run_subprocess_safe") as run:
            status, msg = engine.check_device_status("d1")
        self.assertEqual(status, "unknown")
        self.assertIn("resolve", msg)
        run.assert_not_called()

    def test_ipv4_literal_still_pinged_directly(self):
        engine = self._engine({"id": "d1", "name": "pc", "ip": "192.168.2.50"})
        with patch("wol_app.wol_engine.resolve_ipv4_all",
                   return_value=["192.168.2.50"]), \
             patch("wol_app.wol_engine.run_subprocess_safe",
                   return_value=self._completed("TTL=64")) as run:
            status, _msg = engine.check_device_status("d1")
        self.assertEqual(status, "online")
        self.assertEqual(run.call_args.args[0][-1], "192.168.2.50")


if __name__ == "__main__":
    unittest.main()
