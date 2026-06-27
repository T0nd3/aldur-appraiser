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
