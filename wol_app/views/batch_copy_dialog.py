"""Modern UI: dialog for copying batches to other devices.

Opened from the dashboard's batch library ("Kopieren nach"). The source
is always the device whose dashboard is open; the dialog picks one or
more target devices (checkbox list, nothing preselected) and which
batches to copy. The copy MERGES into each target's batch list: only
target batches whose name matches a copied batch are overwritten, all
other target batches stay untouched. The dialog warns about the number
of name collisions that will be overwritten.

The optional "Batches erlauben" checkbox mirrors the per-device
``allow_batch`` opt-in on the target (local config only — the host-side
``--enable-batch`` gate is unaffected and mentioned in the tooltip).

Design prototype: ``design_prototype/Batch_Copy.html``.
"""

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QFontMetrics, QPainter, QPalette
from PyQt6.QtWidgets import (
    QCheckBox,
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
# Same for the target device list — long device lists scroll instead of
# pushing the batch picker off the dialog.
TARGET_MAX_HEIGHT = 176


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


class _TargetCheckRow(QWidget):
    """One checkable target device row (prototype .batchItem styling).

    The checkbox starts unchecked: the dialog opens with no target
    selected so nothing is copied accidentally.
    """

    def __init__(self, device: dict, text: str,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.device = device
        self.setObjectName("batchItem")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        row = QHBoxLayout(self)
        row.setContentsMargins(_ROW_MARGIN_X, _ROW_MARGIN_Y,
                               _ROW_MARGIN_X, _ROW_MARGIN_Y)
        row.setSpacing(_ROW_SPACING)
        self.check = QCheckBox()
        label = _ElidedLabel(text)
        label.setObjectName("batchItemTitle")
        row.addWidget(self.check, 0, Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(label, 1)


class BatchCopyDialog(QDialog):
    """Pick target devices and the batches to copy onto them.

    ``exec()`` returns ``QDialog.Accepted``/``Rejected``; read
    :attr:`target_device_ids`, :meth:`selected_batches` and
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
        self._target_rows: list[_TargetCheckRow] = []
        self.setWindowTitle(Translations.tr("modern.dashboard.batch.copy.title"))
        self.setMinimumWidth(470)
        self._setup_ui()

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

        # ── Target devices (multi-select, nothing preselected) ───────
        lbl_target = QLabel(Translations.tr("modern.dashboard.batch.copy.targets"))
        lbl_target.setObjectName("pageSubtitle")
        layout.addWidget(lbl_target)
        target_box = QFrame()
        target_box.setObjectName("batchListBox")
        tb_layout = QVBoxLayout(target_box)
        tb_layout.setContentsMargins(0, 0, 0, 0)
        tb_layout.setSpacing(0)
        self.target_scroll = QScrollArea()
        self.target_scroll.setObjectName("batchScroll")
        self.target_scroll.setWidgetResizable(True)
        self.target_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.target_scroll.setFrameShape(QFrame.Shape.NoFrame)
        target_container = QWidget()
        target_container.setObjectName("batchListInner")
        target_rows_layout = QVBoxLayout(target_container)
        target_rows_layout.setContentsMargins(4, 4, 4, 4)
        target_rows_layout.setSpacing(2)
        for dev in self._targets:
            count = len(ConfigManager.get_device_batches(dev))
            text = Translations.tr("modern.dashboard.batch.copy.target_entry",
                                   name=dev.get("name", ""),
                                   ip=dev.get("ip", ""),
                                   count=count)
            if self._statuses.get(dev.get("id")) == "offline":
                text += Translations.tr("modern.dashboard.batch.copy.offline_suffix")
            row = _TargetCheckRow(dev, text, target_container)
            row.check.toggled.connect(self._update_state)
            target_rows_layout.addWidget(row)
            self._target_rows.append(row)
        target_rows_layout.addStretch()
        self.target_scroll.setWidget(target_container)
        tb_layout.addWidget(self.target_scroll)
        # Grow with the device count, scroll only beyond the cap.
        needed = sum(r.sizeHint().height() for r in self._target_rows)
        needed += 2 * max(len(self._target_rows) - 1, 0) + 8
        self.target_scroll.setFixedHeight(min(needed, TARGET_MAX_HEIGHT))
        layout.addWidget(target_box)

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
            row.check.toggled.connect(self._update_state)
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
        self._update_state()

    # ── State helpers ────────────────────────────────────────────────────

    def _checked_targets(self) -> list[dict]:
        return [r.device for r in self._target_rows if r.check.isChecked()]

    def _update_state(self) -> None:
        """Refresh warning/offline labels and the copy button.

        The replace warning sums the same-name collisions over all checked
        targets (merge-by-name policy per target); the offline hint shows
        when any checked target is currently offline.
        """
        targets = self._checked_targets()
        selected_names = {r.batch.get("name", "") for r in self._rows
                          if r.check.isChecked()}
        colliding = 0
        for target in targets:
            colliding += sum(
                1 for b in ConfigManager.get_device_batches(target)
                if b.get("name", "") in selected_names)
        if colliding:
            if len(targets) == 1:
                text = Translations.tr(
                    "modern.dashboard.batch.copy.replace_warning",
                    name=targets[0].get("name", ""), count=colliding)
            else:
                names = ", ".join(t.get("name", "") for t in targets)
                text = Translations.tr(
                    "modern.dashboard.batch.copy.replace_warning_multi",
                    name=names, count=colliding)
            self.warn_label.setText(text)
        self.warn_label.setVisible(colliding > 0)
        self.offline_label.setVisible(
            any(self._statuses.get(t.get("id")) == "offline"
                for t in targets))
        self._update_count()

    def _on_all_clicked(self, checked: bool) -> None:
        for row in self._rows:
            row.check.setChecked(checked)

    def _update_count(self) -> None:
        n = self.selected_count()
        self.copy_btn.setText(
            Translations.tr("modern.dashboard.batch.copy.action", count=n))
        # Copying needs at least one checked target and one checked batch.
        self.copy_btn.setEnabled(n > 0 and bool(self._checked_targets()))
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
    def target_device_ids(self) -> list[str]:
        return [t.get("id") for t in self._checked_targets()]

    def selected_count(self) -> int:
        return sum(1 for row in self._rows if row.check.isChecked())

    def selected_batches(self) -> list[dict]:
        """Deep-ish copies of the checked batches, in source order."""
        return [dict(row.batch) for row in self._rows if row.check.isChecked()]

    def allow_batch_enabled(self) -> bool:
        return self.allow_check.isChecked()
