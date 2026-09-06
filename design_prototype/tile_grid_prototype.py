"""Prototyp: Geräte-Kachel-Grid mit exakter CSS-auto-fill-Berechnung.

Sollverhalten (Parität zu design_prototype/Sidebar.html, Zeile 68:
``repeat(auto-fill, minmax(230px, 1fr))``):

- Die Kacheln füllen die Zeile IMMER vollständig aus: die rechte Kachel
  schließt rechts exakt mit dem rechten Rand der Suchleiste ab
  (beide nutzen denselben Seitenrand MARGIN).
- Fenster breiter  → Kacheln wachsen gleichmäßig, bis eine weitere
  Kachel in die Zeile passt (dann Sprung auf cols+1, Kacheln wieder
  auf MINIMUM-Breite, wachsen dann wieder mit).
- Fenster schmaler → alle Kacheln schrumpfen gleichmäßig bis
  CARD_MIN_WIDTH, dann fällt eine Spalte weg und die verbleibenden
  Kacheln füllen die Breite sofort wieder vollständig.

Kern der Berechnung (bewusst aus der ACTUELLEN Breite des Grid-Containers
gemessen, NICHT aus dem ScrollArea-Viewport — das ist der Bug in der App:
dort kann ein zu breiter Toolbar-Inhalt den Content breiter als den
Viewport machen, dann stimmt die gemessene Breite nicht und rechts bleibt
Rand bzw. der Content läuft über):

    avail = grid_width                       # echte, konkrete Breite
    cols  = max(1, (avail + GAP) // (MIN + GAP))
    tileW = (avail - (cols - 1) * GAP) // cols

    →  cols * tileW + (cols - 1) * GAP  ==  avail   (Rest ≤ cols-1 px,
      läuft in die letzte Spalte; QGridLayout-Stretch verteilt ihn)

Start:   python design_prototype/tile_grid_prototype.py
Der Debug-Balken unten zeigt live: Fensterbreite, cols, Kachelbreite und
ob die rechte Kachel bündig mit der Suchleiste steht (grün = OK).
"""

from __future__ import annotations

import sys

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QLineEdit, QMainWindow, QPushButton, QScrollArea, QSizePolicy,
    QVBoxLayout, QWidget,
)

# ── Konstanten (identisch zur App) ───────────────────────────────────────
# 300 statt 230 (HTML-Prototyp): bei 230 passt der "Herunterfahren"-Button
# neben den 3 Remote-Tiles nicht mehr (ab ~278 px abschneidend).
CARD_MIN_WIDTH = 300
GRID_SPACING = 16
MARGIN = 36            # linker UND rechter Rand: Inhalt UND Suchleiste

DEVICES = [
    ("A4-H2O", "192.168.2.50", "60:CF:84:84:31:29", True),
    ("A4-TV", "a4-tv.lan", "A0:AD:9F:1C:09:FF", True),
    ("Blade-18", "Blade-18.fritz.box", "98:BB:1E:1F:5A:54", False),
    ("Fractal (ich)", "192.168.2.62", "50:EB:F6:B7:8B:0C", True),
    ("ubuntu-mercury", "ubuntu-mercury.fritz.box", "00:23:A4:0A:03:B5", True),
    ("X15", "192.168.2.73", "F4:4D:AD:03:0F:37", True),
]

QSS = """
QMainWindow, #content { background: #0d1117; }
#side { background: #11151c; border-right: 1px solid #232a35; }
#sideTitle { color: #e6edf3; font-size: 16px; font-weight: 600; padding: 8px; }
#pageTitle { color: #e6edf3; font-size: 22px; font-weight: 600; }
#pageSubtitle { color: #8b949e; font-size: 12px; }
QLineEdit { background: #161b22; border: 1px solid #30363d; border-radius: 8px;
            color: #e6edf3; padding: 8px 10px; }
QComboBox { background: #161b22; border: 1px solid #30363d; border-radius: 8px;
            color: #e6edf3; padding: 6px 10px; }
#primaryButton { background: #10b981; color: #04110c; border: none;
                 border-radius: 8px; padding: 8px 14px; font-weight: 600; }
#iconBtn { background: #161b22; border: 1px solid #30363d; border-radius: 8px; }
#deviceCard { background: #161b22; border: 1px solid #262d38; border-radius: 14px; }
#rowTitle { color: #e6edf3; font-weight: 600; }
#rowMono { color: #8b949e; font-family: Consolas, monospace; font-size: 11px; }
#wakeButton, #shutdownButton { background: transparent; border-radius: 8px;
                               padding: 6px 12px; font-weight: 600; }
#wakeButton { color: #10b981; border: 1px solid #10b981; }
#shutdownButton { color: #f85149; border: 1px solid #f85149; }
#debugBar { background: #0a0d12; border-top: 1px solid #232a35;
            color: #8b949e; font-family: Consolas, monospace; font-size: 11px;
            padding: 4px 12px; }
"""


class WidthPinnedScrollArea(QScrollArea):
    """ScrollArea, deren Content-Breite IMMER exakt der Viewport-Breite ist.

    Das ist der entscheidende Unterschied zur App (und die Ursache des
    Bugs): normalerweise ist der Content mindestens so breit wie sein
    Layout-Minimum (Toolbar-Festbreiten, Karten-Inhalte ...). Wird das
    Fenster schmaler, kann der Content nicht mit schrumpfen → die
    Grid-Berechnung sieht eine veraltete/zu große Breite, rechts entsteht
    Rand bzw. Überlauf (Qt klemmt die Breite ein, statt ein neues
    resizeEvent mit kleinerer Breite zu liefern — "Ratchet").

    CSS macht es bei Block-Elementen anders: Breite = enthaltendes
    Element, punkt. Genau das erzwingen wir hier: content wird auf die
    Viewport-Breite festgenagelt; zu breite Toolbar-Elemente laufen dann
    intern über, statt die Grid-Rechnung zu vergiften.
    """

    def __init__(self, content: QWidget, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setWidget(content)
        self._content = content

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        vw = self.viewport().width()
        if vw > 0 and self._content.width() != vw:
            # setFixedWidth statt nur resize: verhindert, dass das Layout
            # des Contents je wieder über die Viewport-Breite wächst.
            self._content.setFixedWidth(vw)


def compute_columns(avail: int) -> int:
    """CSS ``auto-fill``: max. Anzahl Spalten mit MIN-Breite + GAP.

    Nutzt die GESAMTE Breite: eine weitere Spalte passt, sobald
    ``tileW >= MIN`` gilt, also bei avail >= cols*MIN + (cols-1)*GAP.
    """
    if avail <= 0:
        return 1
    return max(1, (avail + GRID_SPACING) // (CARD_MIN_WIDTH + GRID_SPACING))


def compute_tile_width(avail: int, cols: int) -> int:
    """Gleichmäßige Kachelbreite, sodass cols Kacheln + Gaps exakt passen."""
    return (avail - (cols - 1) * GRID_SPACING) // cols


class FlexToolbar(QWidget):
    """Toolbar wie CSS ``display:flex; justify-content:space-between``.

    Qt-eigene QBoxLayout verteilt Platzmangel auf ALLE Items — dann rutscht
    die Suchleiste nach links und ist nicht mehr bündig mit der letzten
    Kachel. Hier wird komplett manuell positioniert:

    - Rechte Gruppe (Sortierung + Suche): IMMER rechtsbündig am Container-
      rand; Suchfeld schrumpft zuerst (260 → 160), Combo bleibt 150.
    - Linke Gruppe (Buttons): starts at the left edge; der letzte Button
      ("Alle starten") staucht bis auf 0, bevor etwas anderes überläuft.

    Damit gilt bei JEWER Breite: rechte Kante Suchleiste == rechte Kante
    Grid == Content-Breite - MARGIN.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._left: list[QWidget] = []
        self._right: list[QWidget] = []
        self._gap = 10

    def add_left(self, w: QWidget) -> None:
        w.setParent(self)
        self._left.append(w)

    def add_right(self, w: QWidget) -> None:
        w.setParent(self)
        self._right.append(w)

    # CSS-Parität: rechte Gruppe schrumpft erst die Suche (min 160),
    # dann die Combo (min 100); linke Gruppe weicht unbegrenzt.
    SEARCH_MIN, SEARCH_MAX = 160, 260
    COMBO_MIN, COMBO_W = 100, 150

    def _widths_right(self, avail: int) -> list[int]:
        """Breiten der rechten Gruppe (listen-rechts = Suchfeld) berechnen."""
        n = len(self._right)
        widths = [self.COMBO_W, self.SEARCH_MAX][:n]
        need = sum(widths) + self._gap * max(0, n - 1)
        deficit = need - avail
        if deficit <= 0:
            return widths
        # Zuerst das Suchfeld schrumpfen lassen, dann die Combo.
        take = min(deficit, self.SEARCH_MAX - self.SEARCH_MIN)
        widths[-1] -= take
        deficit -= take
        if deficit > 0:
            widths[-2] = max(60, widths[-2] - deficit)
        return widths

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        w = self.width()
        h = self.height()
        # Rechte Gruppe: von rechts nach links aufbauen.
        widths = self._widths_right(w)
        x = w
        for widget, width in zip(reversed(self._right), reversed(widths)):
            x -= width
            widget.setGeometry(x, (h - widget.sizeHint().height()) // 2,
                               width, max(widget.sizeHint().height(), 36))
            x -= self._gap
        right_block_left = x + self._gap
        # Linke Gruppe: von links, letzter Button staucht zuerst.
        x = 0
        for i, widget in enumerate(self._left):
            pref = widget.sizeHint().width()
            remaining = right_block_left - self._gap - x
            if i == len(self._left) - 1:
                width = max(0, min(pref, remaining))
            else:
                width = min(pref, max(0, remaining))
            widget.setGeometry(x, (h - widget.sizeHint().height()) // 2,
                               width, max(widget.sizeHint().height(), 36))
            x += width + self._gap

    def sizeHint(self) -> QSize:  # noqa: N802
        lh = max((w.sizeHint().height() for w in self._left + self._right),
                 default=36)
        return QSize(400, max(lh, 36))

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(0, self.sizeHint().height())


class TileCard(QFrame):
    def __init__(self, name: str, ip: str, mac: str, online: bool, parent=None):
        super().__init__(parent)
        self.setObjectName("deviceCard")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        # KRITISCH (App-Bug!): Kein Mindestbreiten-Ratchet. Qt's
        # Layout-Engine verwendet min(minimumSizeHint, sizeHint) als
        # Untergrenze — ein gesetztes minimumWidth(0) wird bei Preferred-
        # Policy IGNORIERT. Wäre die Karten-Untergrenze (interne Tiles +
        # Button) größer als die berechnete Kachelbreite, kann das Grid beim
        # Schrumpfen nicht folgen: der ScrollArea-Viewport bleibt zu breit,
        # resizeEvent feuert nie kleiner → Überlauf / abgeschnittene rechte
        # Kachel (Screenshot 2 der App).
        # Horizontale Ignored-Policy: qSmartMinSize ignoriert alleHints und
        # nutzt nur das explizite minimumSize (0) → die Kachel folgt immer
        # exakt ihrer Grid-Spalte, egal wie schmal sie wird.
        sp = self.sizePolicy()
        sp.setHorizontalPolicy(QSizePolicy.Policy.Ignored)
        sp.setVerticalPolicy(QSizePolicy.Policy.Preferred)
        self.setSizePolicy(sp)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(10)

        top = QHBoxLayout()
        title = QLabel(name)
        title.setObjectName("rowTitle")
        dot = QLabel("●")
        dot.setStyleSheet(f"color: {'#10b981' if online else '#f85149'};")
        top.addWidget(title, 1)
        top.addWidget(dot, 0, Qt.AlignmentFlag.AlignVCenter)
        lay.addLayout(top)

        mono = QLabel(f"{ip}\n{mac}")
        mono.setObjectName("rowMono")
        lay.addWidget(mono)

        bottom = QHBoxLayout()
        bottom.setSpacing(8)
        for glyph in ("🖥", "🪟", "📊"):
            t = QPushButton(glyph)
            t.setObjectName("iconBtn")
            t.setFixedSize(36, 36)
            bottom.addWidget(t)
        bottom.addStretch()
        btn = QPushButton("Herunterfahren" if online else "Aufwecken")
        btn.setObjectName("shutdownButton" if online else "wakeButton")
        # Action-Button minimal halten: 3 Tiles (124) + Gaps + Button(64)
        # + Margen (36) ≈ 232 → passt exakt in CARD_MIN_WIDTH.
        btn.setMinimumWidth(64)
        bottom.addWidget(btn)
        lay.addLayout(bottom)


class GridPanel(QWidget):
    """Grid-Container: berechnet cols + Kachelbreite aus SEINER echten Breite.

    Entscheidend: gemessen wird das resizeEvent dieses Containers (concrete
    width nach Layout/Margen), nie der ScrollArea-Viewport. Damit kann ein
    anderer Toolbar-Inhalt die Rechnung nie verfälschen.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(GRID_SPACING)
        self._cards: list[TileCard] = []
        self._cols = 0
        self._tile_w = 0
        # Höchste je belegte Spaltenanzahl: QGridLayout merkt sich
        # Spalten-Eigenschaften (stretch/minWidth) PERMANENT. Fällt cols von
        # 3 auf 2, behält Spalte 2 ihr stretch=1 — das Grid rechnet weiter
        # mit 3 Spalten, die Kacheln bleiben zu schmal und rechts entsteht
        # die Lücke. Deshalb jede je genutzte Spalte beim Reflow explizit
        # auf stretch 0 (bzw. 1) zurücksetzen.
        self._max_cols = 0
        self.on_layout: callable | None = None
        # Wie bei den Kacheln: nie ein Mindestbreiten-Ratchet erlauben.
        sp = self.sizePolicy()
        sp.setHorizontalPolicy(QSizePolicy.Policy.Ignored)
        self.setSizePolicy(sp)

    def set_devices(self, devices: list[tuple]) -> None:
        for c in self._cards:
            self.grid.removeWidget(c)
            c.deleteLater()
        self._cards = [TileCard(*d) for d in devices]
        self._relayout(self.width())

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._relayout(event.size().width())

    def _relayout(self, width: int) -> None:
        if width <= 0 or not self._cards:
            return
        cols = compute_columns(width)
        tile_w = compute_tile_width(width, cols)
        # Widgets nur bei echtem Spaltenwechsel umhängen — die Breite
        # verteilt QGridLayout dank Stretch=1 + Ignored-Karten ohnehin
        # pixelgenau und kontinuierlich mit (kein Flackern, kein Reflow).
        if cols != self._cols:
            self._cols = cols
            while self.grid.count():
                self.grid.takeAt(0)
            for i, card in enumerate(self._cards):
                r, c = divmod(i, cols)
                self.grid.addWidget(card, r, c)
            # KEIN setColumnMinimumWidth(tile_w): das wäre ein Ratchet — beim
            # nächsten Schrumpfen käme kein resizeEvent mit kleinerer Breite
            # mehr an. Stretch=1 auf allen Spalten verteilt die Breite
            # gleichmäßig; der ganzzahlige Rest (0..cols-1 px) bleibt bündig.
            # WICHTIG: Spalten > cols explizit auf stretch 0 — sonst bleiben
            # sie als "Phantomspalten" aus einem früheren Reflow erhalten
            # (QGridLayout speichert Spalten-Eigenschaften dauerhaft) und
            # erzeugen den rechten Rand, obwohl cols kleiner geworden ist.
            for c in range(cols, self._max_cols + 1):
                self.grid.setColumnStretch(c, 0)
            for c in range(cols):
                self.grid.setColumnStretch(c, 1)
            self._max_cols = max(self._max_cols, cols)
        self._tile_w = tile_w
        if self.on_layout:
            self.on_layout(width, cols, tile_w)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Kachel-Grid Prototyp")
        self.resize(1100, 760)
        self.setStyleSheet(QSS)

        root = QHBoxLayout()
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        central = QWidget()
        central.setLayout(root)
        self.setCentralWidget(central)

        side = QWidget()
        side.setObjectName("side")
        side.setFixedWidth(190)
        side_lay = QVBoxLayout(side)
        side_lay.addWidget(QLabel("Wake-on-LAN"))
        side_lay.addStretch()
        root.addWidget(side)

        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(0)
        root.addLayout(right, 1)

        content = QWidget()
        content.setObjectName("content")
        scroll = WidthPinnedScrollArea(content)
        right.addWidget(scroll, 1)
        self._scroll = scroll
        self._content = content
        col = QVBoxLayout(content)
        # EXAKT MARGIN links/rechts — Suchleiste und Grid teilen sich den Rand.
        col.setContentsMargins(MARGIN, 24, MARGIN, 24)
        col.setSpacing(14)

        title = QLabel("Geräte")
        title.setObjectName("pageTitle")
        sub = QLabel("6 Geräte · 5 online")
        sub.setObjectName("pageSubtitle")
        col.addWidget(title)
        col.addWidget(sub)

        # Toolbar: manuell positioniert (CSS space-between) — rechte Kante
        # der Suchleiste ist bei JEGER Breite exakt die rechte Kante des
        # Grids (beide = Content-Breite, Content = Viewport-Breite).
        toolbar = FlexToolbar()
        for glyph in ("☰", "⟳"):
            b = QPushButton(glyph)
            b.setObjectName("iconBtn")
            b.setFixedSize(36, 36)
            toolbar.add_left(b)
        wake_all = QPushButton("Alle starten")
        wake_all.setObjectName("primaryButton")
        toolbar.add_left(wake_all)
        sort_combo = QComboBox()
        sort_combo.addItems(["Name", "IP", "MAC", "Status"])
        toolbar.add_right(sort_combo)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Suche nach Name, MAC, IP oder Benutzer")
        toolbar.add_right(self.search)
        col.addWidget(toolbar)

        self.panel = GridPanel()
        self.panel.set_devices(DEVICES)
        col.addWidget(self.panel)
        col.addStretch()

        self.debug = QLabel()
        self.debug.setObjectName("debugBar")
        # Langer Text dürfte nie eine Fenster-Mindestbreite erzwingen.
        dbg_sp = self.debug.sizePolicy()
        dbg_sp.setHorizontalPolicy(QSizePolicy.Policy.Ignored)
        self.debug.setSizePolicy(dbg_sp)
        right.addWidget(self.debug)
        self.panel.on_layout = self._update_debug

    def _update_debug(self, width: int, cols: int, tile_w: int) -> None:
        # Bündigkeit prüfen: rechte Kachel vs. rechte Suchleistenkante.
        # Beide hängen in denselben Margen → exakt gleich, wenn kein
        # horizontales Überlaufproblem existiert.
        grid_right = self.panel.mapTo(self._content, self.panel.rect().topRight()).x()
        search_right = self.search.mapTo(self._content, self.search.rect().topRight()).x()
        delta = abs(grid_right - search_right)
        ok = "BÜNDIG ✓" if delta <= 1 else f"VERSATZ {delta}px ✗"
        color = "#10b981" if delta <= 1 else "#f85149"
        self.debug.setText(
            f"grid_width={width}  cols={cols}  tile_w={tile_w}  "
            f"rechte Kachel vs. Suchleiste: <span style='color:{color}'>{ok}</span>   "
            f"(min={CARD_MIN_WIDTH}, gap={GRID_SPACING}, margin={MARGIN})")


def verify() -> None:
    """Konsistenzcheck der Formel über viele Breiten (ohne GUI)."""
    print(f"{'avail':>6} {'cols':>5} {'tile_w':>7} {'summe':>7} {'rest':>5}")
    for avail in range(160, 1620, 1):
        cols = compute_columns(avail)
        tw = compute_tile_width(avail, cols)
        total = cols * tw + (cols - 1) * GRID_SPACING
        rest = avail - total
        assert 0 <= rest <= cols - 1, (avail, cols, tw, rest)
        assert tw >= CARD_MIN_WIDTH or cols == 1, (avail, cols, tw)
        if avail % 100 == 0:
            print(f"{avail:>6} {cols:>5} {tw:>7} {total:>7} {rest:>5}")
    print("Formel-Check OK: Rest immer 0..cols-1 px, tile_w >= MIN.")


if __name__ == "__main__":
    if "--verify" in sys.argv:
        verify()
        sys.exit(0)
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
