"""Tests for wol_app.host_service_client send_host_command."""

import json
import socket
import unittest
from unittest import mock

from wol_app.host_service_client import get_metrics, run_batch, send_host_command


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


class TestGetMetrics(unittest.TestCase):
    def test_success(self):
        payload = {
            "status": "ok", "protocol": 2, "hostname": "PC-01",
            "cpu": 42.0, "cpu_count": 8, "ram_used": 8, "ram_total": 16,
            "gpu": 30.0, "vram_used": 1, "vram_total": 12,
            "gpu_name": "RTX", "uptime": 100,
        }
        with mock.patch(
            "wol_app.host_service_client.socket.create_connection",
            return_value=_fake_socket_responding(payload),
        ):
            ok, result = get_metrics("1.2.3.4", "u", "p")
        self.assertTrue(ok)
        self.assertEqual(result["cpu"], 42.0)
        self.assertEqual(result["hostname"], "PC-01")

    def test_auth_failure(self):
        with mock.patch(
            "wol_app.host_service_client.socket.create_connection",
            return_value=_fake_socket_responding(
                {"status": "error", "message": "Authentication failed"}),
        ):
            ok, msg = get_metrics("1.2.3.4", "u", "p")
        self.assertFalse(ok)
        self.assertEqual(msg, "Authentication failed")

    def test_old_protocol_rejected(self):
        with mock.patch(
            "wol_app.host_service_client.socket.create_connection",
            return_value=_fake_socket_responding({"status": "ok", "protocol": 1}),
        ):
            ok, msg = get_metrics("1.2.3.4", "u", "p")
        self.assertFalse(ok)
        self.assertIn("too old", msg)

    def test_timeout(self):
        with mock.patch(
            "wol_app.host_service_client.socket.create_connection",
            side_effect=socket.timeout,
        ):
            ok, msg = get_metrics("1.2.3.4", "u", "p")
        self.assertFalse(ok)
        self.assertIn("timed out", msg)


class TestGetMetricsApiKey(unittest.TestCase):
    """protocol v10: the dashboard API key rides along in the metrics request."""

    def _sent_payload(self, **kwargs):
        sent: dict = {}

        class _FakeSock:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def sendall(self, data):
                sent.update(json.loads(data.decode("utf-8")))

            def recv(self, size):
                line = json.dumps({"status": "ok", "protocol": 2,
                                   "cpu": 1.0}).encode("utf-8") + b"\n"
                return line[:size]

        with mock.patch(
            "wol_app.host_service_client.socket.create_connection",
            return_value=_FakeSock(),
        ):
            ok, result = get_metrics("1.2.3.4", "u", "p", **kwargs)
        self.assertTrue(ok, result)
        return sent

    def test_api_key_included_when_set(self):
        sent = self._sent_payload(watch=["strata:8080"], api_key="dummy")
        self.assertEqual(sent["api_key"], "dummy")
        self.assertEqual(sent["watch"], ["strata:8080"])

    def test_api_key_omitted_when_empty(self):
        sent = self._sent_payload(watch=["strata:8080"])
        self.assertNotIn("api_key", sent)

    def test_api_key_truncated_to_schema_limit(self):
        sent = self._sent_payload(api_key="x" * 300)
        self.assertEqual(len(sent["api_key"]), 128)


class TestRunBatch(unittest.TestCase):
    def test_success(self):
        payload = {
            "status": "ok", "exit_code": 0, "stdout": "hi\n",
            "stderr": "", "duration_ms": 12, "truncated": False,
        }
        with mock.patch(
            "wol_app.host_service_client.socket.create_connection",
            return_value=_fake_socket_responding(payload),
        ):
            ok, result = run_batch("1.2.3.4", "echo hi", "u", "p")
        self.assertTrue(ok)
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["stdout"], "hi\n")

    def test_batch_disabled_on_host(self):
        with mock.patch(
            "wol_app.host_service_client.socket.create_connection",
            return_value=_fake_socket_responding(
                {"status": "error", "message": "Batch execution disabled on host"}),
        ):
            ok, msg = run_batch("1.2.3.4", "echo hi", "u", "p")
        self.assertFalse(ok)
        self.assertIn("disabled", msg)


if __name__ == "__main__":
    unittest.main()
