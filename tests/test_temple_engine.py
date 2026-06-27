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


# --- restricted (articulation) rooms -----------------------------------------


def test_restricted_room_detected_and_loop_clears_it():
    t = _temple(entrance=(0, 0))
    t.place((0, 0), "garrison")     # entrance
    t.place((0, 1), "armoury")      # sole connector -> restricted
    t.place((0, 2), "commander")    # behind it (a leaf)
    r = t.restricted_room_cells()
    assert (0, 1) in r
    assert (0, 2) not in r          # leaf is safe
    # add a redundant path loop around the armoury -> it's no longer the sole link
    t.place((1, 0), "path")
    t.place((1, 1), "path")
    t.place((1, 2), "path")
    assert (0, 1) not in t.restricted_room_cells()


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
