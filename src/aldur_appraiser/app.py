"""Orchestration loop: capture -> detect -> OCR -> price -> render.

The per-frame work is split into AppraiserLoop.step() (pure, testable with a
fed frame) and run() (the timed capture loop). Rendering goes through callbacks
so the same loop drives the console now and an overlay later.

A frame-diff gate avoids re-running OCR (and re-rendering) while the panel
content is unchanged, which keeps CPU low at the poll rate.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from aldur_appraiser.parse import parse_rows
from aldur_appraiser.pricing.client import PriceTable
from aldur_appraiser.pricing.valuation import EvalResult, evaluate
from aldur_appraiser.vision import ocr
from aldur_appraiser.vision.detect import PanelDetector

# ROI is downsampled to this many cells per side for the change signature.
_SIG_SIZE = 24
_SIG_EPS = 4.0  # mean abs per-cell delta above which the ROI is "changed"


def _signature(roi: np.ndarray) -> np.ndarray:
    import cv2

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY) if roi.ndim == 3 else roi
    return cv2.resize(gray, (_SIG_SIZE, _SIG_SIZE), interpolation=cv2.INTER_AREA).astype(np.float32)


def _changed(a: np.ndarray | None, b: np.ndarray) -> bool:
    return a is None or a.shape != b.shape or float(np.abs(a - b).mean()) > _SIG_EPS


@dataclass
class AppraiserLoop:
    prices: PriceTable
    detector: PanelDetector
    engine: ocr.OcrEngine
    on_result: Callable[[EvalResult], None]
    on_hide: Callable[[], None]
    score_cutoff: int = 80

    _last_sig: np.ndarray | None = None
    _panel_visible: bool = False

    def step(self, frame: np.ndarray) -> EvalResult | None:
        """Process one frame. Returns the result if (re)evaluated, else None."""
        panel = self.detector.find_panel(frame)
        if panel is None:
            if self._panel_visible:
                self._panel_visible = False
                self._last_sig = None
                self.on_hide()
            return None

        roi = self.detector.reward_image(frame, panel)
        sig = _signature(roi)
        if not _changed(self._last_sig, sig):
            return None  # panel open but unchanged -> skip OCR

        self._last_sig = sig
        self._panel_visible = True
        rows = ocr.read_reward_rows(roi, engine=self.engine)
        options = parse_rows(
            rows, self.prices.keys(), score_cutoff=self.score_cutoff, keep_unknown=True
        )
        result = evaluate(options, self.prices)
        self.on_result(result)
        return result

    def run(self, capture, *, poll_fps: float = 3.0, region=None) -> None:
        """Timed capture loop until interrupted."""
        interval = 1.0 / poll_fps
        while True:
            t0 = time.monotonic()
            frame = capture.grab(region)
            self.step(frame)
            dt = time.monotonic() - t0
            if dt < interval:
                time.sleep(interval - dt)


# --- console rendering -------------------------------------------------------


def render_console(result: EvalResult, *, base: str, stale: bool = False) -> str:
    if not result.items:
        return "Panel open — no reward options recognised."
    lines = [f"Reward ranking (base={base}){' [STALE PRICES]' if stale else ''}:"]
    for v in result.items:
        marker = "  <-- BEST" if v.is_best else ""
        if v.known:
            lines.append(f"  {v.qty}x {v.name:<26} {v.total:>10.2f} {base}{marker}")
        else:
            lines.append(f"  {v.qty}x {v.name:<26} {'unknown':>10}{marker}")
    if result.incomplete:
        lines.append("  (comparison incomplete: an option has no market price)")
    return "\n".join(lines)


def run_app(*, backend: str | None = None) -> int:
    """Entry point for `appraiser run`: wire everything and loop on the console."""
    from aldur_appraiser.config import load_config
    from aldur_appraiser.pricing.cache import get_or_fetch
    from aldur_appraiser.vision.capture import default_backend, open_capture

    cfg = load_config()
    pc = cfg.pricing
    cached = get_or_fetch(
        pc.league,
        pc.base,
        ttl_minutes=pc.cache_ttl_minutes,
        realm=pc.realm,
        categories=pc.categories,
    )
    poll_fps = float(cfg.raw.get("vision", {}).get("poll_fps", 3))
    chosen = backend or default_backend()

    loop = AppraiserLoop(
        prices=cached.table,
        detector=PanelDetector(),
        engine=ocr.get_engine(),
        on_result=lambda r: print(render_console(r, base=pc.base, stale=cached.stale) + "\n"),
        on_hide=lambda: print("(panel closed)\n"),
    )

    print(f"aldur-appraiser running (backend={chosen}, league={pc.league}, base={pc.base}).")
    print("Open a Runeshape Combinations panel in-game. Ctrl+C to stop.\n")
    try:
        with open_capture(backend=chosen) as cap:
            if hasattr(cap, "assert_capturable"):
                cap.assert_capturable()
            loop.run(cap, poll_fps=poll_fps)
    except KeyboardInterrupt:
        print("\nstopped.")
        return 0
    return 0
