"""Modern UI: shutdown confirmation dialog (Dark Control Center look).

Shown when the user clicks "Herunterfahren" on a device card. Displays the
power symbol (a circle interrupted by a vertical line on top), the question
"Wollen Sie das Gerät wirklich herunterfahren?" and two buttons: Ja / Nein.

The dialog is styled purely through the modern theme (objectName-based QSS),
so it reads as a continuation of the control-center window rather than a
native system message box.

The centered glyph follows the question: ``icon="power"`` (default) shows the
danger-red power symbol, ``icon="play"`` the accent-colored play badge used
before running a batch (parity with the Apple Watch / mobile confirmation
sheets), ``icon="none"`` omits it.
"""

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPen, QPixmap, QPolygonF
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from wol_app.modern_theme import current_tokens
from wol_app.translations import Translations

#: Result code returned by :meth:`QDialog.exec` when the optional third
#: ("minimise") button is used. Deliberately different from both
#: ``QDialog.Rejected`` (0) and ``QDialog.Accepted`` (1) so that existing
#: ``if dialog.exec():`` call-sites keep their meaning.
MINIMIZE_RESULT_CODE = 2


def _power_icon_pixmap(size: int, color: str, dpr: float = 1.0) -> QPixmap:
    """Render the power symbol (open circle + vertical line) as a QPixmap.

    The glyph is a circle with a gap at the top, crossed by a short vertical
    line — the standard "power on/off" symbol. Drawn with QPainter so it can
    pick up the current theme's danger color and stay crisp on HiDPI screens.
    """
    dpr = dpr or 1.0
    pixmap = QPixmap(int(size * dpr), int(size * dpr))
    if dpr != 1.0:
        pixmap.setDevicePixelRatio(dpr)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(QColor(color))
        pen.setWidthF(max(2.0, size * 0.06))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)

        r = size * 0.34
        cx = size / 2
        cy = size / 2 + size * 0.02
        rect = QRectF(cx - r, cy - r, 2 * r, 2 * r)
        # Circle with a ~48° gap centered at 12 o'clock (start 114°, span 312°).
        painter.drawArc(rect, 114 * 16, 312 * 16)
        # Vertical line from above the circle down to the center.
        painter.drawLine(QPointF(cx, cy - r - size * 0.10), QPointF(cx, cy))
    finally:
        painter.end()
    return pixmap


def _play_icon_pixmap(size: int, color: str, dpr: float = 1.0) -> QPixmap:
    """Render the play symbol (triangle in a tinted circle) as a QPixmap.

    Same badge the Apple Watch app and the mobile apps show next to a batch
    name — it marks the confirmation as *constructive* (run something) rather
    than destructive, so the accent color replaces the danger red here.
    """
    dpr = dpr or 1.0
    pixmap = QPixmap(int(size * dpr), int(size * dpr))
    if dpr != 1.0:
        pixmap.setDevicePixelRatio(dpr)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        tint = QColor(color)
        tint.setAlpha(int(255 * 0.15))
        painter.setBrush(tint)
        painter.drawEllipse(QRectF(0, 0, size, size))

        # Triangle, optically centred (a geometrically centred triangle looks
        # too far left inside a circle).
        w, h = size * 0.34, size * 0.38
        cx = size / 2 + size * 0.045 - w / 2
        cy = size / 2
        painter.setBrush(QColor(color))
        painter.drawPolygon(QPolygonF([
            QPointF(cx, cy - h / 2),
            QPointF(cx, cy + h / 2),
            QPointF(cx + w, cy),
        ]))
    finally:
        painter.end()
    return pixmap


class ModernShutdownConfirmDialog(QDialog):
    """Confirmation dialog for destructive actions (modern look).

    Defaults to the device-shutdown texts; the window-quit confirmation
    reuses the same layout with ``title_key``/``message_key`` overrides.

    Passing ``min_key`` adds a third button between Ja and Nein whose
    ``exec()`` result is :data:`MINIMIZE_RESULT_CODE` — used by the quit
    confirmation when "keep running in the notification area" is enabled.

    ``icon`` picks the centered glyph: ``"power"`` (default, danger red),
    ``"play"`` (accent-colored play badge for batch runs) or ``"none"``.
    """

    def __init__(self, device_name: str, parent: QWidget | None = None, *,
                 title_key: str = "modern.shutdown_confirm.title",
                 message_key: str = "modern.shutdown_confirm.message",
                 yes_key: str = "modern.shutdown_confirm.yes",
                 no_key: str = "modern.shutdown_confirm.no",
                 min_key: str | None = None,
                 message_kwargs: dict | None = None,
                 yes_object_name: str = "dangerButton",
                 show_icon: bool = True,
                 icon: str = "power") -> None:
        super().__init__(parent)
        self.device_name = device_name
        self._title_key = title_key
        self._message_key = message_key
        self._message_kwargs = message_kwargs or {}
        self._yes_key = yes_key
        self._no_key = no_key
        self._min_key = min_key
        self._yes_object_name = yes_object_name
        self._show_icon = show_icon
        self._icon = icon
        self.setWindowTitle(Translations.tr(title_key))
        self.setMinimumWidth(380)
        self._setup_ui()

    def _setup_ui(self) -> None:
        t = current_tokens()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 26, 28, 24)
        layout.setSpacing(14)

        # Centered glyph (optional — non-destructive confirmations such as
        # "apply password to same-user devices" hide it)
        if self._show_icon and self._icon != "none":
            if self._icon == "play":
                pixmap = _play_icon_pixmap(64, t["accent"],
                                           self.devicePixelRatioF())
            else:
                pixmap = _power_icon_pixmap(64, t["danger"],
                                            self.devicePixelRatioF())
            icon = QLabel()
            icon.setPixmap(pixmap)
            icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon_row = QHBoxLayout()
            icon_row.addStretch()
            icon_row.addWidget(icon)
            icon_row.addStretch()
            layout.addLayout(icon_row)

        # Question
        msg = QLabel(Translations.tr(self._message_key, **self._message_kwargs))
        msg.setObjectName("rowTitle")
        msg.setWordWrap(True)
        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(msg)

        layout.addSpacing(4)

        # Buttons: Ja (danger/confirm) — [Minimieren] — Nein
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.yes_btn = QPushButton(Translations.tr(self._yes_key))
        self.yes_btn.setObjectName(self._yes_object_name)
        self.yes_btn.clicked.connect(self.accept)
        self.min_btn: QPushButton | None = None
        if self._min_key:
            self.min_btn = QPushButton(Translations.tr(self._min_key))
            self.min_btn.clicked.connect(
                lambda: self.done(MINIMIZE_RESULT_CODE))
        self.no_btn = QPushButton(Translations.tr(self._no_key))
        self.no_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.yes_btn)
        if self.min_btn is not None:
            btn_row.addWidget(self.min_btn)
        btn_row.addWidget(self.no_btn)
        layout.addLayout(btn_row)

        self.yes_btn.setDefault(True)
