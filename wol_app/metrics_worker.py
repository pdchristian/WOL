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
        watch: "list[str] | None" = None,
    ) -> None:
        super().__init__()
        self.ip = ip
        self.username = username
        self.password = password
        self.timeout = timeout
        self.watch = watch

    def run(self) -> None:
        try:
            ok, result = get_metrics(
                self.ip, self.username, self.password,
                timeout=self.timeout, sock_sink=self._sink,
                watch=self.watch,
            )
        except Exception as e:  # never let run() raise: it would wedge the
            # dashboard's single-flight flag and leave the QThread dangling.
            if not self.cancelled:
                self.failed.emit(str(e))
            return
        if self.cancelled:
            return  # dashboard closed — do not signal into a dying view
        if ok and isinstance(result, dict):
            self.metrics_ready.emit(result)
        else:
            self.failed.emit(str(result))


class InferenceSweepWorker(QObject):
    """Poll the inference-activity badge state for many devices at once.

    One ``metrics`` request per device (with the device's watch list), run in
    a small thread pool like :class:`wol_app.app_core.StatusWorker` — the
    devices view owns the timer and only starts the next sweep when the
    previous one finished (single-flight). Each result carries the full
    metrics response so the view can derive the badge state from
    ``processes[*]["requests_active"]`` (host protocol v9); ``None`` means
    the host was unreachable or rejected the request.

    Unlike :class:`_CancellableWorker` the sockets are not individually
    closable (many run at once), so ``cancel`` only stops collecting results;
    the per-request timeout bounds the tail.
    """

    # Emits list of (device_id, metrics_response_dict | None).
    finished = pyqtSignal(list)

    # Max concurrent metrics requests (hosts answer in ~1 s; 8 keeps a
    # sweep of the 8-device watch limit comfortably parallel).
    MAX_CONCURRENT = 8

    def __init__(
        self,
        devices: "list[dict]",
        timeout: float = 4.0,
    ) -> None:
        super().__init__()
        # Each device dict: {"id", "ip", "username", "password", "watch"}.
        self.devices = devices
        self.timeout = timeout
        self._cancelled = False

    def cancel(self) -> None:
        """Stop collecting results (in-flight requests finish on timeout)."""
        self._cancelled = True

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    def run(self) -> None:
        import concurrent.futures

        if self._cancelled or not self.devices:
            self.finished.emit([])
            return

        def _fetch(device: dict):
            ok, result = get_metrics(
                device["ip"], device.get("username", ""),
                device.get("password", ""),
                timeout=self.timeout, watch=device.get("watch") or None,
            )
            return result if ok and isinstance(result, dict) else None

        results: "dict[str, dict | None]" = {}
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=min(self.MAX_CONCURRENT, len(self.devices))
        ) as pool:
            futures = {pool.submit(_fetch, d): d["id"] for d in self.devices}
            for future in concurrent.futures.as_completed(futures):
                if self._cancelled:
                    break
                device_id = futures[future]
                try:
                    results[device_id] = future.result()
                except Exception:
                    results[device_id] = None

        if self._cancelled:
            return  # view closed — do not signal into a dying view
        ordered = [
            (d["id"], results.get(d["id"]))
            for d in self.devices if d["id"] in results
        ]
        self.finished.emit(ordered)


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
        try:
            ok, result = run_batch(
                self.ip, self.script, self.username, self.password,
                timeout=self.timeout, sock_sink=self._sink,
            )
        except Exception as e:  # never let run() raise — thread.quit is
            # connected to the result signals and would never fire otherwise.
            if not self.cancelled:
                self.failed.emit(str(e))
            return
        if self.cancelled:
            return
        if ok and isinstance(result, dict):
            self.batch_finished.emit(result)
        else:
            self.failed.emit(str(result))
