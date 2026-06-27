"""Temple rules engine — pure, no UI.

Models a 9x9 grid of placed rooms/paths and derives everything the editor and the
advisor need:

  - connectivity & accessibility from the entrance (BFS over occupied cells) —
    used for the Generator's "must be connected to a road" rule and to let the
    editor keep placements connected (the game never allows orphaned rooms),
  - room tier from its group upgrade rules (count / require_all / source_min_tier
    over a list of source types; a "generator" source is satisfied by a Generator
    *powering* the cell via the road network, not plain adjacency),
  - Garrison conversions (Spymaster -> Legion, Synthflesh -> Transcendent).

Tiers are resolved to a fixed point because they can depend on neighbours' tiers
(Generator range, source_min_tier rules). Upgrade rules are ported from the
Tetriszocker editor; see docs/temple-plan.md.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from aldur_appraiser.temple.rooms import ROOMS

GRID_SIZE = 9
ENTRANCE = (4, 8)  # bottom-centre; the build grows up from here (VERIFY orientation)
GEN_RADIUS = {1: 3, 2: 4, 3: 5}  # Generator Manhattan power range by tier

Cell = tuple[int, int]


def manhattan(a: Cell, b: Cell) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


@dataclass
class Temple:
    size: int = GRID_SIZE
    entrance: Cell = ENTRANCE
    # pre-destabilised / unusable cells (2-3 random per entry)
    blocked: set[Cell] = field(default_factory=set)
    # (x, y) -> room id (an id in ROOMS, including "path")
    cells: dict[Cell, str] = field(default_factory=dict)
    # (x, y) -> tier, for rooms whose tier comes from a player action (sacrifice /
    # assassinate) and so can't be derived from the layout (manual_tier rooms).
    tier_overrides: dict[Cell, int] = field(default_factory=dict)

    # --- grid basics ---------------------------------------------------------

    def copy(self) -> Temple:
        t = Temple(self.size, self.entrance, set(self.blocked), dict(self.cells))
        t.tier_overrides = dict(self.tier_overrides)
        return t

    def in_bounds(self, c: Cell) -> bool:
        return 0 <= c[0] < self.size and 0 <= c[1] < self.size

    def neighbors4(self, c: Cell) -> list[Cell]:
        x, y = c
        return [n for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)) if self.in_bounds(n)]

    def place(self, c: Cell, room_id: str) -> None:
        if room_id not in ROOMS:
            raise ValueError(f"unknown room id {room_id!r}")
        if not self.in_bounds(c):
            raise ValueError(f"cell {c} out of bounds")
        if c in self.blocked:
            raise ValueError(f"cell {c} is destabilised/blocked")
        if c in self.cells:
            raise ValueError(f"cell {c} already occupied by {self.cells[c]!r}")
        self.cells[c] = room_id

    def remove(self, c: Cell) -> None:
        self.cells.pop(c, None)
        self.tier_overrides.pop(c, None)

    def is_path(self, c: Cell) -> bool:
        return self.cells.get(c) == "path"

    def is_room(self, c: Cell) -> bool:
        rid = self.cells.get(c)
        return rid is not None and rid != "path"

    def room_cells(self) -> list[Cell]:
        return [c for c, rid in self.cells.items() if rid != "path"]

    # --- connectivity / accessibility ---------------------------------------

    def accessible_cells(self, *, ignore: Cell | None = None) -> set[Cell]:
        """Occupied cells reachable from the entrance over 4-adjacent occupied
        cells. `ignore` removes a cell first (used to test what a removal would
        orphan). Drives the Generator's road-connection rule and the chokepoint
        (articulation) check."""
        occupied = {c for c in self.cells if c != ignore}
        if not occupied:
            return set()
        # Seed: occupied cells adjacent to (or at) the entrance.
        seeds = [c for c in occupied if c == self.entrance or self.entrance in self.neighbors4(c)]
        seen: set[Cell] = set()
        q = deque(seeds)
        seen.update(seeds)
        while q:
            cur = q.popleft()
            for n in self.neighbors4(cur):
                if n in occupied and n not in seen:
                    seen.add(n)
                    q.append(n)
        return seen

    def accessible_room_cells(self) -> set[Cell]:
        acc = self.accessible_cells()
        return {c for c in acc if self.is_room(c)}

    def chokepoint_room_cells(self) -> set[Cell]:
        """Chokepoint rooms = accessible rooms that are the SOLE connection to some
        room behind them (articulation points): if one is destabilised by the
        random 2-3 per entry, everything behind it is stranded. A valuable room is
        safer as a non-chokepoint — build a redundant path (a loop) around it.

        NB: this is a layout-risk heuristic, NOT the game's "Restricted Rooms"
        (those are the Architect reward Vaults — see is_volatile())."""
        base = self.accessible_room_cells()
        if not base:
            return set()
        chokepoints: set[Cell] = set()
        for c in self.room_cells():
            after = {rc for rc in self.accessible_cells(ignore=c) if self.is_room(rc)}
            if (base - {c}) - after:  # some other room lost access -> c is a chokepoint
                chokepoints.add(c)
        return chokepoints

    # --- conversions ---------------------------------------------------------

    def effective_room_id(self, c: Cell) -> str:
        """A Garrison adjacent to a Spymaster becomes a Legion Barracks; adjacent
        to a Synthflesh Lab it becomes Transcendent Barracks (Spymaster wins ties;
        VERIFY)."""
        rid = self.cells.get(c, "")
        if rid != "garrison":
            return rid
        neigh = {self.cells.get(n) for n in self.neighbors4(c)}
        if "spymaster" in neigh:
            return "legion_barracks"
        if "synthflesh_lab" in neigh:
            return "transcendent_barracks"
        return rid

    # --- tiers ---------------------------------------------------------------

    def _generator_powering(self, cur: dict[Cell, int]) -> dict[Cell, set[Cell]]:
        """room cell -> set of Generator cells powering it. A Generator on the road
        network powers directly adjacent rooms and conducts along connected Path
        cells up to its tier's range, powering rooms beside those powered paths."""
        accessible = self.accessible_cells()
        powering: dict[Cell, set[Cell]] = {}
        gens = [c for c in self.cells if self.cells[c] == "generator"]
        for g in gens:
            if g not in accessible:
                continue  # an unconnected Generator provides no power
            rng = GEN_RADIUS.get(cur.get(g, 1), 0)
            reached: set[Cell] = {n for n in self.neighbors4(g) if self.is_room(n)}
            seen = {g}
            q: deque[tuple[Cell, int]] = deque()
            for p in self.neighbors4(g):
                if self.is_path(p):
                    seen.add(p)
                    q.append((p, 1))
            while q:
                cell, d = q.popleft()
                for n in self.neighbors4(cell):
                    if n in seen:
                        continue
                    if self.is_room(n):
                        reached.add(n)
                    elif self.is_path(n) and d < rng:
                        seen.add(n)
                        q.append((n, d + 1))
            for r in reached:
                powering.setdefault(r, set()).add(g)
        return powering

    def _rule_satisfied(self, c: Cell, rule, cur, powering) -> bool:
        def qualifying(source: str) -> int:
            if source == "generator":
                return sum(
                    1 for g in powering.get(c, ()) if cur.get(g, 1) >= rule.source_min_tier
                )
            return sum(
                1
                for n in self.neighbors4(c)
                if self.is_room(n)
                and self.effective_room_id(n) == source
                and cur.get(n, 1) >= rule.source_min_tier
            )

        if rule.require_all:
            return all(qualifying(s) >= 1 for s in rule.sources)
        return sum(qualifying(s) for s in rule.sources) >= rule.count

    def _compute_tier(self, c: Cell, room, cur, powering) -> int:
        tier = 1
        for rule in room.upgraded_by:
            if self._rule_satisfied(c, rule, cur, powering):
                tier = max(tier, rule.tier)
        return min(tier, 3)

    def tiers(self) -> dict[Cell, int]:
        """Tier of every placed room (paths excluded).

        Iterated to a fixed point because tiers can depend on neighbours' tiers
        (Generator power range; `source_min_tier` rules like Flesh Surgeon needing
        a T2+ Synthflesh). Tiers only rise and are capped at 3, so it converges in
        a few passes."""
        rooms = self.room_cells()
        cur: dict[Cell, int] = {}
        for c in rooms:
            room = ROOMS[self.effective_room_id(c)]
            if room.fixed_tier is not None:
                cur[c] = room.fixed_tier
            elif room.manual_tier:
                cur[c] = self.tier_overrides.get(c, 1)
            else:
                cur[c] = 1
        for _ in range(6):
            powering = self._generator_powering(cur)
            new = dict(cur)
            for c in rooms:
                room = ROOMS[self.effective_room_id(c)]
                if room.fixed_tier is None and not room.manual_tier:
                    new[c] = self._compute_tier(c, room, cur, powering)
            if new == cur:
                break
            cur = new
        return cur

    def room_tier(self, c: Cell) -> int:
        return self.tiers().get(c, 1)

    # --- rule checks ---------------------------------------------------------

    def connection_violations(self) -> list[tuple[Cell, Cell]]:
        """Adjacent room pairs that break a `cannot_connect` rule."""
        bad: list[tuple[Cell, Cell]] = []
        for c in self.room_cells():
            rid = self.effective_room_id(c)
            forbidden = ROOMS[rid].cannot_connect
            for n in self.neighbors4(c):
                if n > c and self.is_room(n) and self.effective_room_id(n) in forbidden:
                    bad.append((c, n))
        return bad
