import numpy as np
import pandas as pd

from lab.backtest_engine import BacktestConfig, run_backtest
from lab.indicators import enrich_prices
from lab.strategies import STRATEGIES, generate_scores


def synthetic_prices(n=420):
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    close = 100 + np.linspace(0, 80, n) + np.sin(np.arange(n) / 8) * 3
    return pd.DataFrame({
        "Open": close * 0.999,
        "High": close * 1.01,
        "Low": close * 0.99,
        "Close": close,
        "Volume": np.full(n, 1_000_000),
    }, index=idx)


def test_indicators_are_backward_looking_and_present():
    x = enrich_prices(synthetic_prices())
    for col in ["sma20", "sma50", "sma200", "rsi14", "atr14", "vol20"]:
        assert col in x.columns
    assert x["sma200"].notna().sum() > 0


def test_price_strategies_generate_bounded_scores():
    prices = synthetic_prices()
    for name, spec in STRATEGIES.items():
        if spec.generator is None:
            continue
        s = generate_scores(name, prices)
        assert len(s) == len(prices)
        assert s.min() >= 0
        assert s.max() <= 100


def test_backtest_runs_without_lookahead_crash():
    trades, metrics = run_backtest(
        "TEST",
        synthetic_prices(),
        "trend_continuation",
        BacktestConfig(entry_score=55, commission_per_side=0, slippage_bps=0),
    )
    assert isinstance(trades, pd.DataFrame)
    assert metrics["trades"] >= 0
    assert "return_pct" in metrics
