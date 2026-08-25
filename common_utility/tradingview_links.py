from __future__ import annotations

from urllib.parse import quote

# TradingView exchange hints for the symbols currently used by Production and
# the USA Laboratory universe. Explicit hints avoid ambiguous ticker routing.
_EXCHANGE_BY_TICKER = {
    "SPY": "AMEX", "QQQ": "NASDAQ",
    "AAPL": "NASDAQ", "MSFT": "NASDAQ", "NVDA": "NASDAQ", "AMZN": "NASDAQ",
    "GOOG": "NASDAQ", "GOOGL": "NASDAQ", "META": "NASDAQ", "AVGO": "NASDAQ",
    "AMD": "NASDAQ", "COST": "NASDAQ", "WMT": "NASDAQ", "ADBE": "NASDAQ",
    "NFLX": "NASDAQ", "FTNT": "NASDAQ", "ASML": "NASDAQ", "BKNG": "NASDAQ",
    "PANW": "NASDAQ", "LIN": "NASDAQ", "CSCO": "NASDAQ", "ARRY": "NASDAQ",
    "PYPL": "NASDAQ",
    "JPM": "NYSE", "GS": "NYSE", "AXP": "NYSE", "PGR": "NYSE", "V": "NYSE",
    "MA": "NYSE", "UNH": "NYSE", "LLY": "NYSE", "NVO": "NYSE", "CVS": "NYSE",
    "HD": "NYSE", "CAT": "NYSE", "GE": "NYSE", "RTX": "NYSE", "XOM": "NYSE",
    "CVX": "NYSE", "CRM": "NYSE", "ORCL": "NYSE", "MUFG": "NYSE", "TSM": "NYSE",
    "UBER": "NYSE", "F": "NYSE", "FNV": "NYSE", "TAP": "NYSE", "CF": "NYSE",
}

_MARKET_TO_TV = {
    "NASDAQ": "NASDAQ",
    "NYSE": "NYSE",
    "AMEX": "AMEX",
    "BIT": "MIL",
    "MIL": "MIL",
    "BORSA ITALIANA": "MIL",
}


def tradingview_symbol(ticker: str, market: str | None = None) -> str:
    raw = str(ticker or "").strip().upper()
    if not raw:
        return ""

    if raw.endswith(".MI"):
        return f"MIL:{raw[:-3]}"

    market_key = str(market or "").strip().upper()
    exchange = _MARKET_TO_TV.get(market_key) or _EXCHANGE_BY_TICKER.get(raw)
    return f"{exchange}:{raw}" if exchange else raw


def tradingview_url(ticker: str, market: str | None = None) -> str:
    symbol = tradingview_symbol(ticker, market)
    if not symbol:
        return ""
    return f"https://www.tradingview.com/chart/?symbol={quote(symbol, safe='')}"
