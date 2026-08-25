from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .indicators import enrich_prices


@dataclass(frozen=True)
class TrendFibPullbackConfig:
    """Research defaults for TREND_FIB_PULLBACK_V1.

    The implementation is intentionally long-only in v1 because the current
    Laboratory backtest engine models long positions only. Short support must be
    added together with an execution-engine extension, not faked inside a score.
    """

    pivot_left: int = 5
    pivot_right: int = 5
    ema_slope_bars: int = 5
    rsi_threshold: float = 50.0
    min_relative_volume: float = 1.0
    min_impulse_atr: float = 3.0
    max_impulse_age_bars: int = 40


def _confirmed_pivots(
    high: pd.Series,
    low: pd.Series,
    left: int,
    right: int,
) -> tuple[pd.Series, pd.Series]:
    """Return pivot values only on the bar where each pivot becomes knowable.

    A pivot located at candidate bar c is emitted at c + right. This preserves
    the confirmation delay and prevents future data from leaking into signals.
    """

    n = len(high)
    pivot_high = pd.Series(np.nan, index=high.index, dtype=float)
    pivot_low = pd.Series(np.nan, index=low.index, dtype=float)
    high_values = high.to_numpy(dtype=float)
    low_values = low.to_numpy(dtype=float)

    for confirm_i in range(left + right, n):
        candidate_i = confirm_i - right
        start = candidate_i - left
        end = candidate_i + right + 1
        if start < 0 or end > n:
            continue

        candidate_high = high_values[candidate_i]
        candidate_low = low_values[candidate_i]
        high_window = high_values[start:end]
        low_window = low_values[start:end]

        if np.isfinite(candidate_high) and candidate_high == np.nanmax(high_window):
            pivot_high.iloc[confirm_i] = candidate_high
        if np.isfinite(candidate_low) and candidate_low == np.nanmin(low_window):
            pivot_low.iloc[confirm_i] = candidate_low

    return pivot_high, pivot_low


def trend_fib_pullback_scores(
    df: pd.DataFrame,
    config: TrendFibPullbackConfig | None = None,
) -> pd.Series:
    """Generate deterministic 0/100 trigger scores for TREND_FIB_PULLBACK_V1.

    Logic:
    - confirmed bullish trend: Close > EMA50 > EMA200 and EMA50 rising;
    - latest confirmed pivot sequence must be low -> high;
    - impulse size must be at least min_impulse_atr ATR;
    - prior bar must pull back into 38.2%-61.8% Fibonacci zone;
    - prior bar must be bullish, close above its previous close, RSI-confirmed and
      volume-confirmed;
    - current bar must trade above the confirmation-bar high (trigger).

    All pivot information is used only from its confirmation bar onward.
    No future-looking values or backfilled signals are used.
    """

    cfg = config or TrendFibPullbackConfig()
    if cfg.pivot_left < 1 or cfg.pivot_right < 1:
        raise ValueError("pivot_left and pivot_right must be >= 1")

    x = enrich_prices(df)
    close = x["Close"].astype(float)
    high = x["High"].astype(float)
    low = x["Low"].astype(float)
    open_ = x["Open"].astype(float)

    ema50 = close.ewm(span=50, adjust=False, min_periods=50).mean()
    ema200 = close.ewm(span=200, adjust=False, min_periods=200).mean()
    trend_ok = (
        (close > ema50)
        & (ema50 > ema200)
        & (ema50 > ema50.shift(cfg.ema_slope_bars))
    )

    confirmed_high, confirmed_low = _confirmed_pivots(
        high, low, cfg.pivot_left, cfg.pivot_right
    )

    scores = pd.Series(0.0, index=x.index, dtype=float)
    last_low_price: float | None = None
    last_low_confirm_i: int | None = None
    last_high_price: float | None = None
    last_high_confirm_i: int | None = None

    for i in range(len(x)):
        if pd.notna(confirmed_low.iloc[i]):
            last_low_price = float(confirmed_low.iloc[i])
            last_low_confirm_i = i
            # A new low starts a new candidate impulse.
            last_high_price = None
            last_high_confirm_i = None

        if pd.notna(confirmed_high.iloc[i]) and last_low_price is not None:
            if last_low_confirm_i is not None and last_low_confirm_i <= i:
                candidate_high = float(confirmed_high.iloc[i])
                if candidate_high > last_low_price:
                    last_high_price = candidate_high
                    last_high_confirm_i = i

        if i < 2 or last_low_price is None or last_high_price is None:
            continue
        if last_high_confirm_i is None or last_low_confirm_i is None:
            continue
        if last_high_confirm_i <= last_low_confirm_i:
            continue
        if i - last_high_confirm_i > cfg.max_impulse_age_bars:
            continue

        atr_at_high = x["atr14"].iloc[last_high_confirm_i]
        if pd.isna(atr_at_high) or float(atr_at_high) <= 0:
            continue
        impulse = last_high_price - last_low_price
        if impulse < cfg.min_impulse_atr * float(atr_at_high):
            continue

        fib_382 = last_high_price - 0.382 * impulse
        fib_618 = last_high_price - 0.618 * impulse

        confirmation_i = i - 1
        confirmation_close = float(close.iloc[confirmation_i])
        confirmation_open = float(open_.iloc[confirmation_i])
        confirmation_low = float(low.iloc[confirmation_i])
        confirmation_high = float(high.iloc[confirmation_i])
        prior_close = float(close.iloc[confirmation_i - 1])

        in_fib_zone = (
            confirmation_low <= fib_382
            and confirmation_high >= fib_618
            and confirmation_close >= fib_618
            and confirmation_close <= fib_382
        )
        bullish_confirmation = (
            confirmation_close > confirmation_open
            and confirmation_close > prior_close
        )
        rsi_ok = (
            pd.notna(x["rsi14"].iloc[confirmation_i])
            and float(x["rsi14"].iloc[confirmation_i]) > cfg.rsi_threshold
        )
        volume_ok = (
            pd.notna(x["relative_volume"].iloc[confirmation_i])
            and float(x["relative_volume"].iloc[confirmation_i]) > cfg.min_relative_volume
        )
        origin_valid = confirmation_low > last_low_price
        trigger_confirmed = float(high.iloc[i]) > confirmation_high

        if (
            bool(trend_ok.iloc[i])
            and in_fib_zone
            and bullish_confirmation
            and rsi_ok
            and volume_ok
            and origin_valid
            and trigger_confirmed
        ):
            scores.iloc[i] = 100.0

    return scores
