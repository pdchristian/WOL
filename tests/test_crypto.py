"""Tests for wol_app.crypto encryption helpers."""

import unittest

from wol_app.crypto import decrypt_password, encrypt_password, is_encrypted


class TestCrypto(unittest.TestCase):
    def test_roundtrip(self):
        original = "S3cret!"
        encrypted = encrypt_password(original)
        self.assertNotEqual(encrypted, original)
        self.assertEqual(decrypt_password(encrypted), original)

    def test_empty_password(self):
        self.assertEqual(encrypt_password(""), "")
        self.assertEqual(decrypt_password(""), "")
        self.assertFalse(is_encrypted(""))

    def test_is_encrypted_detects_ciphertext(self):
        encrypted = encrypt_password("mypassword")
        self.assertTrue(is_encrypted(encrypted))

    def test_plaintext_not_detected_as_encrypted(self):
        self.assertFalse(is_encrypted("plaintext"))

    def test_long_password_rejected(self):
        with self.assertRaises(ValueError):
            encrypt_password("x" * 129)

    def test_control_chars_rejected(self):
        with self.assertRaises(ValueError):
            encrypt_password("pass\x00word")

    def test_encryption_is_randomized(self):
        # Two encryptions of the same plaintext must differ (random nonce)
        e1 = encrypt_password("same")
        e2 = encrypt_password("same")
        self.assertNotEqual(e1, e2)


if __name__ == "__main__":
    unittest.main()
