from __future__ import annotations

import math
import os
import sys
from datetime import datetime, timedelta, timezone
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


def _alert_type(status: str, trigger: str, price: float, entry: float, max_buy: float) -> tuple[str, float | None]:
    if trigger == "CONFIRMED" and status in {"PRE_BUY", "PAPER_OPEN"}:
        return "TRIGGER_CONFIRMED", entry
    if price <= entry:
        return "ENTRY_REACHED", entry
    if price <= max_buy:
        return "BUY_ZONE", entry
    return "ENTRY_APPROACH", entry


def _upsert_watchlist(client, payload: dict) -> None:
    client.table("lab_watchlist").upsert(payload, on_conflict="symbol,strategy").execute()


def _open_position_if_needed(client, symbol: str, strategy: str, signal_date: str, price: float, stop: float, tp1: float, tp2: float, qty: int, details: dict) -> bool:
    if qty <= 0:
        return False
    existing = (
        client.table("lab_paper_positions")
        .select("id,status")
        .eq("symbol", symbol)
        .eq("strategy", strategy)
        .in_("status", ["OPEN", "TP1_HIT"])
        .limit(1)
        .execute()
    )
    if existing.data:
        return False
    capital = qty * price
    row = {
        "symbol": symbol,
        "strategy": strategy,
        "market": "USA",
        "source_signal_date": signal_date,
        "entry_price": price,
        "qty": qty,
        "capital": capital,
        "commission_entry": COMMISSION,
        "stop_initial": stop,
        "stop_current": stop,
        "tp1": tp1,
        "tp2": tp2,
        "last_price": price,
        "last_checked_date": signal_date,
        "status": "OPEN",
        "details": details,
    }
    response = client.table("lab_paper_positions").insert(row).execute()
    if response.data:
        client.table("lab_paper_events").insert({
            "position_id": response.data[0]["id"],
            "event_type": "OPEN",
            "price": price,
            "new_stop": stop,
            "note": "Paper position opened by confirmed Lab signal. Research-only.",
        }).execute()
    return True


def _update_existing_positions(client, symbol: str, last_bar, check_date: str) -> int:
    response = (
        client.table("lab_paper_positions")
        .select("*")
        .eq("symbol", symbol)
        .in_("status", ["OPEN", "TP1_HIT"])
        .execute()
    )
    if not response.data:
        return 0

    high = float(last_bar.High)
    low = float(last_bar.Low)
    close = float(last_bar.Close)
    updated = 0

    for p in response.data:
        position_id = p["id"]
        entry = float(p["entry_price"])
        qty = int(p["qty"])
        stop = _safe(p.get("stop_current")) or _safe(p.get("stop_initial"))
        tp1 = _safe(p.get("tp1"))
        tp2 = _safe(p.get("tp2"))
        status = str(p.get("status") or "OPEN")

        # Conservative same-bar policy: stop has priority over target.
        if stop is not None and low <= stop:
            gross = (stop - entry) * qty
            net = gross - float(p.get("commission_entry") or COMMISSION) - COMMISSION
            client.table("lab_paper_positions").update({
                "status": "CLOSED",
                "last_price": close,
                "last_checked_date": check_date,
                "closed_at": datetime.now(timezone.utc).isoformat(),
                "exit_price": stop,
                "exit_reason": "STOP",
                "gross_pnl": gross,
                "net_pnl": net,
                "return_pct": net / max(entry * qty, 1) * 100.0,
            }).eq("id", position_id).execute()
            client.table("lab_paper_events").insert({
                "position_id": position_id,
                "event_type": "STOP",
                "price": stop,
                "old_stop": stop,
                "note": "Conservative stop-first lifecycle update.",
            }).execute()
            updated += 1
            continue

        if tp2 is not None and high >= tp2:
            gross = (tp2 - entry) * qty
            net = gross - float(p.get("commission_entry") or COMMISSION) - COMMISSION
            client.table("lab_paper_positions").update({
                "status": "CLOSED",
                "last_price": close,
                "last_checked_date": check_date,
                "closed_at": datetime.now(timezone.utc).isoformat(),
                "exit_price": tp2,
                "exit_reason": "TP2",
                "gross_pnl": gross,
                "net_pnl": net,
                "return_pct": net / max(entry * qty, 1) * 100.0,
            }).eq("id", position_id).execute()
            client.table("lab_paper_events").insert({
                "position_id": position_id,
                "event_type": "TP2",
                "price": tp2,
                "note": "Paper target 2 reached.",
            }).execute()
            updated += 1
            continue

        if status == "OPEN" and tp1 is not None and high >= tp1:
            new_stop = max(entry, stop or entry)
            client.table("lab_paper_positions").update({
                "status": "TP1_HIT",
                "stop_current": new_stop,
                "tp1_hit_at": datetime.now(timezone.utc).isoformat(),
                "last_price": close,
                "last_checked_date": check_date,
            }).eq("id", position_id).execute()
            client.table("lab_paper_events").insert({
                "position_id": position_id,
                "event_type": "TP1",
                "price": tp1,
                "old_stop": stop,
                "new_stop": new_stop,
                "note": "TP1 reached; paper stop moved to break-even.",
            }).execute()
            updated += 1
        else:
            client.table("lab_paper_positions").update({
                "last_price": close,
                "last_checked_date": check_date,
            }).eq("id", position_id).execute()
    return updated


def main() -> int:
    if not os.getenv("SUPABASE_URL") or not os.getenv("SUPABASE_SECRET_KEY"):
        print("Supabase secrets missing; no opportunity feed persisted")
        return 2

    client = get_supabase_client()
    watch_threshold = float(os.getenv("LAB_WATCH_SCORE", "55"))
    written = 0
    watch_written = 0
    opened = 0
    lifecycle_updates = 0
    now = datetime.now(timezone.utc)

    # Expire stale Lab watchlist rows. Historical paper signals remain untouched.
    try:
        stale_before = (now - timedelta(days=3)).isoformat()
        client.table("lab_watchlist").update({"active": False}).lt("last_seen_at", stale_before).eq("active", True).execute()
    except Exception as exc:
        print(f"lab_watchlist stale cleanup warning: {exc}")

    for symbol in symbols():
        try:
            prices = download_prices(MarketDataRequest(symbol=symbol, start="2024-01-01"))
            x = enrich_prices(prices)
            if len(x) < 220:
                continue
            last = x.iloc[-1]
            signal_date = x.index[-1].date().isoformat()
            catalyst = _news_and_calendar(symbol)
            lifecycle_updates += _update_existing_positions(client, symbol, last, signal_date)

            for strategy in PRICE_STRATEGIES:
                score = float(generate_scores(strategy, prices).iloc[-1])
                if score < watch_threshold:
                    continue

                price = float(last.Close)
                atr = _safe(last.atr14)
                if atr is None or atr <= 0:
                    continue

                entry, trigger, setup_note = _entry_and_trigger(strategy, last)
                risk_per_share = 2.0 * atr
                stop = price - risk_per_share
                tp1 = price + 1.5 * risk_per_share
                tp2 = price + 2.5 * risk_per_share
                max_buy = entry + 0.8 * atr
                distance_pct = ((price - entry) / entry * 100.0) if entry else None
                qty = max(0, math.floor((MAX_POSITION - COMMISSION) / price))
                capital = qty * price
                loss_max = qty * max(price - stop, 0) + COMMISSION
                state = _ladder(score)
                if state == "PAPER_OPEN" and trigger != "CONFIRMED":
                    state = "PRE_BUY"

                details = {
                    "generated_at": now.isoformat(),
                    "trigger": trigger,
                    "setup_note": setup_note,
                    "distance_to_entry_pct": distance_pct,
                    "max_buy": max_buy,
                    "tp1": tp1,
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
                }
                payload = {
                    "symbol": symbol,
                    "strategy": strategy,
                    "signal_date": signal_date,
                    "score": score,
                    "price": price,
                    "proposed_entry": entry,
                    "proposed_stop": stop,
                    "proposed_target": tp2,
                    "status": state,
                    "details": details,
                }
                client.table("lab_paper_signals").upsert(payload, on_conflict="symbol,strategy,signal_date").execute()
                written += 1

                alert_type, alert_price = _alert_type(state, trigger, price, entry, max_buy)
                _upsert_watchlist(client, {
                    "symbol": symbol,
                    "strategy": strategy,
                    "market": "USA",
                    "status": state,
                    "score": score,
                    "price": price,
                    "entry": entry,
                    "max_buy": max_buy,
                    "stop": stop,
                    "tp1": tp1,
                    "tp2": tp2,
                    "trigger": trigger,
                    "alert_type": alert_type,
                    "alert_price": alert_price,
                    "distance_to_entry_pct": distance_pct,
                    "reason": setup_note,
                    "signal_date": signal_date,
                    "last_seen_at": now.isoformat(),
                    "active": True,
                    "details": details,
                })
                watch_written += 1

                if state == "PAPER_OPEN" and trigger == "CONFIRMED":
                    if _open_position_if_needed(client, symbol, strategy, signal_date, price, stop, tp1, tp2, qty, details):
                        opened += 1
        except Exception as exc:
            print(f"{symbol}: {exc}")

    print(
        f"opportunity rows={written} watchlist={watch_written} "
        f"paper_opened={opened} lifecycle_updates={lifecycle_updates}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
