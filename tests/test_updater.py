"""Tests for wol_app.updater version parsing logic."""

import unittest

from wol_app.updater import _parse_version


class TestParseVersion(unittest.TestCase):
    def test_standard_version(self):
        self.assertEqual(_parse_version("1.2.3"), (1, 2, 3))

    def test_v_prefix(self):
        self.assertEqual(_parse_version("v1.2.3"), (1, 2, 3))

    def test_two_segments_normalized(self):
        self.assertEqual(_parse_version("1.2"), (1, 2, 0))

    def test_one_segment_normalized(self):
        self.assertEqual(_parse_version("1"), (1, 0, 0))

    def test_whitespace(self):
        self.assertEqual(_parse_version("  2.0.1  "), (2, 0, 1))

    def test_invalid_returns_zero(self):
        self.assertEqual(_parse_version("invalid"), (0,))
        self.assertEqual(_parse_version(""), (0,))
        self.assertEqual(_parse_version("1.2.3-beta"), (0,))
        self.assertEqual(_parse_version(None), (0,))

    def test_comparison_ordering(self):
        # A newer version must compare greater
        self.assertGreater(_parse_version("1.3.0"), _parse_version("1.2.3"))
        self.assertGreater(_parse_version("1.2.3"), _parse_version("1.2.0"))
        # An invalid *new* version never counts as newer than a valid one
        self.assertFalse(_parse_version("broken") > _parse_version("1.5.0"))
        # An invalid version is never newer than another invalid one
        self.assertFalse(_parse_version("broken") > _parse_version("also-broken"))


if __name__ == "__main__":
    unittest.main()
