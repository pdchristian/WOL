"""Tests for the network-profile gate (public networks ⇒ read-only).

Covers the client-side detector (:mod:`wol_app.network_profile`) and the
authoritative host-service gate in both :mod:`wol_host_service` and
:mod:`wol_host_service_linux`. No real network calls: the OS detectors are
monkeypatched, and the client honours ``WOL_FORCE_NETWORK``.
"""

import importlib
from unittest import mock

import pytest

from wol_app import network_profile


# --- client detector: wol_app.network_profile -----------------------------

class TestNetworkProfileClient:
    def setup_method(self):
        network_profile.reset_cache_for_tests()

    def teardown_method(self):
        import os
        os.environ.pop("WOL_FORCE_NETWORK", None)
        network_profile.reset_cache_for_tests()

    def test_force_public(self, monkeypatch):
        monkeypatch.setenv("WOL_FORCE_NETWORK", "public")
        assert network_profile.is_public_network() is True
        assert network_profile.describe_network() == "public"

    def test_force_private(self, monkeypatch):
        monkeypatch.setenv("WOL_FORCE_NETWORK", "private")
        assert network_profile.is_public_network() is False
        assert network_profile.describe_network() == "private"

    def test_unknown_is_not_public(self, monkeypatch):
        monkeypatch.setenv("WOL_FORCE_NETWORK", "unknown")
        assert network_profile.is_public_network() is False

    def test_privileged_blocked_only_on_public(self, monkeypatch):
        monkeypatch.setenv("WOL_FORCE_NETWORK", "public")
        assert network_profile.is_privileged_command_blocked() is True
        # ...unless the caller passes the per-app override.
        assert network_profile.is_privileged_command_blocked(
            allow_override=True) is False

    def test_privileged_allowed_on_private(self, monkeypatch):
        monkeypatch.setenv("WOL_FORCE_NETWORK", "private")
        assert network_profile.is_privileged_command_blocked() is False

    def test_detection_failure_is_private(self, monkeypatch):
        # No force override; make the Windows NLM call raise -> UNKNOWN.
        monkeypatch.delenv("WOL_FORCE_NETWORK", raising=False)
        network_profile.reset_cache_for_tests()
        monkeypatch.setattr(
            network_profile, "_category_from_nlm",
            lambda: (_ for _ in ()).throw(OSError("no nlm")))
        import sys
        monkeypatch.setattr(sys, "platform", "win32")
        assert network_profile.get_network_category() == \
            network_profile.CATEGORY_UNKNOWN
        assert network_profile.is_public_network() is False


# --- host-service gate helpers --------------------------------------------

def _service_gate_module(name):
    mod = importlib.import_module(name)
    return mod


def _cat(hsi, kind):
    """Category constant — Windows uses _NLM_CATEGORY_*, Linux CATEGORY_*."""
    prefix = "_NLM_CATEGORY_" if hasattr(hsi, "_NLM_CATEGORY_PUBLIC") \
        else "CATEGORY_"
    return getattr(hsi, prefix + kind)


class TestServiceNetworkGate:
    @pytest.mark.parametrize("modname", ["wol_host_service",
                                         "wol_host_service_linux"])
    def test_read_commands_never_gated(self, modname, monkeypatch):
        hsi = _service_gate_module(modname)
        # Even on a public network, status/metrics are allowed.
        monkeypatch.setattr(hsi, "network_gate_enabled", lambda: True)
        monkeypatch.setattr(hsi, "allow_in_public_network", lambda: False)
        monkeypatch.setattr(hsi, "_network_category",
                            lambda: _cat(hsi, "PUBLIC"))
        assert hsi.network_gate_check("status") is None
        assert hsi.network_gate_check("metrics") is None

    @pytest.mark.parametrize("modname", ["wol_host_service",
                                         "wol_host_service_linux"])
    def test_public_blocks_privileged(self, modname, monkeypatch):
        hsi = _service_gate_module(modname)
        monkeypatch.setattr(hsi, "network_gate_enabled", lambda: True)
        monkeypatch.setattr(hsi, "allow_in_public_network", lambda: False)
        monkeypatch.setattr(hsi, "_network_category",
                            lambda: _cat(hsi, "PUBLIC"))
        for cmd in ("shutdown", "reboot", "run_batch"):
            err = hsi.network_gate_check(cmd)
            assert err and "public network" in err

    @pytest.mark.parametrize("modname", ["wol_host_service",
                                         "wol_host_service_linux"])
    def test_override_allows_privileged(self, modname, monkeypatch):
        hsi = _service_gate_module(modname)
        monkeypatch.setattr(hsi, "network_gate_enabled", lambda: True)
        monkeypatch.setattr(hsi, "allow_in_public_network", lambda: True)
        monkeypatch.setattr(hsi, "_network_category",
                            lambda: _cat(hsi, "PUBLIC"))
        assert hsi.network_gate_check("shutdown") is None

    @pytest.mark.parametrize("modname", ["wol_host_service",
                                         "wol_host_service_linux"])
    def test_gate_disabled_allows(self, modname, monkeypatch):
        hsi = _service_gate_module(modname)
        monkeypatch.setattr(hsi, "network_gate_enabled", lambda: False)
        monkeypatch.setattr(hsi, "allow_in_public_network", lambda: False)
        monkeypatch.setattr(hsi, "_network_category",
                            lambda: _cat(hsi, "PUBLIC"))
        assert hsi.network_gate_check("shutdown") is None

    @pytest.mark.parametrize("modname", ["wol_host_service",
                                         "wol_host_service_linux"])
    def test_unknown_network_never_blocks(self, modname, monkeypatch):
        hsi = _service_gate_module(modname)
        monkeypatch.setattr(hsi, "network_gate_enabled", lambda: True)
        monkeypatch.setattr(hsi, "allow_in_public_network", lambda: False)
        monkeypatch.setattr(hsi, "_network_category",
                            lambda: _cat(hsi, "UNKNOWN"))
        assert hsi.network_gate_check("shutdown") is None

    @pytest.mark.parametrize("modname", ["wol_host_service",
                                         "wol_host_service_linux"])
    def test_private_network_allows(self, modname, monkeypatch):
        hsi = _service_gate_module(modname)
        monkeypatch.setattr(hsi, "network_gate_enabled", lambda: True)
        monkeypatch.setattr(hsi, "allow_in_public_network", lambda: False)
        monkeypatch.setattr(hsi, "_network_category",
                            lambda: _cat(hsi, "PRIVATE"))
        assert hsi.network_gate_check("shutdown") is None


# --- handler integration: NETWORK-REJECT before execution ------------------

class TestHandlerNetworkGate:
    class _Sock:
        def __init__(self, request: bytes):
            self._request = request
            self.sent = b""

        def recv(self, _size):
            data, self._request = self._request, b""
            return data

        def sendall(self, data):
            self.sent += data

    def _handle(self, wol_host_service, request: bytes, **patches):
        import contextlib
        import json

        handler = wol_host_service._CommandHandler.__new__(
            wol_host_service._CommandHandler)
        handler.request = self._Sock(request)
        handler.client_address = ("10.0.0.9", 40000)
        ctx = (mock.patch.multiple(wol_host_service, **patches)
               if patches else contextlib.nullcontext())
        with ctx:
            handler.handle()
        return json.loads(handler.request.sent.decode("utf-8").strip())

    def test_public_network_rejects_shutdown(self, monkeypatch):
        import wol_host_service

        # Auth succeeds, but the network gate blocks the privileged command.
        resp = self._handle(
            wol_host_service,
            b'{"command":"shutdown","username":"u","password":"p",'
            b'"nonce":"abc","ts":0}\n',
            validate_credentials=lambda u, p: True,
            replay_check=lambda req, cmd: None,
            network_gate_check=lambda cmd: (
                "Blocked: host is connected to a public network"),
            _auth_audit=lambda msg: None,
        )
        assert resp["status"] == "error"
        assert resp.get("error") == "network_untrusted"
