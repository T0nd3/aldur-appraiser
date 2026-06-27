"""Read the drawn temple cards off the real screenshot fixtures (needs OCR).

Fixtures live in assets/fixtures (gitignored, local-only) — these tests skip when
they're absent, like test_detect.py.
"""

from __future__ import annotations

from pathlib import Path

import pytest

cv2 = pytest.importorskip("cv2")

from aldur_appraiser.temple.vision import detect_hand  # noqa: E402

FIXDIR = Path(__file__).resolve().parents[1] / "assets" / "fixtures"
CARDS = FIXDIR / "temple_cards.png"
FULL = FIXDIR / "temple_full.png"

EXPECTED = ["path", "generator", "treasure_vault", "path", "smithy", "path"]


@pytest.mark.skipif(not CARDS.exists(), reason="temple card fixture not present")
def test_detect_hand_reads_the_room_cards_panel():
    pytest.importorskip("rapidocr_onnxruntime")
    assert detect_hand(cv2.imread(str(CARDS))) == EXPECTED


@pytest.mark.skipif(not FULL.exists(), reason="full temple fixture not present")
def test_detect_hand_works_on_the_full_frame():
    pytest.importorskip("rapidocr_onnxruntime")
    # the same cards must be found even on the whole console screenshot
    assert detect_hand(cv2.imread(str(FULL)))[:6] == EXPECTED
