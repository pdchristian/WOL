"""Modern UI: dialog for copying batches to another device.

Opened from the dashboard's batch library ("Kopieren nach"). The source
is always the device whose dashboard is open; the dialog picks a target
device and which batches to copy. Following the ``device_io`` import
policy the copy REPLACES the target's batch list, so the dialog warns
about the number of existing batches that will be lost.

The optional "Batches erlauben" checkbox mirrors the per-device
``allow_batch`` opt-in on the target (local config only — the host-side
``--enable-batch`` gate is unaffected and mentioned in the tooltip).

Design prototype: ``design_prototype/Batch_Copy.html``.
"""

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QFontMetrics, QPainter, QPalette
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from wol_app.config import ConfigManager
from wol_app.modern_theme import current_tokens
from wol_app.translations import Translations

# Same insets for the master checkbox row and every batch row, so all
# checkboxes line up on one vertical line (QSS padding does not move child
# widgets of a plain QWidget — the insets have to come from the layout).
_ROW_MARGIN_X = 10
_ROW_MARGIN_Y = 7
_ROW_SPACING = 10
# The picker grows with the number of batches and only scrolls past this.
PICKER_MAX_HEIGHT = 232


class _ElidedLabel(QLabel):
    """Label that elides long text instead of clipping it horizontally."""

    def minimumSizeHint(self):  # noqa: N802 (Qt naming)
        hint = super().minimumSizeHint()
        return QSize(0, hint.height())

    def paintEvent(self, event):  # noqa: N802 (Qt naming)
        painter = QPainter(self)
        fm = QFontMetrics(self.font())
        elided = fm.elidedText(self.text(), Qt.TextElideMode.ElideRight,
                               self.width())
        painter.setPen(self.palette().color(QPalette.ColorRole.WindowText))
        painter.drawText(self.rect(), int(self.alignment()), elided)


class _BatchCheckRow(QWidget):
    """One checkable batch row inside the picker (prototype .batchItem)."""

    def __init__(self, batch: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.batch = batch
        self.setObjectName("batchItem")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        row = QHBoxLayout(self)
        row.setContentsMargins(_ROW_MARGIN_X, _ROW_MARGIN_Y,
                               _ROW_MARGIN_X, _ROW_MARGIN_Y)
        row.setSpacing(_ROW_SPACING)
        self.check = QCheckBox()
        self.check.setChecked(True)
        title = _ElidedLabel(batch.get("name")
                             or Translations.tr("modern.dashboard.batch.untitled"))
        title.setObjectName("batchItemTitle")
        lines = batch.get("script", "").count("\n") + 1
        meta = QLabel(Translations.tr("modern.dashboard.batch.copy.meta",
                                      timeout=int(batch.get("timeout", 0)),
                                      lines=lines))
        meta.setObjectName("batchItemMeta")
        col = QVBoxLayout()
        col.setSpacing(1)
        col.addWidget(title)
        col.addWidget(meta)
        row.addWidget(self.check, 0, Qt.AlignmentFlag.AlignVCenter)
        row.addLayout(col, 1)


class BatchCopyDialog(QDialog):
    """Pick a target device and the batches to copy onto it.

    ``exec()`` returns ``QDialog.Accepted``/``Rejected``; read
    :attr:`target_device_id`, :meth:`selected_batches` and
    :meth:`allow_batch_enabled` afterwards.
    """

    def __init__(
        self,
        source_device: dict,
        batches: list[dict],
        targets: list[dict],
        statuses: dict[str, str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._source = source_device
        self._batches = batches
        self._targets = targets
        self._statuses = statuses or {}
        self._rows: list[_BatchCheckRow] = []
        self.setWindowTitle(Translations.tr("modern.dashboard.batch.copy.title"))
        self.setMinimumWidth(470)
        self._setup_ui()
        self._on_target_changed()
    def _setup_ui(self) -> None:
        t = current_tokens()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        header = QLabel(Translations.tr("modern.dashboard.batch.copy.title"))
        header.setObjectName("pageTitle")
        layout.addWidget(header)

        src_ip = self._source.get("ip", "")
        src = QLabel(Translations.tr("modern.dashboard.batch.copy.source_info",
                                     name=self._source.get("name", ""),
                                     ip=src_ip,
                                     count=len(self._batches)))
        src.setObjectName("statusLine")
        layout.addWidget(src)

        # ── Target device ────────────────────────────────────────────
        lbl_target = QLabel(Translations.tr("modern.dashboard.batch.copy.target"))
        lbl_target.setObjectName("pageSubtitle")
        layout.addWidget(lbl_target)
        self.target_combo = QComboBox()
        for dev in self._targets:
            count = len(ConfigManager.get_device_batches(dev))
            text = Translations.tr("modern.dashboard.batch.copy.target_entry",
                                   name=dev.get("name", ""),
                                   ip=dev.get("ip", ""),
                                   count=count)
            if self._statuses.get(dev.get("id")) == "offline":
                text += Translations.tr("modern.dashboard.batch.copy.offline_suffix")
            self.target_combo.addItem(text, dev.get("id"))
        self.target_combo.currentIndexChanged.connect(self._on_target_changed)
        layout.addWidget(self.target_combo)

        # Replace warning (danger) + offline hint, shown per target
        self.warn_label = QLabel("")
        self.warn_label.setObjectName("statusLine")
        self.warn_label.setStyleSheet(f"color: {t['danger']};")
        self.warn_label.setWordWrap(True)
        self.warn_label.setVisible(False)
        layout.addWidget(self.warn_label)

        self.offline_label = QLabel(
            Translations.tr("modern.dashboard.batch.copy.offline_info"))
        self.offline_label.setObjectName("fieldHint")
        self.offline_label.setWordWrap(True)
        self.offline_label.setVisible(False)
        layout.addWidget(self.offline_label)

        # ── Batch picker ─────────────────────────────────────────────
        lbl_pick = QLabel(Translations.tr("modern.dashboard.batch.copy.pick"))
        lbl_pick.setObjectName("pageSubtitle")
        layout.addWidget(lbl_pick)

        # Bordered box holding the master checkbox and the scrollable rows.
        # The master row uses the same left inset as the rows below, so all
        # checkboxes sit on one vertical line.
        box = QFrame()
        box.setObjectName("batchListBox")
        box_layout = QVBoxLayout(box)
        # 4 px side inset on the box; rows container adds none, so master and
        # rows share the identical left inset and their checkboxes align.
        box_layout.setContentsMargins(4, 0, 4, 0)
        box_layout.setSpacing(0)

        master = QWidget()
        master.setObjectName("batchMasterRow")
        master_row = QHBoxLayout(master)
        # The rows sit inside the scroll container which already has a 4 px
        # left margin, so the master row uses just _ROW_MARGIN_X to land on
        # the same vertical line as every row checkbox (verified by mapping).
        master_row.setContentsMargins(_ROW_MARGIN_X, _ROW_MARGIN_Y,
                                      _ROW_MARGIN_X, _ROW_MARGIN_Y)
        master_row.setSpacing(_ROW_SPACING)
        self.all_check = QCheckBox(
            Translations.tr("modern.dashboard.batch.copy.select_all"))
        self.all_check.clicked.connect(self._on_all_clicked)
        master_row.addWidget(self.all_check, 0, Qt.AlignmentFlag.AlignVCenter)
        master_row.addStretch()
        box_layout.addWidget(master)

        separator = QFrame()
        separator.setObjectName("batchListSep")
        box_layout.addWidget(separator)

        self.pick_scroll = QScrollArea()
        self.pick_scroll.setObjectName("batchScroll")
        self.pick_scroll.setWidgetResizable(True)
        self.pick_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.pick_scroll.setFrameShape(QFrame.Shape.NoFrame)
        container = QWidget()
        container.setObjectName("batchListInner")
        rows_layout = QVBoxLayout(container)
        # No side inset here: the box layout already provides the 4 px, so the
        # rows line up with the master checkbox above.
        rows_layout.setContentsMargins(0, 4, 0, 4)
        rows_layout.setSpacing(2)
        for batch in self._batches:
            row = _BatchCheckRow(batch, container)
            row.check.toggled.connect(self._update_count)
            rows_layout.addWidget(row)
            self._rows.append(row)
        rows_layout.addStretch()
        self.pick_scroll.setWidget(container)
        box_layout.addWidget(self.pick_scroll)
        # Grow with the number of batches, scroll only beyond the cap — with a
        # single batch the dialog stays compact instead of leaving dead space.
        needed = sum(r.sizeHint().height() for r in self._rows)
        needed += 2 * max(len(self._rows) - 1, 0) + 8
        self.pick_scroll.setFixedHeight(min(needed, PICKER_MAX_HEIGHT))
        layout.addWidget(box)

        # ── allow_batch opt-in on the target ─────────────────────────
        self.allow_check = QCheckBox(
            Translations.tr("modern.dashboard.batch.copy.allow_batch"))
        self.allow_check.setToolTip(
            Translations.tr("modern.dashboard.batch.copy.allow_batch_tip"))
        layout.addWidget(self.allow_check)

        # ── Actions ──────────────────────────────────────────────────
        actions = QHBoxLayout()
        actions.addStretch()
        self.cancel_btn = QPushButton(Translations.tr("common.cancel"))
        self.cancel_btn.clicked.connect(self.reject)
        actions.addWidget(self.cancel_btn)
        self.copy_btn = QPushButton()
        self.copy_btn.setObjectName("primaryButton")
        self.copy_btn.clicked.connect(self.accept)
        actions.addWidget(self.copy_btn)
        layout.addLayout(actions)
        self._update_count()

    # ── State helpers ────────────────────────────────────────────────────

    def _current_target(self) -> dict | None:
        dev_id = self.target_combo.currentData()
        return next((d for d in self._targets if d.get("id") == dev_id), None)

    def _on_target_changed(self) -> None:
        target = self._current_target()
        if target is None:
            return
        existing = len(ConfigManager.get_device_batches(target))
        if existing:
            self.warn_label.setText(Translations.tr("modern.dashboard.batch.copy.replace_warning",
                                                    name=target.get("name", ""),
                                                    count=existing))
        self.warn_label.setVisible(existing > 0)
        self.offline_label.setVisible(
            self._statuses.get(target.get("id")) == "offline")
        allowed = bool(target.get("allow_batch", False))
        self.allow_check.blockSignals(True)
        self.allow_check.setChecked(allowed)
        self.allow_check.setEnabled(not allowed)  # already allowed: no-op
        self.allow_check.blockSignals(False)

    def _on_all_clicked(self, checked: bool) -> None:
        for row in self._rows:
            row.check.setChecked(checked)

    def _update_count(self) -> None:
        n = self.selected_count()
        self.copy_btn.setText(
            Translations.tr("modern.dashboard.batch.copy.action", count=n))
        self.copy_btn.setEnabled(n > 0)
        states = {row.check.checkState() for row in self._rows}
        if states == {Qt.CheckState.Checked}:
            state = Qt.CheckState.Checked
        elif states == {Qt.CheckState.Unchecked}:
            state = Qt.CheckState.Unchecked
        else:
            state = Qt.CheckState.PartiallyChecked
        self.all_check.blockSignals(True)
        self.all_check.setCheckState(state)
        self.all_check.blockSignals(False)

    # ── Public API ───────────────────────────────────────────────────────

    @property
    def target_device_id(self) -> str | None:
        return self.target_combo.currentData()

    def selected_count(self) -> int:
        return sum(1 for row in self._rows if row.check.isChecked())

    def selected_batches(self) -> list[dict]:
        """Deep-ish copies of the checked batches, in source order."""
        return [dict(row.batch) for row in self._rows if row.check.isChecked()]

    def allow_batch_enabled(self) -> bool:
        return self.allow_check.isChecked()
