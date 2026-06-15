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

# "1x Orb of Augmentation", "20 x Chaos Orb", "3X Divine Orb"
ROW_RE = re.compile(r"(\d+)\s*[xX]\s*(.+)", re.IGNORECASE)

DEFAULT_CUTOFF = 80
# Reject absurd quantities (OCR garbage); real stacks stay well under this.
MAX_QTY = 100_000


def parse_row(
    raw: str,
    dictionary: Iterable[str],
    *,
    score_cutoff: int = DEFAULT_CUTOFF,
) -> tuple[int, str] | None:
    """Parse one OCR line into (qty, canonical_name), or None if unusable."""
    if not raw:
        return None
    match = ROW_RE.search(raw.strip())
    if not match:
        return None

    qty = int(match.group(1))
    if qty < 1 or qty > MAX_QTY:
        return None

    name = snap_name(match.group(2), dictionary, score_cutoff=score_cutoff)
    if name is None:
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
) -> list[tuple[int, str]]:
    """Parse many OCR lines, dropping any that don't yield a confident option."""
    dictionary = list(dictionary)  # reuse across rows
    out: list[tuple[int, str]] = []
    for raw in rows:
        opt = parse_row(raw, dictionary, score_cutoff=score_cutoff)
        if opt is not None:
            out.append(opt)
    return out
