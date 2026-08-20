from __future__ import annotations

import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yfinance as yf

LAB_ROOT = Path(__file__).resolve().parents[1]
SRC = LAB_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from lab.db import get_supabase_client
from lab.indicators import enrich_prices
from lab.market_data import MarketDataRequest, download_prices
from lab.strategies import STRATEGIES, generate_scores

DEFAULT_SYMBOLS = [
    "SPY", "QQQ", "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "AVGO", "AMD",
    "JPM", "GS", "AXP", "PGR", "V", "MA", "UNH", "LLY", "NVO", "CVS",
    "COST", "WMT", "HD", "CAT", "GE", "RTX", "XOM", "CVX", "ADBE", "CRM",
    "ORCL", "NFLX", "FTNT", "MUFG", "TSM", "ASML", "BKNG", "UBER", "PANW", "LIN",
]
PRICE_STRATEGIES = [name for name, spec in STRATEGIES.items() if spec.generator is not None]
MAX_POSITION = 5000.0
COMMISSION = 12.0


def symbols() -> list[str]:
    raw = os.getenv("LAB_SYMBOLS", "")
    return [x.strip().upper() for x in raw.split(",") if x.strip()] or DEFAULT_SYMBOLS


def _safe(v):
    try:
        if pd.isna(v):
            return None
        return float(v)
    except Exception:
        return None


def _ladder(score: float) -> str:
    if score >= 80:
        return "PAPER_OPEN"
    if score >= 75:
        return "PRE_BUY"
    if score >= 65:
        return "NEAR_SETUP"
    return "WATCH"


def _entry_and_trigger(strategy: str, last) -> tuple[float, str, str]:
    price = float(last.Close)
    sma20, sma50, sma200 = _safe(last.sma20), _safe(last.sma50), _safe(last.sma200)
    high20 = _safe(last.high20)
    rsi = _safe(last.rsi14)
    ret1 = _safe(last.ret_1d)

    if strategy == "trend_continuation":
        entry = sma50 or sma20 or price
        confirmed = sma50 is not None and sma200 is not None and price > sma50 > sma200
        return entry, "CONFIRMED" if confirmed else "WAITING", "Pullback/continuazione sopra SMA50>SMA200"
    if strategy == "cross_sectional_momentum":
        entry = high20 or price
        confirmed = high20 is not None and price >= high20
        return entry, "CONFIRMED" if confirmed else "WAITING", "Breakout del massimo 20 giorni"
    if strategy == "short_term_reversal":
        entry = price
        confirmed = (ret1 is not None and ret1 > 0) and (rsi is not None and rsi < 45)
        return entry, "CONFIRMED" if confirmed else "WAITING", "Stabilizzazione dopo eccesso ribassista"
    entry = sma20 or price
    confirmed = sma200 is not None and price > sma200
    return entry, "CONFIRMED" if confirmed else "WAITING", "Low-vol sopra trend strutturale"


def _news_and_calendar(symbol: str) -> dict:
    out = {"news": [], "earnings_date": None, "catalyst_quality": "AGGREGATOR_ONLY"}
    try:
        t = yf.Ticker(symbol)
        items = t.news or []
        for item in items[:3]:
            content = item.get("content", item) if isinstance(item, dict) else {}
            out["news"].append({
                "title": content.get("title") or item.get("title"),
                "publisher": content.get("provider", {}).get("displayName") if isinstance(content.get("provider"), dict) else item.get("publisher"),
                "url": (content.get("canonicalUrl") or {}).get("url") if isinstance(content.get("canonicalUrl"), dict) else item.get("link"),
                "classification": "NEWS_AGGREGATOR_UNVERIFIED",
            })
        try:
            cal = t.calendar
            if isinstance(cal, dict):
                value = cal.get("Earnings Date") or cal.get("EarningsDate")
                if isinstance(value, (list, tuple)) and value:
                    value = value[0]
                if value is not None:
                    out["earnings_date"] = str(pd.Timestamp(value).date())
        except Exception:
            pass
    except Exception:
        pass
    return out


def main() -> int:
    if not os.getenv("SUPABASE_URL") or not os.getenv("SUPABASE_SECRET_KEY"):
        print("Supabase secrets missing; no opportunity feed persisted")
        return 2

    client = get_supabase_client()
    watch_threshold = float(os.getenv("LAB_WATCH_SCORE", "55"))
    written = 0

    for symbol in symbols():
        try:
            prices = download_prices(MarketDataRequest(symbol=symbol, start="2024-01-01"))
            x = enrich_prices(prices)
            if len(x) < 220:
                continue
            last = x.iloc[-1]
            signal_date = x.index[-1].date().isoformat()
            catalyst = _news_and_calendar(symbol)

            for strategy in PRICE_STRATEGIES:
                score = float(generate_scores(strategy, prices).iloc[-1])
                if score < watch_threshold:
                    continue

                price = float(last.Close)
                atr = _safe(last.atr14)
                if atr is None or atr <= 0:
                    continue

                entry, trigger, setup_note = _entry_and_trigger(strategy, last)
                stop = price - 2.0 * atr
                target = price + 2.5 * (price - stop)
                max_buy = entry + 0.8 * atr
                distance_pct = ((price - entry) / entry * 100.0) if entry else None
                qty = max(0, math.floor((MAX_POSITION - COMMISSION) / price))
                capital = qty * price
                loss_max = qty * max(price - stop, 0) + COMMISSION
                state = _ladder(score)
                if state == "PAPER_OPEN" and trigger != "CONFIRMED":
                    state = "PRE_BUY"

                payload = {
                    "symbol": symbol,
                    "strategy": strategy,
                    "signal_date": signal_date,
                    "score": score,
                    "price": price,
                    "proposed_entry": entry,
                    "proposed_stop": stop,
                    "proposed_target": target,
                    "status": state,
                    "details": {
                        "generated_at": datetime.now(timezone.utc).isoformat(),
                        "trigger": trigger,
                        "setup_note": setup_note,
                        "distance_to_entry_pct": distance_pct,
                        "max_buy": max_buy,
                        "qty": qty,
                        "capital": capital,
                        "loss_max": loss_max,
                        "max_position_policy": MAX_POSITION,
                        "commission": COMMISSION,
                        "sma20": _safe(last.sma20),
                        "sma50": _safe(last.sma50),
                        "sma200": _safe(last.sma200),
                        "rsi14": _safe(last.rsi14),
                        "atr14": atr,
                        "relative_volume": _safe(last.relative_volume),
                        "earnings_date": catalyst.get("earnings_date"),
                        "news": catalyst.get("news", []),
                        "catalyst_quality": catalyst.get("catalyst_quality"),
                        "warning": "News are aggregator enrichment only; verify primary sources before any real trade.",
                    },
                }
                client.table("lab_paper_signals").upsert(payload, on_conflict="symbol,strategy,signal_date").execute()
                written += 1
        except Exception as exc:
            print(f"{symbol}: {exc}")

    print(f"opportunity rows written: {written}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
