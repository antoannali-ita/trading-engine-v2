from __future__ import annotations

from itertools import product
from typing import Any

import pandas as pd

from .backtest_engine import BacktestConfig, run_backtest


ENTRY_SCORES = (70.0, 75.0, 80.0)
STOP_MULTS = (1.5, 2.0, 2.5)
TARGET_MULTS = (2.0, 2.5, 3.0)


def split_walk_forward(prices: pd.DataFrame, split: float = 0.70) -> tuple[pd.DataFrame, pd.DataFrame, pd.Timestamp]:
    cut = max(250, int(len(prices) * split))
    if cut >= len(prices) - 50:
        raise ValueError("Not enough observations for guarded evolution split")
    train = prices.iloc[:cut].copy()
    test = prices.iloc[max(0, cut - 220):].copy()
    return train, test, pd.Timestamp(prices.index[cut])


def _finite_pf(value: Any) -> float:
    try:
        x = float(value)
    except (TypeError, ValueError):
        return 0.0
    if x == float("inf"):
        return 10.0
    return max(0.0, min(x, 10.0))


def _oos_metrics(symbol: str, prices: pd.DataFrame, strategy: str, cfg: BacktestConfig, test_start: pd.Timestamp) -> tuple[pd.DataFrame, dict]:
    trades, metrics = run_backtest(symbol, prices, strategy, cfg)
    if trades.empty:
        return trades, metrics
    trades = trades[pd.to_datetime(trades.entry_date) >= test_start].copy()
    if trades.empty:
        empty_metrics = dict(metrics)
        empty_metrics.update({"trades": 0, "return_pct": 0.0, "profit_factor": 0.0, "max_drawdown_pct": 0.0})
        return trades, empty_metrics

    pnl = trades.net_pnl.cumsum()
    equity = cfg.initial_capital + pnl
    peaks = equity.cummax()
    dd = (equity / peaks - 1.0) * 100.0
    wins = trades.loc[trades.net_pnl > 0, "net_pnl"].sum()
    losses = -trades.loc[trades.net_pnl < 0, "net_pnl"].sum()
    metrics = {
        "trades": int(len(trades)),
        "return_pct": float(trades.net_pnl.sum() / cfg.initial_capital * 100.0),
        "profit_factor": float(wins / losses) if losses > 0 else float("inf") if wins > 0 else 0.0,
        "max_drawdown_pct": float(dd.min()) if not dd.empty else 0.0,
    }
    return trades, metrics


def critique_parent(oos: dict) -> list[str]:
    """Explain why the parent deserves challengers. No optimization claim is made here."""
    reasons: list[str] = []
    n = int(oos.get("trades", 0))
    ret = float(oos.get("return_pct", 0.0))
    pf = _finite_pf(oos.get("profit_factor", 0.0))
    dd = abs(float(oos.get("max_drawdown_pct", 0.0)))
    if n < 5:
        reasons.append("OOS_SAMPLE_TOO_SMALL")
    if ret <= 0:
        reasons.append("OOS_RETURN_NON_POSITIVE")
    if pf < 1.15:
        reasons.append("OOS_PROFIT_FACTOR_WEAK")
    if dd > 5.0:
        reasons.append("OOS_DRAWDOWN_HIGH")
    if not reasons:
        reasons.append("PARENT_HEALTHY_CHALLENGER_TEST")
    return reasons


def robustness_score(train: dict, oos: dict) -> float:
    """Conservative 0-100 score. OOS dominates; drawdown and sample size matter."""
    oos_ret = float(oos.get("return_pct", 0.0))
    oos_pf = _finite_pf(oos.get("profit_factor", 0.0))
    oos_n = int(oos.get("trades", 0))
    oos_dd = abs(float(oos.get("max_drawdown_pct", 0.0)))
    train_ret = float(train.get("return_pct", 0.0))

    score = 50.0
    score += max(-20.0, min(20.0, oos_ret * 2.0))
    score += max(-15.0, min(15.0, (oos_pf - 1.0) * 15.0))
    score += max(-10.0, min(10.0, (oos_n - 5) * 1.0))
    score -= min(15.0, oos_dd * 2.0)
    if train_ret > 0 and oos_ret <= 0:
        score -= 15.0
    if train_ret != 0 and oos_ret != 0 and (train_ret > 0) != (oos_ret > 0):
        score -= 10.0
    return float(max(0.0, min(100.0, score)))


def verdict(parent_oos: dict, child_oos: dict, child_score: float) -> str:
    child_n = int(child_oos.get("trades", 0))
    child_ret = float(child_oos.get("return_pct", 0.0))
    child_pf = _finite_pf(child_oos.get("profit_factor", 0.0))
    child_dd = abs(float(child_oos.get("max_drawdown_pct", 0.0)))
    parent_ret = float(parent_oos.get("return_pct", 0.0))
    parent_pf = _finite_pf(parent_oos.get("profit_factor", 0.0))
    parent_dd = abs(float(parent_oos.get("max_drawdown_pct", 0.0)))

    if child_n < 5 or child_ret <= 0 or child_pf < 1.05:
        return "REJECTED"
    beats_return = child_ret > parent_ret
    beats_pf = child_pf >= parent_pf
    drawdown_ok = child_dd <= max(parent_dd * 1.15, parent_dd + 0.5)
    if child_score >= 70 and beats_return and beats_pf and drawdown_ok:
        return "PROMOTABLE"
    if child_score >= 60 and (beats_return or beats_pf) and drawdown_ok:
        return "CANDIDATE"
    return "REJECTED"


def evaluate_family(symbol: str, prices: pd.DataFrame, strategy: str) -> list[dict[str, Any]]:
    """Create parameter children around a fixed strategy signal generator.

    Generation 1 evolves execution/risk parameters only. Strategy-code mutation is intentionally excluded.
    """
    train, test, test_start = split_walk_forward(prices)
    parent_cfg = BacktestConfig()
    _, parent_train = run_backtest(symbol, train, strategy, parent_cfg)
    _, parent_oos = _oos_metrics(symbol, test, strategy, parent_cfg, test_start)
    critique = critique_parent(parent_oos)

    rows: list[dict[str, Any]] = []
    for entry_score, stop_mult, target_mult in product(ENTRY_SCORES, STOP_MULTS, TARGET_MULTS):
        cfg = BacktestConfig(entry_score=entry_score, atr_stop_mult=stop_mult, target_r_multiple=target_mult)
        _, train_metrics = run_backtest(symbol, train, strategy, cfg)
        _, oos_metrics = _oos_metrics(symbol, test, strategy, cfg, test_start)
        score = robustness_score(train_metrics, oos_metrics)
        state = verdict(parent_oos, oos_metrics, score)
        rows.append({
            "symbol": symbol,
            "strategy": strategy,
            "parameters": {
                "entry_score": entry_score,
                "atr_stop_mult": stop_mult,
                "target_r_multiple": target_mult,
            },
            "parent_parameters": {
                "entry_score": parent_cfg.entry_score,
                "atr_stop_mult": parent_cfg.atr_stop_mult,
                "target_r_multiple": parent_cfg.target_r_multiple,
            },
            "train": train_metrics,
            "oos": oos_metrics,
            "parent_train": parent_train,
            "parent_oos": parent_oos,
            "parent_critique": critique,
            "robustness_score": score,
            "verdict": state,
        })
    return rows


def best_child(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    eligible = [r for r in rows if r["verdict"] in {"PROMOTABLE", "CANDIDATE"}]
    if not eligible:
        return None
    return max(
        eligible,
        key=lambda r: (
            r["verdict"] == "PROMOTABLE",
            r["robustness_score"],
            float(r["oos"].get("return_pct", 0.0)),
            _finite_pf(r["oos"].get("profit_factor", 0.0)),
        ),
    )
