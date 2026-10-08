"""Contract tests: wire protocol (protocol/) vs. the actual host services.

These tests lock the documented contract in ``protocol/`` (SPEC.md, schema/,
examples/) against the real implementations (``wol_host_service.py`` and
``wol_host_service_linux.py``):

* every shipped example validates against its schema (and bad payloads don't)
* responses produced by the *live* TCP handler validate against the schemas
* protocol version + limits in the schemas match the service constants

A future Android (or any) client can rely on ``protocol/`` alone; breaking
this contract must fail CI here.
"""

import builtins
import json
import re
from pathlib import Path
from unittest import mock
from unittest.mock import MagicMock

import pytest

jsonschema = pytest.importorskip(
    "jsonschema", reason="pip install jsonschema (see requirements-dev.txt)")
import referencing  # noqa: E402  (ships with jsonschema >= 4.18)

ROOT = Path(__file__).resolve().parents[1]
PROTO = ROOT / "protocol"
SCHEMA_DIR = PROTO / "schema"
EXAMPLES_DIR = PROTO / "examples"

wol_host_service = pytest.importorskip(
    "wol_host_service", reason="Windows service module")


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


SCHEMAS = {p.stem: _load(p) for p in sorted(SCHEMA_DIR.glob("*.json"))}


def _validator(name: str):
    registry = referencing.Registry().with_resources(
        [(s["$id"], referencing.Resource.from_contents(s))
         for s in SCHEMAS.values()])
    return jsonschema.Draft202012Validator(SCHEMAS[name], registry=registry)


def assert_valid(schema_name: str, payload):
    errors = sorted(_validator(schema_name).iter_errors(payload), key=str)
    assert not errors, f"{schema_name}: " + "; ".join(
        f"{list(e.absolute_path)} {e.message}" for e in errors)


def assert_invalid(schema_name: str, payload):
    assert any(_validator(schema_name).iter_errors(payload)), \
        f"{schema_name} unexpectedly accepted {payload!r}"


# ── Schema hygiene ─────────────────────────────────────────────────────────

class TestSchemaFiles:
    def test_all_schemas_are_valid_draft2020(self):
        for name, schema in SCHEMAS.items():
            try:
                jsonschema.Draft202012Validator.check_schema(schema)
            except jsonschema.SchemaError as e:
                pytest.fail(f"{name}.json is not a valid schema: {e}")

    def test_expected_schema_files_exist(self):
        expected = {"request", "response-core", "response-status",
                    "response-metrics", "response-run_batch",
                    "response-shutdown-reboot"}
        assert expected <= set(SCHEMAS), \
            f"missing schema files: {expected - set(SCHEMAS)}"


# ── Examples validate ──────────────────────────────────────────────────────

# (example file, primary schema). Every response example must *also*
# validate against response-core (checked in a second test).
EXAMPLE_TO_SCHEMA = {
    "request-status.json": "request",
    "request-metrics.json": "request",
    "request-run_batch.json": "request",
    "response-status.json": "response-status",
    "response-shutdown.json": "response-shutdown-reboot",
    "response-reboot.json": "response-shutdown-reboot",
    "response-metrics-full.json": "response-metrics",
    "response-metrics-no-gpu.json": "response-metrics",
    "response-run_batch-ok.json": "response-run_batch",
    "response-error-auth.json": "response-core",
    "response-error-batch-disabled.json": "response-core",
}


class TestExamples:
    def test_all_example_files_are_covered(self):
        on_disk = {p.name for p in EXAMPLES_DIR.glob("*.json")}
        assert on_disk == set(EXAMPLE_TO_SCHEMA), \
            "add/remove examples in this test when files change"

    @pytest.mark.parametrize("name,schema", sorted(EXAMPLE_TO_SCHEMA.items()))
    def test_example_validates_against_primary_schema(self, name, schema):
        assert_valid(schema, _load(EXAMPLES_DIR / name))

    @pytest.mark.parametrize("name", sorted(
        n for n in EXAMPLE_TO_SCHEMA if n.startswith("response-")))
    def test_response_examples_validate_against_core(self, name):
        """Every response — whatever the command — satisfies response-core."""
        assert_valid("response-core", _load(EXAMPLES_DIR / name))


# ── Bad payloads must be rejected ──────────────────────────────────────────

class TestNegativeExamples:
    def test_request_rejects_unknown_command(self):
        assert_invalid("request", {"command": "nuke"})

    def test_request_rejects_too_many_watch_entries(self):
        assert_invalid("request", {"command": "metrics", "username": "u",
                                   "password": "p",
                                   "watch": [f"p{i}.exe" for i in range(9)]})

    def test_request_rejects_oversized_script(self):
        assert_invalid("request", {"command": "run_batch", "username": "u",
                                   "password": "p",
                                   "script": "x" * 32_001})

    def test_core_rejects_unknown_status(self):
        assert_invalid("response-core", {"status": "weird", "message": "x"})

    def test_metrics_requires_protocol_field(self):
        payload = _load(EXAMPLES_DIR / "response-metrics-no-gpu.json")
        del payload["protocol"]
        assert_invalid("response-metrics", payload)

    def test_metrics_watch_not_running_must_be_bare(self):
        payload = _load(EXAMPLES_DIR / "response-metrics-full.json")
        payload["processes"]["backup-sync.exe"]["pid"] = 99
        assert_invalid("response-metrics", payload)

    def test_metrics_watch_models_capped(self):
        payload = _load(EXAMPLES_DIR / "response-metrics-full.json")
        payload["processes"]["llama-server.exe:8080"]["models"] = \
            [f"m{i}" for i in range(17)]
        assert_invalid("response-metrics", payload)

    def test_metrics_watch_model_metrics_ok(self):
        # The shipped example carries a v5 model_metrics map -> valid.
        payload = _load(EXAMPLES_DIR / "response-metrics-full.json")
        assert_valid("response-metrics", payload)

    def test_metrics_watch_model_metrics_rejects_string_value(self):
        payload = _load(EXAMPLES_DIR / "response-metrics-full.json")
        payload["processes"]["llama-server.exe:8080"]["model_metrics"] = {
            "Qwen3.8-Flash-256k-62": {"prompt_tps": "261.15"}}
        assert_invalid("response-metrics", payload)

    def test_metrics_watch_requests_active_ok(self):
        """v9: the shipped example carries requests_active -> valid."""
        payload = _load(EXAMPLES_DIR / "response-metrics-full.json")
        assert payload["processes"]["llama-server.exe:8080"][
            "requests_active"] == 2
        assert_valid("response-metrics", payload)

    def test_metrics_watch_requests_active_rejects_negative(self):
        payload = _load(EXAMPLES_DIR / "response-metrics-full.json")
        payload["processes"]["llama-server.exe:8080"]["requests_active"] = -1
        assert_invalid("response-metrics", payload)

    def test_metrics_watch_requests_active_rejects_string(self):
        payload = _load(EXAMPLES_DIR / "response-metrics-full.json")
        payload["processes"]["llama-server.exe:8080"]["requests_active"] = "2"
        assert_invalid("response-metrics", payload)

    def test_metrics_watch_model_metrics_partial_entry_ok(self):
        # A model with only one readable gauge is allowed (keys optional).
        payload = _load(EXAMPLES_DIR / "response-metrics-full.json")
        payload["processes"]["llama-server.exe:8080"]["model_metrics"] = {
            "Qwen3.8-Flash-256k-62": {"predicted_tps": 26.65}}
        assert_valid("response-metrics", payload)

    def test_metrics_watch_port_only_entry_ok(self):
        # v7: a port-only entry (running:false + api_port fields) is valid -
        # the "bare entry" rule only applies when no api_port is present.
        payload = _load(EXAMPLES_DIR / "response-metrics-full.json")
        assert ":8081" in payload["processes"]
        assert_valid("response-metrics", payload)

    def test_metrics_watch_rejects_unknown_api_kind(self):
        payload = _load(EXAMPLES_DIR / "response-metrics-full.json")
        payload["processes"][":8081"]["api_kind"] = "vllm"
        assert_invalid("response-metrics", payload)

    def test_metrics_watch_rejects_unknown_api_feature(self):
        payload = _load(EXAMPLES_DIR / "response-metrics-full.json")
        payload["processes"][":8081"]["api_features"] = ["models", "completions"]
        assert_invalid("response-metrics", payload)

    def test_run_batch_ok_requires_exit_code(self):
        payload = _load(EXAMPLES_DIR / "response-run_batch-ok.json")
        del payload["exit_code"]
        assert_invalid("response-run_batch", payload)

    def test_shutdown_ack_pattern(self):
        assert_invalid("response-shutdown-reboot",
                       {"status": "ok", "message": "format c: accepted"})


# ── Live handler: real service responses validate against the schemas ──────

def _run_handler(svc, raw: bytes, *, auth_ok=True, batch_allowed=False,
                 monkeypatch=None):
    """Push one raw request through the real _CommandHandler, return the
    parsed response dict (or None when the handler stayed silent)."""
    monkeypatch.setattr(svc, "validate_credentials",
                        lambda u, p: auth_ok)
    monkeypatch.setattr(svc, "is_batch_allowed", lambda: batch_allowed)
    sent = {}

    class _Req:
        def __init__(self, data):
            self._chunks = [data]

        def recv(self, _n):
            return self._chunks.pop(0) if self._chunks else b""

        def sendall(self, data):
            sent["data"] = data

    handler = svc._CommandHandler.__new__(svc._CommandHandler)
    handler.request = _Req(raw)
    handler.handle()
    if "data" not in sent:
        return None
    return json.loads(sent["data"].decode("utf-8").strip())


def _fake_psutil_with_llama(monkeypatch, svc, port_open=True,
                            models=None):
    """Patch psutil + port/model probes so a llama-server watch entry reports
    as running with an open API port (mirrors test_host_service_metrics)."""
    proc = mock.MagicMock()
    proc.info = {"pid": 4711, "name": "llama-server.exe"}
    proc.cpu_percent.return_value = 12.5
    proc.memory_info.return_value = mock.MagicMock(rss=5 * 1024 ** 3)
    proc.create_time.return_value = 0
    proc.cmdline.return_value = ["llama-server.exe", "-m",
                                 "models/qwen2.5.gguf"]

    class _VM:
        used = 8 * 1024 ** 3
        total = 32 * 1024 ** 3

    fake = mock.MagicMock()
    fake.cpu_percent.return_value = 42.0
    fake.cpu_count.return_value = 8
    fake.virtual_memory.return_value = _VM()
    fake.boot_time.return_value = 0
    fake.process_iter.return_value = [proc]
    monkeypatch.setitem(__import__("sys").modules, "psutil", fake)
    monkeypatch.setattr(svc, "_gpu_metrics_cached", lambda: {
        "gpu": 64.0, "vram_used": 18 * 1024 ** 3,
        "vram_total": 24 * 1024 ** 3, "gpu_name": "NVIDIA GeForce RTX 4090"})
    monkeypatch.setattr(svc, "_check_port_loopback", lambda port: True)
    monkeypatch.setattr(
        svc, "_fetch_models_and_up",
        lambda port, api_key="": (models or ["Qwen3.8-Flash-256k-62"], True))
    monkeypatch.setattr(svc, "_probe_api_identity",
                        lambda port, api_up=False, api_key="": {})
    monkeypatch.setattr(
        svc, "_fetch_model_metrics",
        lambda port, name, api_key="": {"prompt_tps": 261.15, "predicted_tps": 26.65})
    svc._WATCH_PROCS.clear()


class TestLiveHandlerContract:
    """The responses produced by the real TCP handler validate against
    protocol/schema — this is what an Android client will actually receive."""

    def test_status(self, monkeypatch):
        resp = _run_handler(wol_host_service, b'{"command": "status"}\n',
                            monkeypatch=monkeypatch)
        assert_valid("response-status", resp)
        assert_valid("response-core", resp)

    def test_metrics_with_watch_models(self, monkeypatch):
        _fake_psutil_with_llama(monkeypatch, wol_host_service)
        try:
            resp = _run_handler(
                wol_host_service,
                json.dumps({"command": "metrics", "username": "u",
                            "password": "p",
                            "watch": ["llama-server.exe:8080"]}).encode() + b"\n",
                monkeypatch=monkeypatch)
        finally:
            wol_host_service._WATCH_PROCS.clear()
        assert_valid("response-metrics", resp)
        assert resp["protocol"] == wol_host_service.PROTOCOL_VERSION
        entry = resp["processes"]["llama-server.exe:8080"]
        assert entry["running"] is True and entry["api_port_open"] is True
        assert entry["models"]  # v4 field present

    def test_metrics_without_watch(self, monkeypatch):
        monkeypatch.setitem(__import__("sys").modules, "psutil", None)
        monkeypatch.setattr(wol_host_service, "_gpu_metrics_cached",
                            lambda: {"gpu": None, "vram_used": None,
                                     "vram_total": None, "gpu_name": None})
        resp = _run_handler(
            wol_host_service,
            json.dumps({"command": "metrics", "username": "u",
                        "password": "p"}).encode() + b"\n",
            monkeypatch=monkeypatch)
        assert_valid("response-metrics", resp)
        assert "processes" not in resp

    def test_metrics_auth_failure(self, monkeypatch):
        resp = _run_handler(
            wol_host_service,
            json.dumps({"command": "metrics", "username": "u",
                        "password": "wrong"}).encode() + b"\n",
            auth_ok=False, monkeypatch=monkeypatch)
        assert_valid("response-core", resp)
        assert resp == {"status": "error", "message": "Authentication failed"}

    def test_run_batch_disabled_on_host(self, monkeypatch):
        resp = _run_handler(
            wol_host_service,
            json.dumps({"command": "run_batch", "username": "u",
                        "password": "p", "script": "echo hi"}).encode() + b"\n",
            batch_allowed=False, monkeypatch=monkeypatch)
        assert_valid("response-core", resp)
        assert resp["status"] == "error"
        assert "disabled" in resp["message"]

    def test_run_batch_ok(self, monkeypatch):
        monkeypatch.setattr(wol_host_service, "run_batch_script",
                            lambda script, timeout: {
                                "status": "ok", "exit_code": 0,
                                "stdout": "hi\r\n", "stderr": "",
                                "duration_ms": 42, "truncated": False})
        resp = _run_handler(
            wol_host_service,
            json.dumps({"command": "run_batch", "username": "u",
                        "password": "p", "script": "echo hi"}).encode() + b"\n",
            batch_allowed=True, monkeypatch=monkeypatch)
        assert_valid("response-run_batch", resp)
        assert_valid("response-core", resp)

    def test_unknown_command(self, monkeypatch):
        resp = _run_handler(wol_host_service, b'{"command": "nuke"}\n',
                            monkeypatch=monkeypatch)
        assert_valid("response-core", resp)
        assert resp["status"] == "error"
        assert "Unknown command" in resp["message"]

    def test_invalid_json(self, monkeypatch):
        resp = _run_handler(wol_host_service, b"{not json\n",
                            monkeypatch=monkeypatch)
        assert_valid("response-core", resp)
        assert resp["message"] == "Invalid JSON"

    def test_shutdown_ack(self, monkeypatch):
        # Never let the real shutdown/reboot run on the test machine.
        monkeypatch.setattr(wol_host_service.subprocess, "run",
                            lambda *a, **k: mock.MagicMock())
        monkeypatch.setattr(wol_host_service.time, "sleep", lambda _s: None)
        resp = _run_handler(
            wol_host_service,
            json.dumps({"command": "shutdown", "username": "u",
                        "password": "p"}).encode() + b"\n",
            monkeypatch=monkeypatch)
        assert_valid("response-shutdown-reboot", resp)


# ── v8: platform reporting ("os") ──────────────────────────────────────────

class TestOsField:
    def test_status_response_carries_os(self, monkeypatch):
        resp = _run_handler(wol_host_service, b'{"command": "status"}\n',
                            monkeypatch=monkeypatch)
        assert resp["os"] == "windows"
        assert_valid("response-status", resp)

    def test_metrics_response_carries_os(self, monkeypatch):
        monkeypatch.setitem(__import__("sys").modules, "psutil", None)
        monkeypatch.setattr(wol_host_service, "_gpu_metrics_cached",
                            lambda: {"gpu": None, "vram_used": None,
                                     "vram_total": None, "gpu_name": None})
        resp = _run_handler(
            wol_host_service,
            json.dumps({"command": "metrics", "username": "u",
                        "password": "p"}).encode() + b"\n",
            monkeypatch=monkeypatch)
        assert resp["os"] == "windows"
        assert_valid("response-metrics", resp)

    def test_linux_core_reports_distribution(self, monkeypatch):
        import wol_host_service_linux as linux_svc

        monkeypatch.setattr(linux_svc, "_OS_ID_CACHE", None)
        monkeypatch.setattr(linux_svc.sys, "platform", "linux")
        monkeypatch.setattr(builtins, "open", mock.mock_open(
            read_data='NAME="Ubuntu"\nID=ubuntu\nID_LIKE=debian\n'))
        assert linux_svc.os_id() == "ubuntu"

    def test_linux_core_falls_back_to_linux(self, monkeypatch):
        import wol_host_service_linux as linux_svc

        monkeypatch.setattr(linux_svc, "_OS_ID_CACHE", None)
        monkeypatch.setattr(linux_svc.sys, "platform", "linux")
        monkeypatch.setattr(builtins, "open",
                            MagicMock(side_effect=FileNotFoundError()))
        assert linux_svc.os_id() == "linux"

    def test_linux_core_reports_macos_for_darwin(self, monkeypatch):
        # The macOS variant reuses the Linux core, so the darwin branch is
        # what makes wol_host_service_macos.py report "macos".
        import wol_host_service_linux as linux_svc

        monkeypatch.setattr(linux_svc, "_OS_ID_CACHE", None)
        monkeypatch.setattr(linux_svc.sys, "platform", "darwin")
        assert linux_svc.os_id() == "macos"

    def test_schema_allows_pre_v8_hosts_without_os(self):
        # "os" must stay optional: a v2 host has no such field.
        payload = _load(EXAMPLES_DIR / "response-metrics-no-gpu.json")
        assert "os" not in payload
        assert_valid("response-metrics", payload)

    def test_schema_rejects_non_string_os(self):
        payload = _load(EXAMPLES_DIR / "response-metrics-full.json")
        payload["os"] = 7
        assert_invalid("response-metrics", payload)

    def test_schema_rejects_empty_os(self):
        payload = _load(EXAMPLES_DIR / "response-metrics-full.json")
        payload["os"] = ""
        assert_invalid("response-metrics", payload)


# ── Contract invariants: SPEC/schema constants vs. service code ────────────

LINUX_SRC = ROOT / "wol_host_service_linux.py"


def _const_from_source(text: str, name: str) -> int:
    m = re.search(rf"^{name}\s*=\s*(\d+)", text, re.MULTILINE)
    assert m, f"{name} not found in source"
    return int(m.group(1))


class TestContractInvariants:
    def test_protocol_version_matches_schema_maximum(self):
        assert (SCHEMAS["response-metrics"]["properties"]["protocol"]
                ["maximum"]) == wol_host_service.PROTOCOL_VERSION

    def test_linux_service_reports_same_protocol_version(self):
        assert _const_from_source(
            LINUX_SRC.read_text(encoding="utf-8"),
            "PROTOCOL_VERSION") == wol_host_service.PROTOCOL_VERSION

    def test_spec_documents_current_version(self):
        spec = (PROTO / "SPEC.md").read_text(encoding="utf-8")
        m = re.search(r"\*\*Version:\*\* (\d+)", spec)
        assert m and int(m.group(1)) == wol_host_service.PROTOCOL_VERSION, \
            "SPEC.md header version drifted from PROTOCOL_VERSION"

    def test_watch_limit_matches_schema(self):
        assert (SCHEMAS["request"]["properties"]["watch"]["maxItems"]
                == wol_host_service.WATCH_MAX_ENTRIES)
        assert (SCHEMAS["response-metrics"]["properties"]["processes"]
                ["maxProperties"] == wol_host_service.WATCH_MAX_ENTRIES)

    def test_models_cap_matches_schema(self):
        watch_entry = SCHEMAS["response-metrics"]["$defs"]["watchEntry"]
        assert (watch_entry["properties"]["models"]["maxItems"]
                == wol_host_service.WATCH_MAX_MODELS)

    def test_batch_limits_match_schema(self):
        assert (SCHEMAS["request"]["properties"]["script"]["maxLength"]
                == wol_host_service.MAX_SCRIPT_CHARS)
        rb = SCHEMAS["response-run_batch"]
        assert (rb["then"]["properties"]["stdout"]["maxLength"]
                == wol_host_service.MAX_BATCH_OUTPUT_CHARS)
        assert (rb["then"]["properties"]["stderr"]["maxLength"]
                == wol_host_service.MAX_BATCH_OUTPUT_CHARS)
        to = SCHEMAS["request"]["properties"]["timeout"]
        assert to["minimum"] == wol_host_service.BATCH_TIMEOUT_MIN
        assert to["maximum"] == wol_host_service.BATCH_TIMEOUT_MAX

    def test_api_key_limit_matches_schema(self):
        """v10: one ceiling for the dashboard API key across all layers."""
        from wol_app.config import MAX_API_KEY_CHARS

        key = SCHEMAS["request"]["properties"]["api_key"]
        assert key["type"] == "string"
        assert key["maxLength"] == wol_host_service.WATCH_API_KEY_MAX_CHARS
        assert MAX_API_KEY_CHARS == key["maxLength"]
        validator = _validator("request")
        long_key = "k" * (key["maxLength"] + 1)
        with pytest.raises(jsonschema.ValidationError):
            validator.validate({"command": "metrics", "username": "u",
                                "password": "p", "api_key": long_key})

    def test_linux_core_matches_api_key_contract(self):
        """The Ubuntu/macOS service must behave exactly like the Windows one."""
        import wol_host_service_linux as linux_svc

        assert (linux_svc.WATCH_API_KEY_MAX_CHARS
                == wol_host_service.WATCH_API_KEY_MAX_CHARS)
        for value in ("  dummy  ", "k" * 128, "a\r\nX: 1", "x" * 129,
                      "schl\xfcssel", None, 7):
            assert (linux_svc._sanitize_api_key(value)
                    == wol_host_service._sanitize_api_key(value)), repr(value)

        conn = mock.MagicMock()
        conn.getresponse.return_value.status = 200
        conn.getresponse.return_value.read.return_value = b"{}"
        with mock.patch.object(linux_svc.http.client, "HTTPConnection",
                               lambda *a, **k: conn):
            assert linux_svc._http_get_loopback(
                8080, "/metrics", "text/plain", api_key="dummy") == (200, "{}")
        assert (conn.request.call_args.kwargs["headers"]["Authorization"]
                == "Bearer dummy")

    def test_linux_core_matches_watch_timeouts(self):
        """Both services must give /metrics the same patient timeout."""
        import wol_host_service_linux as linux_svc

        for name in ("WATCH_PORT_TIMEOUT_S", "WATCH_MODELS_TIMEOUT_S",
                     "WATCH_METRICS_TIMEOUT_S", "WATCH_PROBE_TTL_S"):
            assert (getattr(linux_svc, name)
                    == getattr(wol_host_service, name)), name
