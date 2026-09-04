"""Optional GUI freeze watchdog (diagnostics, opt-in via ``WOL_WATCHDOG``).

Enable by setting the environment variable ``WOL_WATCHDOG`` before starting
the app — either ``1`` (default timeout 5 s) or a number of seconds
(e.g. ``WOL_WATCHDOG=3``). When the GUI thread stops beating for longer
than the timeout — i.e. the window "does not respond" — a monitor thread
dumps the Python stacks of **all** threads (via :mod:`faulthandler`) to::

    %LOCALAPPDATA%\\WakeOnLAN\\wol_watchdog.log

The dump is written once per hang (re-arms after the GUI thread recovers).
The watchdog is pure diagnostics: it never changes behaviour and is fully
disabled by default.

Usage (main_window.main)::

    watchdog = maybe_start_watchdog(app)   # no-op unless WOL_WATCHDOG is set
"""

import faulthandler
import os
import threading
import time
from datetime import datetime
from pathlib import Path

DEFAULT_TIMEOUT_S = 5.0
BEAT_INTERVAL_MS = 1000

_LOG_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "WakeOnLAN"
LOG_FILE = _LOG_DIR / "wol_watchdog.log"


def _env_flag() -> float | None:
    """Return the configured timeout seconds, or None when disabled.

    ``WOL_WATCHDOG`` accepts ``1``/``true``/``yes`` (default timeout) or a
    positive number of seconds.
    """
    raw = os.environ.get("WOL_WATCHDOG", "").strip().lower()
    if not raw or raw in ("0", "false", "no", "off"):
        return None
    if raw in ("1", "true", "yes", "on"):
        return DEFAULT_TIMEOUT_S
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_TIMEOUT_S
    return value if value > 0 else None


class GuiWatchdog(threading.Thread):
    """Monitor thread that dumps all stacks when the GUI thread stalls.

    The GUI thread must call :meth:`beat` regularly (a QTimer does this).
    If :attr:`timeout_s` passes without a beat, the stacks of every Python
    thread are appended to the log file — the exact code path of the hang.
    """

    def __init__(self, timeout_s: float = DEFAULT_TIMEOUT_S,
                 log_path: Path | None = None) -> None:
        super().__init__(name="GuiWatchdog", daemon=True)
        self.timeout_s = timeout_s
        self.log_path = Path(log_path) if log_path else LOG_FILE
        self._last_beat = time.monotonic()
        self._hang_dumped = False
        # NB: not "_stop" — threading.Thread owns an internal _stop attribute.
        self._stop_event = threading.Event()
        self.hangs = 0

    def beat(self) -> None:
        """Call from the GUI thread to signal 'still alive'."""
        self._last_beat = time.monotonic()
        self._hang_dumped = False

    def stop(self) -> None:
        self._stop_event.set()

    # -- thread body --------------------------------------------------------

    def run(self) -> None:
        while not self._stop_event.wait(0.5):
            stalled = time.monotonic() - self._last_beat
            if stalled >= self.timeout_s and not self._hang_dumped:
                self._hang_dumped = True
                self.hangs += 1
                self._dump(stalled)

    def _dump(self, stalled_s: float) -> None:
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.log_path, "a", encoding="utf-8") as fh:
                fh.write(
                    f"\n===== GUI freeze: no beat for {stalled_s:.1f} s "
                    f"at {datetime.now().isoformat(timespec='seconds')} "
                    f"=====\n")
                fh.flush()
                faulthandler.dump_traceback(file=fh, all_threads=True)
        except OSError:
            pass  # diagnostics must never crash the app


def maybe_start_watchdog(app) -> GuiWatchdog | None:
    """Start the watchdog when ``WOL_WATCHDOG`` is set; otherwise no-op.

    ``app`` is the QApplication instance — used as the QTimer parent and to
    stop the watchdog on quit.
    """
    timeout_s = _env_flag()
    if timeout_s is None or app is None:
        return None
    from PyQt6.QtCore import QTimer

    watchdog = GuiWatchdog(timeout_s=timeout_s)
    watchdog.start()
    timer = QTimer(app)
    timer.setInterval(BEAT_INTERVAL_MS)
    timer.timeout.connect(watchdog.beat)
    timer.start()
    app.aboutToQuit.connect(watchdog.stop)
    try:
        watchdog.log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(watchdog.log_path, "a", encoding="utf-8") as fh:
            fh.write(f"\n--- watchdog started "
                     f"{datetime.now().isoformat(timespec='seconds')} "
                     f"(timeout {timeout_s:.1f} s) ---\n")
    except OSError:
        pass
    return watchdog
