"""Update Dialogs for Wake-on-LAN Manager.

Shows release notes when a new version is available and provides
buttons to download, dismiss, or skip the update.
"""

import json
import os
import subprocess
import sys
import tempfile
import threading
from datetime import datetime

from PyQt6.QtCore import QUrl, QTimer, Qt
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QProgressDialog,
    QTextBrowser,
    QVBoxLayout,
)

from wol_app.updater import DownloadWorker


def _launch_installer_safe(temp_path: str) -> bool:
    """Try to launch the installer with admin rights. Returns True on success."""
    try:
        import ctypes
        import os
        result = ctypes.windll.shell32.ShellExecuteW(
            None,              # HWND
            "runas",           # verb — triggers UAC elevation prompt
            temp_path,         # executable path
            "",               # no silent flag — let the installer show its GUI
            os.path.dirname(temp_path),  # working directory for elevated process
            1                 # SW_SHOWNORMAL — visible to user
        )
        # ShellExecute returns an error code <= 32 on failure
        if int(result) <= 32:
            return False
        return True
    except Exception:
        return False


class UpdateAvailableDialog(QDialog):
    """Dialog shown when a new version is detected."""

    def __init__(self, release_info: dict, current_version: str, parent=None):
        super().__init__(parent)
        self.release_info = release_info
        self.current_version = current_version
        self.setWindowTitle("Update Verfübar")
        self.setMinimumSize(520, 420)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Title with version info
        tag_name = self.release_info.get("tag_name", "")
        title_label = QLabel(
            f"Ein Update für Wake-on-LAN Manager ist verfügbar!<br>"
            f"<b>Aktuelle Version:</b> {self.current_version}<br>"
            f"<b>Neue Version:</b> {tag_name}"
        )
        title_label.setStyleSheet("font-size: 14px; padding: 8px;")
        title_label.setWordWrap(True)
        layout.addWidget(title_label)

        # Release date
        published_at = self.release_info.get("published_at", "")
        if published_at:
            try:
                dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
                date_label = QLabel(f"Veröffentlicht am: {dt.strftime('%d.%m.%Y')}")
                date_label.setStyleSheet("padding: 4px;")
                layout.addWidget(date_label)
            except (ValueError, TypeError):
                pass

        # Release notes
        section_label = QLabel("<b>Release Notes:</b>")
        layout.addWidget(section_label)

        self.release_notes = QTextBrowser()
        body = self.release_info.get("body", "Keine Release Notes verfügbar.")
        self.release_notes.setMarkdown(body)
        self.release_notes.setOpenExternalLinks(True)
        layout.addWidget(self.release_notes, 1)

        # Skip version checkbox
        self.skip_checkbox = QCheckBox("Dieses Update überspringen")
        layout.addWidget(self.skip_checkbox)

        # Buttons
        btn_layout = QHBoxLayout()

        self.download_btn = QPushButton("Herunterladen und Installieren")
        self.download_btn.setObjectName("primaryButton")
        self.download_btn.clicked.connect(self._download_and_install)
        btn_layout.addWidget(self.download_btn)

        later_btn = QPushButton("Nicht Jetzt")
        later_btn.clicked.connect(self._reject_without_skip)
        btn_layout.addWidget(later_btn)

        github_btn = QPushButton("Auf GitHub ansehen")
        github_btn.clicked.connect(self._open_github)
        btn_layout.addWidget(github_btn)

        layout.addLayout(btn_layout)

    def _reject_without_skip(self):
        """Close dialog without marking version as skipped."""
        self.reject()

    def _download_and_install(self):
        """Download the latest installer .exe and launch it."""
        assets = self.release_info.get("assets", [])
        installer_asset = None

        for asset in assets:
            name = asset["name"]
            if "installer" in name.lower() and name.endswith(".exe"):
                installer_asset = asset
                break

        if not installer_asset:
            # Fallback: find any .exe
            for asset in assets:
                if asset["name"].endswith(".exe"):
                    installer_asset = asset
                    break

        if not installer_asset:
            self._show_error("Kein Installationsprogramm gefunden.")
            return

        download_url = installer_asset.get("browser_download_url", "")
        if not download_url:
            self._show_error("Download-URL nicht verfügbar.")
            return

        # Show progress dialog
        self._progress = QProgressDialog(
            "Update wird heruntergeladen...", "Abbrechen", 0, 100, self
        )
        self._progress.setWindowTitle("Update Download")
        self._progress.setWindowModality(Qt.WindowModality.ApplicationModal)
        self._progress.setAutoClose(False)
        self._progress.setAutoReset(False)
        self._progress.show()

        # Shared state between download thread and UI polling timer (protected by lock)
        self._download_state = {
            "done": False,
            "error": None,
            "temp_path": None,
            "downloaded": 0,
            "total": 0,
        }
        self._download_lock = threading.Lock()

        def download_worker(url, state, lock):
            """Download in background thread and update state dict."""
            fd = -1
            try:
                from urllib.request import Request, urlopen
                req = Request(url, headers={"User-Agent": "Wake-on-LAN-Manager"})
                with urlopen(req, timeout=60) as response:
                    total = int(response.headers.get("Content-Length", 0))
                    downloaded = 0

                    fd, temp_path = tempfile.mkstemp(suffix=".exe")
                    try:
                        with os.fdopen(fd, "wb") as f:
                            fd = -1  # fd now owned by the file object
                            while True:
                                chunk = response.read(65536)
                                if not chunk:
                                    break
                                f.write(chunk)
                                downloaded += len(chunk)
                                with lock:
                                    state["downloaded"] = downloaded
                                    state["total"] = total
                    except Exception:
                        if fd >= 0:
                            os.close(fd)
                        raise

                with lock:
                    state["temp_path"] = temp_path
            except Exception as e:
                with lock:
                    state["error"] = str(e)
                if fd >= 0:
                    try:
                        os.close(fd)
                    except OSError:
                        pass
            finally:
                with lock:
                    state["done"] = True

        # Start background download thread
        thread = threading.Thread(
            target=download_worker,
            args=(download_url, self._download_state, self._download_lock),
            daemon=True,
        )
        thread.start()

        # Poll download progress from UI thread using QTimer (avoids QThread signal issues in modal dialogs)
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._on_poll_progress)
        self._poll_timer.start(200)  # Update every 200ms

    def _on_poll_progress(self):
        """Poll download state from background thread and update UI."""
        state = getattr(self, '_download_state', None)
        if not state:
            return

        progress = getattr(self, '_progress', None)
        if not progress:
            return

        lock = getattr(self, '_download_lock', threading.Lock())
        with lock:
            total = state.get("total", 0)
            downloaded = state.get("downloaded", 0)
            done = state["done"]
            error = state.get("error")
            temp_path = state.get("temp_path")

        if total > 0:
            pct = int(downloaded / total * 100)
            progress.setValue(pct)
        else:
            # Unknown size, show indeterminate with bytes counter
            progress.setMaximum(0)
            progress.setValue(int(downloaded // 1024))

        if done:
            self._poll_timer.stop()
            if error:
                self._on_download_error(error)
            elif temp_path:
                self._on_download_finished(temp_path)
            return

    def _open_github(self):
        """Open the GitHub release page in browser."""
        tag_name = self.release_info.get("tag_name", "")
        url = QUrl.fromUserInput(f"https://github.com/pdchristian/WOL/releases/tag/{tag_name}")
        QDesktopServices.openUrl(url)

    def _on_download_finished(self, temp_path: str):
        """Schedule shutdown sequence on main Qt thread to avoid race conditions."""
        if hasattr(self, '_progress') and self._progress:
            self._progress.close()

        # Store installer path for deferred execution on main thread
        self._installer_path = temp_path

        # Schedule shutdown on the main Qt event loop — ensures closeEvent
        # can properly stop QThread workers before exit
        QTimer.singleShot(100, self._perform_shutdown)

    def _perform_shutdown(self):
        """Execute on main Qt thread: launch installer → close dialog → exit.

        IMPORTANT: The installer MUST be launched BEFORE closing the dialog.
        Calling self.accept() immediately destroys the modal context, which
        can cause crashes if subsequent Qt operations (like QTimer callbacks)
        depend on the parent MainWindow's event loop state.

        By launching the native ShellExecuteW call first (pure Win32 API,
        non-Qt), we ensure the installer is spawned while the dialog is still
        fully alive, then close cleanly afterward.
        """
        # 1. Launch installer FIRST — while dialog is still fully alive
        success = _launch_installer_safe(self._installer_path)

        # 2. Close the dialog (this triggers exec() → return on MainWindow)
        self.accept()

        # 3. Exit immediately — ShellExecuteW spawns an independent process,
        #    so the installer survives after this process exits.
        if success:
            QApplication.instance().exit(0)

    def _on_download_error(self, message: str):
        """Handle download failure."""
        if hasattr(self, '_progress') and self._progress:
            self._progress.close()
        self._show_error(f"Download fehlgeschlagen: {message}")

    def _show_error(self, message: str):
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.warning(self, "Update-Fehler", message)


class UpdateInfoDialog(QDialog):
    """Simple confirmation dialog when the user is already on the latest version."""

    def __init__(self, current_version: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Aktualitäts-Prüfung")
        self.setMinimumWidth(380)
        self._setup_ui(current_version)

    def _setup_ui(self, version: str):
        layout = QVBoxLayout(self)

        icon_label = QLabel("✅")
        icon_label.setStyleSheet("font-size: 32px;")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)

        info_label = QLabel(
            f"<b>Sie verwenden die aktuellste Version.</b><br>"
            f"Wake-on-LAN Manager {version}"
        )
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(ok_btn)
        layout.addLayout(btn_layout)


class UpdateErrorDialog(QDialog):
    """Shown when the update check itself fails (network error, etc.)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Update-Prüfung fehlgeschlagen")
        self.setMinimumWidth(380)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        icon_label = QLabel("⚠️")
        icon_label.setStyleSheet("font-size: 32px;")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)

        info_label = QLabel(
            "<b>Die Aktualitätsprüfung konnte nicht durchgeführt werden.</b><br><br>"
            "Überprüfen Sie Ihre Internetverbindung und versuchen Sie es später erneut."
        )
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(ok_btn)
        layout.addLayout(btn_layout)
