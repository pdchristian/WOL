"""Shared application core for the Wake-on-LAN Manager (Windows + Linux).

Holds the headless-mode flag, the thread-tracking registry and the
status-check worker that the modern views import. Keeping these here means
the views depend only on :mod:`wol_app.app_core`, never on the classic
``MainWindow`` — which does not exist on the Linux (Modern-UI-only) port.

``wol_app.main_window`` re-exports these symbols for backwards compatibility.
"""

import os

from PyQt6.QtCore import QObject, pyqtSignal

# Module-level registry to hold thread references until native threads truly finish.
# Prevents premature GC of QThread wrapper objects while C-level I/O is blocked.
_active_threads: list = []


def _track_thread(thread: QObject) -> None:
    """Keep a strong reference to *thread* until it finishes, then auto-remove.

    This guarantees the registry never grows unbounded even if a worker's
    dedicated cleanup callback is missed or disconnected.
    """
    _active_threads.append(thread)

    def _on_finished() -> None:
        try:
            if thread in _active_threads:
                _active_threads.remove(thread)
        except Exception:
            pass

    thread.finished.connect(_on_finished)


# Headless/test mode: disables all background threads to avoid QThread shutdown warnings.
# Set WOL_HEADLESS=1 in test/headless environments (CI, automated tests, no display).
HEADLESS_MODE: bool = os.environ.get("WOL_HEADLESS", "").lower() in ("1", "true", "yes")


class StatusWorker(QObject):
    """Background worker for checking device statuses without blocking the UI."""

    finished = pyqtSignal(list)  # Emits list of (device_id, name, status, msg)

    # Max concurrent pings to avoid overwhelming the network
    MAX_CONCURRENT = 16

    def __init__(self, engine) -> None:
        super().__init__()
        self.engine = engine
        self._cancelled = False

    def cancel(self) -> None:
        """Signal the worker to stop."""
        self._cancelled = True

    def run(self) -> None:
        import concurrent.futures

        devices = [d for d in self.engine.config.get_devices() if d.get("enabled", True)]
        if self._cancelled or not devices:
            self.finished.emit([])
            return

        results: dict[str, tuple] = {}

        def _check(device_id: str) -> tuple[str, str, str]:
            status, msg = self.engine.check_device_status(device_id)
            return (device_id, status, msg)

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=min(self.MAX_CONCURRENT, len(devices))
        ) as pool:
            futures = {pool.submit(_check, d["id"]): d["id"] for d in devices}
            for future in concurrent.futures.as_completed(futures):
                if self._cancelled:
                    break
                device_id = futures[future]
                try:
                    did, status, msg = future.result()
                    results[did] = (did, status, msg)
                except Exception:
                    results[device_id] = (device_id, "unknown", "Error checking status")

        # Build ordered result list (device_id, name, status, msg)
        ordered = []
        for device in devices:
            did = device["id"]
            if did in results:
                _, status, msg = results[did]
                ordered.append((did, device["name"], status, msg))
        if self._cancelled:
            # The view that started us is already gone — emitting into a
            # deleted receiver crashes the process instead of warning.
            return
        self.finished.emit(ordered)


class OsDetectWorker(QObject):
    """Background platform detection for stored devices that have none.

    Devices added by hand — or added before the scanner started storing the
    platform — have no ``os`` value, so the platform pill would stay at
    "unknown" and the Remote buttons could not pick the right client. This
    worker runs the already-implemented fingerprint of
    :mod:`wol_app.os_detect` for exactly those devices (never for devices
    that already carry a platform) and reports what it found; persisting is
    left to the caller.
    """

    # Emits list of (device_id, os_id, confidence, source)
    finished = pyqtSignal(list)

    # Fewer parallel probes than the status sweep: every device costs a
    # host-service connect, a ping and an SMB probe.
    MAX_CONCURRENT = 8

    def __init__(self, config) -> None:
        super().__init__()
        self.config = config
        self._cancelled = False

    def cancel(self) -> None:
        """Signal the worker to stop."""
        self._cancelled = True

    # Addresses tried per device when the name has several DNS records.
    MAX_TARGETS_PER_DEVICE = 3

    @staticmethod
    def probe_targets(device: dict) -> tuple[list[str], str]:
        """Return ``(probe addresses, name hint)`` for *device*.

        ``ip`` may hold a DNS name (xrdp/Linux hosts are commonly reached by
        name). The TTL ping needs a real IPv4 — ``os_detect.get_ping_ttl``
        rejects names — so the name is resolved first; the TCP probes and the
        host-service query work with either. A name can have several records
        (and the first one may be a stale lease), so every address is tried
        until one answers.
        """
        from wol_app.utils import resolve_ipv4_all, validate_ip

        value = (device.get("ip") or "").strip()
        if not value:
            return [], ""
        if validate_ip(value):
            return [value], device.get("name", "") or value
        ips = resolve_ipv4_all(value)
        return (list(ips[:OsDetectWorker.MAX_TARGETS_PER_DEVICE])
                if ips else [value]), value

    def run(self) -> None:
        import concurrent.futures

        from wol_app.os_detect import fingerprint_host
        from wol_app.utils import normalize_os

        devices = [
            d for d in self.config.get_devices()
            if d.get("enabled", True)
            and not normalize_os(d.get("os", ""))
            and (d.get("ip") or "").strip()
        ]
        if self._cancelled or not devices:
            self.finished.emit([])
            return

        def _probe(device: dict) -> tuple[str, str, str, str]:
            targets, hostname = self.probe_targets(device)
            os_id, confidence, source = "", "", ""
            for target in targets:
                if self._cancelled:
                    break
                try:
                    found = fingerprint_host(
                        target, hostname=hostname, mac=device.get("mac", "")
                    )
                except Exception:
                    # A probe must never break the sweep — the device just
                    # stays without a platform.
                    continue
                os_id, confidence, source = found
                if normalize_os(os_id):
                    break
            return (device["id"], normalize_os(os_id), confidence, source)

        results: dict[str, tuple] = {}
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=min(self.MAX_CONCURRENT, len(devices))
        ) as pool:
            futures = {pool.submit(_probe, d): d["id"] for d in devices}
            for future in concurrent.futures.as_completed(futures):
                if self._cancelled:
                    break
                device_id = futures[future]
                try:
                    results[device_id] = future.result()
                except Exception:
                    results[device_id] = (device_id, "", "", "")

        ordered = [results[d["id"]] for d in devices if d["id"] in results]
        if self._cancelled:
            # cancel_workers() already tore the view down — emitting into a
            # deleted receiver crashes the process instead of warning.
            return
        self.finished.emit(ordered)
