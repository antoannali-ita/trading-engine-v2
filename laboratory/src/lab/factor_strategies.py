from __future__ import annotations

import numpy as np
import pandas as pd

from .strategies import DataRequired


def _require(df: pd.DataFrame, columns: list[str], strategy: str) -> None:
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise DataRequired(f"{strategy} missing point-in-time fields: {', '.join(missing)}")


def _pct_rank(s: pd.Series, ascending: bool = True) -> pd.Series:
    return s.rank(pct=True, ascending=ascending).fillna(0.5) * 100


def pead_scores(df: pd.DataFrame) -> pd.Series:
    """Post-earnings-announcement drift score using only as-known event fields."""
    cols = ["eps_surprise_pct", "revenue_surprise_pct", "revision_30d_pct", "event_age_days", "post_event_ret_1d"]
    _require(df, cols, "pead")
    age_ok = df.event_age_days.between(1, 10).astype(float)
    score = (
        _pct_rank(df.eps_surprise_pct) * 0.35
        + _pct_rank(df.revenue_surprise_pct) * 0.20
        + _pct_rank(df.revision_30d_pct) * 0.30
        + _pct_rank(df.post_event_ret_1d) * 0.15
    ) * age_ok
    return score.clip(0, 100)


def event_mean_reversion_scores(df: pd.DataFrame) -> pd.Series:
    """Non-binary shock mean reversion; binary events are excluded by hard gate."""
    cols = ["event_return_pct", "event_vol_z", "post_event_ret_1d", "is_binary_event"]
    _require(df, cols, "event_driven_mean_reversion")
    shock = _pct_rank(-df.event_return_pct) * 0.45
    abnormal = _pct_rank(df.event_vol_z) * 0.25
    stabilization = _pct_rank(df.post_event_ret_1d) * 0.30
    gate = (~df.is_binary_event.astype(bool)).astype(float)
    return ((shock + abnormal + stabilization) * gate).clip(0, 100)


def quality_value_scores(df: pd.DataFrame) -> pd.Series:
    """Cross-sectional rerating score from PIT fundamentals and valuation."""
    cols = ["fcf_yield", "roic", "revenue_growth_yoy", "eps_growth_yoy", "net_debt_ebitda", "valuation_discount_sector"]
    _require(df, cols, "quality_value_rerating")
    score = (
        _pct_rank(df.fcf_yield) * 0.20
        + _pct_rank(df.roic) * 0.20
        + _pct_rank(df.revenue_growth_yoy) * 0.15
        + _pct_rank(df.eps_growth_yoy) * 0.15
        + _pct_rank(df.net_debt_ebitda, ascending=False) * 0.15
        + _pct_rank(df.valuation_discount_sector) * 0.15
    )
    return score.clip(0, 100)


def macro_intermarket_scores(df: pd.DataFrame) -> pd.Series:
    """Directional macro score after asset-sensitivity fields are estimated ex ante."""
    cols = ["trend_score", "rates_impulse", "credit_impulse", "commodity_impulse", "usd_impulse", "macro_fit"]
    _require(df, cols, "macro_intermarket")
    directional = (
        df.rates_impulse * 0.25
        + df.credit_impulse * 0.25
        + df.commodity_impulse * 0.20
        + df.usd_impulse * 0.15
    )
    macro = (50 + directional * 10).clip(0, 100)
    fit = df.macro_fit.clip(0, 1)
    return (df.trend_score.clip(0, 100) * 0.35 + macro * 0.65 * fit).clip(0, 100)
