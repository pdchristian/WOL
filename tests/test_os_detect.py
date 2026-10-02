"""Tests for wol_app.os_detect — platform detection for LAN devices.

The pure heuristics (TTL parsing, OUI hints, scoring) are exercised without
any network traffic; the probe helpers are patched so the tests stay
hermetic and fast on every platform.
"""

import os
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("WOL_HEADLESS", "1")

import wol_app.os_detect as os_detect  # noqa: E402
from wol_app.os_detect import (  # noqa: E402
    CONFIDENCE_HIGH,
    OS_LINUX,
    OS_MACOS,
    OS_WINDOWS,
    fingerprint_host,
    get_ping_ttl,
    infer_os,
    oui_hint,
    probe_tcp_port,
    score_platforms,
    ttl_from_ping_output,
)


class TestTtlParsing:
    def test_windows_output(self):
        out = "Pinging 192.168.2.50 with 32 bytes of data:\nReply from 192.168.2.50: bytes=32 time=1ms TTL=128"
        assert ttl_from_ping_output(out) == 128

    def test_linux_output_lowercase(self):
        assert ttl_from_ping_output("64 bytes from 10.0.0.5: icmp_seq=1 ttl=64 time=0.4 ms") == 64

    def test_macos_output(self):
        assert ttl_from_ping_output("64 bytes from 10.0.0.9: icmp_seq=0 ttl=63 time=2.120 ms") == 63

    def test_colon_variant(self):
        assert ttl_from_ping_output("Reply: ttl : 128") == 128

    def test_no_token_returns_none(self):
        assert ttl_from_ping_output("Request timed out.") is None
        assert ttl_from_ping_output("") is None


class TestOuiHint:
    def test_apple_prefix_maps_to_macos(self):
        assert oui_hint("B8:C7:5D:11:22:33") == OS_MACOS

    def test_separatorless_and_lowercase(self):
        assert oui_hint("b8c75d112233") == OS_MACOS

    def test_unknown_prefix(self):
        assert oui_hint("50:EB:F6:B7:8B:0C") == ""

    def test_short_or_empty(self):
        assert oui_hint("") == ""
        assert oui_hint("B8:C7") == ""


class TestScoring:
    def test_no_signals_score_zero(self):
        scores = score_platforms()
        assert scores == {OS_WINDOWS: 0, OS_MACOS: 0, OS_LINUX: 0}

    def test_ttl_128_favours_windows(self):
        scores = score_platforms(ttl=128)
        assert scores[OS_WINDOWS] > max(scores[OS_MACOS], scores[OS_LINUX])

    def test_ttl_64_is_ambiguous_between_macos_and_linux(self):
        scores = score_platforms(ttl=64)
        assert scores[OS_MACOS] == scores[OS_LINUX] > 0
        assert scores[OS_WINDOWS] == 0

    def test_network_gear_ttl_scores_nothing(self):
        assert set(score_platforms(ttl=255).values()) == {0}


class TestInferOs:
    def test_windows_ttl_plus_smb(self):
        os_id, confidence = infer_os(ttl=128, smb_open=True)
        assert os_id == OS_WINDOWS
        assert confidence == "medium"

    def test_macos_local_name_breaks_the_ttl_tie(self):
        os_id, _conf = infer_os(ttl=64, hostname="MacBook-Pro.local")
        assert os_id == OS_MACOS

    def test_apple_product_name_breaks_the_ttl_tie(self):
        # A plain DNS name (no ".local") with an Apple product in it.
        os_id, _conf = infer_os(ttl=64, hostname="MACBOOKPRO")
        assert os_id == OS_MACOS

    def test_ambiguous_mac_substring_does_not_suggest_macos(self):
        os_id, _conf = infer_os(ttl=64, hostname="mac-server")
        assert os_id == OS_LINUX

    def test_linux_when_ttl_64_without_macos_signals(self):
        os_id, _conf = infer_os(ttl=64, smb_open=False, hostname="server")
        assert os_id == OS_LINUX

    def test_oui_alone_is_low_confidence(self):
        os_id, confidence = infer_os(mac="B8:C7:5D:00:00:00")
        assert os_id == OS_MACOS
        assert confidence == "low"

    def test_no_evidence_returns_empty(self):
        assert infer_os() == ("", "")
        assert infer_os(ttl=255) == ("", "")

    def test_ttl_64_with_smb_stays_on_the_unix_side(self):
        # Samba on a file server must not flip the host to Windows.
        os_id, _conf = infer_os(ttl=64, smb_open=True)
        assert os_id in (OS_LINUX, OS_MACOS)


class TestProbeTcpPort:
    def test_failure_is_swallowed(self):
        with patch.object(os_detect.socket, "create_connection",
                          side_effect=OSError("refused")):
            assert probe_tcp_port("192.168.1.5", 445) is False

    def test_success(self):
        with patch.object(os_detect.socket, "create_connection",
                          return_value=MagicMock()):
            assert probe_tcp_port("192.168.1.5", 445) is True

    def test_invalid_ip_does_not_raise(self):
        # create_connection raises ValueError for garbage hosts.
        with patch.object(os_detect.socket, "create_connection",
                          side_effect=ValueError("not an address")):
            assert probe_tcp_port("not-an-ip", 445) is False


class TestGetPingTtl:
    def test_invalid_ip_short_circuits(self):
        assert get_ping_ttl("nope") is None

    def test_parses_ttl_from_stdout(self):
        fake = MagicMock(returncode=0,
                        stdout=b"Reply from 1.2.3.4: bytes=32 time=1ms TTL=128",
                        stderr=b"")
        with patch.object(os_detect, "run_subprocess_safe", return_value=fake):
            assert get_ping_ttl("1.2.3.4") == 128

    def test_timeout_returns_none(self):
        with patch.object(os_detect, "run_subprocess_safe",
                          side_effect=TimeoutError("ping")):
            assert get_ping_ttl("1.2.3.4") is None

    def test_nonzero_exit_returns_none(self):
        fake = MagicMock(returncode=1, stdout=b"Request timed out.", stderr=b"")
        with patch.object(os_detect, "run_subprocess_safe", return_value=fake):
            assert get_ping_ttl("1.2.3.4") is None


class TestFingerprintHost:
    def test_service_answer_is_authoritative(self):
        with patch.object(os_detect, "probe_host_service_os",
                          return_value="ubuntu"):
            os_id, confidence, source = fingerprint_host("10.0.0.5")
        assert os_id == "ubuntu"
        assert confidence == CONFIDENCE_HIGH
        assert source == "service"

    def test_fallback_to_fingerprint(self):
        with patch.object(os_detect, "probe_host_service_os", return_value=""), \
             patch.object(os_detect, "get_ping_ttl", return_value=128), \
             patch.object(os_detect, "probe_tcp_port", return_value=True):
            os_id, confidence, source = fingerprint_host("10.0.0.5")
        assert os_id == OS_WINDOWS
        assert source == "fingerprint"

    def test_silent_host_yields_nothing(self):
        with patch.object(os_detect, "probe_host_service_os", return_value=""), \
             patch.object(os_detect, "get_ping_ttl", return_value=None), \
             patch.object(os_detect, "probe_tcp_port", return_value=False):
            os_id, confidence, source = fingerprint_host("10.0.0.5")
        assert os_id == ""
        assert source == ""

    def test_probe_port_can_be_skipped(self):
        with patch.object(os_detect, "probe_host_service_os", return_value=""), \
             patch.object(os_detect, "get_ping_ttl", return_value=64), \
             patch.object(os_detect, "probe_tcp_port") as port_probe:
            fingerprint_host("10.0.0.5", probe_port=False)
        port_probe.assert_not_called()


class TestProbeHostServiceOs:
    def test_client_error_is_swallowed(self):
        # A missing/unreachable service must never break the scan.
        with patch("wol_app.host_service_client.get_host_os",
                   side_effect=OSError("boom")):
            assert os_detect.probe_host_service_os("10.0.0.5") == ""

    def test_none_becomes_empty_string(self):
        with patch("wol_app.host_service_client.get_host_os",
                   return_value=None):
            assert os_detect.probe_host_service_os("10.0.0.5") == ""

    def test_value_is_passed_through(self):
        with patch("wol_app.host_service_client.get_host_os",
                   return_value="macos"):
            assert os_detect.probe_host_service_os("10.0.0.5") == "macos"


class TestScanWiring:
    def test_scan_subnet_stores_os_fields(self):
        import wol_app.network_scanner as ns

        with patch.object(ns, "ping_host", return_value=True), \
             patch.object(ns, "resolve_hostname", return_value="FRACTAL"), \
             patch.object(ns, "get_mac_from_arp",
                          return_value="50:EB:F6:B7:8B:0C"), \
             patch.object(ns, "get_ipv6_from_nd", return_value=None), \
             patch.object(ns, "fingerprint_host",
                          return_value=("windows", "high", "service")):
            hosts = ns.scan_subnet("192.168.1.0", "255.255.255.248", timeout=1)

        assert hosts
        for host in hosts:
            assert host["os"] == "windows"
            assert host["os_confidence"] == "high"

    def test_scan_subnet_normalizes_distribution(self):
        import wol_app.network_scanner as ns

        with patch.object(ns, "ping_host", return_value=True), \
             patch.object(ns, "resolve_hostname", return_value="mercury"), \
             patch.object(ns, "get_mac_from_arp", return_value=None), \
             patch.object(ns, "get_ipv6_from_nd", return_value=None), \
             patch.object(ns, "fingerprint_host",
                          return_value=("ubuntu", "high", "service")):
            hosts = ns.scan_subnet("192.168.1.0", "255.255.255.248", timeout=1)

        assert [h["os"] for h in hosts] == ["linux"] * len(hosts)

    def test_detect_os_false_skips_fingerprinting(self):
        import wol_app.network_scanner as ns

        with patch.object(ns, "ping_host", return_value=True), \
             patch.object(ns, "resolve_hostname", return_value="x"), \
             patch.object(ns, "get_mac_from_arp", return_value=None), \
             patch.object(ns, "get_ipv6_from_nd", return_value=None), \
             patch.object(ns, "fingerprint_host") as fp:
            hosts = ns.scan_subnet("192.168.1.0", "255.255.255.248",
                                   timeout=1, detect_os=False)

        fp.assert_not_called()
        assert hosts
        assert all(h["os"] == "" for h in hosts)

    def test_fingerprint_failure_does_not_break_scan(self):
        import wol_app.network_scanner as ns

        with patch.object(ns, "ping_host", return_value=True), \
             patch.object(ns, "resolve_hostname", return_value="x"), \
             patch.object(ns, "get_mac_from_arp", return_value=None), \
             patch.object(ns, "get_ipv6_from_nd", return_value=None), \
             patch.object(ns, "fingerprint_host", side_effect=RuntimeError):
            hosts = ns.scan_subnet("192.168.1.0", "255.255.255.248", timeout=1)

        assert hosts
        assert all(h["os"] == "" for h in hosts)


class TestPlatformLabels:
    """The scan UIs label platforms through locale keys that must exist."""

    LOCALES = ("en", "de", "fr", "es")
    REQUIRED_KEYS = (
        "scan_dialog.col.os",
        "scan_dialog.opt.detect_os",
        "scan_dialog.opt.detect_os_tooltip",
        "scan_dialog.os.unknown",
        "scan_dialog.os.tip_service",
        "scan_dialog.os.tip_estimate",
        "scan_dialog.search_placeholder",
    )

    def test_label_keys_cover_all_platform_ids(self):
        from wol_app.utils import OS_LABEL_KEYS, VALID_OS_IDS

        assert sorted(OS_LABEL_KEYS) == sorted(VALID_OS_IDS)

    def test_all_locale_files_have_the_keys(self):
        import json
        from pathlib import Path

        from wol_app.utils import OS_LABEL_KEYS

        base = Path(__file__).resolve().parents[1] / "wol_app" / "locales"
        for lang in self.LOCALES:
            data = json.loads((base / f"{lang}.json").read_text(encoding="utf-8"))
            for key in (*self.REQUIRED_KEYS, *OS_LABEL_KEYS.values()):
                assert key in data, f"{lang}.json is missing {key}"
                assert data[key], f"{lang}.json has an empty {key}"
