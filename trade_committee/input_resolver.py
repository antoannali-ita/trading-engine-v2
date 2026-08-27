from __future__ import annotations

import re
from dataclasses import dataclass

import yfinance as yf


@dataclass(frozen=True)
class ResolvedSymbol:
    query: str
    ticker: str
    name: str | None = None
    exchange: str | None = None
    source: str = "INPUT"


def split_queries(raw: str) -> list[str]:
    """Split manual Committee input.

    Primary separator is comma. Semicolon and newline are accepted too so a pasted
    shortlist does not require cleanup.
    """
    parts = [p.strip() for p in re.split(r"[,;\n]+", raw or "") if p.strip()]
    # preserve order and remove duplicates case-insensitively
    out: list[str] = []
    seen: set[str] = set()
    for part in parts:
        key = part.casefold()
        if key not in seen:
            seen.add(key)
            out.append(part)
    return out


def _looks_like_ticker(value: str) -> bool:
    value = value.strip().upper()
    return bool(re.fullmatch(r"[A-Z0-9.^=-]{1,15}", value)) and " " not in value


def resolve_query(query: str) -> ResolvedSymbol:
    q = query.strip()
    if not q:
        raise ValueError("Query vuota")

    # Direct tickers remain deterministic and do not depend on search ranking.
    if _looks_like_ticker(q):
        return ResolvedSymbol(query=q, ticker=q.upper(), source="DIRECT_TICKER")

    try:
        search = yf.Search(q, max_results=8, news_count=0)
        quotes = list(getattr(search, "quotes", None) or [])
    except Exception as exc:
        raise ValueError(f"Impossibile cercare '{q}': {type(exc).__name__}") from exc

    equities = []
    for item in quotes:
        quote_type = str(item.get("quoteType") or item.get("typeDisp") or "").upper()
        symbol = str(item.get("symbol") or "").strip().upper()
        if not symbol:
            continue
        if quote_type in {"EQUITY", "STOCK"} or "EQUITY" in quote_type:
            equities.append(item)

    if not equities:
        # Yahoo search occasionally omits quoteType; use first symbol as a transparent fallback.
        equities = [x for x in quotes if x.get("symbol")]
    if not equities:
        raise ValueError(f"Nessun titolo trovato per '{q}'")

    best = equities[0]
    return ResolvedSymbol(
        query=q,
        ticker=str(best.get("symbol") or "").upper(),
        name=best.get("longname") or best.get("shortname") or best.get("name"),
        exchange=best.get("exchange") or best.get("exchDisp"),
        source="YAHOO_SEARCH",
    )


def resolve_many(raw: str, max_symbols: int = 10) -> list[ResolvedSymbol]:
    queries = split_queries(raw)
    if not queries:
        return []
    if len(queries) > max_symbols:
        raise ValueError(f"Massimo {max_symbols} titoli per analisi batch")

    resolved: list[ResolvedSymbol] = []
    seen: set[str] = set()
    for query in queries:
        item = resolve_query(query)
        if item.ticker not in seen:
            resolved.append(item)
            seen.add(item.ticker)
    return resolved
