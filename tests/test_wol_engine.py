"""Tests for wol_app.wol_engine magic packet creation and scheduling."""

import locale
import unittest
from datetime import datetime

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


if __name__ == "__main__":
    unittest.main()
