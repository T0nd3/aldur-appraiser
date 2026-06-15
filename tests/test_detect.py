"""Detection tests against the real fixtures + ROI geometry + capture helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

cv2 = pytest.importorskip("cv2")
np = pytest.importorskip("numpy")

from aldur_appraiser.vision import detect as detect_mod  # noqa: E402
from aldur_appraiser.vision.capture import Region, _to_bgr  # noqa: E402
from aldur_appraiser.vision.detect import PanelBox, PanelDetector  # noqa: E402

FIXDIR = Path(__file__).resolve().parents[1] / "assets" / "fixtures"
FIXTURES = [
    p
    for p in (
        FIXDIR / "runeshape_01.png",
        FIXDIR / "runeshape_02.png",
        FIXDIR / "runeshape_03.png",
    )
    if p.exists()
]
REGAL_FIXTURES = [p for p in FIXTURES if p.name in {"runeshape_01.png", "runeshape_02.png"}]
RUNE_FIXTURE = FIXDIR / "runeshape_03.png"


# --- capture helpers (no live display needed) --------------------------------


def test_to_bgr_drops_alpha():
    bgra = np.zeros((4, 5, 4), dtype=np.uint8)
    bgr = _to_bgr(bgra)
    assert bgr.shape == (4, 5, 3)


def test_region_to_mss_roundtrip():
    r = Region(10, 20, 30, 40)
    assert r.to_mss() == {"left": 10, "top": 20, "width": 30, "height": 40}


# --- ROI geometry (pure, no image) -------------------------------------------


def test_reward_roi_scales_with_header():
    panel = PanelBox(x=1085, y=140, w=267, h=68, scale=1.0, confidence=1.0)
    roi = panel.reward_roi()
    assert roi.left == 1085
    assert roi.top == 140 + 68          # one header-height below header top
    assert roi.width == int(267 * detect_mod.ROI_WIDTH_FROM_HEADER_W)
    assert roi.height == int(68 * detect_mod.ROI_HEIGHT_FROM_HEADER_H)


# --- detection on blanks -----------------------------------------------------


def test_no_panel_in_uniform_image():
    det = PanelDetector()
    blank = np.full((400, 600, 3), 30, dtype=np.uint8)
    assert det.find_panel(blank) is None


def test_no_panel_in_noise():
    det = PanelDetector()
    rng = np.random.default_rng(0)
    noise = rng.integers(0, 255, (400, 600, 3), dtype=np.uint8)
    assert det.find_panel(noise) is None


# --- detection on real fixtures ----------------------------------------------


@pytest.mark.skipif(not FIXTURES, reason="real fixtures not present")
@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.name)
def test_detects_panel_in_fixture(path):
    det = PanelDetector()
    img = cv2.imread(str(path))
    panel = det.find_panel(img)
    assert panel is not None
    assert panel.confidence > 0.8
    # ROI must land inside the frame and be non-empty
    crop = det.reward_image(img, panel)
    assert crop.size > 0
    assert crop.shape[0] > 0 and crop.shape[1] > 0


@pytest.mark.skipif(not REGAL_FIXTURES, reason="regal fixtures not present")
@pytest.mark.parametrize("path", REGAL_FIXTURES, ids=lambda p: p.name)
def test_roi_ocr_isolates_currency_reward(path):
    pytest.importorskip("rapidocr_onnxruntime")
    from aldur_appraiser.parse import parse_rows
    from aldur_appraiser.vision import ocr

    det = PanelDetector()
    img = cv2.imread(str(path))
    panel = det.find_panel(img)
    crop = det.reward_image(img, panel)
    rows = ocr.read_reward_rows(crop)
    options = parse_rows(rows, ["Regal Orb", "Divine Orb", "Chaos Orb"])
    assert (1, "Regal Orb") in options


@pytest.mark.skipif(not RUNE_FIXTURE.exists(), reason="rune fixture not present")
def test_roi_keeps_unknown_runes_and_finds_bonus_orb():
    pytest.importorskip("rapidocr_onnxruntime")
    from aldur_appraiser.parse import parse_rows
    from aldur_appraiser.vision import ocr

    det = PanelDetector()
    img = cv2.imread(str(RUNE_FIXTURE))
    crop = det.reward_image(img, det.find_panel(img))
    rows = ocr.read_reward_rows(crop)
    # ROI mode: every "Nx <name>" line kept; 4 runes + the bonus Artificer's Orb
    options = parse_rows(rows, ["Artificer's Orb", "Divine Orb"], keep_unknown=True)
    qtys_names = {name for _, name in options}
    assert "Artificer's Orb" in qtys_names         # qty "Ix" normalised to 1
    assert sum("Lesser" in n and "Rune" in n for n in qtys_names) >= 4
