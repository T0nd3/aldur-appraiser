"""Pipeline glue tests with a fake OCR engine (no OCR dependency needed)."""

from __future__ import annotations

import numpy as np

from aldur_appraiser.pipeline import appraise_image
from aldur_appraiser.vision.ocr import OcrLine

PRICES = {"Divine Orb": 165.0, "Chaos Orb": 13.76, "Orb of Augmentation": 0.05}


class FakeEngine:
    def __init__(self, lines: list[str]):
        self._lines = [OcrLine(text=t, conf=0.9, top=float(i)) for i, t in enumerate(lines)]

    def lines(self, img):  # noqa: ARG002
        return self._lines


def _blank():
    return np.zeros((10, 10, 3), dtype=np.uint8)


def test_pipeline_filters_noise_and_ranks():
    engine = FakeEngine(
        [
            "Runeshape Combinations",        # header noise -> dropped
            "1x Orb of Augmentation",
            "20x Chaos Orb",
            "CRUDE BOW",                     # world text noise -> dropped
            "1x Divine Orb",
        ]
    )
    result = appraise_image(_blank(), PRICES, engine=engine)

    names = [v.name for v in result.items]
    assert "Divine Orb" in names and "Chaos Orb" in names
    # 20x chaos = 275.2 ex beats 1 divine = 165 ex
    assert result.best.name == "Chaos Orb"
    assert result.incomplete is False


def test_pipeline_marks_unknown_incomplete():
    engine = FakeEngine(["1x Divine Orb", "1x Mystery Relic"])
    result = appraise_image(_blank(), PRICES, engine=engine)
    # No detector -> whole-frame mode -> dictionary is the noise filter, so
    # "Mystery Relic" is dropped and isn't even an option.
    assert [v.name for v in result.items] == ["Divine Orb"]
    assert result.incomplete is False


class FakeDetector:
    """Returns a panel and passes the frame through as the reward ROI."""

    def find_panel(self, frame):  # noqa: ARG002
        return object()

    def reward_image(self, frame, panel):  # noqa: ARG002
        return frame


def test_pipeline_roi_mode_keeps_unknown_rewards():
    # In ROI mode every "Nx <name>" line is a real reward: unknown ones are
    # kept (known=False) and flag the comparison incomplete.
    engine = FakeEngine(
        [
            "1x Divine Orb",
            "1x Lesser Storm Rune",
            "1x Lesser Glacial Rune",
            "Bonus Reward",   # no qty -> still dropped
        ]
    )
    result = appraise_image(_blank(), PRICES, engine=engine, detector=FakeDetector())

    names = [v.name for v in result.items]
    assert "Divine Orb" in names
    assert "Lesser Storm Rune" in names and "Lesser Glacial Rune" in names
    assert "Bonus Reward" not in names
    assert result.best.name == "Divine Orb"     # only valuable option
    assert result.incomplete is True            # two unvaluable rewards present
