"""Value and rank reward options.

Values are already in the base currency (the source returns CurrentPrice in the
chosen ReferenceCurrency), so total = qty * unit. Unknown / thin-market currency
is never guessed: known=False, total=None. If any option is unknown the result
is flagged incomplete, because the "best" pick can't be stated with certainty.
"""

from __future__ import annotations

from dataclasses import dataclass

from aldur_appraiser.pricing.client import PriceTable


@dataclass(frozen=True)
class Valuation:
    name: str
    qty: int
    unit: float | None       # unit value in base currency, or None if unknown
    total: float | None      # qty * unit, or None if unknown
    known: bool
    is_best: bool = False


@dataclass(frozen=True)
class EvalResult:
    items: list[Valuation]   # sorted: known by total desc, then unknown
    incomplete: bool         # True if at least one option couldn't be valued

    @property
    def best(self) -> Valuation | None:
        return next((v for v in self.items if v.is_best), None)


def evaluate(options: list[tuple[int, str]], prices: PriceTable) -> EvalResult:
    """options: [(qty, canonical_name)] -> ranked EvalResult."""
    valuations: list[Valuation] = []
    for qty, name in options:
        unit = prices.get(name)
        if unit is None:
            valuations.append(Valuation(name=name, qty=qty, unit=None, total=None, known=False))
        else:
            valuations.append(
                Valuation(name=name, qty=qty, unit=unit, total=qty * unit, known=True)
            )

    known = [v for v in valuations if v.known]
    unknown = [v for v in valuations if not v.known]
    known.sort(key=lambda v: v.total, reverse=True)

    if known:
        top = known[0]
        known[0] = Valuation(**{**top.__dict__, "is_best": True})

    return EvalResult(items=known + unknown, incomplete=bool(unknown))
