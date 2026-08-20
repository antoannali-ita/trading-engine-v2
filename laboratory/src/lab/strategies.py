from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd

from .indicators import enrich_prices


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


def trend_continuation(df: pd.DataFrame) -> pd.Series:
    x = enrich_prices(df)
    trend = ((x.Close > x.sma50) & (x.sma50 > x.sma200)).astype(float) * 35
    pullback = (1 - ((x.Close - x.sma50).abs() / x.atr14.replace(0, np.nan)).clip(0, 2) / 2) * 25
    momentum = x.ret_60d.rank(pct=True) * 20
    volume = x.relative_volume.clip(0, 2) / 2 * 10
    breakout = (x.Close > x.high20).astype(float) * 10
    return _clip(trend + pullback.fillna(0) + momentum.fillna(0) + volume.fillna(0) + breakout)


def cross_sectional_momentum(df: pd.DataFrame) -> pd.Series:
    x = enrich_prices(df)
    score = (x.ret_20d.rank(pct=True) * 30 + x.ret_60d.rank(pct=True) * 35 + x.ret_120d.rank(pct=True) * 35)
    return _clip(score)


def short_term_reversal(df: pd.DataFrame) -> pd.Series:
    x = enrich_prices(df)
    oversold = ((45 - x.rsi14) / 25 * 45).clip(0, 45)
    stretch = ((x.sma20 - x.Close) / x.atr14.replace(0, np.nan) * 20).clip(0, 30)
    long_trend = ((x.Close > x.sma200).astype(float) * 15)
    stabilization = ((x.ret_1d > 0).astype(float) * 10)
    return _clip(oversold.fillna(0) + stretch.fillna(0) + long_trend + stabilization)


def defensive_low_vol(df: pd.DataFrame) -> pd.Series:
    x = enrich_prices(df)
    lowvol = (1 - x.vol20.rank(pct=True)) * 40
    trend = ((x.Close > x.sma200).astype(float) * 25)
    stability = (1 - x.atr_pct.rank(pct=True)) * 20
    momentum = x.ret_60d.rank(pct=True) * 15
    return _clip(lowvol.fillna(0) + trend + stability.fillna(0) + momentum.fillna(0))


STRATEGIES: dict[str, StrategySpec] = {
    "trend_continuation": StrategySpec("trend_continuation", 20, trend_continuation),
    "cross_sectional_momentum": StrategySpec("cross_sectional_momentum", 40, cross_sectional_momentum),
    "short_term_reversal": StrategySpec("short_term_reversal", 10, short_term_reversal),
    "defensive_low_vol_quality": StrategySpec("defensive_low_vol_quality", 60, defensive_low_vol),
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
