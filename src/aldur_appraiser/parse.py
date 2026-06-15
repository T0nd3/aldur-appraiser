"""Turn raw OCR reward lines into (qty, canonical_name) options.

The reward is text-only (e.g. "1x Orb of Augmentation"); the icons left of it
are the runeshape combination (recipe input), not the reward. So we OCR the
text, regex out the quantity, and fuzzy-snap the name against the known
currency list (the PriceTable keys) — which fixes OCR/italic slips like
"Orb of Augrnentation" -> "Orb of Augmentation". Anything below the fuzzy
cutoff returns None: better nothing than a wrong match.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from rapidfuzz import process

# "1x Orb of Augmentation", "20 x Chaos Orb", "3X Divine Orb".
# The quantity token allows letters the OCR confuses with digits on the italic
# serif font ("1x" -> "Ix"/"ix"/"lx", "0" -> "O"); they're normalised below.
ROW_RE = re.compile(r"([0-9IilOo]+)\s*[xX×]\s*(.+)")
_QTY_FIX = str.maketrans({"I": "1", "i": "1", "l": "1", "O": "0", "o": "0"})

DEFAULT_CUTOFF = 80
# Reject absurd quantities (OCR garbage); real stacks stay well under this.
MAX_QTY = 100_000


def _parse_qty(token: str) -> int | None:
    fixed = token.translate(_QTY_FIX)
    return int(fixed) if fixed.isdigit() else None


def parse_row(
    raw: str,
    dictionary: Iterable[str],
    *,
    score_cutoff: int = DEFAULT_CUTOFF,
    keep_unknown: bool = False,
) -> tuple[int, str] | None:
    """Parse one OCR line into (qty, name), or None if unusable.

    With keep_unknown=False the name must fuzzy-snap to the dictionary (used on
    full frames, where the dictionary doubles as a noise filter). With
    keep_unknown=True a parseable "<qty>x <name>" line that doesn't snap keeps
    its cleaned raw name (used inside the detected reward ROI, where every such
    line is a genuine reward we just can't price -> later valued known=False).
    """
    if not raw:
        return None
    match = ROW_RE.search(raw.strip())
    if not match:
        return None

    qty = _parse_qty(match.group(1))
    if qty is None or qty < 1 or qty > MAX_QTY:
        return None

    raw_name = match.group(2).strip().strip(".,:;")
    name = snap_name(raw_name, dictionary, score_cutoff=score_cutoff)
    if name is None:
        if keep_unknown and raw_name:
            return qty, raw_name
        return None
    return qty, name


def snap_name(
    raw_name: str,
    dictionary: Iterable[str],
    *,
    score_cutoff: int = DEFAULT_CUTOFF,
) -> str | None:
    """Fuzzy-snap a noisy name to the closest known currency name."""
    cleaned = raw_name.strip().strip(".,:;")
    if not cleaned:
        return None
    result = process.extractOne(cleaned, list(dictionary), score_cutoff=score_cutoff)
    return result[0] if result else None


def parse_rows(
    rows: Iterable[str],
    dictionary: Iterable[str],
    *,
    score_cutoff: int = DEFAULT_CUTOFF,
    keep_unknown: bool = False,
) -> list[tuple[int, str]]:
    """Parse many OCR lines, dropping any that don't yield a usable option."""
    dictionary = list(dictionary)  # reuse across rows
    out: list[tuple[int, str]] = []
    for raw in rows:
        opt = parse_row(raw, dictionary, score_cutoff=score_cutoff, keep_unknown=keep_unknown)
        if opt is not None:
            out.append(opt)
    return out
