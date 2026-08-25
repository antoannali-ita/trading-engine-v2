from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

COMMISSION_USD = 9.90
SLIPPAGE_BPS = 5.0


def as_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _iso_date(value: Any) -> str | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt.date().isoformat()
    except Exception:
        text = str(value)
        return text[:10] if len(text) >= 10 else None


def date_label(value: Any) -> str:
    iso = _iso_date(value)
    if not iso:
        return "N/D"
    try:
        return datetime.fromisoformat(iso).strftime("%d/%m/%Y")
    except Exception:
        return iso


def trading_days_elapsed(opened_at: Any, ended_at: Any, market_sessions: Iterable[str]) -> int | None:
    """Count completed market sessions after the opening date up to the end date.

    Opening session is day 0. Example: Friday open -> Monday end = 1, assuming
    both dates are actual sessions. The caller supplies authoritative market dates.
    """
    opened = _iso_date(opened_at)
    ended = _iso_date(ended_at)
    if not opened or not ended:
        return None
    if ended < opened:
        return None
    sessions = {str(day)[:10] for day in market_sessions if day}
    if not sessions:
        return None
    return sum(1 for day in sessions if opened < day <= ended)


def gross_price_pnl(entry: Any, current: Any, qty: Any) -> float | None:
    e, c, q = as_float(entry), as_float(current), as_float(qty)
    if e is None or c is None or q is None:
        return None
    return (c - e) * q


def gross_price_return_pct(entry: Any, current: Any) -> float | None:
    e, c = as_float(entry), as_float(current)
    if e in (None, 0) or c is None:
        return None
    return ((c / e) - 1.0) * 100.0


def estimated_entry_cost(entry: Any, qty: Any, commission: float = COMMISSION_USD, slippage_bps: float = SLIPPAGE_BPS) -> float | None:
    e, q = as_float(entry), as_float(qty)
    if e is None or q is None:
        return None
    slip = slippage_bps / 10000.0
    return commission + (e * q * slip)


def estimated_round_trip_cost(entry: Any, current: Any, qty: Any, commission: float = COMMISSION_USD, slippage_bps: float = SLIPPAGE_BPS) -> float | None:
    e, c, q = as_float(entry), as_float(current), as_float(qty)
    if e is None or c is None or q is None:
        return None
    slip = slippage_bps / 10000.0
    return 2.0 * commission + ((e + c) * q * slip)


def open_net_pnl(entry: Any, current: Any, qty: Any, commission: float = COMMISSION_USD, slippage_bps: float = SLIPPAGE_BPS) -> float | None:
    """Open mark-to-market P&L: price move less costs already incurred at entry only."""
    gross = gross_price_pnl(entry, current, qty)
    cost = estimated_entry_cost(entry, qty, commission, slippage_bps)
    if gross is None or cost is None:
        return None
    return gross - cost


def closed_net_pnl(entry: Any, exit_price: Any, qty: Any, commission: float = COMMISSION_USD, slippage_bps: float = SLIPPAGE_BPS) -> float | None:
    e, x, q = as_float(entry), as_float(exit_price), as_float(qty)
    if e is None or x is None or q is None:
        return None
    slip = slippage_bps / 10000.0
    return (x * (1.0 - slip) - e * (1.0 + slip)) * q - 2.0 * commission


def cost_band_pct(entry: Any, current: Any, qty: Any, commission: float = COMMISSION_USD, slippage_bps: float = SLIPPAGE_BPS) -> float | None:
    e, q = as_float(entry), as_float(qty)
    cost = estimated_round_trip_cost(entry, current, qty, commission, slippage_bps)
    if e in (None, 0) or q in (None, 0) or cost is None:
        return None
    return cost / (e * q) * 100.0


def age_days(opened_at: Any, now: datetime | None = None) -> float | None:
    if not opened_at:
        return None
    try:
        opened = datetime.fromisoformat(str(opened_at).replace("Z", "+00:00"))
        if opened.tzinfo is None:
            opened = opened.replace(tzinfo=timezone.utc)
        current = now or datetime.now(timezone.utc)
        return max(0.0, (current - opened).total_seconds() / 86400.0)
    except Exception:
        return None


def open_trade_state(
    entry: Any,
    current: Any,
    qty: Any,
    opened_at: Any = None,
    early_days: float = 2.0,
    trading_days_open: int | None = None,
) -> str:
    move = gross_price_return_pct(entry, current)
    band = cost_band_pct(entry, current, qty)
    calendar_age = age_days(opened_at)
    early = trading_days_open <= 2 if trading_days_open is not None else (calendar_age is None or calendar_age <= early_days)
    if move is None:
        return "⚪ OPEN · N/D"
    if band is not None and abs(move) <= band and early:
        return "⚪ OPEN · TOO EARLY"
    if move > 0:
        return "🟢 OPEN · POSITIVE"
    if move < 0:
        return "🔴 OPEN · NEGATIVE"
    return "⚪ OPEN · FLAT"
