"""OCR of the reward text column.

Primary engine: RapidOCR (pure pip wheel, no system dependency, robust on the
italic serif font). Fallback: Tesseract, used only if its binary is present.
The reward name is later fuzzy-snapped (parse.py), so raw name accuracy is
forgiving; the quantity has no fuzzy net, so we expose per-line confidence.

Heavy deps (rapidocr, cv2, pytesseract) are imported lazily so the pricing-only
install keeps working.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from typing import Protocol

import numpy as np


@dataclass(frozen=True)
class OcrLine:
    text: str
    conf: float          # 0..1; -1.0 if the engine reports none
    top: float           # y of the line's top edge, for ordering
    # bounding box (x0, y0, x1, y1) in ROI pixels; None if the engine omits it.
    box: tuple[float, float, float, float] | None = None


class OcrEngine(Protocol):
    def lines(self, img: np.ndarray) -> list[OcrLine]: ...


# --- preprocessing -----------------------------------------------------------


def preprocess(img: np.ndarray, *, scale: float = 2.0, threshold: bool = False) -> np.ndarray:
    """Upscale (helps small text); optionally grayscale+Otsu for Tesseract.

    RapidOCR handles colour/texture well, so threshold defaults off. Tesseract
    benefits from black-on-white, so its engine passes threshold=True.
    """
    import cv2

    out = img
    if scale and scale != 1.0:
        out = cv2.resize(out, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    if threshold:
        gray = cv2.cvtColor(out, cv2.COLOR_BGR2GRAY) if out.ndim == 3 else out
        _, out = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return out


# --- engines -----------------------------------------------------------------


class RapidOcrEngine:
    """Wraps rapidocr_onnxruntime. One detected text box -> one OcrLine."""

    def __init__(self, scale: float = 2.0):
        from rapidocr_onnxruntime import RapidOCR

        self._ocr = RapidOCR()
        self._scale = scale

    def lines(self, img: np.ndarray) -> list[OcrLine]:
        proc = preprocess(img, scale=self._scale, threshold=False)
        result, _ = self._ocr(proc)
        if not result:
            return []
        s = self._scale or 1.0
        out: list[OcrLine] = []
        for box, text, score in result:
            xs = [pt[0] for pt in box]
            ys = [pt[1] for pt in box]
            # OCR ran on the upscaled ROI -> divide back to original ROI pixels
            bbox = (min(xs) / s, min(ys) / s, max(xs) / s, max(ys) / s)
            out.append(
                OcrLine(text=str(text).strip(), conf=float(score), top=bbox[1], box=bbox)
            )
        out.sort(key=lambda ln: ln.top)
        return out


class TesseractEngine:
    """Fallback engine. Requires the tesseract binary on PATH."""

    def __init__(self, scale: float = 3.0, psm: int = 6):
        import pytesseract  # noqa: F401  (import-time check)

        self._scale = scale
        self._psm = psm

    def lines(self, img: np.ndarray) -> list[OcrLine]:
        import pytesseract
        from pytesseract import Output

        proc = preprocess(img, scale=self._scale, threshold=True)
        data = pytesseract.image_to_data(
            proc, config=f"--psm {self._psm}", output_type=Output.DICT
        )
        # Group words into lines by (block, paragraph, line).
        groups: dict[tuple[int, int, int], list[int]] = {}
        for i, word in enumerate(data["text"]):
            if not word.strip():
                continue
            key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
            groups.setdefault(key, []).append(i)

        out: list[OcrLine] = []
        for idxs in groups.values():
            text = " ".join(data["text"][i] for i in idxs)
            confs = [float(data["conf"][i]) for i in idxs if float(data["conf"][i]) >= 0]
            conf = (sum(confs) / len(confs) / 100.0) if confs else -1.0
            s = self._scale or 1.0
            x0 = min(data["left"][i] for i in idxs) / s
            y0 = min(data["top"][i] for i in idxs) / s
            x1 = max(data["left"][i] + data["width"][i] for i in idxs) / s
            y1 = max(data["top"][i] + data["height"][i] for i in idxs) / s
            box = (float(x0), float(y0), float(x1), float(y1))
            out.append(OcrLine(text=text.strip(), conf=conf, top=float(y0), box=box))
        out.sort(key=lambda ln: ln.top)
        return out


def tesseract_available() -> bool:
    return shutil.which("tesseract") is not None


def get_engine(prefer: str = "rapidocr") -> OcrEngine:
    """Return an OCR engine. Prefer RapidOCR; fall back to Tesseract if present.

    Never crashes just because one engine is missing — only raises if neither
    is usable.
    """
    order = ["rapidocr", "tesseract"] if prefer == "rapidocr" else ["tesseract", "rapidocr"]
    errors: list[str] = []
    for name in order:
        try:
            if name == "rapidocr":
                return RapidOcrEngine()
            if name == "tesseract":
                if not tesseract_available():
                    errors.append("tesseract: binary not found on PATH")
                    continue
                return TesseractEngine()
        except ImportError as exc:
            errors.append(f"{name}: {exc}")
    raise RuntimeError("no OCR engine available: " + "; ".join(errors))


def read_reward_rows(img: np.ndarray, *, engine: OcrEngine | None = None) -> list[str]:
    """Convenience: ordered text lines from a reward-column ROI."""
    engine = engine or get_engine()
    return [ln.text for ln in engine.lines(img) if ln.text]
