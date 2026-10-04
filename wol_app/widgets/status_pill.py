"""Combined status / platform chip used by the modern device views.

The pill replaces the bare status dot in the device card header and is placed
in front of the action tiles of a list row: one glance shows whether the device
answers *and* which client (RDP or TurboVNC) its Remote buttons will open.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QWidget

from wol_app.translations import Translations
from wol_app.utils import normalize_os, os_display_text

#: QSS object name of the dot for each status (mirrors #dotOnline etc.)
_DOT_NAMES = {
    "online": "pillDotOnline",
    "offline": "pillDotOffline",
}

#: Inference badge states (host protocol v9 "requests_active") -> QSS name.
#: "none" hides the bolt entirely (pre-v9 host / nothing watched).
_BOLT_NAMES = {
    "active": "pillBoltActive",
    "idle": "pillBoltIdle",
    "warn": "pillBoltWarn",
}

#: tooltip key per inference state
_BOLT_TIPS = {
    "active": "modern.devices.infer.active",
    "idle": "modern.devices.infer.idle",
    "warn": "modern.devices.infer.warn",
}

#: Platform glyph in front of the label — icons are not translatable
OS_ICONS = {"windows": "🪟", "macos": "🍏", "linux": "🐧"}

#: shown when the platform was never detected
UNKNOWN_ICON = "❓"


class StatusPill(QWidget):
    """Rounded chip with the online dot and the detected platform of a device.

    ``confidence`` is the fingerprint confidence (``high`` = reported by the
    host service, anything else = estimated). The pill itself shows only the
    platform icon and label (no ``~`` marker between the dot and the icon);
    the tooltip spells out how the value was obtained.
    """

    def __init__(
        self,
        os_id: str = "",
        confidence: str = "",
        status: str = "unknown",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("statusPill")
        # Plain QWidgets need this attribute to paint their QSS background.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self._os_id = normalize_os(os_id)
        self._confidence = confidence or ""
        self._status = status
        self._inference = "none"

        layout = QHBoxLayout(self)
        layout.setContentsMargins(9, 3, 11, 3)
        layout.setSpacing(7)

        # Inference badge (lightning bolt) — left of the status dot, hidden
        # unless a watched inference server reports activity (v9 hosts).
        self.bolt = QLabel()
        self.bolt.setFixedSize(15, 15)
        self.bolt.setVisible(False)
        layout.addWidget(self.bolt, 0, Qt.AlignmentFlag.AlignVCenter)

        self.dot = QLabel()
        self.dot.setFixedSize(9, 9)
        layout.addWidget(self.dot, 0, Qt.AlignmentFlag.AlignVCenter)

        self.text = QLabel()
        self.text.setObjectName("pillText")
        layout.addWidget(self.text, 0, Qt.AlignmentFlag.AlignVCenter)

        self._refresh()

    # ── State ─────────────────────────────────────────────────────────────

    def set_status(self, status: str) -> None:
        """Move the dot to the colour of *status* (online/offline/unknown)."""
        if status != self._status:
            self._status = status
            self._refresh()

    def set_platform(self, os_id: str, confidence: str = "") -> None:
        """Show the platform of the device ("" = unknown)."""
        os_id = normalize_os(os_id)
        confidence = confidence or ""
        if os_id != self._os_id or confidence != self._confidence:
            self._os_id = os_id
            self._confidence = confidence
            self._refresh()

    def set_inference(self, state: str) -> None:
        """Show the inference badge: active/idle/warn, or "none" to hide.

        Driven by the devices view's poll of host protocol v9
        ``requests_active`` — "active" = a job is running right now,
        "idle" = the watched API answers but nothing runs, "warn" = the
        API port is open but activity is unmeasurable, "hidden" = the
        watched server is off (port closed) so the bolt is cleared.
        """
        if state not in _BOLT_NAMES:
            state = "none"
        if state != self._inference:
            self._inference = state
            self._refresh()

    def retranslate(self) -> None:
        """Re-pick the translated label and tooltip (language switch)."""
        self._refresh()

    # ── Rendering ─────────────────────────────────────────────────────────

    def _refresh(self) -> None:
        dot_name = _DOT_NAMES.get(self._status, "pillDotUnknown")
        if self.dot.objectName() != dot_name:
            self.dot.setObjectName(dot_name)
            style = self.dot.style()
            style.unpolish(self.dot)
            style.polish(self.dot)

        bolt_name = _BOLT_NAMES.get(self._inference, "")
        self.bolt.setVisible(bool(bolt_name))
        if bolt_name and self.bolt.objectName() != bolt_name:
            self.bolt.setObjectName(bolt_name)
            style = self.bolt.style()
            style.unpolish(self.bolt)
            style.polish(self.bolt)

        label = os_display_text(self._os_id, self._confidence)
        if label:
            icon = OS_ICONS.get(self._os_id, "")
            # drop the "~" estimate marker so it does not sit between the
            # status dot and the platform icon; the tooltip still explains
            # how the platform was obtained
            if label.startswith("~"):
                label = label[1:].strip()
            text = f"{icon} {label}"
            if self._confidence == "high":
                tip_key = "scan_dialog.os.tip_service"
            elif self._confidence:
                tip_key = "scan_dialog.os.tip_estimate"
            else:
                # Stored devices keep only the platform, not how it was found
                tip_key = "modern.devices.pill_detected"
        else:
            text = f"{UNKNOWN_ICON} {Translations.tr('scan_dialog.os.unknown')}"
            tip_key = "modern.devices.pill_unknown"

        self.text.setText(text)
        tooltip = (
            f"{Translations.tr(f'status.{self._status}')}\n"
            f"{Translations.tr(tip_key)}"
        )
        bolt_tip = _BOLT_TIPS.get(self._inference)
        if bolt_tip:
            tooltip += f"\n{Translations.tr(bolt_tip)}"
        self.setToolTip(tooltip)
