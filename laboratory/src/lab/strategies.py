from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd

from .indicators import enrich_prices
from .trend_fib_pullback import trend_fib_pullback_scores


class DataRequired(RuntimeError):
    pass


@dataclass(frozen=True)
class StrategySpec:
    name: str
    holding_days: int
    generator: Callable[[pd.DataFrame], pd.Series] | None
    requires: tuple[str, ...] = ()


def _clip(s: pd.Series) -> pd.Series:
    return s.clip(lower=0, upper=100).fillna(0.0)


def _pct_rank(s: pd.Series, ascending: bool = True) -> pd.Series:
    """Percentile rank helper.

    NOTE: for true cross-sectional momentum the production Laboratory job ranks
    the latest 20/60/120d returns across the whole configured universe. This
    helper is still useful for single-series backtests, where it is explicitly
    a time-series proxy rather than a cross-sectional observation.
    """
    return s.rank(pct=True, ascending=ascending).fillna(0.5) * 100.0


def trend_continuation(df: pd.DataFrame) -> pd.Series:
    x = enrich_prices(df)
    trend = ((x.Close > x.sma50) & (x.sma50 > x.sma200)).astype(float) * 35
    pullback = (1 - ((x.Close - x.sma50).abs() / x.atr14.replace(0, np.nan)).clip(0, 2) / 2) * 25
    momentum = x.ret_60d.rank(pct=True) * 20
    volume = x.relative_volume.clip(0, 2) / 2 * 10
    breakout = (x.Close > x.high20).astype(float) * 10
    return _clip(trend + pullback.fillna(0) + momentum.fillna(0) + volume.fillna(0) + breakout)


def cross_sectional_momentum(df: pd.DataFrame) -> pd.Series:
    """Backtest proxy only.

    The daily Laboratory feed computes the real score cross-sectionally across
    the complete universe at the same observation date. A one-symbol historical
    DataFrame cannot provide a genuine cross-sectional rank, so this function is
    deliberately retained only as a time-series proxy for legacy backtests.
    """
    x = enrich_prices(df)
    score = (
        x.ret_20d.rank(pct=True) * 30
        + x.ret_60d.rank(pct=True) * 35
        + x.ret_120d.rank(pct=True) * 35
    )
    return _clip(score)


def _short_term_reversal(df: pd.DataFrame, rsi_threshold: float) -> pd.Series:
    """Comparable reversal score for alternative RSI admission thresholds.

    RSI intensity is normalized over the same 20-point depth for every variant:
    at the threshold the RSI component is zero; 20 RSI points below the threshold
    it reaches the full 45 points. This keeps RSI35 and RSI45 comparable rather
    than reusing a score calibrated only for the old threshold.
    """
    x = enrich_prices(df)
    oversold_depth = ((rsi_threshold - x.rsi14) / 20.0).clip(0, 1)
    oversold = oversold_depth * 45
    stretch = ((x.sma20 - x.Close) / x.atr14.replace(0, np.nan) * 20).clip(0, 30)
    long_trend = (x.Close > x.sma200).astype(float) * 15
    stabilization = (x.ret_1d > 0).astype(float) * 10
    return _clip(oversold.fillna(0) + stretch.fillna(0) + long_trend + stabilization)


def short_term_reversal_rsi45(df: pd.DataFrame) -> pd.Series:
    return _short_term_reversal(df, 45.0)


def short_term_reversal_rsi35(df: pd.DataFrame) -> pd.Series:
    return _short_term_reversal(df, 35.0)


def defensive_low_vol(df: pd.DataFrame) -> pd.Series:
    x = enrich_prices(df)
    lowvol = (1 - x.vol20.rank(pct=True)) * 40
    trend = (x.Close > x.sma200).astype(float) * 25
    stability = (1 - x.atr_pct.rank(pct=True)) * 20
    momentum = x.ret_60d.rank(pct=True) * 15
    return _clip(lowvol.fillna(0) + trend + stability.fillna(0) + momentum.fillna(0))


STRATEGIES: dict[str, StrategySpec] = {
    "trend_continuation": StrategySpec("trend_continuation", 20, trend_continuation),
    "trend_fib_pullback_v1": StrategySpec("trend_fib_pullback_v1", 60, trend_fib_pullback_scores),
    "cross_sectional_momentum": StrategySpec("cross_sectional_momentum", 40, cross_sectional_momentum),
    "short_term_reversal_rsi45": StrategySpec("short_term_reversal_rsi45", 10, short_term_reversal_rsi45),
    "short_term_reversal_rsi35": StrategySpec("short_term_reversal_rsi35", 10, short_term_reversal_rsi35),
    "defensive_low_vol": StrategySpec("defensive_low_vol", 60, defensive_low_vol),
    "pead": StrategySpec("pead", 20, None, ("point_in_time_earnings", "analyst_revisions")),
    "event_driven_mean_reversion": StrategySpec("event_driven_mean_reversion", 10, None, ("point_in_time_events",)),
    "quality_value_rerating": StrategySpec("quality_value_rerating", 60, None, ("point_in_time_fundamentals",)),
    "macro_intermarket": StrategySpec("macro_intermarket", 40, None, ("rates", "credit_spreads", "commodities", "usd")),
}


def generate_scores(name: str, df: pd.DataFrame) -> pd.Series:
    spec = STRATEGIES[name]
    if spec.generator is None:
        raise DataRequired(f"{name} requires: {', '.join(spec.requires)}")
    return spec.generator(df)
