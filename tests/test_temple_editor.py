"""Headless smoke test for the temple editor (offscreen Qt)."""

from __future__ import annotations

import os

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from aldur_appraiser.temple.editor import abbrev, build_editor  # noqa: E402


@pytest.fixture(autouse=True)
def _isolated_layout(tmp_path, monkeypatch):
    """Point persistence at a throwaway file so a real saved layout in the user's
    config dir can't leak into (and break) these tests."""
    import aldur_appraiser.temple.editor as ed

    monkeypatch.setattr(ed, "layout_path", lambda: tmp_path / "layout.json")


def test_editor_builds_and_reflects_engine_state():
    from PySide6.QtWidgets import QApplication

    _app = QApplication.instance() or QApplication([])
    w = build_editor()

    # place a Commander with 2 adjacent Garrisons -> the engine should read T2
    w.temple.place((4, 4), "commander")
    w.temple.place((5, 4), "garrison")
    w.temple.place((3, 4), "garrison")
    w._refresh()

    assert w.temple.tiers()[(4, 4)] == 2
    assert "Rooms: 3" in w.status.text()
    assert "Tier 3: 0" in w.status.text()


def test_abbrev_uses_initials():
    assert abbrev("commander") == "CC"   # Commander's Chamber
    assert abbrev("path") == ""


def test_editor_advisor_highlights_best_cell():
    from PySide6.QtWidgets import QApplication

    _app = QApplication.instance() or QApplication([])
    w = build_editor()
    t = w.temple
    t.place((4, 7), "commander")   # adjacent to the entrance (4,8) -> connected
    t.place((5, 7), "garrison")
    t.place((3, 7), "garrison")   # Commander at T2; (4, 6) takes it to T3
    w._refresh()

    w.brush = "garrison"
    w._add_card()
    assert w.hand == ["garrison"]
    w._suggest()
    assert w.grid._highlights == {(4, 6)}


def test_remove_selected_card_from_hand():
    from PySide6.QtWidgets import QApplication

    _app = QApplication.instance() or QApplication([])
    w = build_editor()
    for rid in ("garrison", "commander", "path"):
        w.brush = rid
        w._add_card()
    assert w.hand == ["garrison", "commander", "path"]
    w.hand_list.setCurrentRow(1)                # select "Commander"
    w._remove_card()
    assert w.hand == ["garrison", "path"]
    assert w.hand_list.count() == 2


def test_editor_preset_feeds_the_advisor():
    from PySide6.QtWidgets import QApplication

    _app = QApplication.instance() or QApplication([])
    w = build_editor()
    w.temple.place((4, 8), "garrison")          # anchor
    w.hand = ["garrison", "alchemy_lab"]
    w.preset_select.setCurrentText("Currency & Rarity")   # weights Alchemy Lab up
    assert w.weights.get("alchemy_lab", 1.0) > 1.0
    w._suggest()
    assert "Alchemy Lab" in w.suggestions.text().splitlines()[1]


def test_medallion_rooms_feed_the_advisor():
    from PySide6.QtWidgets import QApplication

    _app = QApplication.instance() or QApplication([])
    w = build_editor()
    w.temple.place((4, 8), "garrison")          # anchor at the entrance
    w.medallions = ["alchemy_lab"]              # a medallion-granted Armoury/Lab
    w._suggest()
    # the medallion room is considered even with an empty drawn hand
    assert "Alchemy Lab" in w.suggestions.text()


def test_medallions_persist_across_editor_sessions(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QApplication

    import aldur_appraiser.temple.editor as ed

    monkeypatch.setattr(ed, "layout_path", lambda: tmp_path / "layout.json")
    _app = QApplication.instance() or QApplication([])

    w = ed.build_editor()
    w.medallions = ["armoury"]
    w._persist()

    w2 = ed.build_editor()
    assert w2.medallions == ["armoury"]


def test_cellname_is_one_indexed_col_row():
    from aldur_appraiser.temple.editor import cellname

    assert cellname((0, 0)) == "col 1, row 1"
    assert cellname((3, 6)) == "col 4, row 7"


def test_layout_persists_across_editor_sessions(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QApplication

    import aldur_appraiser.temple.editor as ed

    monkeypatch.setattr(ed, "layout_path", lambda: tmp_path / "layout.json")
    _app = QApplication.instance() or QApplication([])

    w = ed.build_editor()                       # starts empty (tmp file absent)
    w.temple.place((4, 7), "garrison")
    w.preset_select.setCurrentText("Experience")
    w._persist()

    w2 = ed.build_editor()                       # a fresh session restores it
    assert w2.temple.cells.get((4, 7)) == "garrison"
    assert w2.preset_select.currentText() == "Experience"


def test_editor_applies_tier_override_to_manual_room():
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    _app = QApplication.instance() or QApplication([])
    w = build_editor()
    w.tier_select.setCurrentIndex(2)            # Tier 3
    w.brush = "spymaster"
    w._on_cell((2, 2), int(Qt.LeftButton.value))
    assert w.temple.tier_overrides[(2, 2)] == 3
    assert w.temple.room_tier((2, 2)) == 3

