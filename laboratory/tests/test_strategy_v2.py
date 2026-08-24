from __future__ import annotations

import numpy as np
import pandas as pd

from lab.strategies import STRATEGIES, generate_scores


def _prices(n: int = 260) -> pd.DataFrame:
    idx = pd.date_range("2025-01-01", periods=n, freq="B")
    base = np.linspace(100.0, 130.0, n)
    close = base + np.sin(np.arange(n) / 7.0) * 2.0
    return pd.DataFrame({
        "Open": close - 0.5,
        "High": close + 1.0,
        "Low": close - 1.0,
        "Close": close,
        "Volume": np.linspace(1_000_000, 1_500_000, n),
    }, index=idx)


def test_v2_strategy_registry_uses_canonical_names():
    assert "short_term_reversal_rsi35" in STRATEGIES
    assert "short_term_reversal_rsi45" in STRATEGIES
    assert "defensive_low_vol" in STRATEGIES
    assert "defensive_low_vol_quality" not in STRATEGIES


def test_reversal_variants_are_distinct_and_bounded():
    prices = _prices()
    s35 = generate_scores("short_term_reversal_rsi35", prices)
    s45 = generate_scores("short_term_reversal_rsi45", prices)
    assert len(s35) == len(prices)
    assert len(s45) == len(prices)
    assert s35.between(0, 100).all()
    assert s45.between(0, 100).all()
    assert not s35.equals(s45)


def test_cross_sectional_backtest_proxy_is_explicitly_bounded():
    scores = generate_scores("cross_sectional_momentum", _prices())
    assert scores.between(0, 100).all()
