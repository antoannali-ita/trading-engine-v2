"""Market-boundary guardrails for the modular migration.

Phase A remains parity-first and executes the frozen reference engines.  These
helpers make the USA/Italy boundaries explicit for Phase B and for normalized
outputs, without changing the frozen baselines.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Optional

_GEM_RE = re.compile(r"^\d+[A-Z]+$")
_FINANCIAL_KEYS = ("finance", "financial", "finanza", "bank", "banca", "insurance", "assicur")


def market_name(cfg: Dict[str, Any]) -> str:
    return str(cfg.get("market") or "").strip().upper()


def prebuy_enabled(cfg: Dict[str, Any]) -> bool:
    return bool(cfg.get("prebuy_enabled", False))


def financial_adjustment_enabled(cfg: Dict[str, Any], sector: Optional[str] = None) -> bool:
    """Financial-sector special treatment is an Italy-only rule in Phase A."""
    if market_name(cfg) != "ITALY":
        return False
    if not bool(cfg.get("financial_sector_adjustment", False)):
        return False
    if sector is None:
        return True
    s = str(sector).strip().lower()
    return any(k in s for k in _FINANCIAL_KEYS)


def should_exclude_gem(cfg: Dict[str, Any], ticker: str) -> bool:
    """Apply the GEM/foreign-listing regex only to the Italian universe."""
    if market_name(cfg) != "ITALY":
        return False
    if not bool(cfg.get("gem_filter_enabled", False)):
        return False
    return bool(_GEM_RE.fullmatch(str(ticker or "").strip().upper()))


def rs_state_when_benchmark_missing(benchmark_hist: Any) -> Optional[str]:
    """Return N/D when the benchmark series is unavailable, else None.

    The caller may continue with the baseline RS classification when None is
    returned.  This prevents provider outages from becoming exceptions or
    invented relative-strength values.
    """
    if benchmark_hist is None:
        return "N/D"
    try:
        if bool(getattr(benchmark_hist, "empty", False)):
            return "N/D"
    except Exception:
        return "N/D"
    return None


def presentation_state(reference: Any, cfg: Dict[str, Any], candidate: Dict[str, Any]) -> str:
    """Return the user-facing state without silently adding PRE-BUY to Italy.

    USA v5.5 may use its native ``display_state``/PRE-BUY logic. Italy v1.2 did
    not have PRE-BUY, so Phase A keeps its visual semantics unchanged.
    """
    decision = candidate.get("decision")

    if prebuy_enabled(cfg) and hasattr(reference, "display_state"):
        return reference.display_state(candidate)

    if decision == "BUY_NOW":
        return "BUY NOW"
    if decision == "BUY_LIMIT":
        return "BUY LIMIT"
    if decision in {"AVOID", "DATA_INSUFFICIENT"}:
        return "AVOID"
    return "WAIT"
