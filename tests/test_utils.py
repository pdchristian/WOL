"""Tests for wol_app.utils validation helpers."""

import unittest

from wol_app.utils import (
    get_ip_key,
    validate_device_name,
    validate_ip,
    validate_mac,
    validate_password,
    validate_username,
)


class TestValidateIP(unittest.TestCase):
    def test_valid_ip(self):
        self.assertTrue(validate_ip("192.168.1.1"))
        self.assertTrue(validate_ip("255.255.255.255"))
        self.assertTrue(validate_ip("0.0.0.0"))

    def test_invalid_ip(self):
        self.assertFalse(validate_ip("999.1.1.1"))
        self.assertFalse(validate_ip("1.2.3"))
        self.assertFalse(validate_ip("not-an-ip"))
        self.assertFalse(validate_ip(""))
        self.assertFalse(validate_ip("256.256.256.256"))


class TestValidateMac(unittest.TestCase):
    def test_valid_mac(self):
        self.assertTrue(validate_mac("AA:BB:CC:DD:EE:FF"))
        self.assertTrue(validate_mac("AA-BB-CC-DD-EE-FF"))
        self.assertTrue(validate_mac("aa:bb:cc:dd:ee:ff"))

    def test_invalid_mac(self):
        self.assertFalse(validate_mac(""))
        self.assertFalse(validate_mac("AA:BB:CC:DD:EE:GG"))
        self.assertFalse(validate_mac("AA:BB:CC:DD:EE"))
        self.assertFalse(validate_mac("not-a-mac"))


class TestValidateDeviceName(unittest.TestCase):
    def test_valid_name(self):
        self.assertTrue(validate_device_name("Living Room PC"))
        self.assertTrue(validate_device_name("PC-1"))

    def test_invalid_name(self):
        self.assertFalse(validate_device_name(""))
        self.assertFalse(validate_device_name("A" * 65))
        self.assertFalse(validate_device_name("bad<script>"))
        self.assertFalse(validate_device_name("semi;colon"))


class TestValidateUsername(unittest.TestCase):
    def test_optional(self):
        self.assertTrue(validate_username(""))
        self.assertTrue(validate_username("user"))

    def test_invalid(self):
        self.assertFalse(validate_username("A" * 65))
        self.assertFalse(validate_username("bad\x00"))


class TestValidatePassword(unittest.TestCase):
    def test_optional(self):
        self.assertTrue(validate_password(""))
        self.assertTrue(validate_password("pass"))

    def test_invalid(self):
        self.assertFalse(validate_password("A" * 129))
        self.assertFalse(validate_password("p\xff"))


class TestGetIPKey(unittest.TestCase):
    def test_sorts_ip(self):
        self.assertLess(get_ip_key("192.168.1.2"), get_ip_key("192.168.1.10"))

    def test_invalid_returns_zeros(self):
        self.assertEqual(get_ip_key(""), (0, 0, 0, 0))
        self.assertEqual(get_ip_key("invalid"), (0, 0, 0, 0))


if __name__ == "__main__":
    unittest.main()
