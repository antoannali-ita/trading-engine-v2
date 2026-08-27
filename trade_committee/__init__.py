"""LAB-RESEARCH-001 · Trade Committee.

Modulo manuale e indipendente di due diligence pre-trade.
Il CORE resta la single source of truth per la trade; i dati tecnici locali sono
cross-check normalizzati e non sostituiscono segnali, score o ordini Production.
"""

from . import research_checks as _research_checks
from .core_snapshot_store import find_latest_core_snapshot
from .technical_normalization import normalize_market_bundle


_raw_fetch_market_bundle = _research_checks.fetch_market_bundle


def _normalized_fetch_market_bundle(symbol: str):
    return normalize_market_bundle(_raw_fetch_market_bundle(symbol))


# Adapter transitorio: mantiene research_checks compatibile, ma standardizza RSI Wilder
# e impedisce che un RVOL daily parziale venga penalizzato come full-session.
_research_checks.fetch_market_bundle = _normalized_fetch_market_bundle

from .orchestrator import run_committee as _run_committee


def run_committee(ticker: str, progress_cb=None, *, core_snapshot=None):
    """Run Committee using the newest persisted CORE snapshot when available."""
    snapshot_source = None
    if core_snapshot is None:
        core_snapshot, snapshot_source = find_latest_core_snapshot(ticker)
    result = _run_committee(ticker, progress_cb, core_snapshot=core_snapshot)
    result["core_snapshot_source"] = snapshot_source or ("explicit" if core_snapshot is not None else None)
    return result


__all__ = ["run_committee"]
