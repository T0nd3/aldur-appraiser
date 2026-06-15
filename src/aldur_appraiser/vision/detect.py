"""Panel detection via multi-scale template matching.

Matches the "Runeshape Combinations" header (a stable, distinctive element) and
derives the reward-text ROI relative to the match. Multi-scale because the
header's pixel size depends on resolution (calibrated at native 5120x1440; the
3437-wide fixture matches at ~0.67 scale).

ROI ratios are expressed in units of the matched header box, so they scale with
the detected scale automatically. They were measured from runeshape_01.png:
header at x[1085,140], reward text spanning to ~x1575 / y480.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from aldur_appraiser.resources import resource_path
from aldur_appraiser.vision.capture import Region

DEFAULT_TEMPLATE = resource_path("assets/templates/header_runeshape.png")
# Calibrated from a live frame: real panels match ~0.9 (downscaled), a
# non-game desktop produced a 0.75 false positive, so 0.8 separates them.
# Re-tune once we have a live panel-open capture.
DEFAULT_THRESHOLD = 0.8

# Reward ROI as multiples of the matched header box (left=hx, top=hy).
ROI_TOP_FROM_HEADER_H = 1.0   # start one header-height below the header top
ROI_WIDTH_FROM_HEADER_W = 1.95
# Tall enough for up to ~4 options + the bonus reward row (Artificer's Orb in
# fixture 03 sits ~6.5 header-heights below the header top). x stays inside the
# book, so extra height only catches empty parchment, never the quest tracker.
ROI_HEIGHT_FROM_HEADER_H = 7.0


@dataclass(frozen=True)
class PanelBox:
    x: int            # header match top-left
    y: int
    w: int            # matched header width  (template_w * scale)
    h: int            # matched header height (template_h * scale)
    scale: float
    confidence: float

    def reward_roi(self) -> Region:
        return Region(
            left=self.x,
            top=self.y + int(self.h * ROI_TOP_FROM_HEADER_H),
            width=int(self.w * ROI_WIDTH_FROM_HEADER_W),
            height=int(self.h * ROI_HEIGHT_FROM_HEADER_H),
        )


def _clamp_roi(roi: Region, frame_shape: tuple[int, int]) -> Region:
    h, w = frame_shape[:2]
    left = max(0, min(roi.left, w - 1))
    top = max(0, min(roi.top, h - 1))
    return Region(left, top, min(roi.width, w - left), min(roi.height, h - top))


class PanelDetector:
    def __init__(
        self,
        template_path: Path | None = None,
        *,
        threshold: float = DEFAULT_THRESHOLD,
        scales: np.ndarray | None = None,
        detect_downscale: float = 0.4,
    ):
        path = template_path or DEFAULT_TEMPLATE
        tpl = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if tpl is None:
            raise FileNotFoundError(f"detection template not found: {path}")
        self._tpl = tpl
        self.threshold = threshold
        # The template is calibrated at one resolution; multi-scale matching
        # makes detection resolution-/UI-scale-independent. 0.4-1.7 spans roughly
        # 1080p (smaller UI) up to 4K (larger UI) relative to the template.
        self.scales = scales if scales is not None else np.linspace(0.4, 1.7, 27)
        # Match on a downscaled frame for speed; coords are mapped back to full
        # resolution. matchTemplate over a 5120px frame is ~1.5s at full res,
        # ~150ms at 0.4. Set to 1.0 to disable.
        self.detect_downscale = detect_downscale

    def find_panel(self, frame: np.ndarray) -> PanelBox | None:
        """Return the best header match above threshold, else None."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
        d = self.detect_downscale
        if d != 1.0:
            small = cv2.resize(gray, None, fx=d, fy=d, interpolation=cv2.INTER_AREA)
        else:
            small = gray
        th, tw = self._tpl.shape[:2]

        best: PanelBox | None = None
        for scale in self.scales:
            # template size in the (downscaled) search frame
            sw, sh = int(tw * scale * d), int(th * scale * d)
            if sw < 8 or sh < 8 or sw > small.shape[1] or sh > small.shape[0]:
                continue
            tpl = cv2.resize(self._tpl, (sw, sh), interpolation=cv2.INTER_AREA)
            res = cv2.matchTemplate(small, tpl, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)
            if not np.isfinite(max_val):  # uniform region -> NaN
                continue
            if best is None or max_val > best.confidence:
                # map location + size back to full resolution
                best = PanelBox(
                    x=int(max_loc[0] / d), y=int(max_loc[1] / d),
                    w=int(tw * scale), h=int(th * scale),
                    scale=float(scale), confidence=float(max_val),
                )

        if best is None or best.confidence < self.threshold:
            return None
        return best

    def reward_image(self, frame: np.ndarray, panel: PanelBox) -> np.ndarray:
        roi = _clamp_roi(panel.reward_roi(), frame.shape)
        return frame[roi.top : roi.top + roi.height, roi.left : roi.left + roi.width]
