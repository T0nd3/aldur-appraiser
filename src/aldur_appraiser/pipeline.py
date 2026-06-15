"""Glue: image -> OCR -> parse -> valuation.

This is the game-independent end of the orchestration loop (app.py adds capture
+ detection on top). Running it on a full panel image works even without ROI
cropping: the "<qty>x <name>" pattern plus the fuzzy cutoff naturally isolate
reward lines from surrounding UI text. ROI cropping (detect.py) is a Phase-3
robustness/perf optimisation, not a correctness requirement here.
"""

from __future__ import annotations

import numpy as np

from aldur_appraiser.parse import parse_rows
from aldur_appraiser.pricing.client import PriceTable
from aldur_appraiser.pricing.valuation import EvalResult, evaluate
from aldur_appraiser.vision.ocr import OcrEngine, read_reward_rows


def appraise_image(
    image: np.ndarray,
    prices: PriceTable,
    *,
    engine: OcrEngine | None = None,
    score_cutoff: int = 80,
) -> EvalResult:
    """OCR an image, parse reward options, value and rank them."""
    rows = read_reward_rows(image, engine=engine)
    options = parse_rows(rows, prices.keys(), score_cutoff=score_cutoff)
    return evaluate(options, prices)
