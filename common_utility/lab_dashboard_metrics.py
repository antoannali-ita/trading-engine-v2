from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

COMMISSION_USD = 9.90
SLIPPAGE_BPS = 5.0


def as_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


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


def open_trade_state(entry: Any, current: Any, qty: Any, opened_at: Any = None, early_days: float = 2.0) -> str:
    move = gross_price_return_pct(entry, current)
    band = cost_band_pct(entry, current, qty)
    age = age_days(opened_at)
    if move is None:
        return "⚪ OPEN · N/D"
    if band is not None and abs(move) <= band and (age is None or age <= early_days):
        return "⚪ OPEN · TOO EARLY"
    if move > 0:
        return "🟢 OPEN · POSITIVE"
    if move < 0:
        return "🔴 OPEN · NEGATIVE"
    return "⚪ OPEN · FLAT"
