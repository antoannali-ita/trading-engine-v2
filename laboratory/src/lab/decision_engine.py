from __future__ import annotations

import math
from datetime import date
from typing import Any

import pandas as pd

from lab.settings import (
    CAPITAL_TOTAL_BASE,
    EARNINGS_BLOCK_DAYS,
    EARNINGS_CAUTION_DAYS,
    ESTIMATED_SLIPPAGE_BPS,
    MAX_ACTIVE_PAPER_POSITIONS,
    MAX_POSITION_USD,
    MIN_NET_RR,
    RISK_PER_TRADE_PCT,
    USA_COMMISSION_USD,
)


def _num(value: Any) -> float | None:
    try:
        if value is None or pd.isna(value):
            return None
        return float(value)
    except Exception:
        return None


def earnings_distance_days(earnings_date: Any, as_of: date) -> int | None:
    if earnings_date in (None, "", "N/D"):
        return None
    try:
        d = pd.Timestamp(earnings_date).date()
        return (d - as_of).days
    except Exception:
        return None


def data_quality_check(
    *,
    price: float | None,
    entry: float | None,
    max_buy: float | None,
    stop: float | None,
    tp1: float | None,
    tp2: float | None,
    atr: float | None,
    sma50: float | None,
    sma200: float | None,
) -> dict[str, Any]:
    red: list[str] = []
    yellow: list[str] = []

    if price is None or price <= 0:
        red.append("PRICE_INVALID")
    if entry is None or entry <= 0:
        red.append("ENTRY_INVALID")
    if stop is None or (entry is not None and stop >= entry):
        red.append("STOP_INVALID")
    if tp1 is None or tp2 is None:
        yellow.append("TARGET_MISSING")
    elif tp1 > tp2:
        red.append("TARGET_ORDER_INVALID")
    if max_buy is not None and entry is not None and entry > max_buy:
        red.append("ENTRY_ABOVE_MAX_BUY")
    if atr is None or atr <= 0:
        red.append("ATR_INVALID")
    if sma50 is None or sma200 is None:
        yellow.append("STRUCTURAL_SMA_MISSING")

    status = "RED" if red else "YELLOW" if yellow else "GREEN"
    return {"status": status, "red": red, "yellow": yellow, "blocked": bool(red)}


def risk_based_qty(
    *,
    entry: float,
    stop: float,
    capital_base: float = CAPITAL_TOTAL_BASE,
    max_position: float = MAX_POSITION_USD,
    risk_pct: float = RISK_PER_TRADE_PCT,
    commission: float = USA_COMMISSION_USD,
) -> int:
    risk_per_share = max(entry - stop, 0.0)
    if entry <= 0 or risk_per_share <= 0:
        return 0
    risk_budget = capital_base * (risk_pct / 100.0)
    round_trip_commission = 2.0 * commission
    qty_by_risk = math.floor(max(risk_budget - round_trip_commission, 0.0) / risk_per_share)
    qty_by_cap = math.floor(max(max_position - commission, 0.0) / entry)
    return max(0, min(qty_by_risk, qty_by_cap))


def net_rr(
    *,
    entry: float,
    stop: float,
    target: float,
    qty: int,
    commission: float = USA_COMMISSION_USD,
    slippage_bps: float = ESTIMATED_SLIPPAGE_BPS,
) -> float | None:
    if qty <= 0 or entry <= stop or target <= entry:
        return None
    slip = slippage_bps / 10_000.0
    entry_exec = entry * (1.0 + slip)
    stop_exec = stop * (1.0 - slip)
    target_exec = target * (1.0 - slip)
    loss = (entry_exec - stop_exec) * qty + 2.0 * commission
    gain = (target_exec - entry_exec) * qty - 2.0 * commission
    if loss <= 0:
        return None
    return gain / loss


def trade_score(
    *,
    strategy_score: float,
    price: float,
    entry: float,
    max_buy: float,
    atr: float,
    rr_net: float | None,
    trigger: str,
    earnings_days: int | None,
) -> float:
    # Fixed ex-ante weights. They are intentionally not optimized from historical outcomes.
    rr_component = 0.0 if rr_net is None else min(100.0, max(0.0, 40.0 * rr_net))
    distance_atr = abs(price - entry) / atr if atr > 0 else 99.0
    if distance_atr <= 0.25:
        entry_component = 100.0
    elif distance_atr <= 0.50:
        entry_component = 90.0
    elif distance_atr <= 1.00:
        entry_component = 75.0
    elif distance_atr <= 1.50:
        entry_component = 50.0
    else:
        entry_component = 20.0

    trigger_component = 100.0 if str(trigger).upper() == "CONFIRMED" else 35.0
    extension_component = 100.0 if price <= max_buy else 0.0
    if earnings_days is None:
        earnings_component = 60.0
    elif earnings_days < EARNINGS_BLOCK_DAYS:
        earnings_component = 0.0
    elif earnings_days <= EARNINGS_CAUTION_DAYS:
        earnings_component = 50.0
    else:
        earnings_component = 100.0

    score = (
        0.15 * float(strategy_score)
        + 0.35 * rr_component
        + 0.20 * entry_component
        + 0.15 * trigger_component
        + 0.10 * extension_component
        + 0.05 * earnings_component
    )
    return round(max(0.0, min(100.0, score)), 2)


def trade_eligibility(
    *,
    data_quality: dict[str, Any],
    trigger: str,
    price: float,
    max_buy: float,
    rr_net: float | None,
    earnings_days: int | None,
    event_driven: bool = False,
) -> dict[str, Any]:
    failed: list[str] = []
    warnings: list[str] = []

    if data_quality.get("status") == "RED":
        failed.append("DATA_QUALITY_RED")
    if str(trigger).upper() != "CONFIRMED":
        failed.append("TRIGGER_NOT_CONFIRMED")
    if price > max_buy:
        failed.append("PRICE_ABOVE_MAX_BUY")
    if rr_net is None or rr_net < MIN_NET_RR:
        failed.append("RR_NET_BELOW_MIN")

    if earnings_days is not None:
        if earnings_days < EARNINGS_BLOCK_DAYS and not event_driven:
            failed.append("EARNINGS_LT_7D")
        elif earnings_days <= EARNINGS_CAUTION_DAYS:
            warnings.append("EARNINGS_7_14D")
    else:
        warnings.append("EARNINGS_DATE_ND")

    return {
        "eligible": not failed,
        "failed": failed,
        "warnings": warnings,
        "earnings_bypass": bool(event_driven and earnings_days is not None and earnings_days < EARNINGS_BLOCK_DAYS),
    }


def portfolio_fit_v1(*, symbol: str, open_positions: list[dict[str, Any]], opened_this_run: int, max_new_buys: int = 2) -> dict[str, Any]:
    failed: list[str] = []
    same_symbol = [p for p in open_positions if str(p.get("symbol", "")).upper() == symbol.upper() and str(p.get("status", "")).upper() in {"OPEN", "TP1_HIT"}]
    active_count = sum(1 for p in open_positions if str(p.get("status", "")).upper() in {"OPEN", "TP1_HIT"})

    if same_symbol:
        failed.append("DUPLICATE_TICKER")
    if active_count >= MAX_ACTIVE_PAPER_POSITIONS:
        failed.append("MAX_ACTIVE_PAPER_POSITIONS")
    if opened_this_run >= max_new_buys:
        failed.append("MAX_NEW_BUYS_THIS_RUN")

    score = 100.0
    if active_count >= max(1, MAX_ACTIVE_PAPER_POSITIONS - 2):
        score -= 20.0
    if failed:
        score = 0.0

    return {
        "score": round(score, 2),
        "eligible": not failed,
        "failed": failed,
        "model": "V1_DETERMINISTIC_NO_CORRELATION",
    }


def regime_v1(spy_enriched: pd.DataFrame) -> dict[str, Any]:
    if spy_enriched is None or spy_enriched.empty or len(spy_enriched) < 220:
        return {"state": "UNKNOWN", "trend": "N/D", "volatility": "N/D"}

    x = spy_enriched.copy()
    last = x.iloc[-1]
    price = _num(last.get("Close"))
    sma50 = _num(last.get("sma50"))
    sma200 = _num(last.get("sma200"))
    vol20 = _num(last.get("vol20"))
    if price is None or sma50 is None or sma200 is None or vol20 is None:
        return {"state": "UNKNOWN", "trend": "N/D", "volatility": "N/D"}

    sma50_prev = _num(x["sma50"].iloc[-21]) if len(x) >= 21 else None
    slope_up = sma50_prev is not None and sma50 > sma50_prev
    vol_hist = pd.to_numeric(x["vol20"].tail(252), errors="coerce").dropna()
    vol_pct = float((vol_hist <= vol20).mean() * 100.0) if not vol_hist.empty else None
    high_vol = vol_pct is not None and vol_pct > 75.0

    bull = price > sma200 and slope_up
    bear = price < sma200 and not slope_up
    if bull and not high_vol:
        state = "BULL_QUIET"
    elif bull and high_vol:
        state = "BULL_VOLATILE"
    elif bear and high_vol:
        state = "BEAR_HIGH_VOL"
    else:
        state = "RANGE_NEUTRAL"

    return {
        "state": state,
        "trend": "BULL" if bull else "BEAR" if bear else "MIXED",
        "volatility": "HIGH" if high_vol else "NORMAL",
        "vol20": vol20,
        "vol_percentile_252": vol_pct,
        "spy_price": price,
        "spy_sma50": sma50,
        "spy_sma200": sma200,
    }
