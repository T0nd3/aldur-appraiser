"""Glue: image -> OCR -> parse -> valuation.

This is the game-independent end of the orchestration loop (app.py adds capture
+ detection on top). Running it on a full panel image works even without ROI
cropping: the "<qty>x <name>" pattern plus the fuzzy cutoff naturally isolate
reward lines from surrounding UI text. ROI cropping (detect.py) is a Phase-3
robustness/perf optimisation, not a correctness requirement here.
"""

from __future__ import annotations

from typing import Protocol

import numpy as np

from aldur_appraiser.parse import parse_rows
from aldur_appraiser.pricing.client import PriceTable
from aldur_appraiser.pricing.valuation import EvalResult, evaluate
from aldur_appraiser.vision.ocr import OcrEngine, read_reward_rows


class Detector(Protocol):
    """Duck-typed PanelDetector (kept here so pipeline stays cv2-free to import)."""

    def find_panel(self, frame: np.ndarray): ...
    def reward_image(self, frame: np.ndarray, panel) -> np.ndarray: ...


def appraise_image(
    image: np.ndarray,
    prices: PriceTable,
    *,
    engine: OcrEngine | None = None,
    detector: Detector | None = None,
    score_cutoff: int = 80,
) -> EvalResult:
    """OCR an image, parse reward options, value and rank them.

    If a detector is given and finds the panel, OCR runs on the reward ROI and
    every "<qty>x <name>" line is treated as a real reward (unknown currency
    kept -> known=False -> incomplete). Without a panel we fall back to OCRing
    the whole frame, where the price dictionary acts as the noise filter.
    """
    roi_mode = False
    target = image
    if detector is not None:
        panel = detector.find_panel(image)
        if panel is not None:
            target = detector.reward_image(image, panel)
            roi_mode = True

    rows = read_reward_rows(target, engine=engine)
    options = parse_rows(rows, prices.keys(), score_cutoff=score_cutoff, keep_unknown=roi_mode)
    return evaluate(options, prices)
