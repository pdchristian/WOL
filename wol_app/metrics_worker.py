"""Background workers for the device dashboard (metrics polling + batches).

Both workers follow the :class:`wol_app.scan_worker.ScanWorker` pattern:
create, move to a :class:`QThread`, connect the signals, start. All socket
I/O happens in the worker thread so the UI never blocks.

:class:`MetricsWorker` performs a *single* metrics request per run — the
dashboard view owns the polling timer and only starts the next request when
the previous one finished (single-flight), so slow hosts never pile up.

Both workers support :meth:`cancel`, which closes the in-flight socket so a
blocked ``recv``/``sendall`` aborts immediately. This lets the dashboard join
the thread on close instead of destroying a running ``QThread`` (which crashes
Qt with "QThread: Destroyed while thread is still running").
"""

import threading

from PyQt6.QtCore import QObject, pyqtSignal

from wol_app.host_service_client import get_metrics, run_batch


class _CancellableWorker(QObject):
    """Base worker holding the in-flight socket so it can be cancelled."""

    def __init__(self) -> None:
        super().__init__()
        self._sock = None
        self._cancelled = False
        self._lock = threading.Lock()

    def _sink(self, sock) -> None:
        """Socket sink handed to the client: remember, or close if cancelled."""
        with self._lock:
            if self._cancelled:
                cancelled = True
            else:
                self._sock = sock
                cancelled = False
        if cancelled:
            try:
                sock.close()
            except OSError:
                pass

    def cancel(self) -> None:
        """Abort the request: close the in-flight socket (thread-safe)."""
        with self._lock:
            self._cancelled = True
            sock = self._sock
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass

    @property
    def cancelled(self) -> bool:
        return self._cancelled


class MetricsWorker(_CancellableWorker):
    """Fetch one metrics sample from the WOL Host Service of one device."""

    metrics_ready = pyqtSignal(dict)  # metrics dict (values may be None)
    failed = pyqtSignal(str)          # human-readable error message

    def __init__(
        self,
        ip: str,
        username: str = "",
        password: str = "",
        timeout: float = 5.0,
    ) -> None:
        super().__init__()
        self.ip = ip
        self.username = username
        self.password = password
        self.timeout = timeout

    def run(self) -> None:
        ok, result = get_metrics(
            self.ip, self.username, self.password,
            timeout=self.timeout, sock_sink=self._sink,
        )
        if self.cancelled:
            return  # dashboard closed — do not signal into a dying view
        if ok and isinstance(result, dict):
            self.metrics_ready.emit(result)
        else:
            self.failed.emit(str(result))


class BatchWorker(_CancellableWorker):
    """Run one batch script on the WOL Host Service of one device."""

    batch_finished = pyqtSignal(dict)  # exit_code/stdout/stderr/duration_ms/truncated
    failed = pyqtSignal(str)           # transport/auth/gating error message

    def __init__(
        self,
        ip: str,
        script: str,
        username: str = "",
        password: str = "",
        timeout: float = 120.0,
    ) -> None:
        super().__init__()
        self.ip = ip
        self.script = script
        self.username = username
        self.password = password
        self.timeout = timeout

    def run(self) -> None:
        ok, result = run_batch(
            self.ip, self.script, self.username, self.password,
            timeout=self.timeout, sock_sink=self._sink,
        )
        if self.cancelled:
            return
        if ok and isinstance(result, dict):
            self.batch_finished.emit(result)
        else:
            self.failed.emit(str(result))
