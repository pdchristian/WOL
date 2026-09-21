"""Pytest configuration: ensure the project root is importable.

SAFETY (two layers, both scoped to the test session only):

1. ``WOL_TEST_NO_POWER`` — the host service's ``_execute_power`` short-circuits
   when this is set, so an in-process handler call can never run the real
   ``shutdown`` / ``systemctl poweroff``.
2. A guard around :func:`socket.create_connection` that refuses outbound
   connections to the host-service port (8765) on the *developer machine*
   (loopback / 192.168.2.62). This protects against the case where a real
   WOL Host Service is installed and running locally: a test that (directly
   or via the client) opened a live connection and sent ``shutdown`` would
   otherwise power off the workstation. Deliberate integration tests against
   another machine (e.g. 192.168.2.111) are NOT affected. Set
   ``WOL_ALLOW_LOCAL_HOST_SERVICE=1`` to lift the guard for manual testing.
"""

import os
import socket
import sys

# Add the repository root so `import wol_app` works regardless of CWD
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Block real OS power actions (shutdown/reboot) for the entire test session.
os.environ["WOL_TEST_NO_POWER"] = "1"

# Deterministic client-side network gate: the detector always reports a
# PRIVATE network unless a test overrides WOL_FORCE_NETWORK itself. Without
# this, tests touching the privileged-command gate would depend on how the
# developer machine happens to be connected.
os.environ.setdefault("WOL_FORCE_NETWORK", "private")

# --- Socket guard: never connect to the local host service in tests --------

# Host-service TCP port (mirrors wol_host_service.DEFAULT_PORT / client).
_HOST_SERVICE_PORT = 8765
# Addresses that identify the developer workstation running the tests.
_LOCAL_HOST_SERVICE_TARGETS = {
    "localhost", "127.0.0.1", "::1", "0.0.0.0", "",
    "192.168.2.62",
}

if not os.environ.get("WOL_ALLOW_LOCAL_HOST_SERVICE"):
    _orig_create_connection = socket.create_connection

    def _guarded_create_connection(address, *args, **kwargs):
        host, port = address[0], address[1]
        if port == _HOST_SERVICE_PORT and str(host) in _LOCAL_HOST_SERVICE_TARGETS:
            raise AssertionError(
                f"Blocked test connection to host service at {host}:{port}. "
                "A live connection here could shut down the machine running "
                "the tests. Mock socket.create_connection (unit test) or "
                "target a different host, e.g. 192.168.2.111 "
                "(set WOL_ALLOW_LOCAL_HOST_SERVICE=1 to override)."
            )
        return _orig_create_connection(address, *args, **kwargs)

    socket.create_connection = _guarded_create_connection
