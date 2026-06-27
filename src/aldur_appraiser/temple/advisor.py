"""Per-run placement advisor.

Each run you draw 6 random cards (rooms + paths); this ranks where to place them.
Pure functions over the engine: `score` turns a temple into a single number,
`suggest` ranks every legal (card, cell) by how much it raises the score, and
`plan_hand` greedily places a whole hand.

The score is intentionally simple and tweakable: sum of `value[room] * tier` over
placed rooms, minus a penalty per cannot-connect violation. A placement's worth =
the score delta it causes, so it automatically credits not just the placed room's
own tier but every neighbour it upgrades (and a Path that connects a Generator to
the network gets credit for the rooms that Generator then powers).
"""

from __future__ import annotations

from dataclasses import dataclass

from aldur_appraiser.temple.engine import Cell, Temple
from aldur_appraiser.temple.rooms import ROOMS, is_volatile

VIOLATION_PENALTY = 5.0
# A chokepoint (articulation) room is the sole link to rooms behind it, so a
# random destabilisation there strands them — discount its value to nudge the
# advisor toward redundant paths (loops) that protect valuable rooms.
CHOKEPOINT_DISCOUNT = 0.6
# A volatile room (Treasure Vault / Architect reward rooms) self-destabilises once
# used, so it won't persist in a re-runnable temple — discounted the same way.
VOLATILE_DISCOUNT = 0.6


@dataclass
class Suggestion:
    card: str          # room id to place
    cell: Cell
    gain: float        # score delta from placing `card` at `cell`
    result_tier: int   # tier the placed room ends up at
    upgrades: int      # how many already-placed neighbours it pushes up a tier
    note: str = ""


def score(temple: Temple, values: dict[str, float] | None = None) -> float:
    """A single number for the whole temple: sum of value*tier, less violations."""
    values = values or {}
    chokepoints = temple.chokepoint_room_cells()
    total = 0.0
    for c, tier in temple.tiers().items():
        rid = temple.effective_room_id(c)
        worth = values.get(rid, 1.0) * tier
        if c in chokepoints:          # sole link -> a random destab strands rooms
            worth *= 1.0 - CHOKEPOINT_DISCOUNT
        if is_volatile(ROOMS[rid]):   # self-destabilises once used
            worth *= 1.0 - VOLATILE_DISCOUNT
        total += worth
    total -= VIOLATION_PENALTY * len(temple.connection_violations())
    return total


def legal_cells(temple: Temple) -> list[Cell]:
    """Empty, non-blocked cells a card may legally go on: connected to the
    existing network (the game never allows a disconnected placement). On an
    empty grid only cells touching the entrance qualify."""
    out: list[Cell] = []
    for x in range(temple.size):
        for y in range(temple.size):
            c = (x, y)
            if c in temple.cells or c in temple.blocked:
                continue
            touches = c == temple.entrance or any(
                n in temple.cells or n == temple.entrance for n in temple.neighbors4(c)
            )
            if touches:
                out.append(c)
    return out


def _evaluate(temple: Temple, card: str, cell: Cell, base: float,
              base_tiers: dict[Cell, int], values) -> Suggestion:
    temple.cells[cell] = card
    try:
        gain = score(temple, values) - base
        new_tiers = temple.tiers()
        result_tier = new_tiers.get(cell, 1)
        upgrades = sum(
            1
            for n in temple.neighbors4(cell)
            if temple.is_room(n) and new_tiers.get(n, 1) > base_tiers.get(n, 1)
        )
    finally:
        del temple.cells[cell]
    name = ROOMS[card].name
    if card == "path":
        note = "Path — connector" + (f" (+{gain:.0f} from enabling power)" if gain > 0 else "")
    else:
        note = f"{name} → T{result_tier}"
        if upgrades:
            note += f", upgrades {upgrades} neighbour(s)"
        if is_volatile(ROOMS[card]):
            note += " [one-use]"
    return Suggestion(card, cell, gain, result_tier, upgrades, note)


def suggest(temple: Temple, hand, *, values=None, top: int = 5) -> list[Suggestion]:
    """Rank the best single placements for the distinct cards in `hand`."""
    base = score(temple, values)
    base_tiers = temple.tiers()
    work = temple.copy()
    cells = legal_cells(work)
    out = [
        _evaluate(work, card, cell, base, base_tiers, values)
        for card in dict.fromkeys(hand)  # distinct, order-preserving
        if card in ROOMS
        for cell in cells
    ]
    out.sort(key=lambda s: s.gain, reverse=True)
    return out[:top]


def plan_hand(temple: Temple, hand, *, values=None) -> list[Suggestion]:
    """Greedily place a whole hand: repeatedly take the best legal placement for a
    remaining card, apply it, recompute, until the hand is spent or nothing helps."""
    work = temple.copy()
    remaining = list(hand)
    steps: list[Suggestion] = []
    while remaining:
        best = suggest(work, set(remaining), values=values, top=1)
        if not best:
            break
        s = best[0]
        # place it for real and consume one matching card
        work.cells[s.cell] = s.card
        remaining.remove(s.card)
        steps.append(s)
    return steps
