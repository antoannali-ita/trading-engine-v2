from __future__ import annotations

from dataclasses import dataclass
import itertools

import pandas as pd

from .backtest_engine import BacktestConfig, run_backtest


@dataclass(frozen=True)
class CalibrationResult:
    entry_score: float
    atr_stop_mult: float
    target_r_multiple: float
    train_return_pct: float
    test_return_pct: float
    test_trades: int


def walk_forward_grid(symbol: str, prices: pd.DataFrame, strategy_name: str, split: float = 0.7) -> pd.DataFrame:
    """Small robust grid for calibration. Selection is train-only; test is untouched."""
    cut = max(250, int(len(prices) * split))
    if cut >= len(prices) - 50:
        raise ValueError("Not enough observations for walk-forward split")
    train = prices.iloc[:cut].copy()
    test = prices.iloc[cut - 220 :].copy()  # warm-up only; trades reported on test dates below
    test_start = prices.index[cut]

    rows = []
    grid = itertools.product((70.0, 75.0, 80.0), (1.5, 2.0, 2.5), (2.0, 2.5, 3.0))
    candidates = []
    for entry_score, stop_mult, target_mult in grid:
        cfg = BacktestConfig(entry_score=entry_score, atr_stop_mult=stop_mult, target_r_multiple=target_mult)
        _, m = run_backtest(symbol, train, strategy_name, cfg)
        candidates.append((m["return_pct"], m["trades"], cfg))

    viable = [x for x in candidates if x[1] >= 5]
    if not viable:
        viable = candidates
    best = max(viable, key=lambda x: (x[0], x[1]))
    best_cfg = best[2]
    test_trades, test_metrics = run_backtest(symbol, test, strategy_name, best_cfg)
    if not test_trades.empty:
        test_trades = test_trades[pd.to_datetime(test_trades.entry_date) >= pd.Timestamp(test_start)]
        test_return = float(test_trades.net_pnl.sum() / best_cfg.initial_capital * 100)
        test_n = int(len(test_trades))
    else:
        test_return, test_n = 0.0, 0

    rows.append({
        "symbol": symbol,
        "strategy": strategy_name,
        "entry_score": best_cfg.entry_score,
        "atr_stop_mult": best_cfg.atr_stop_mult,
        "target_r_multiple": best_cfg.target_r_multiple,
        "train_return_pct": float(best[0]),
        "test_return_pct": test_return,
        "test_trades": test_n,
    })
    return pd.DataFrame(rows)
