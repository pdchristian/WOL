"""Tests for wol_app.host_service_client send_host_command."""

import json
import socket
import unittest
from unittest import mock

from wol_app.host_service_client import send_host_command


def _fake_socket_responding(response_payload: dict):
    """Return a context-manager socket that answers with a JSON line."""
    class _FakeSock:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def sendall(self, data):
            pass

        def recv(self, size):
            line = json.dumps(response_payload).encode("utf-8") + b"\n"
            return line[:size]

    return _FakeSock()


class TestSendHostCommand(unittest.TestCase):
    def test_invalid_command(self):
        ok, msg = send_host_command("1.2.3.4", "nuke", "u", "p")
        self.assertFalse(ok)
        self.assertIn("Unknown command", msg)

    def test_success(self):
        with mock.patch(
            "wol_app.host_service_client.socket.create_connection",
            return_value=_fake_socket_responding({"status": "ok", "message": "shutdown accepted"}),
        ):
            ok, msg = send_host_command("1.2.3.4", "shutdown", "u", "p")
        self.assertTrue(ok)
        self.assertEqual(msg, "shutdown accepted")

    def test_auth_failure(self):
        with mock.patch(
            "wol_app.host_service_client.socket.create_connection",
            return_value=_fake_socket_responding({"status": "error", "message": "Authentication failed"}),
        ):
            ok, msg = send_host_command("1.2.3.4", "shutdown", "u", "p")
        self.assertFalse(ok)
        self.assertEqual(msg, "Authentication failed")

    def test_timeout(self):
        with mock.patch(
            "wol_app.host_service_client.socket.create_connection",
            side_effect=socket.timeout,
        ):
            ok, msg = send_host_command("1.2.3.4", "shutdown", "u", "p")
        self.assertFalse(ok)
        self.assertIn("timed out", msg)

    def test_connection_refused(self):
        with mock.patch(
            "wol_app.host_service_client.socket.create_connection",
            side_effect=ConnectionRefusedError("refused"),
        ):
            ok, msg = send_host_command("1.2.3.4", "shutdown", "u", "p")
        self.assertFalse(ok)
        self.assertIn("Could not connect", msg)

    def test_invalid_response_json(self):
        class _FakeSock:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def sendall(self, data):
                pass

            def recv(self, size):
                return b"not json\n"

        with mock.patch(
            "wol_app.host_service_client.socket.create_connection",
            return_value=_FakeSock(),
        ):
            ok, msg = send_host_command("1.2.3.4", "shutdown", "u", "p")
        self.assertFalse(ok)
        self.assertIn("Invalid response", msg)

    def test_no_response(self):
        class _FakeSock:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def sendall(self, data):
                pass

            def recv(self, size):
                return b""

        with mock.patch(
            "wol_app.host_service_client.socket.create_connection",
            return_value=_FakeSock(),
        ):
            ok, msg = send_host_command("1.2.3.4", "shutdown", "u", "p")
        self.assertFalse(ok)
        self.assertIn("No response", msg)


if __name__ == "__main__":
    unittest.main()
