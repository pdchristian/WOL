"""Pill-style toggle switch matching the design prototype.

Mirrors the ``.toggle`` / ``.toggle.on`` CSS of
Design_Prototpye/dark_control_center_full.html: a 40x22 px pill with a
16 px white knob that slides when toggled. Colors follow the currently
applied modern theme (see :func:`wol_app.modern_theme.current_tokens`).
"""

from PyQt6.QtCore import (
    QPropertyAnimation,
    pyqtProperty,
    pyqtSignal,
    Qt,
)
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QWidget

# Pill geometry (prototype: width 40, height 22, knob 16, padding 3)
TRACK_WIDTH = 40
TRACK_HEIGHT = 22
KNOB_SIZE = 16
KNOB_MARGIN = 3


class ToggleSwitch(QWidget):
    """A checkable pill toggle with a sliding knob (no QSS needed)."""

    toggled = pyqtSignal(bool)

    def __init__(self, checked: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._checked = checked
        # Knob x position (left edge), animated between the two stops.
        self._knob_x = float(
            TRACK_WIDTH - KNOB_SIZE - KNOB_MARGIN if checked else KNOB_MARGIN
        )

        self.setFixedSize(TRACK_WIDTH, TRACK_HEIGHT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setObjectName("toggleSwitch")
        self.setAccessibleName("toggle")

    # ── Public API (mirrors QCheckBox where practical) ───────────────────

    def isChecked(self) -> bool:  # noqa: N802 (Qt naming)
        return self._checked

    def setChecked(self, checked: bool) -> None:  # noqa: N802 (Qt naming)
        """Set the checked state without emitting ``toggled``."""
        if checked == self._checked:
            return
        self._checked = checked
        self._animate_knob(checked)
        self.update()

    def toggle(self) -> None:
        """Flip the state and emit ``toggled``."""
        self._checked = not self._checked
        self._animate_knob(self._checked)
        self.update()
        self.toggled.emit(self._checked)

    # ── Internals ────────────────────────────────────────────────────────

    def _knob_x_get(self) -> float:
        return self._knob_x

    def _knob_x_set(self, value: float) -> None:
        self._knob_x = value
        self.update()

    # Property for QPropertyAnimation (float for smooth interpolation)
    knobX = pyqtProperty(float, fget=_knob_x_get, fset=_knob_x_set)

    def _animate_knob(self, checked: bool) -> None:
        target = float(
            TRACK_WIDTH - KNOB_SIZE - KNOB_MARGIN if checked else KNOB_MARGIN
        )
        anim = QPropertyAnimation(self, b"knobX", self)
        anim.setDuration(120)
        anim.setStartValue(self._knob_x)
        anim.setEndValue(target)
        anim.start()
        # Keep a reference alive while running
        self._anim = anim

    def mousePressEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle()
            event.accept()
        else:
            super().mousePressEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        from wol_app.modern_theme import current_tokens

        t = current_tokens()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Track: accent when on, border color when off (prototype CSS)
        track_color = QColor(t["accent"]) if self._checked else QColor(t["border"])
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(track_color)
        painter.drawRoundedRect(0, 0, TRACK_WIDTH, TRACK_HEIGHT, TRACK_HEIGHT / 2, TRACK_HEIGHT / 2)

        # Knob: white circle
        painter.setBrush(QColor("#ffffff"))
        painter.drawEllipse(
            int(round(self._knob_x)), KNOB_MARGIN, KNOB_SIZE, KNOB_SIZE
        )
        painter.end()


class ToggleWithLabel(QWidget):
    """A :class:`ToggleSwitch` with a text label next to it.

    Drop-in replacement for a labelled ``QCheckBox`` in the modern UI:
    exposes ``isChecked()`` / ``setChecked()`` / ``setText()`` and a
    ``toggled`` signal, so existing call-sites keep working.
    """

    toggled = pyqtSignal(bool)

    def __init__(
        self, text: str = "", checked: bool = False, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.toggle = ToggleSwitch(checked=checked)
        self.label = QLabel(text)
        self.label.setCursor(Qt.CursorShape.PointingHandCursor)

        layout.addWidget(self.toggle, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.label, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addStretch()

        self.toggle.toggled.connect(self.toggled.emit)
        self.label.mousePressEvent = self._on_label_click

    # ── Public API (mirrors QCheckBox where practical) ───────────────────

    def isChecked(self) -> bool:  # noqa: N802 (Qt naming)
        return self.toggle.isChecked()

    def setChecked(self, checked: bool) -> None:  # noqa: N802 (Qt naming)
        self.toggle.setChecked(checked)

    def setText(self, text: str) -> None:  # noqa: N802 (Qt naming)
        self.label.setText(text)

    def text(self) -> str:
        return self.label.text()

    # ── Internals ────────────────────────────────────────────────────────

    def _on_label_click(self, event) -> None:  # noqa: N802 (Qt naming)
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle.toggle()
            event.accept()
        else:
            QWidget.mousePressEvent(self.label, event)
