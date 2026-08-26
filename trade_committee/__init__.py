"""LAB-RESEARCH-001 · Trade Committee.

Modulo manuale e indipendente di due diligence pre-trade.
Non modifica segnali, score o ordini Production.
"""

from .orchestrator import run_committee

__all__ = ["run_committee"]
