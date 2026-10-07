"""Regression tests for QThread object lifetime.

Background: the packaged app aborted with Windows exception code
0xC0000409 (``abort()``). The crash dump showed the Qt fatal message
``QThread: Destroyed while thread '%ls' is still running`` reached through
``QThread::~QThread`` -> ``QMessageLogger::fatal`` -> ``abort()``. Qt cannot
recover from that condition, so *any* code path that lets the last reference
to a running QThread go away — or that schedules ``deleteLater()`` on one —
is a crash rather than a warning.
"""

import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("WOL_HEADLESS", "1")

import pytest  # noqa: E402

pytest.importorskip("PyQt6")

from PyQt6.QtCore import QObject, QThread, pyqtSignal  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from wol_app import host_service_installer as hsi  # noqa: E402
from wol_app.app_core import release_finished_thread  # noqa: E402
from wol_app.config import ConfigManager  # noqa: E402
from wol_app.translations import Translations  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(autouse=True)
def _translations():
    Translations().load("de")


def pump(app, seconds: float = 0.5) -> None:
    """Spin the event loop for a while (a modal message box does the same)."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.005)


# ── host service installer: holder released while the thread runs ──────────

class TrackedHolder(dict):
    """Dict that records every QThread released while it was still running."""

    def __init__(self):
        super().__init__()
        self.released_while_running = []

    def pop(self, key, *args):
        obj = self.get(key)
        if isinstance(obj, QThread) and obj.isRunning():
            self.released_while_running.append(obj)
        return super().pop(key, *args)


class _SlowWorker(QObject):
    """Emits ``finished`` and then keeps its thread's event loop alive.

    Real installs behave the same way: ``run()`` emits ``finished`` as its
    last statement, so the worker thread is still running (it only exits on
    the ``quit()`` posted from the GUI thread) while the GUI-side handler —
    which opens a modal ``QMessageBox`` — runs.
    """

    finished = pyqtSignal(str, str)

    def __init__(self, action: str, texts: dict) -> None:
        super().__init__()
        self.action = action

    def run(self) -> None:
        self.finished.emit("2.4.0", "")
        time.sleep(0.3)


def test_privileged_action_never_releases_a_running_thread(qapp, monkeypatch):
    """The holder must keep the QThread alive until it has actually finished."""
    monkeypatch.setattr(hsi, "make_worker_class", lambda: _SlowWorker)

    holder = TrackedHolder()
    results = []

    def on_result(outcome: str, message: str) -> None:
        # Stand-in for QMessageBox.information(): spins a nested event loop.
        pump(qapp, 0.6)
        results.append((outcome, message))

    hsi.run_privileged_action("install", {}, on_result, holder)
    pump(qapp, 1.5)

    assert holder.released_while_running == [], (
        "QThread was released from the holder while still running")
    assert dict(holder) == {}, "holder was not cleaned up after finishing"
    assert results == [("2.4.0", "")]


# ── views: stale ``finished`` handlers must not touch the current thread ───

class _SlotRecorder:
    """Stands in for ``QThread.finished`` so the test picks delivery time."""

    def __init__(self):
        self.slots = []

    def connect(self, slot) -> None:
        self.slots.append(slot)


class FakeThread(QThread):
    """QThread whose lifecycle the test controls completely."""

    def __init__(self):
        super().__init__()
        self.running = True
        self.delete_later_called = False
        # Shadows QThread.finished: nothing is delivered until deliver_finished().
        self.finished = _SlotRecorder()

    def start(self, priority=None) -> None:
        self.running = True

    def isRunning(self) -> bool:  # noqa: N802
        return self.running

    def quit(self) -> None:
        pass

    def wait(self, msecs: int = -1) -> bool:
        return True

    def deleteLater(self) -> bool:  # noqa: N802
        self.delete_later_called = True
        return True

    def deliver_finished(self) -> None:
        """Deliver the queued ``finished`` signal to every connected slot."""
        self.running = False
        for slot in list(self.finished.slots):
            slot()


class FakeStatusWorker(QObject):
    finished = pyqtSignal(list)
    progress = pyqtSignal(str, int, int)

    def __init__(self, engine=None):
        super().__init__()

    def run(self) -> None:
        pass

    def cancel(self) -> None:
        pass


@pytest.fixture
def devices_view(qapp, tmp_path, monkeypatch):
    from wol_app.views import devices_view as dv

    threads: list[FakeThread] = []

    def make_thread() -> FakeThread:
        thread = FakeThread()
        threads.append(thread)
        return thread

    # refresh_statuses() is skipped in headless mode; the test drives the
    # threading bookkeeping itself, so no real worker/ping is started.
    monkeypatch.setattr(dv, "HEADLESS_MODE", False)
    monkeypatch.setattr(dv, "QThread", make_thread)
    monkeypatch.setattr(dv, "StatusWorker", FakeStatusWorker)

    view = dv.DevicesView(ConfigManager(str(tmp_path / "devices.json")))
    yield view, threads
    view.cancel_workers()


def test_stale_finished_handler_does_not_delete_current_sweep(devices_view):
    """A finished sweep must not deleteLater() the sweep that replaced it.

    ``QThread.finished`` is emitted from the worker thread and delivered to
    the GUI thread as a *queued* event, so it can be delivered after a newer
    sweep already took over the view attribute. The old handler read
    ``self._status_thread`` at call time and scheduled ``deleteLater()`` on
    the running thread — Qt then aborted the process.
    """
    view, threads = devices_view

    view.refresh_statuses()
    first = threads[0]
    first.running = False        # thread ended; queued handler not delivered

    view.refresh_statuses()      # a second sweep takes over
    second = threads[1]
    assert view._status_thread is second

    first.deliver_finished()     # the stale handler runs now
    assert not second.delete_later_called, (
        "stale finished handler scheduled deleteLater() on the running thread")
    assert view._status_thread is second, (
        "stale finished handler cleared the attribute of the current sweep")
    assert first.delete_later_called, "the finished thread was not released"

    second.deliver_finished()
    assert second.delete_later_called
    assert view._status_thread is None


# ── the shared helper itself ───────────────────────────────────────────────

class _Owner:
    def __init__(self):
        self.thread = None


def test_release_finished_thread_only_clears_the_current_attribute():
    owner = _Owner()
    old, current = FakeThread(), FakeThread()

    owner.thread = old
    assert release_finished_thread(owner, "thread", old) is True
    assert owner.thread is None
    assert old.delete_later_called

    # A stale handler for `old` must leave the running `current` untouched.
    owner.thread = current
    assert release_finished_thread(owner, "thread", old) is False
    assert owner.thread is current
    assert not current.delete_later_called

    assert release_finished_thread(owner, "thread", current) is True
    assert owner.thread is None
    assert current.delete_later_called
