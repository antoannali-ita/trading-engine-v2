from __future__ import annotations

# Single source of truth for Laboratory paper-cost scenarios.
# Current Fineco USA cost applies now; discount scenario is planned for next month.
CURRENT_COMMISSION_PER_SIDE = 12.0
DISCOUNT_COMMISSION_PER_SIDE = 9.90
SLIPPAGE_BPS = 5.0


def entry_cost(entry: float | None, qty: float | None, commission: float = CURRENT_COMMISSION_PER_SIDE, slippage_bps: float = SLIPPAGE_BPS) -> float | None:
    if entry is None or qty is None:
        return None
    slip = slippage_bps / 10000.0
    return commission + entry * qty * slip


def estimated_exit_cost(price: float | None, qty: float | None, commission: float = CURRENT_COMMISSION_PER_SIDE, slippage_bps: float = SLIPPAGE_BPS) -> float | None:
    if price is None or qty is None:
        return None
    slip = slippage_bps / 10000.0
    return commission + price * qty * slip


def open_price_pnl(entry: float | None, current: float | None, qty: float | None) -> float | None:
    if entry is None or current is None or qty is None:
        return None
    return (current - entry) * qty


def open_net_pnl(entry: float | None, current: float | None, qty: float | None, commission: float = CURRENT_COMMISSION_PER_SIDE, slippage_bps: float = SLIPPAGE_BPS) -> float | None:
    price_pnl = open_price_pnl(entry, current, qty)
    cost = entry_cost(entry, qty, commission, slippage_bps)
    if price_pnl is None or cost is None:
        return None
    return price_pnl - cost


def projected_round_trip_pnl(entry: float | None, current: float | None, qty: float | None, commission: float = CURRENT_COMMISSION_PER_SIDE, slippage_bps: float = SLIPPAGE_BPS) -> float | None:
    value = open_net_pnl(entry, current, qty, commission, slippage_bps)
    exit_cost = estimated_exit_cost(current, qty, commission, slippage_bps)
    if value is None or exit_cost is None:
        return None
    return value - exit_cost


def closed_net_pnl(entry: float | None, exit_price: float | None, qty: float | None, commission: float = CURRENT_COMMISSION_PER_SIDE, slippage_bps: float = SLIPPAGE_BPS) -> float | None:
    if entry is None or exit_price is None or qty is None:
        return None
    slip = slippage_bps / 10000.0
    entry_exec = entry * (1 + slip)
    exit_exec = exit_price * (1 - slip)
    return (exit_exec - entry_exec) * qty - 2 * commission
