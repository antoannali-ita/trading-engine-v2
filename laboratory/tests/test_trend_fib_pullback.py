from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from lab.strategies import STRATEGIES, generate_scores
from lab.trend_fib_pullback import (
    TrendFibPullbackConfig,
    _confirmed_pivots,
    trend_fib_pullback_scores,
)


def _prices(n: int = 260) -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=n, freq="D")
    base = np.linspace(100.0, 180.0, n)
    wave = np.sin(np.arange(n) / 8.0) * 3.0
    close = base + wave
    return pd.DataFrame(
        {
            "Open": close - 0.25,
            "High": close + 1.0,
            "Low": close - 1.0,
            "Close": close,
            "Volume": np.full(n, 1_000_000.0),
        },
        index=index,
    )


def test_strategy_is_registered_as_price_strategy() -> None:
    spec = STRATEGIES["trend_fib_pullback_v1"]
    assert spec.generator is not None
    assert spec.holding_days == 60


def test_confirmed_pivot_is_emitted_only_after_right_bars() -> None:
    index = pd.date_range("2026-01-01", periods=7, freq="D")
    high = pd.Series([1, 2, 5, 2, 1, 2, 1], index=index, dtype=float)
    low = pd.Series([0, 0, 1, 0, 0, 0, 0], index=index, dtype=float)

    pivot_high, _ = _confirmed_pivots(high, low, left=2, right=2)

    # Peak is physically at index 2 but can only be known at index 4.
    assert pd.isna(pivot_high.iloc[2])
    assert pd.isna(pivot_high.iloc[3])
    assert pivot_high.iloc[4] == 5.0


def test_score_output_is_aligned_finite_and_bounded() -> None:
    prices = _prices()
    scores = generate_scores("trend_fib_pullback_v1", prices)

    assert scores.index.equals(prices.index)
    assert scores.notna().all()
    assert ((scores >= 0.0) & (scores <= 100.0)).all()


def test_invalid_pivot_config_is_rejected() -> None:
    prices = _prices()
    with pytest.raises(ValueError):
        trend_fib_pullback_scores(
            prices,
            TrendFibPullbackConfig(pivot_left=0, pivot_right=5),
        )
