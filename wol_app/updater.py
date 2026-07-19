"""Auto-Update Module for Wake-on-LAN Manager.

Checks GitHub Releases for a newer version and notifies the user.
Uses only stdlib (urllib) — no external dependencies required.
"""

import json
import tempfile
from datetime import datetime
from urllib.request import Request, urlopen
from urllib.error import URLError

from PyQt6.QtCore import QObject, QThread, pyqtSignal

GITHUB_RELEASES_URL = "https://api.github.com/repos/pdchristian/WOL/releases/latest"
USER_AGENT = "Wake-on-LAN-Manager"


def _parse_version(version_str: str) -> tuple:
    """Parse a version string like '1.2.3' or 'v1.2.3' into a comparable tuple."""
    try:
        clean = version_str.strip().lstrip("v")
        return tuple(int(part) for part in clean.split("."))
    except (ValueError, AttributeError):
        return (0,)


class UpdateChecker(QObject):
    """Background worker that queries the GitHub API for the latest release.

    Usage:
        checker = UpdateChecker(current_version="1.0.0")
        thread = QThread()
        checker.moveToThread(thread)
        thread.started.connect(checker.run)
        checker.finished.connect(on_update_check_finished)
        checker.finished.connect(thread.quit)
        thread.start()
    """

    # Signals: (release_info_dict | None, has_update: bool)
    finished = pyqtSignal(object, bool)

    def __init__(self, current_version: str):
        super().__init__()
        self.current_version = current_version
        self._cancel = False

    def cancel(self):
        """Signal the worker to cancel the current operation."""
        self._cancel = True

    def run(self):
        """Fetch the latest release from GitHub and compare versions."""
        try:
            req = Request(
                GITHUB_RELEASES_URL,
                headers={"Accept": "application/vnd.github.v3+json", "User-Agent": USER_AGENT},
            )
            with urlopen(req, timeout=2) as response:
                if self._cancel:
                    self.finished.emit(None, False)
                    return
                release = json.loads(response.read().decode("utf-8"))

            latest_version = release.get("tag_name", "").lstrip("v")
            has_update = _parse_version(latest_version) > _parse_version(self.current_version)
            self.finished.emit(release, has_update)
        except (URLError, OSError, json.JSONDecodeError, Exception):
            # Network error or parse error — silently report no update
            self.finished.emit(None, False)


class DownloadWorker(QObject):
    """Background worker for downloading an installer file from GitHub.

    Signals:
        progress: (current_bytes, total_bytes)
        finished: (temp_file_path: str)
        error: (message: str)
    """

    progress = pyqtSignal(int, int)   # (downloaded, total)
    finished = pyqtSignal(str)        # temp_file_path
    error = pyqtSignal(str)           # error message

    def __init__(self, download_url: str):
        super().__init__()
        self.download_url = download_url

    def run(self):
        try:
            req = Request(
                self.download_url,
                headers={"User-Agent": USER_AGENT},
            )
            with urlopen(req, timeout=30) as response:
                total = int(response.headers.get("Content-Length", 0))
                downloaded = 0

                # Write to a temp file with .exe extension
                fd, temp_path = tempfile.mkstemp(suffix=".exe")
                try:
                    with open(fd, "wb") as f:
                        while True:
                            chunk = response.read(65536)
                            if not chunk:
                                break
                            f.write(chunk)
                            downloaded += len(chunk)
                            self.progress.emit(downloaded, total)
                except Exception:
                    # Close fd on error
                    import os
                    os.close(fd)
                    raise

            self.finished.emit(temp_path)
        except Exception as e:
            self.error.emit(str(e))


def check_for_updates_sync(current_version: str):
    """Synchronous helper that returns (release_info, has_update).

    Suitable for quick manual checks from the menu where a full thread setup
    is overkill and the call is already user-triggered.
    """
    try:
        req = Request(
            GITHUB_RELEASES_URL,
            headers={"Accept": "application/vnd.github.v3+json", "User-Agent": USER_AGENT},
        )
        with urlopen(req, timeout=15) as response:
            release = json.loads(response.read().decode("utf-8"))

        latest_version = release.get("tag_name", "").lstrip("v")
        has_update = _parse_version(latest_version) > _parse_version(current_version)
        return release, has_update
    except Exception:
        return None, False
