"""Single-instance lock for the Wake-on-LAN application (Windows + Linux).

By default only one instance of the application runs per config file. A
second launch tells the running instance to bring its window to the front
and exits itself. The behaviour can be switched off with the
"allow multiple instances" setting (``ui.allow_multiple_instances``), in
which case every launch is independent (the pre-lock behaviour).

Two primitives cooperate:

* :class:`QLockFile` (QtCore) — an atomic, PID-aware lock file inside the
  config directory. A crashed process's lock is reclaimed automatically
  because QLockFile checks whether the owning PID is still alive.
* :class:`QLocalServer` / :class:`QLocalSocket` (QtNetwork) — the primary
  instance listens on a per-config local socket; a second instance
  connects, writes the ``RAISE`` command and quits.

The contract is strict: if another process holds the lock, this process
always exits (``ensure_primary_instance`` returns ``None``) — even when the
holder does not answer the raise request. QLockFile already reclaims locks
of crashed processes inside ``tryLock()`` (dead PID ⇒ lock is stale), so a
failed ``tryLock`` means the holder is alive and starting a second instance
anyway would break the single-instance default. (Only pathological PID
reuse could fake a live holder; delete ``instance-<key>.lock`` to recover.)

The lock identity is derived from the config file path, so parallel setups
using separate config files never block each other, and tests using
``tmp_path`` are isolated for free (override ``lock_path``/``server_name``
directly to sandbox without a config file).
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any, Callable

from PyQt6.QtCore import QLockFile
from PyQt6.QtNetwork import QAbstractSocket, QLocalServer, QLocalSocket

from wol_app.app_core import HEADLESS_MODE

_logger = logging.getLogger("wol_app.single_instance")

#: Command a secondary instance sends to ask the primary to raise its window.
RAISE_COMMAND = b"RAISE"

# The secondary keeps trying for ~1.5 s total: right after a fresh install
# the primary can still be busy (AV scan, first-run config write) when its
# local server has not accepted connections yet.
_CONNECT_ATTEMPTS = 5
_CONNECT_TIMEOUT_MS = 300
_READY_READ_MS = 250
_WRITE_TIMEOUT_MS = 1000


def instance_key(config_path: str | Path) -> str:
    """Stable short identifier for a config file (lock/socket namespace)."""
    return hashlib.sha256(str(config_path).encode("utf-8")).hexdigest()[:16]


class SingleInstanceGuard:
    """Holds the lock + local server of the primary instance.

    The lock and server are kept as attributes so they are not garbage
    collected while the application runs. :meth:`release` is wired to
    ``QApplication.aboutToQuit`` so both are torn down on every exit path.
    """

    def __init__(self, server_name: str) -> None:
        self._server_name = server_name
        self._lock: QLockFile | None = None
        self._server: QLocalServer | None = None
        self._raise_handler: Callable[[], None] | None = None

    # ── Public API ───────────────────────────────────────────────────────

    def set_raise_handler(self, handler: Callable[[], None]) -> None:
        """Register the callback invoked when a second launch asks to raise."""
        self._raise_handler = handler

    def release(self) -> None:
        """Close the local server and release the lock file (idempotent)."""
        if self._server is not None:
            self._server.close()
            QLocalServer.removeServer(self._server_name)
            self._server.deleteLater()
            self._server = None
        if self._lock is not None:
            self._lock.unlock()
            self._lock = None

    # ── Internals ────────────────────────────────────────────────────────

    def _start_server(self) -> bool:
        """Start listening; a stale socket from a crashed run is cleared."""
        server = QLocalServer()
        if not server.listen(self._server_name):
            if (server.serverError()
                    == QAbstractSocket.SocketError.AddressInUseError):
                QLocalServer.removeServer(self._server_name)
                if not server.listen(self._server_name):
                    server.deleteLater()
                    _logger.warning("Could not start single-instance server %r",
                                    self._server_name)
                    return False
            else:
                server.deleteLater()
                _logger.warning("Could not start single-instance server %r: %s",
                                self._server_name, server.serverError())
                return False
        server.newConnection.connect(self._on_new_connection)
        self._server = server
        return True

    def _on_new_connection(self) -> None:
        """Handle one incoming secondary-instance connection (raise request)."""
        if self._server is None:
            return
        conn = self._server.nextPendingConnection()
        if conn is None:
            return
        try:
            conn.waitForReadyRead(_READY_READ_MS)
            data = bytes(conn.readAll())
            if RAISE_COMMAND in data and self._raise_handler is not None:
                self._raise_handler()
        except Exception:  # never let a raise request crash the app
            _logger.exception("Error while handling a raise request")
        finally:
            conn.disconnectFromServer()
            conn.deleteLater()


class _NoopGuard:
    """Stand-in when locking is disabled or unavailable (fail-open)."""

    def set_raise_handler(self, handler: Callable[[], None]) -> None:
        return None

    def release(self) -> None:
        return None


def _notify_running_instance(server_name: str) -> bool:
    """Send RAISE to a running primary. True if a primary accepted it."""
    for _ in range(_CONNECT_ATTEMPTS):
        sock = QLocalSocket()
        sock.connectToServer(server_name)
        if sock.waitForConnected(_CONNECT_TIMEOUT_MS):
            try:
                sock.write(RAISE_COMMAND)
                sock.waitForBytesWritten(_WRITE_TIMEOUT_MS)
            finally:
                sock.disconnectFromServer()
                sock.deleteLater()
            return True
        error = sock.error()
        sock.deleteLater()
        if error == QLocalSocket.LocalSocketError.ServerNotFoundError:
            return False  # no server to notify — nothing more to try
    return False


def _as_primary(app: Any, lock: QLockFile, server_name: str) -> SingleInstanceGuard:
    """Promote an acquired lock to a running primary instance."""
    guard = SingleInstanceGuard(server_name)
    guard._lock = lock
    # Best effort: the instance stays primary even if the IPC server cannot
    # start (a second launch then just fails to notify and falls back).
    guard._start_server()
    if app is not None:
        app.aboutToQuit.connect(guard.release)
    return guard


def ensure_primary_instance(
    app: Any,
    config: Any,
    *,
    lock_path: str | Path | None = None,
    server_name: str | None = None,
) -> SingleInstanceGuard | _NoopGuard | None:
    """Acquire the single-instance lock, or hand off to the running instance.

    Returns
    -------
    guard
        A guard (real or no-op) when this process should continue running.
    None
        Another instance is running: it was asked to raise its window and
        this process must exit.
    """
    if HEADLESS_MODE or config.get_allow_multiple_instances():
        return _NoopGuard()

    key = instance_key(config.config_path)
    server_name = server_name or f"WakeOnLAN-{key}"
    if lock_path is None:
        lock_path = Path(config.config_path).parent / f"instance-{key}.lock"
    lock_path = Path(lock_path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    lock = QLockFile(str(lock_path))
    if lock.tryLock(0):
        return _as_primary(app, lock, server_name)

    # Another instance holds the lock. QLockFile reclaims locks of CRASHED
    # processes inside tryLock() (PID/hostname are checked), so a failed
    # tryLock means the holder is alive. Ask it to raise its window and let
    # this process exit — even when it does not answer (a hung instance is
    # still "the" instance). Starting anyway here was the old fail-open path
    # and exactly how two instances could coexist with the default setting.
    if not _notify_running_instance(server_name):
        _logger.warning(
            "Instance lock %s is held but the running instance did not "
            "respond to the raise request; exiting anyway to keep the "
            "single-instance contract.", lock_path)
    return None
