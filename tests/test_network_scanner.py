"""Tests for the network scanner helpers."""

from wol_app.network_scanner import is_real_interface


class TestIsRealInterface:
    """Dummy/APIPA ranges must be hidden from the UI interface lists."""

    def test_apipa_range_hidden(self):
        assert is_real_interface("169.254.1.5") is False

    def test_any_169_hidden(self):
        assert is_real_interface("169.1.2.3") is False

    def test_private_172_hidden(self):
        assert is_real_interface("172.16.0.1") is False

    def test_any_172_hidden(self):
        # Per user decision: hide the complete 172.* range (virtual adapters)
        assert is_real_interface("172.67.8.9") is False

    def test_typical_lan_visible(self):
        assert is_real_interface("192.168.1.10") is True

    def test_private_10_visible(self):
        assert is_real_interface("10.0.0.5") is True

    def test_public_ip_visible(self):
        assert is_real_interface("8.8.8.8") is True

    def test_empty_ip_hidden(self):
        assert is_real_interface("") is False
