from __future__ import annotations

import os
import time
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


# In-process cache: several jobs (paper signals, evolution, dynamic exit)
# call download_prices for the same symbol more than once per run (e.g. the
# same symbol appears both in the candidate universe and among open-position
# lifecycle symbols). Without this cache each of those calls was a separate
# blocking network round-trip to Yahoo Finance for identical data.
_CACHE: dict[tuple[str, str, str | None], pd.DataFrame] = {}

DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_BACKOFF_SECONDS = 1.5


def _cache_key(request: MarketDataRequest) -> tuple[str, str, str | None]:
    return (request.symbol.upper(), request.start, request.end)


def clear_cache() -> None:
    """Exposed for tests and for callers that want a clean slate between runs."""
    _CACHE.clear()


def _download_once(request: MarketDataRequest) -> pd.DataFrame:
    data = yf.download(
        request.symbol, start=request.start, end=request.end,
        auto_adjust=True, progress=False, actions=False, threads=False,
    )
    if data is None or data.empty:
        raise MarketDataError(f"No price data returned for {request.symbol}")
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    required = {"Open", "High", "Low", "Close", "Volume"}
    missing = required.difference(data.columns)
    if missing:
        raise MarketDataError(f"Missing columns for {request.symbol}: {sorted(missing)}")
    return data.loc[:, ["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"])


def download_prices(
    request: MarketDataRequest,
    *,
    use_cache: bool = True,
    max_attempts: int | None = None,
    backoff_seconds: float | None = None,
) -> pd.DataFrame:
    """Download OHLCV prices with retry/backoff and an in-process cache.

    Yahoo Finance occasionally returns empty data or times out on a
    perfectly valid symbol; previously a single failed attempt aborted that
    symbol for the whole run. This retries with exponential backoff before
    giving up, and reuses already-downloaded data for repeat requests within
    the same process so a run does not re-fetch the same symbol multiple
    times across different jobs/loops.
    """
    key = _cache_key(request)
    if use_cache and key in _CACHE:
        return _CACHE[key]

    attempts = max_attempts if max_attempts is not None else int(os.getenv("LAB_MARKET_DATA_MAX_ATTEMPTS", DEFAULT_MAX_ATTEMPTS))
    backoff = backoff_seconds if backoff_seconds is not None else float(os.getenv("LAB_MARKET_DATA_BACKOFF_SECONDS", DEFAULT_BACKOFF_SECONDS))

    last_exc: Exception | None = None
    for attempt in range(1, max(1, attempts) + 1):
        try:
            data = _download_once(request)
            if use_cache:
                _CACHE[key] = data
            return data
        except Exception as exc:  # noqa: BLE001 - network/library errors vary widely
            last_exc = exc
            if attempt < attempts:
                time.sleep(backoff * (2 ** (attempt - 1)))

    raise MarketDataError(f"Failed to download {request.symbol} after {attempts} attempts: {last_exc}") from last_exc
