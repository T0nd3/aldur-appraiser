"""Headless smoke test for the temple editor (offscreen Qt)."""

from __future__ import annotations

import os

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from aldur_appraiser.temple.editor import abbrev, build_editor  # noqa: E402


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
    t.place((4, 5), "commander")
    t.place((5, 5), "garrison")
    t.place((3, 5), "garrison")   # Commander at T2; (4, 4) takes it to T3
    w._refresh()

    w.brush = "garrison"
    w._add_card()
    assert w.hand == ["garrison"]
    w._suggest()
    assert w.grid._highlights == {(4, 4)}


def test_editor_priority_weight_feeds_the_advisor():
    from PySide6.QtWidgets import QApplication

    _app = QApplication.instance() or QApplication([])
    w = build_editor()
    w.temple.place((4, 8), "garrison")          # anchor
    w.hand = ["garrison", "alchemy_lab"]
    # set the Alchemy Lab's priority to 5 via the spinbox
    w.brush = "alchemy_lab"
    w.weight_spin.setValue(5.0)
    assert w.weights == {"alchemy_lab": 5.0}
    w._suggest()
    assert "Alchemy Lab" in w.suggestions.text().splitlines()[1]


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

