"""Report email parity-safe.

Phase A non riscrive il rendering HTML: espone le funzioni della baseline congelata
per evitare differenze di presentazione che possano nascondere regressioni operative.
In Phase B queste funzioni potranno essere estratte una alla volta, con parity test.
"""
from __future__ import annotations

from typing import Any, Dict

REPORT_FUNCTIONS = (
    "generate_html",
    "build_action_board",
    "action_needed_text",
    "tv_chart_url",
)


def bind(reference: Any) -> Dict[str, Any]:
    """Restituisce le funzioni report effettive della baseline selezionata."""
    missing = [name for name in REPORT_FUNCTIONS if not hasattr(reference, name)]
    if missing:
        raise AttributeError(
            "Baseline priva delle funzioni report richieste: " + ", ".join(missing)
        )
    return {name: getattr(reference, name) for name in REPORT_FUNCTIONS}
