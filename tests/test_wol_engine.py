"""Tests for wol_app.wol_engine magic packet creation."""

import unittest

from wol_app.wol_engine import WOLEngine


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


if __name__ == "__main__":
    unittest.main()
