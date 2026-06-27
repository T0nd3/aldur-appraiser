"""Tests for the temple rules engine (grid/tiers/connectivity/risk)."""

from __future__ import annotations

from aldur_appraiser.temple.engine import Temple


def _temple(entrance=(0, 0), **kw):
    return Temple(entrance=entrance, **kw)


# --- adjacency-based tiers ---------------------------------------------------


def test_commander_tier_scales_with_adjacent_garrisons():
    t = _temple()
    t.place((4, 4), "commander")
    t.place((5, 4), "garrison")
    t.place((3, 4), "garrison")
    assert t.room_tier((4, 4)) == 2  # 2 adjacent Garrisons -> T2
    t.place((4, 3), "garrison")
    assert t.room_tier((4, 4)) == 3  # 3 -> T3


def test_garrison_t3_requires_both_commander_and_armoury():
    # require_all: 1 barrack-line upgrader -> T2, but T3 needs Commander AND Armoury
    t = _temple()
    t.place((4, 4), "garrison")
    t.place((5, 4), "commander")
    assert t.room_tier((4, 4)) == 2
    t.place((3, 4), "armoury")
    assert t.room_tier((4, 4)) == 3


def test_smithy_counts_golem_and_generator_together():
    # group sum: a Generator (power) + a Golem Works count as 2 toward Smithy T3
    t = _temple(entrance=(0, 0))
    t.place((0, 0), "generator")        # powers adjacent
    t.place((1, 0), "smithy")
    assert t.room_tier((1, 0)) == 2     # 1 source (generator)
    t.place((1, 1), "golem_works")
    assert t.room_tier((1, 0)) == 3     # 2 sources (generator + golem)


def test_generator_conducts_power_along_paths():
    # a Generator powers rooms beside paths it feeds (within range), not just
    # directly-adjacent ones
    t = _temple(entrance=(0, 0))
    t.place((0, 0), "generator")
    t.place((1, 0), "path")
    t.place((2, 0), "path")             # 2 path-steps from the generator (range 3)
    t.place((2, 1), "smithy")           # beside the powered path
    assert t.room_tier((2, 1)) == 2


def test_fixed_tier_room_never_upgrades():
    t = _temple()
    t.place((4, 4), "treasure_vault")
    t.place((5, 4), "garrison")
    assert t.room_tier((4, 4)) == 1


# --- generator power (radius + must be connected) ----------------------------


def test_generator_powers_smithy_within_radius_when_connected():
    t = _temple(entrance=(0, 0))
    t.place((0, 0), "generator")   # at the entrance -> accessible
    t.place((1, 0), "smithy")      # manhattan 1 <= T1 radius (3)
    assert t.room_tier((1, 0)) >= 2


def test_disconnected_generator_does_not_power():
    t = _temple(entrance=(8, 8))   # entrance far away
    t.place((0, 0), "generator")   # not connected to the entrance network
    t.place((1, 0), "smithy")
    assert t.room_tier((1, 0)) == 1


def test_generator_out_of_range_does_not_power():
    t = _temple(entrance=(0, 0))
    t.place((0, 0), "generator")
    t.place((5, 0), "smithy")      # manhattan 5 > T1 radius (3)
    # bridge them so the smithy is on the network but still out of power range
    for x in range(1, 5):
        t.place((x, 0), "path")
    assert t.room_tier((5, 0)) == 1


# --- accessibility -----------------------------------------------------------


def test_accessibility_from_entrance():
    t = _temple(entrance=(0, 0))
    t.place((0, 0), "garrison")
    t.place((0, 1), "commander")
    t.place((5, 5), "armoury")     # disconnected island
    acc = t.accessible_room_cells()
    assert (0, 0) in acc and (0, 1) in acc
    assert (5, 5) not in acc


# --- removable (loose-end) rooms / snake logic -------------------------------


def test_removable_rooms_are_the_loose_ends_of_the_chain():
    t = _temple(entrance=(4, 8))
    t.place((4, 7), "garrison")     # first room (anchored to the entrance) -> safe
    t.place((4, 6), "armoury")      # interior of the snake -> safe (articulation)
    t.place((4, 5), "commander")    # the tail -> the only deletable room
    assert t.removable_room_cells() == {(4, 5)}
    assert (4, 6) in t.articulation_room_cells()
    # branching off the middle adds a second loose end (worse for keeping rooms)
    t.place((5, 6), "smithy")
    assert t.removable_room_cells() == {(4, 5), (5, 6)}


def test_temple_to_dict_from_dict_roundtrip():
    t = _temple(entrance=(4, 8))
    t.place((4, 7), "garrison")
    t.place((4, 6), "sacrificial_chamber")
    t.tier_overrides[(4, 6)] = 3
    t2 = Temple.from_dict(t.to_dict())
    assert t2.cells == t.cells
    assert t2.tier_overrides == t.tier_overrides
    assert t2.entrance == t.entrance


# --- manual tier override (sacrifice / assassinate rooms) --------------------


def test_manual_tier_override_for_sacrifice_room():
    t = _temple()
    t.place((4, 4), "sacrificial_chamber")
    assert t.room_tier((4, 4)) == 1            # default until set
    t.tier_overrides[(4, 4)] = 3
    assert t.room_tier((4, 4)) == 3
    t.remove((4, 4))                           # removal drops the override
    assert (4, 4) not in t.tier_overrides


def test_override_ignored_for_layout_upgraded_room():
    t = _temple()
    t.place((4, 4), "commander")               # not a manual_tier room
    t.tier_overrides[(4, 4)] = 3
    assert t.room_tier((4, 4)) == 1            # override ignored; no adjacent garrisons


# --- conversions -------------------------------------------------------------


def test_spymaster_converts_adjacent_garrison_to_legion():
    t = _temple()
    t.place((4, 4), "garrison")
    t.place((5, 4), "spymaster")
    assert t.effective_room_id((4, 4)) == "legion_barracks"


def test_synthflesh_converts_adjacent_garrison_to_transcendent():
    t = _temple()
    t.place((4, 4), "garrison")
    t.place((5, 4), "synthflesh_lab")
    assert t.effective_room_id((4, 4)) == "transcendent_barracks"


# --- cannot-connect rule -----------------------------------------------------


def test_cannot_connect_violation_detected():
    t = _temple()
    t.place((4, 4), "commander")
    t.place((5, 4), "spymaster")    # Commander cannot connect to Spymaster
    assert t.connection_violations() == [((4, 4), (5, 4))]


def test_tiers_returns_all_rooms_only():
    t = _temple(entrance=(0, 0))
    t.place((0, 0), "garrison")
    t.place((0, 1), "path")
    t.place((0, 2), "commander")
    tiers = t.tiers()
    assert set(tiers) == {(0, 0), (0, 2)}  # path excluded
