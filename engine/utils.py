"""Utility comuni estratte dalla baseline USA v5.5 / Italy v1.2.

Phase A parity-first: queste funzioni sono copie fedeli delle utility pure presenti
nei monoliti congelati. Non modificano strategia, scoring o decisioni.
"""
from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from typing import Any, Optional

import pandas as pd


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def safe_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except Exception:
        pass
    try:
        v = float(value)
        if math.isfinite(v):
            return v
    except Exception:
        pass
    return default


def safe_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    v = safe_float(value)
    if v is None:
        return default
    try:
        return int(v)
    except Exception:
        return default


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def first_not_none(*values: Any) -> Any:
    for v in values:
        if v is not None:
            return v
    return None


def fmt_price(v: Optional[float]) -> str:
    return "N/D" if v is None else f"${v:,.2f}"


def fmt_pct(v: Optional[float]) -> str:
    return "N/D" if v is None else f"{v:+.1f}%"


def fmt_num(v: Optional[float], digits: int = 2) -> str:
    if v is None:
        return "N/D"
    return f"{v:,.{digits}f}"


def html_escape(value: Any) -> str:
    s = "" if value is None else str(value)
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def extract_unknown_field(err: Exception) -> Optional[str]:
    s = str(err)
    patterns = [
        r'Unknown field\s+\\?"([^\"]+)\\?"',
        r"unknown field[:\s]+[\"']?([^\"'\s,}]+)",
    ]
    for p in patterns:
        m = re.search(p, s, flags=re.I)
        if m:
            return m.group(1)
    return None


def normalize_percent(v: Optional[float]) -> Optional[float]:
    """Converte 0.23 -> 23 se sembra percentuale in forma frazionaria."""
    if v is None:
        return None
    if -2.0 <= v <= 2.0:
        return v * 100.0
    return v


def normalize_debt_to_equity(v: Optional[float]) -> Optional[float]:
    """Yahoo spesso restituisce D/E come percentuale (es. 35 = 0.35)."""
    if v is None:
        return None
    if abs(v) > 5:
        return v / 100.0
    return v
