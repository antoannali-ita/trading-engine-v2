"""LAB-RESEARCH-001 · Trade Committee.

Modulo manuale e indipendente di due diligence pre-trade.
Il CORE resta la single source of truth per la trade; i dati tecnici locali sono
cross-check normalizzati e non sostituiscono segnali, score o ordini Production.
"""

from . import research_checks as _research_checks
from .technical_normalization import normalize_market_bundle


_raw_fetch_market_bundle = _research_checks.fetch_market_bundle


def _normalized_fetch_market_bundle(symbol: str):
    return normalize_market_bundle(_raw_fetch_market_bundle(symbol))


# Adapter transitorio: mantiene research_checks compatibile, ma standardizza RSI Wilder
# e impedisce che un RVOL daily parziale venga penalizzato come full-session.
_research_checks.fetch_market_bundle = _normalized_fetch_market_bundle

from .orchestrator import run_committee

__all__ = ["run_committee"]
