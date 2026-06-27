"""Vision: read the drawn temple cards off a screenshot (Phase 5a).

Read-only — screen capture + OCR only, no input/memory access. Reuses the pricing
OCR stack (`vision/ocr.py`). `detect_hand` OCRs the image, anchors on the
"Room Cards" header and maps each card label below it to a room id via
`rooms.card_name_to_id` (in-game cards use alternate names: Dynamo=Generator,
Bronzeworks=Smithy, Chamber of Souls=Alchemy Lab, Sealed Vault=Treasure Vault).
Because it anchors on the header and keeps only the panel's column, it works on a
cropped Room Cards panel as well as a full game frame.
"""

from __future__ import annotations

import numpy as np

from aldur_appraiser.temple.rooms import card_name_to_id

# how wide the card column reaches from the header's left edge (ROI pixels);
# keeps the panel's card labels and drops far-away UI text (e.g. Temple Mods).
_COLUMN_WIDTH = 520


def detect_hand(image: np.ndarray, *, engine=None) -> list[str]:
    """Room ids of the drawn cards, top to bottom. Empty if no Room Cards panel
    is recognised. `image` is BGR (a panel crop or a full frame)."""
    from aldur_appraiser.vision.ocr import get_engine

    engine = engine or get_engine()
    lines = sorted(engine.lines(image), key=lambda ln: ln.top)
    if not lines:
        return []

    # find the "Room Cards" header to anchor the list (start + column).
    header = next((ln for ln in lines if "room card" in ln.text.lower()), None)
    if header is None:
        return []
    start_top = header.top + 1
    left = header.box[0] if header.box else 0.0

    hand: list[str] = []
    for ln in lines:
        if ln.top < start_top:
            continue
        x0 = ln.box[0] if ln.box else left
        if not (left - 50 <= x0 <= left + _COLUMN_WIDTH):
            continue  # outside the card column -> unrelated UI text
        rid = card_name_to_id(ln.text)
        if rid:
            hand.append(rid)
    return hand
