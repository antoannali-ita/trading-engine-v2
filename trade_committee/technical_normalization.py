from __future__ import annotations

from datetime import datetime, time
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd


def wilder_rsi(close: pd.Series, n: int = 14) -> float | None:
    s = close.dropna().astype(float)
    if len(s) <= n:
        return None
    delta = s.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    avg_loss = loss.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    last_gain = avg_gain.iloc[-1]
    last_loss = avg_loss.iloc[-1]
    if pd.isna(last_gain) or pd.isna(last_loss):
        return None
    if last_loss == 0:
        return 100.0 if last_gain > 0 else 50.0
    rs = last_gain / last_loss
    return float(100.0 - 100.0 / (1.0 + rs))


def _us_cash_session_open(now: datetime | None = None) -> bool:
    ny = now.astimezone(ZoneInfo("America/New_York")) if now is not None else datetime.now(ZoneInfo("America/New_York"))
    if ny.weekday() >= 5:
        return False
    return time(9, 30) <= ny.time().replace(tzinfo=None) < time(16, 0)


def normalize_market_bundle(market: dict[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    """Allinea i cross-check tecnici alla semantica usata dal motore.

    - RSI14 usa Wilder smoothing, coerente con TradingView.
    - Durante la sessione USA il volume daily corrente è parziale: il raw RVOL viene
      conservato come diagnostica ma non viene usato per penalizzare lo score.
    """
    result = dict(market)
    hist = market.get("history")
    if not isinstance(hist, pd.DataFrame) or hist.empty:
        return result

    close = hist.get("Close")
    if isinstance(close, pd.Series):
        result["rsi14"] = wilder_rsi(close, 14)
        result["rsi_method"] = "WILDER_RMA"

    avg20 = result.get("avg_volume20")
    volume = result.get("volume")
    raw_rvol = None
    try:
        if volume is not None and avg20:
            raw_rvol = float(volume) / float(avg20)
    except (TypeError, ValueError, ZeroDivisionError):
        raw_rvol = None

    if _us_cash_session_open(now):
        result["relative_volume_partial"] = raw_rvol
        result["relative_volume"] = None
        result["rvol_status"] = "PARTIAL_SESSION"
    else:
        result["relative_volume"] = raw_rvol
        result["relative_volume_partial"] = None
        result["rvol_status"] = "FULL_SESSION"

    return result
