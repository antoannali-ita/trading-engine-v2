from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN, getcontext
from statistics import median
from typing import Any

getcontext().prec = 28


def _d(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def pct_deviation(a: Any, b: Any) -> float | None:
    da, db = _d(a), _d(b)
    if da is None or db in (None, Decimal("0")):
        return None
    return float((abs(da - db) / abs(db) * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN))


def verify_market_cap(*, price: Any, shares: Any, reported_market_cap: Any, tolerance_pct: float = 5.0) -> dict[str, Any]:
    p, s, reported = _d(price), _d(shares), _d(reported_market_cap)
    if p is None or s is None or reported is None or reported == 0:
        return {"status": "N/D", "calculated": None, "reported": reported_market_cap, "deviation_pct": None}
    calculated = p * s
    deviation = pct_deviation(calculated, reported)
    return {
        "status": "PASS" if deviation is not None and deviation <= tolerance_pct else "WARNING",
        "calculated": float(calculated),
        "reported": float(reported),
        "deviation_pct": deviation,
        "tolerance_pct": tolerance_pct,
    }


def verify_pe(*, price: Any, eps: Any, reported_pe: Any, tolerance_pct: float = 5.0) -> dict[str, Any]:
    p, e, reported = _d(price), _d(eps), _d(reported_pe)
    if p is None or e in (None, Decimal("0")) or reported is None or reported == 0:
        return {"status": "N/D", "calculated": None, "reported": reported_pe, "deviation_pct": None}
    calculated = p / e
    deviation = pct_deviation(calculated, reported)
    return {
        "status": "PASS" if deviation is not None and deviation <= tolerance_pct else "WARNING",
        "calculated": float(calculated),
        "reported": float(reported),
        "deviation_pct": deviation,
        "tolerance_pct": tolerance_pct,
    }


def cross_validate(values: dict[str, Any], tolerance_pct: float = 2.0) -> dict[str, Any]:
    numeric: dict[str, float] = {}
    for source, value in values.items():
        d = _d(value)
        if d is not None:
            numeric[source] = float(d)
    if len(numeric) < 2:
        return {"status": "N/D", "consensus": next(iter(numeric.values()), None), "sources": numeric, "max_deviation_pct": None}
    consensus = median(numeric.values())
    deviations = {
        source: (abs(value - consensus) / abs(consensus) * 100 if consensus else 0.0)
        for source, value in numeric.items()
    }
    max_dev = max(deviations.values()) if deviations else 0.0
    return {
        "status": "PASS" if max_dev <= tolerance_pct else "WARNING",
        "consensus": consensus,
        "sources": numeric,
        "deviations_pct": deviations,
        "max_deviation_pct": max_dev,
        "tolerance_pct": tolerance_pct,
    }
