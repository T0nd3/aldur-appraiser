"""Glue: image -> OCR -> parse -> valuation.

This is the game-independent end of the orchestration loop (app.py adds capture
+ detection on top). Running it on a full panel image works even without ROI
cropping: the "<qty>x <name>" pattern plus the fuzzy cutoff naturally isolate
reward lines from surrounding UI text. ROI cropping (detect.py) is a Phase-3
robustness/perf optimisation, not a correctness requirement here.
"""

from __future__ import annotations

import statistics
from typing import Protocol

import numpy as np
from rapidfuzz import fuzz

from aldur_appraiser.parse import parse_rows
from aldur_appraiser.pricing.client import PriceTable
from aldur_appraiser.pricing.valuation import EvalResult, evaluate
from aldur_appraiser.vision.ocr import OcrEngine, OcrLine, get_engine, read_reward_rows

# A reward row separated from the ones above by more than this multiple of the
# typical row spacing is the bonus reward (sits below a "Bonus Reward" divider).
_BONUS_GAP_FACTOR = 1.6


class Detector(Protocol):
    """Duck-typed PanelDetector (kept here so pipeline stays cv2-free to import)."""

    def find_panel(self, frame: np.ndarray): ...
    def reward_image(self, frame: np.ndarray, panel) -> np.ndarray: ...


def _is_bonus_label(text: str) -> bool:
    return fuzz.ratio(text.lower(), "bonus reward") >= 75


def split_bonus(lines: list[OcrLine]) -> tuple[list[OcrLine], list[OcrLine]]:
    """Split reward rows into (choices, bonus).

    The bonus reward is always paid, so it must not be ranked. It's identified by
    a "Bonus Reward" divider label, or failing that by the large vertical gap
    that divider leaves before the final row.
    """
    rows = sorted(lines, key=lambda ln: ln.top)
    # 1) explicit divider label -> everything after it is bonus
    for i, ln in enumerate(rows):
        if _is_bonus_label(ln.text):
            return rows[:i], rows[i + 1 :]
    # 2) gap heuristic: the last row, if clearly separated, is the bonus
    if len(rows) >= 2:
        gaps = [rows[i + 1].top - rows[i].top for i in range(len(rows) - 1)]
        if len(gaps) >= 2:
            typical = statistics.median(gaps[:-1])
            if typical > 0 and gaps[-1] > _BONUS_GAP_FACTOR * typical:
                return rows[:-1], [rows[-1]]
    return rows, []


def appraise_roi(
    roi: np.ndarray,
    prices: PriceTable,
    *,
    engine: OcrEngine | None = None,
    score_cutoff: int = 80,
) -> EvalResult:
    """OCR a reward-ROI, separate the always-paid bonus, value and rank choices."""
    engine = engine or get_engine()
    lines = [ln for ln in engine.lines(roi) if ln.text]
    choice_lines, bonus_lines = split_bonus(lines)
    keys = list(prices.keys())

    def _parse(group: list[OcrLine]) -> list[tuple[int, str]]:
        texts = [ln.text for ln in group]
        return parse_rows(texts, keys, score_cutoff=score_cutoff, keep_unknown=True)

    return evaluate(_parse(choice_lines), prices, bonus=_parse(bonus_lines))


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
    if detector is not None:
        panel = detector.find_panel(image)
        if panel is not None:
            roi = detector.reward_image(image, panel)
            return appraise_roi(roi, prices, engine=engine, score_cutoff=score_cutoff)

    # No panel: OCR the whole frame; the price dictionary filters noise and we
    # can't reliably locate a bonus divider, so don't split one out.
    rows = read_reward_rows(image, engine=engine)
    options = parse_rows(rows, prices.keys(), score_cutoff=score_cutoff, keep_unknown=False)
    return evaluate(options, prices)
