from __future__ import annotations

from dataclasses import dataclass
import pandas as pd
import yfinance as yf


class MarketDataError(RuntimeError):
    pass


@dataclass(frozen=True)
class MarketDataRequest:
    symbol: str
    start: str
    end: str | None = None


def download_prices(request: MarketDataRequest) -> pd.DataFrame:
    data = yf.download(request.symbol, start=request.start, end=request.end, auto_adjust=True, progress=False, actions=False, threads=False)
    if data is None or data.empty:
        raise MarketDataError(f"No price data returned for {request.symbol}")
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    required = {"Open", "High", "Low", "Close", "Volume"}
    missing = required.difference(data.columns)
    if missing:
        raise MarketDataError(f"Missing columns for {request.symbol}: {sorted(missing)}")
    return data.loc[:, ["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"])
