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
        self.finished.emit(ordered)
