from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np
import pandas as pd

from .indicators import enrich_prices
from .strategies import STRATEGIES, generate_scores


@dataclass(frozen=True)
class BacktestConfig:
    entry_score: float = 75.0
    initial_capital: float = 100_000.0
    risk_per_trade_pct: float = 0.005
    max_position_pct: float = 0.08
    commission_per_side: float = 12.0
    slippage_bps: float = 5.0
    atr_stop_mult: float = 2.0
    target_r_multiple: float = 2.5


def _apply_slippage(price: float, side: str, bps: float) -> float:
    m = bps / 10_000.0
    return price * (1 + m if side == "BUY" else 1 - m)


def run_backtest(symbol: str, prices: pd.DataFrame, strategy_name: str, config: BacktestConfig | None = None) -> tuple[pd.DataFrame, dict]:
    cfg = config or BacktestConfig()
    if strategy_name not in STRATEGIES:
        raise KeyError(strategy_name)

    spec = STRATEGIES[strategy_name]
    x = enrich_prices(prices)
    scores = generate_scores(strategy_name, prices).reindex(x.index).fillna(0.0)
    cash = cfg.initial_capital
    equity = cfg.initial_capital
    trades: list[dict] = []

    i = 0
    while i < len(x) - 1:
        row = x.iloc[i]
        if scores.iloc[i] < cfg.entry_score or pd.isna(row.get("atr14")):
            i += 1
            continue

        entry_i = i + 1
        entry_row = x.iloc[entry_i]
        entry = _apply_slippage(float(entry_row.Open), "BUY", cfg.slippage_bps)
        atr = float(row.atr14)
        stop = entry - cfg.atr_stop_mult * atr
        risk_per_share = max(entry - stop, 0.01)
        risk_budget = equity * cfg.risk_per_trade_pct
        qty_risk = math.floor(max(risk_budget - 2 * cfg.commission_per_side, 0) / risk_per_share)
        qty_cap = math.floor((equity * cfg.max_position_pct) / entry)
        qty = max(0, min(qty_risk, qty_cap))
        if qty <= 0:
            i += 1
            continue

        target = entry + cfg.target_r_multiple * risk_per_share
        max_exit_i = min(entry_i + spec.holding_days, len(x) - 1)
        exit_i = max_exit_i
        exit_reason = "TIME"
        exit_price = float(x.iloc[exit_i].Close)

        for j in range(entry_i, max_exit_i + 1):
            bar = x.iloc[j]
            hit_stop = float(bar.Low) <= stop
            hit_target = float(bar.High) >= target
            if hit_stop and hit_target:
                exit_i, exit_reason, exit_price = j, "STOP_FIRST_CONSERVATIVE", stop
                break
            if hit_stop:
                exit_i, exit_reason, exit_price = j, "STOP", stop
                break
            if hit_target:
                exit_i, exit_reason, exit_price = j, "TARGET", target
                break

        exit_price = _apply_slippage(float(exit_price), "SELL", cfg.slippage_bps)
        gross = (exit_price - entry) * qty
        net = gross - 2 * cfg.commission_per_side
        equity += net
        cash = equity
        trades.append({
            "symbol": symbol,
            "strategy": strategy_name,
            "signal_date": x.index[i],
            "entry_date": x.index[entry_i],
            "exit_date": x.index[exit_i],
            "score": float(scores.iloc[i]),
            "entry": entry,
            "stop": stop,
            "target": target,
            "exit": exit_price,
            "qty": qty,
            "gross_pnl": gross,
            "net_pnl": net,
            "return_pct": net / max(entry * qty, 1) * 100,
            "exit_reason": exit_reason,
            "holding_days": int(exit_i - entry_i),
        })
        i = exit_i + 1

    frame = pd.DataFrame(trades)
    metrics = summarize_backtest(frame, cfg.initial_capital, equity)
    metrics.update({"symbol": symbol, "strategy": strategy_name, "final_equity": equity, "cash": cash})
    return frame, metrics


def _max_drawdown_pct(trades: pd.DataFrame, initial_capital: float) -> float:
    if trades.empty:
        return 0.0
    equity_curve = initial_capital + trades["net_pnl"].cumsum()
    peaks = equity_curve.cummax()
    drawdowns = (equity_curve / peaks - 1.0) * 100.0
    return float(drawdowns.min()) if not drawdowns.empty else 0.0


def summarize_backtest(trades: pd.DataFrame, initial_capital: float, final_equity: float) -> dict:
    if trades.empty:
        return {
            "trades": 0,
            "win_rate": 0.0,
            "avg_return_pct": 0.0,
            "profit_factor": 0.0,
            "net_pnl": 0.0,
            "return_pct": 0.0,
            "max_drawdown_pct": 0.0,
        }
    wins = trades.loc[trades.net_pnl > 0, "net_pnl"].sum()
    losses = -trades.loc[trades.net_pnl < 0, "net_pnl"].sum()
    return {
        "trades": int(len(trades)),
        "win_rate": float((trades.net_pnl > 0).mean() * 100),
        "avg_return_pct": float(trades.return_pct.mean()),
        "profit_factor": float(wins / losses) if losses > 0 else float("inf") if wins > 0 else 0.0,
        "net_pnl": float(final_equity - initial_capital),
        "return_pct": float((final_equity / initial_capital - 1) * 100),
        "max_drawdown_pct": _max_drawdown_pct(trades, initial_capital),
    }
