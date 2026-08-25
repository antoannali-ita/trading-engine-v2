from __future__ import annotations

from typing import Any


def as_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def usd_to_eur(value_usd: Any, usd_eur_rate: Any) -> float | None:
    value = as_float(value_usd)
    rate = as_float(usd_eur_rate)
    if value is None or rate is None or rate <= 0:
        return None
    return value * rate


def distance_pct(reference: Any, current: Any) -> float | None:
    ref = as_float(reference)
    cur = as_float(current)
    if ref is None or cur in (None, 0):
        return None
    return ((ref / cur) - 1.0) * 100.0


def distance_to_stop_pct(current: Any, stop: Any) -> float | None:
    cur = as_float(current)
    stop_value = as_float(stop)
    if cur in (None, 0) or stop_value is None:
        return None
    return ((cur - stop_value) / cur) * 100.0


def pnl_pct(total_value: Any, total_cost: Any) -> float | None:
    value = as_float(total_value)
    cost = as_float(total_cost)
    if value is None or cost in (None, 0):
        return None
    return ((value / cost) - 1.0) * 100.0


def weight_pct(position_value: Any, portfolio_value: Any) -> float | None:
    value = as_float(position_value)
    total = as_float(portfolio_value)
    if value is None or total in (None, 0):
        return None
    return value / total * 100.0


def risk_to_stop_usd(quantity: Any, current_price: Any, stop_price: Any) -> float | None:
    qty = as_float(quantity)
    current = as_float(current_price)
    stop = as_float(stop_price)
    if qty is None or current is None or stop is None:
        return None
    return max(0.0, qty * (current - stop))


def invested_pct(total_value: Any, capital_total: Any) -> float | None:
    value = as_float(total_value)
    capital = as_float(capital_total)
    if value is None or capital in (None, 0):
        return None
    return value / capital * 100.0
