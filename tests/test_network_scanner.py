"""Tests for the network scanner helpers."""

from wol_app.network_scanner import (
    get_subnet_range,
    is_real_interface,
    netmask_to_cidr,
    network_address,
    subnet_label,
)


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


class TestNetworkAddress:
    """The scan is anchored at the subnet address, never at the adapter address."""

    def test_adapter_ip_maps_to_subnet(self):
        assert network_address("192.168.2.130", "255.255.255.0") == "192.168.2.0"

    def test_second_adapter_ip_same_subnet(self):
        assert network_address("192.168.2.74", "255.255.255.0") == "192.168.2.0"

    def test_non_default_mask_respected(self):
        assert network_address("10.20.30.77", "255.255.252.0") == "10.20.28.0"

    def test_invalid_netmask_falls_back_to_24(self):
        # netmask_to_cidr() defaults to /24 for unparsable masks
        assert network_address("192.168.2.130", "invalid") == "192.168.2.0"

    def test_cidr_label(self):
        assert subnet_label("192.168.2.130", "255.255.255.0") == "192.168.2.0/24"
        assert subnet_label("10.0.5.9", "255.255.0.0") == "10.0.0.0/16"
        assert netmask_to_cidr("255.255.255.0") == 24


class TestGetSubnetRange:
    """get_subnet_range() must cover the whole subnet of the adapter."""

    def test_range_starts_at_first_host_of_subnet(self):
        hosts = get_subnet_range("192.168.2.130", "255.255.255.0")
        assert hosts[0] == "192.168.2.1"

    def test_range_covers_last_usable_host(self):
        hosts = get_subnet_range("192.168.2.130", "255.255.255.0")
        assert hosts[-1] == "192.168.2.254"
        assert len(hosts) == 254

    def test_adapter_address_is_inside_range(self):
        hosts = set(get_subnet_range("192.168.2.74", "255.255.255.0"))
        assert "192.168.2.1" in hosts and "192.168.2.74" in hosts and "192.168.2.254" in hosts

    def test_same_subnet_for_different_adapters(self):
        assert (get_subnet_range("192.168.2.130", "255.255.255.0")
                == get_subnet_range("192.168.2.74", "255.255.255.0"))

    def test_small_subnet_excludes_broadcast(self):
        hosts = get_subnet_range("192.168.1.5", "255.255.255.248")
        assert hosts == ["192.168.1.1", "192.168.1.2", "192.168.1.3",
                         "192.168.1.4", "192.168.1.5", "192.168.1.6"]

    def test_large_subnet_is_capped(self):
        # /16 would be 65k hosts — capped to MAX_SUBNET_SIZE, still subnet-anchored
        hosts = get_subnet_range("10.20.30.40", "255.255.0.0")
        assert len(hosts) == 256
        assert hosts[0] == "10.20.0.1"
