"""Modern UI: "Über" screen (about + update check).

Layout mirrors the prototype's about screen
(Design_Prototpye/dark_control_center_full.html) — a single centered
block (max-width 420 px, vertically centered, no page header):

1. Gradient logo tile ("W").
2. App name (h2) and dim version line.
3. One dim description paragraph.
4. A centered toolbar with "Nach Updates suchen" (primary) and
   "Changelog", plus an inline status label for the check result.

The check itself reuses the shared ``updater.check_for_updates_sync``
(same GitHub Releases API as the classic UI) on a background
``QThread``; when an update is available the classic
``UpdateAvailableDialog`` opens so download/install stays feature
identical. "Changelog" opens the GitHub releases page in the browser.
"""

from typing import Any

from PyQt6.QtCore import QObject, Qt, QThread, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from wol_app import __version__
from wol_app.main_window import HEADLESS_MODE
from wol_app.translations import Translations
from wol_app.update_dialog import UpdateAvailableDialog
from wol_app.updater import check_for_updates_sync

# GitHub releases page (changelog) for the application.
CHANGELOG_URL = "https://github.com/pdchristian/WOL/releases"


class _CheckWorker(QObject):
    """Background worker around the synchronous update check.

    Emits ``finished`` with ``(release_info, has_update)`` or ``None``
    when the check failed (network/parse error) — the same tri-state the
    classic manual menu check distinguishes.
    """

    finished = pyqtSignal(object)  # tuple | None

    def run(self) -> None:
        result = check_for_updates_sync(current_version=__version__)
        self.finished.emit(result)


class UpdateView(QWidget):
    """The modern "Über" screen (about + update check)."""

    def __init__(self, config_manager: Any, parent=None) -> None:
        super().__init__(parent)
        self.config: Any = config_manager
        self._check_thread: QThread | None = None
        self._check_worker: _CheckWorker | None = None
        self._setup_ui()

    # ── UI construction ──────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)

        content = QWidget()
        content.setObjectName("pageContent")
        content.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        scroll.setWidget(content)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(32, 26, 32, 26)
        layout.setSpacing(0)

        # ── Centered about block (prototype .about: max-width 420, auto) ──
        # No page header: the prototype's about screen is header-less.
        # One 420 px-wide container holds the whole block so paragraphs
        # use the full width and wrap like in the prototype.
        layout.addStretch(1)

        block = QWidget()
        block.setObjectName("aboutBlock")
        block.setMaximumWidth(420)
        about = QVBoxLayout(block)
        about.setContentsMargins(0, 0, 0, 0)
        about.setSpacing(0)
        layout.addWidget(block, 0, Qt.AlignmentFlag.AlignHCenter)

        logo = QLabel("W")
        logo.setObjectName("aboutLogo")
        logo.setFixedSize(84, 84)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        about.addWidget(logo, 0, Qt.AlignmentFlag.AlignHCenter)
        self.logo = logo

        # Extra clearance below the logo so the (vertically centered) title
        # never overlaps the logo tile on high-DPI / larger-font systems.
        about.addSpacing(32)

        self.app_name = QLabel(Translations.tr("app.name"))
        self.app_name.setObjectName("aboutTitle")
        self.app_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        about.addWidget(self.app_name, 0, Qt.AlignmentFlag.AlignHCenter)

        about.addSpacing(6)

        self.version_label = QLabel(
            f"{Translations.tr('dialog.about.version')} {__version__}")
        self.version_label.setObjectName("aboutVersion")
        self.version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        about.addWidget(self.version_label, 0, Qt.AlignmentFlag.AlignHCenter)

        about.addSpacing(28)

        # Single description paragraph (prototype .about p)
        self.description = QLabel(Translations.tr("dialog.about.description"))
        self.description.setObjectName("aboutText")
        self.description.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.description.setWordWrap(True)
        about.addWidget(self.description)

        about.addSpacing(28)

        # Toolbar: check (primary) + changelog, centered (prototype)
        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)
        toolbar.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.check_btn = QPushButton(Translations.tr("modern.update.button.check"))
        self.check_btn.setObjectName("primaryButton")
        self.check_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.check_btn.clicked.connect(self.check_now)
        toolbar.addWidget(self.check_btn)

        self.changelog_btn = QPushButton(Translations.tr("modern.update.button.changelog"))
        self.changelog_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.changelog_btn.clicked.connect(self._open_changelog)
        toolbar.addWidget(self.changelog_btn)
        about.addLayout(toolbar)

        about.addSpacing(14)

        # Inline result status (checking / up to date / error / available)
        self.status_label = QLabel("")
        self.status_label.setObjectName("updateStatus")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setWordWrap(True)
        about.addWidget(self.status_label)

        layout.addStretch(1)

    # ── Actions ──────────────────────────────────────────────────────────

    def check_now(self) -> None:
        """Run the update check on a background thread."""
        if self._check_thread is not None and self._check_thread.isRunning():
            return
        if HEADLESS_MODE:
            return

        self.check_btn.setEnabled(False)
        self.status_label.setText(Translations.tr("modern.update.checking"))

        self._check_worker = _CheckWorker()
        self._check_thread = QThread()
        self._check_worker.moveToThread(self._check_thread)
        self._check_thread.started.connect(self._check_worker.run)
        self._check_worker.finished.connect(self._on_check_finished)
        self._check_worker.finished.connect(self._check_thread.quit)
        self._check_worker.finished.connect(self._check_worker.deleteLater)

        def on_thread_finished() -> None:
            self._check_thread.deleteLater()
            self._check_thread = None
            self._check_worker = None
            self.check_btn.setEnabled(True)

        self._check_thread.finished.connect(on_thread_finished)
        self._check_thread.start()

    def _on_check_finished(self, result: Any) -> None:
        """Handle the check result on the GUI thread (mirrors the classic flow)."""
        if result is None:
            self.status_label.setText(Translations.tr(
                "modern.update.error",
                message=Translations.tr("update_error.check_failed")))
            return
        release_info, has_update = result
        if has_update and release_info:
            tag = str(release_info.get("tag_name", ""))
            self.status_label.setText(
                Translations.tr("modern.update.available", version=tag))
            UpdateAvailableDialog(release_info, __version__, self).exec()
        else:
            self.status_label.setText(Translations.tr("modern.update.up_to_date"))

    def _open_changelog(self) -> None:
        QDesktopServices.openUrl(QUrl(CHANGELOG_URL))

    def cancel_checks(self) -> None:
        """Stop a running check thread (called from the window's closeEvent)."""
        if self._check_thread is not None and self._check_thread.isRunning():
            self._check_thread.quit()
            self._check_thread.wait(2000)

    # ── Language ─────────────────────────────────────────────────────────

    def retranslate(self) -> None:
        self.app_name.setText(Translations.tr("app.name"))
        self.version_label.setText(
            f"{Translations.tr('dialog.about.version')} {__version__}")
        self.description.setText(Translations.tr("dialog.about.description"))
        self.check_btn.setText(Translations.tr("modern.update.button.check"))
        self.changelog_btn.setText(Translations.tr("modern.update.button.changelog"))
