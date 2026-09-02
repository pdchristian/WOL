"""Regression tests for wol_app.network_scanner.scan_network().

Covers host de-duplication across interfaces and (C4/A2) that the per-interface
progress message is the *translated* ``scan.scanning_subnet`` string rather than
the previously hardcoded German f-string.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("WOL_HEADLESS", "1")

import pytest  # noqa: E402

pytest.importorskip("PyQt6")

from PyQt6.QtWidgets import QApplication  # noqa: E402

import wol_app.network_scanner as network_scanner  # noqa: E402
from wol_app.translations import Translations  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def english():
    # Deterministic: the asserted progress strings are English values, so pin
    # the active language regardless of other test modules' locale fixtures.
    Translations.set_language("en")
    yield


def _host(ipv4):
    return {"hostname": "", "ipv4": ipv4, "ipv6": "", "mac": "Unknown"}


class TestScanNetwork:
    def test_dedup_across_interfaces(self, qapp, english, monkeypatch):
        interfaces = [
            {"ip": "192.168.1.0", "netmask": "255.255.255.0"},
            {"ip": "10.0.0.0", "netmask": "255.255.255.0"},
        ]
        # 192.168.1.10 appears on BOTH subnets -> must be deduplicated.
        subnet_results = {
            "192.168.1.0": [_host("192.168.1.10"), _host("192.168.1.11")],
            "10.0.0.0": [_host("192.168.1.10"), _host("10.0.0.20")],
        }

        monkeypatch.setattr(network_scanner, "get_local_interfaces", lambda: interfaces)

        def fake_scan_subnet(ip, netmask, timeout=1, progress_callback=None):
            return subnet_results.get(ip, [])

        monkeypatch.setattr(network_scanner, "scan_subnet", fake_scan_subnet)

        results = network_scanner.scan_network(timeout=1)
        ips = [h["ipv4"] for h in results]
        assert sorted(ips) == sorted(["192.168.1.10", "192.168.1.11", "10.0.0.20"])
        # Each IP appears exactly once despite the overlap.
        assert len(ips) == len(set(ips)) == 3

    def test_progress_uses_translated_subnet_message(self, qapp, english, monkeypatch):
        interfaces = [
            {"ip": "192.168.1.0", "netmask": "255.255.255.0"},
            {"ip": "10.0.0.0", "netmask": "255.255.255.0"},
        ]
        monkeypatch.setattr(network_scanner, "get_local_interfaces", lambda: interfaces)
        monkeypatch.setattr(network_scanner, "scan_subnet", lambda *a, **k: [])

        calls = []
        network_scanner.scan_network(
            timeout=1, progress_callback=lambda ip, total, msg: calls.append((ip, total, msg))
        )

        # One callback per interface, with the translated subnet message.
        assert len(calls) == 2
        expected = {
            Translations.tr("scan.scanning_subnet", ip="192.168.1.0"),
            Translations.tr("scan.scanning_subnet", ip="10.0.0.0"),
        }
        assert {msg for _, _, msg in calls} == expected

    def test_progress_message_is_not_legacy_hardcoded(self, qapp, english, monkeypatch):
        # Regression guard (A2): the old code emitted
        # f"Scanne Subnetz {ip}..." — ensure that exact legacy form is gone.
        monkeypatch.setattr(network_scanner, "get_local_interfaces",
                            lambda: [{"ip": "192.168.1.0", "netmask": "255.255.255.0"}])
        monkeypatch.setattr(network_scanner, "scan_subnet", lambda *a, **k: [])
        calls = []
        network_scanner.scan_network(
            timeout=1, progress_callback=lambda ip, total, msg: calls.append(msg)
        )
        assert calls
        for msg in calls:
            assert not msg.startswith("Scanne Subnetz"), (
                "Progress message still uses the legacy hardcoded German string"
            )
