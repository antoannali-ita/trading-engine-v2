from __future__ import annotations

import numpy as np
import pandas as pd


def enrich_prices(df: pd.DataFrame) -> pd.DataFrame:
    """Add deterministic technical features to OHLCV data.

    Input columns are expected to contain Open/High/Low/Close/Volume.
    No forward-looking values are used.
    """
    out = df.copy().sort_index()
    close = out["Close"].astype(float)
    high = out["High"].astype(float)
    low = out["Low"].astype(float)
    volume = out["Volume"].astype(float)

    for n in (20, 50, 200):
        out[f"sma{n}"] = close.rolling(n, min_periods=n).mean()

    out["ret_1d"] = close.pct_change()
    out["ret_5d"] = close.pct_change(5)
    out["ret_20d"] = close.pct_change(20)
    out["ret_60d"] = close.pct_change(60)
    out["ret_120d"] = close.pct_change(120)

    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14, min_periods=14).mean()
    loss = (-delta.clip(upper=0)).rolling(14, min_periods=14).mean()
    rs = gain / loss.replace(0, np.nan)
    out["rsi14"] = 100 - (100 / (1 + rs))

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    out["macd"] = ema12 - ema26
    out["macd_signal"] = out["macd"].ewm(span=9, adjust=False).mean()

    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    out["atr14"] = tr.rolling(14, min_periods=14).mean()
    out["atr_pct"] = out["atr14"] / close

    out["vol20"] = out["ret_1d"].rolling(20, min_periods=20).std() * np.sqrt(252)
    out["volume_avg20"] = volume.rolling(20, min_periods=20).mean()
    out["relative_volume"] = volume / out["volume_avg20"].replace(0, np.nan)

    out["high20"] = high.rolling(20, min_periods=20).max().shift(1)
    out["low20"] = low.rolling(20, min_periods=20).min().shift(1)
    out["high50"] = high.rolling(50, min_periods=50).max().shift(1)
    out["low50"] = low.rolling(50, min_periods=50).min().shift(1)
    return out
