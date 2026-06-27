"""Tests for the per-run placement advisor."""

from __future__ import annotations

from aldur_appraiser.temple.advisor import legal_cells, plan_hand, score, suggest
from aldur_appraiser.temple.engine import Temple


def _temple(entrance=(0, 0)):
    return Temple(entrance=entrance)


def test_score_rewards_higher_tiers():
    t = _temple()
    t.place((4, 4), "commander")
    t.place((5, 4), "garrison")
    low = score(t)
    t.place((3, 4), "garrison")  # commander now T2
    assert score(t) > low


def test_legal_cells_require_network_connection():
    t = _temple(entrance=(4, 8))
    t.place((4, 7), "garrison")           # adjacent to the entrance
    cells = set(legal_cells(t))
    assert (4, 6) in cells                # touches the placed room
    assert (4, 8) in cells                # the entrance itself
    assert (0, 0) not in cells            # far corner, disconnected


def test_suggest_places_third_garrison_next_to_commander():
    # Commander already at T2 (2 adjacent Garrisons); a 3rd adjacent one takes it
    # to T3, which must beat dropping the Garrison anywhere else.
    t = _temple(entrance=(4, 8))
    t.place((4, 5), "commander")
    t.place((5, 5), "garrison")
    t.place((3, 5), "garrison")
    # connect to the entrance so placements are legal around the cluster
    t.place((4, 6), "path")
    t.place((4, 7), "path")
    best = suggest(t, ["garrison"], top=1)[0]
    assert best.card == "garrison"
    assert best.cell == (4, 4)            # the remaining cell adjacent to Commander
    assert best.upgrades >= 1             # it pushed the Commander up a tier


def test_path_that_connects_a_generator_scores_positive():
    # A Generator one tile off the network can't power; a Path bridging it in
    # lets it power the adjacent Smithy -> the Path placement gains score.
    t = _temple(entrance=(0, 0))
    t.place((0, 0), "garrison")           # at entrance
    t.place((2, 0), "generator")
    t.place((2, 1), "smithy")             # within radius once the generator is on the net
    # gap at (1,0) disconnects the generator cluster from the entrance
    s = suggest(t, ["path"], top=1)[0]
    assert s.cell == (1, 0)
    assert s.gain > 0


def test_volatile_room_is_discounted_in_score():
    # a persistent room outscores a one-use (volatile) room of the same tier
    persistent = _temple()
    persistent.place((4, 4), "garrison")          # tier 1, persists
    volatile = _temple()
    volatile.place((4, 4), "treasure_vault")      # tier 1, self-destabilises
    assert score(persistent) > score(volatile)


def test_suggest_flags_one_use_rooms():
    t = _temple(entrance=(4, 8))
    t.place((4, 7), "garrison")                   # something to connect to
    best = [s for s in suggest(t, ["treasure_vault"], top=3) if s.card == "treasure_vault"][0]
    assert "one-use" in best.note


def test_plan_hand_consumes_cards_and_improves_score():
    t = _temple(entrance=(4, 8))
    t.place((4, 7), "commander")
    before = score(t)
    steps = plan_hand(t, ["garrison", "garrison", "path"])
    assert len(steps) == 3                # all cards placed
    # applying the plan for real reproduces a better board
    for s in steps:
        t.cells[s.cell] = s.card
    assert score(t) > before
