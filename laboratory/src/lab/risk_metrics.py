from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Any

RISK_NORMALIZATION_VERSION = "RISK_NORMALIZATION_V1"
RISK_FLOOR_ATR_MULTIPLE = 0.20


@dataclass(frozen=True)
class RiskBasis:
    side: str
    fill_price: float
    stop_initial: float
    atr14: float | None
    raw_initial_risk: float
    normalized_initial_risk: float
    risk_floor_applied: bool
    policy_version: str = RISK_NORMALIZATION_VERSION


def _side(side: str) -> str:
    value = str(side or "LONG").upper()
    if value not in {"LONG", "SHORT"}:
        raise ValueError(f"unsupported side: {side}")
    return value


def build_risk_basis(*, side: str, fill_price: float, stop_initial: float, atr14: float | None = None) -> RiskBasis:
    side = _side(side)
    fill = float(fill_price)
    stop = float(stop_initial)
    raw = (fill - stop) if side == "LONG" else (stop - fill)
    if raw <= 0:
        raise ValueError("stop_initial must define positive initial risk for trade side")
    floor = 0.0
    if atr14 is not None and float(atr14) > 0:
        floor = RISK_FLOOR_ATR_MULTIPLE * float(atr14)
    normalized = max(raw, floor)
    return RiskBasis(
        side=side,
        fill_price=fill,
        stop_initial=stop,
        atr14=float(atr14) if atr14 is not None else None,
        raw_initial_risk=raw,
        normalized_initial_risk=normalized,
        risk_floor_applied=normalized > raw,
    )


def price_r(*, side: str, fill_price: float, price: float, risk_denominator: float) -> float:
    side = _side(side)
    denom = float(risk_denominator)
    if denom <= 0:
        raise ValueError("risk_denominator must be > 0")
    move = float(price) - float(fill_price)
    return move / denom if side == "LONG" else -move / denom


def mtm_r(*, basis: RiskBasis, current_price: float) -> float:
    return price_r(
        side=basis.side,
        fill_price=basis.fill_price,
        price=float(current_price),
        risk_denominator=basis.normalized_initial_risk,
    )


def open_risk_and_locked_profit_r(*, basis: RiskBasis, stop_current: float | None) -> tuple[float, float]:
    if stop_current is None:
        return 1.0, 0.0
    stop_r = price_r(
        side=basis.side,
        fill_price=basis.fill_price,
        price=float(stop_current),
        risk_denominator=basis.normalized_initial_risk,
    )
    # stop_r < 0 means capital can still be lost; stop_r > 0 means profit is locked.
    return max(-stop_r, 0.0), max(stop_r, 0.0)


def realized_r_from_fills(
    *,
    basis: RiskBasis,
    initial_qty: int,
    exit_fills: Iterable[Mapping[str, Any]],
    entry_cost: float = 0.0,
) -> float | None:
    qty0 = int(initial_qty)
    if qty0 <= 0:
        raise ValueError("initial_qty must be > 0")
    total = 0.0
    exited = 0
    for fill in exit_fills:
        qty = int(fill.get("qty") or 0)
        if qty <= 0:
            continue
        price = float(fill["price"])
        commission = float(fill.get("commission") or 0.0)
        leg_r = price_r(
            side=basis.side,
            fill_price=basis.fill_price,
            price=price,
            risk_denominator=basis.normalized_initial_risk,
        )
        commission_r = commission / (basis.normalized_initial_risk * qty)
        total += (qty / qty0) * (leg_r - commission_r)
        exited += qty
    if exited == 0:
        return None
    # Entry cost applies once to the original size.
    total -= float(entry_cost) / (basis.normalized_initial_risk * qty0)
    return total


def expectancy_r(values: Iterable[float]) -> float | None:
    xs = [float(x) for x in values]
    if not xs:
        return None
    return sum(xs) / len(xs)


def profit_factor(values: Iterable[float]) -> float | None:
    xs = [float(x) for x in values]
    gains = sum(x for x in xs if x > 0)
    losses = -sum(x for x in xs if x < 0)
    if losses <= 0:
        return None if gains <= 0 else float("inf")
    return gains / losses


def max_drawdown_r(values: Iterable[float]) -> float | None:
    xs = [float(x) for x in values]
    if not xs:
        return None
    equity = 0.0
    peak = 0.0
    worst = 0.0
    for value in xs:
        equity += value
        peak = max(peak, equity)
        worst = min(worst, equity - peak)
    return worst
