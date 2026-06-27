"""Interactive Qt editor for the Temple (Phase 2).

A 9x9 grid you paint rooms/paths onto; the rules engine drives the live display
(room tiers, the hovered Generator's power radius, cannot-connect violations).
Logic lives in engine.py — this file is just the Qt shell, kept thin so it stays
testable headlessly. Launched via `appraiser temple`.
"""

from __future__ import annotations

from aldur_appraiser.temple.engine import GEN_RADIUS, Temple, manhattan
from aldur_appraiser.temple.rooms import ROOMS, is_volatile

CATEGORY_COLOR = {
    "barrack": "#3b6ea5",
    "production": "#a5703b",
    "ritual": "#7a3ba5",
    "generator": "#a53b3b",
    "utility": "#3ba59a",
    "special": "#c8a13b",
    "path": "#4a4a4a",
}
ERASE = "— erase —"  # sentinel palette entry


def abbrev(room_id: str) -> str:
    """Short cell label for a room id."""
    if room_id == "path":
        return ""
    name = ROOMS[room_id].name
    return "".join(w[0] for w in name.split()[:2]).upper() or name[:2].upper()


def build_editor():
    """Construct the editor widget (imports PySide6 lazily). Returns the widget."""
    from PySide6.QtCore import QRectF, Qt, Signal
    from PySide6.QtGui import QColor, QFont, QPainter
    from PySide6.QtWidgets import (
        QComboBox,
        QHBoxLayout,
        QLabel,
        QListWidget,
        QPushButton,
        QVBoxLayout,
        QWidget,
    )

    class GridWidget(QWidget):
        cellClicked = Signal(tuple, int)  # (cell, Qt.MouseButton value)

        def __init__(self, temple: Temple):
            super().__init__()
            self.temple = temple
            self.cell = 56
            self._hover: tuple[int, int] | None = None
            self._tiers: dict[tuple[int, int], int] = {}
            self._violation_cells: set[tuple[int, int]] = set()
            self._chokepoints: set[tuple[int, int]] = set()
            self._highlights: set[tuple[int, int]] = set()
            self.setMouseTracking(True)
            self.setFixedSize(self.cell * temple.size, self.cell * temple.size)
            self._font = QFont("DejaVu Sans")
            self._font.setPixelSize(15)
            self._font.setBold(True)

        def refresh(self) -> None:
            self.temple_changed()

        def set_highlights(self, cells) -> None:
            self._highlights = set(cells)
            self.update()

        def temple_changed(self) -> None:
            self._tiers = self.temple.tiers()
            self._violation_cells = {
                c for pair in self.temple.connection_violations() for c in pair
            }
            self._chokepoints = self.temple.chokepoint_room_cells()
            self.update()

        def _cell_at(self, x: int, y: int) -> tuple[int, int] | None:
            cx, cy = x // self.cell, y // self.cell
            return (cx, cy) if self.temple.in_bounds((cx, cy)) else None

        def mousePressEvent(self, e) -> None:  # noqa: N802 (Qt naming)
            p = e.position().toPoint()
            c = self._cell_at(p.x(), p.y())
            if c is not None:
                self.cellClicked.emit(c, int(e.button().value))

        def mouseMoveEvent(self, e) -> None:  # noqa: N802
            p = e.position().toPoint()
            c = self._cell_at(p.x(), p.y())
            if c != self._hover:
                self._hover = c
                self.update()

        def leaveEvent(self, _e) -> None:  # noqa: N802
            self._hover = None
            self.update()

        def _power_cells(self) -> set[tuple[int, int]]:
            """Cells lit by the hovered Generator's power radius."""
            h = self._hover
            if h is None or self.temple.cells.get(h) != "generator":
                return set()
            radius = GEN_RADIUS.get(self._tiers.get(h, 1), 3)
            return {
                c
                for c in (
                    (x, y) for x in range(self.temple.size) for y in range(self.temple.size)
                )
                if manhattan(h, c) <= radius
            }

        def paintEvent(self, _e) -> None:  # noqa: N802
            p = QPainter(self)
            p.setRenderHint(QPainter.Antialiasing)
            s = self.cell
            power = self._power_cells()
            for x in range(self.temple.size):
                for y in range(self.temple.size):
                    c = (x, y)
                    r = QRectF(x * s, y * s, s, s)
                    rid = self.temple.cells.get(c)
                    if c in self.temple.blocked:
                        p.fillRect(r, QColor(25, 22, 20))
                    elif rid is not None:
                        p.fillRect(r, QColor(CATEGORY_COLOR.get(ROOMS[rid].category, "#666")))
                    else:
                        p.fillRect(r, QColor(38, 35, 32))
                    if c in power:
                        p.fillRect(r, QColor(150, 205, 255, 60))
                    if c == self.temple.entrance:
                        p.fillRect(r, QColor(124, 252, 138, 50))
                    # border (red if a cannot-connect violation)
                    p.setPen(QColor("#d04a4a") if c in self._violation_cells else QColor(20, 18, 14))
                    p.drawRect(r)
                    if rid and rid != "path":
                        p.setPen(QColor("#f0ead6"))
                        p.setFont(self._font)
                        tier = self._tiers.get(c, 1)
                        p.drawText(r, Qt.AlignCenter, f"{abbrev(rid)}\n{'I' * tier}")
                    if rid and rid != "path" and is_volatile(ROOMS[rid]):
                        p.setPen(QColor("#d04ad0"))  # one-use: consumed on completion
                        p.drawRect(r.adjusted(3, 3, -3, -3))
                    if c in self._chokepoints:  # sole link -> risky if random-destabilised
                        p.setPen(QColor("#e08a2a"))
                        p.drawRect(r.adjusted(6, 6, -6, -6))
                    if c in self._highlights:
                        p.setPen(QColor("#ffd24a"))
                        p.drawRect(r.adjusted(2, 2, -2, -2))
                        p.drawRect(r.adjusted(4, 4, -4, -4))
            p.end()

    class TempleEditor(QWidget):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("Aldur — Temple Planner")
            self.temple = Temple()
            self.brush = "garrison"

            self.grid = GridWidget(self.temple)
            self.grid.cellClicked.connect(self._on_cell)

            self.palette = QListWidget()
            self.palette.addItem(ERASE)
            for rid in ROOMS:
                self.palette.addItem(f"{ROOMS[rid].name}  [{rid}]")
            self.palette.setCurrentRow(1 + list(ROOMS).index("garrison"))
            self.palette.currentRowChanged.connect(self._on_brush)

            clear = QPushButton("Clear grid")
            clear.clicked.connect(self._clear)
            # tier picker for rooms upgraded by a player action (sacrifice/assassinate)
            self.tier_select = QComboBox()
            for t in (1, 2, 3):
                self.tier_select.addItem(f"Tier {t}", t)
            self.status = QLabel()

            # --- per-run advisor: a hand of drawn cards + suggestions ----------
            self.hand: list[str] = []
            self.hand_list = QListWidget()
            add_card = QPushButton("Add selected room to hand")
            add_card.clicked.connect(self._add_card)
            clear_hand = QPushButton("Clear hand")
            clear_hand.clicked.connect(self._clear_hand)
            suggest_btn = QPushButton("Suggest placement")
            suggest_btn.clicked.connect(self._suggest)
            self.suggestions = QLabel("Add your drawn cards, then Suggest.")
            self.suggestions.setWordWrap(True)

            left = QVBoxLayout()
            left.addWidget(QLabel("Room (left-click place · right-click erase)"))
            left.addWidget(self.palette, 1)
            left.addWidget(QLabel("Tier for sacrifice/assassinate rooms"))
            left.addWidget(self.tier_select)
            left.addWidget(clear)
            left.addWidget(QLabel("Hand (drawn cards this run)"))
            left.addWidget(self.hand_list, 1)
            left.addWidget(add_card)
            left.addWidget(clear_hand)
            left.addWidget(suggest_btn)
            row = QHBoxLayout(self)
            row.addLayout(left)
            grid_col = QVBoxLayout()
            grid_col.addWidget(self.grid)
            grid_col.addWidget(self.status)
            grid_col.addWidget(self.suggestions)
            row.addLayout(grid_col)

            self._refresh()

        def _add_card(self) -> None:
            if self.brush != ERASE:
                self.hand.append(self.brush)
                self.hand_list.addItem(ROOMS[self.brush].name)

        def _clear_hand(self) -> None:
            self.hand.clear()
            self.hand_list.clear()
            self.grid.set_highlights(())
            self.suggestions.setText("Add your drawn cards, then Suggest.")

        def _suggest(self) -> None:
            from aldur_appraiser.temple.advisor import suggest

            if not self.hand:
                self.suggestions.setText("Hand is empty — add the cards you drew.")
                return
            ranked = suggest(self.temple, self.hand, top=5)
            if not ranked:
                self.suggestions.setText("No legal placement found.")
                self.grid.set_highlights(())
                return
            self.grid.set_highlights([ranked[0].cell])
            lines = [f"{i + 1}. {s.note}  @{s.cell}  (+{s.gain:.1f})" for i, s in enumerate(ranked)]
            self.suggestions.setText("Best placements:\n" + "\n".join(lines))

        def _on_brush(self, idx: int) -> None:
            if idx <= 0:
                self.brush = ERASE
            else:
                self.brush = list(ROOMS)[idx - 1]

        def _on_cell(self, cell, button) -> None:
            from PySide6.QtCore import Qt

            erase = self.brush == ERASE or button == int(Qt.RightButton.value)
            self.temple.remove(cell)
            if not erase and cell not in self.temple.blocked:
                try:
                    self.temple.place(cell, self.brush)
                    if ROOMS[self.brush].manual_tier:
                        self.temple.tier_overrides[cell] = self.tier_select.currentData()
                except ValueError:
                    pass
            self._refresh()

        def _clear(self) -> None:
            self.temple.cells.clear()
            self._refresh()

        def _refresh(self) -> None:
            self.grid.temple_changed()
            tiers = self.temple.tiers()
            t3 = sum(1 for v in tiers.values() if v == 3)
            viol = len(self.temple.connection_violations())
            chokepoints = len(self.temple.chokepoint_room_cells())
            volatile = sum(
                1 for c in self.temple.room_cells() if is_volatile(ROOMS[self.temple.cells[c]])
            )
            self.status.setText(
                f"Rooms: {len(tiers)}   Tier 3: {t3}   "
                f"Chokepoints: {chokepoints}   "
                f"One-use: {volatile}   Violations: {viol}"
            )

    return TempleEditor()


def run_editor() -> int:
    """Entry point for `appraiser temple` — opens the editor window."""
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    win = build_editor()
    win.show()
    return app.exec()
