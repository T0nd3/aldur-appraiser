"""Tests for the temple room dataset schema + referential integrity."""

from __future__ import annotations

from aldur_appraiser.temple.rooms import ROOMS, UpgradeRule, validate


def test_dataset_is_internally_consistent():
    assert validate() == []


def test_keys_match_ids():
    assert all(rid == room.id for rid, room in ROOMS.items())


def test_commander_upgrades_from_garrison_counts():
    rule = ROOMS["commander"].upgraded_by[0]
    assert isinstance(rule, UpgradeRule)
    assert rule.source == "garrison"
    assert rule.counts == {2: 2, 3: 3}


def test_mutual_cannot_connect_between_spymaster_and_commander():
    # the in-game rule "Spymaster cannot connect to Commander" must hold both ways
    assert "commander" in ROOMS["spymaster"].cannot_connect
    assert "spymaster" in ROOMS["commander"].cannot_connect


def test_generator_flag_and_road_note():
    gen = ROOMS["generator"]
    assert gen.generator is True
    assert any("road" in n.lower() or "path" in n.lower() for n in gen.notes)
