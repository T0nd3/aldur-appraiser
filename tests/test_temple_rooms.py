"""Tests for the temple room dataset schema + referential integrity."""

from __future__ import annotations

from aldur_appraiser.temple.rooms import ROOMS, Upgrade, destabilises, is_volatile, validate


def test_treasure_vault_and_architect_rooms_are_volatile():
    assert is_volatile(ROOMS["treasure_vault"])          # destabilises once opened
    assert is_volatile(ROOMS["currency_vault"])          # architect reward room
    assert not is_volatile(ROOMS["garrison"])            # a normal, persistent room


def test_craft_rooms_destabilise_only_at_their_device_tier():
    # Alchemy Lab is safe at T1/T2 but destabilises at T3 (Soul Core Infuser)
    assert not destabilises(ROOMS["alchemy_lab"], 2)
    assert destabilises(ROOMS["alchemy_lab"], 3)
    # vaults always destabilise, regardless of tier; a Garrison never does
    assert destabilises(ROOMS["treasure_vault"], 1)
    assert not destabilises(ROOMS["garrison"], 3)


def test_dataset_is_internally_consistent():
    assert validate() == []


def test_keys_match_ids():
    assert all(rid == room.id for rid, room in ROOMS.items())


def test_commander_upgrades_from_barracks_as_a_group():
    rules = {r.tier: r for r in ROOMS["commander"].upgraded_by}
    assert isinstance(rules[2], Upgrade)
    # barracks count together: 2 of {garrison, transcendent} for T2, 3 for T3
    assert set(rules[2].sources) == {"garrison", "transcendent_barracks"}
    assert rules[2].count == 2
    assert rules[3].count == 3


def test_mutual_cannot_connect_between_spymaster_and_commander():
    # the in-game rule "Spymaster cannot connect to Commander" must hold both ways
    assert "commander" in ROOMS["spymaster"].cannot_connect
    assert "spymaster" in ROOMS["commander"].cannot_connect


def test_generator_flag_and_road_note():
    gen = ROOMS["generator"]
    assert gen.generator is True
    assert any("road" in n.lower() or "path" in n.lower() for n in gen.notes)
