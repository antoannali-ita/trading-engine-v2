from __future__ import annotations

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
from lab.decision_engine import (
    data_quality_check,
    earnings_distance_days,
    net_rr,
    regime_v1,
    risk_based_qty,
    trade_eligibility,
    trade_score,
)
from lab.indicators import enrich_prices
from lab.market_data import MarketDataRequest, download_prices
from lab.paper_policy import classify_paper_tier, lab_portfolio_fit
from lab.settings import ESTIMATED_SLIPPAGE_BPS, MAX_POSITION_USD, USA_COMMISSION_USD
from lab.strategies import STRATEGIES, generate_scores

DEFAULT_SYMBOLS = [
    "SPY", "QQQ", "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "AVGO", "AMD",
    "JPM", "GS", "AXP", "PGR", "V", "MA", "UNH", "LLY", "NVO", "CVS",
    "COST", "WMT", "HD", "CAT", "GE", "RTX", "XOM", "CVX", "ADBE", "CRM",
    "ORCL", "NFLX", "FTNT", "MUFG", "TSM", "ASML", "BKNG", "UBER", "PANW", "LIN",
]
PRICE_STRATEGIES = [name for name, spec in STRATEGIES.items() if spec.generator is not None]
BENCHMARK_ETFS = {"SPY", "QQQ"}
COMMISSION = USA_COMMISSION_USD


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
    if symbol in BENCHMARK_ETFS:
        return {"news": [], "earnings_date": None, "catalyst_quality": "BENCHMARK_ETF"}

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
    if status == "PAPER_OPEN":
        return "PAPER_OPEN", price
    if trigger == "CONFIRMED" and status in {"PRE_BUY", "CONFIRMED"}:
        return "TRIGGER_CONFIRMED", entry
    if price <= entry:
        return "ENTRY_REACHED", entry
    if price <= max_buy:
        return "BUY_ZONE", entry
    return "ENTRY_APPROACH", entry


def _upsert_watchlist(client, payload: dict) -> None:
    client.table("lab_watchlist").upsert(payload, on_conflict="symbol,strategy").execute()


def _open_position_if_needed(client, symbol: str, strategy: str, signal_date: str, price: float, stop: float, tp1: float, tp2: float, qty: int, details: dict) -> bool:
    if qty <= 0 or symbol in BENCHMARK_ETFS:
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
            "note": f"Research paper position opened under tier {details.get('paper_tier') or 'N/D'}.",
            "details": {
                "decision_model": "LAB_GATEKEEPER_V2_RESEARCH",
                "paper_tier": details.get("paper_tier"),
            },
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

        if stop is not None and low <= stop:
            gross = (stop - entry) * qty
            net = gross - float(p.get("commission_entry") or COMMISSION) - COMMISSION
            client.table("lab_paper_positions").update({
                "status": "CLOSED", "last_price": close, "last_checked_date": check_date,
                "closed_at": datetime.now(timezone.utc).isoformat(), "exit_price": stop,
                "exit_reason": "STOP", "gross_pnl": gross, "net_pnl": net,
                "return_pct": net / max(entry * qty, 1) * 100.0,
            }).eq("id", position_id).execute()
            client.table("lab_paper_events").insert({
                "position_id": position_id, "event_type": "STOP", "price": stop,
                "old_stop": stop, "note": "Conservative stop-first lifecycle update.",
            }).execute()
            updated += 1
            continue

        if tp2 is not None and high >= tp2:
            gross = (tp2 - entry) * qty
            net = gross - float(p.get("commission_entry") or COMMISSION) - COMMISSION
            client.table("lab_paper_positions").update({
                "status": "CLOSED", "last_price": close, "last_checked_date": check_date,
                "closed_at": datetime.now(timezone.utc).isoformat(), "exit_price": tp2,
                "exit_reason": "TP2", "gross_pnl": gross, "net_pnl": net,
                "return_pct": net / max(entry * qty, 1) * 100.0,
            }).eq("id", position_id).execute()
            client.table("lab_paper_events").insert({
                "position_id": position_id, "event_type": "TP2", "price": tp2,
                "note": "Paper target 2 reached.",
            }).execute()
            updated += 1
            continue

        if status == "OPEN" and tp1 is not None and high >= tp1:
            new_stop = max(entry, stop or entry)
            client.table("lab_paper_positions").update({
                "status": "TP1_HIT", "stop_current": new_stop,
                "tp1_hit_at": datetime.now(timezone.utc).isoformat(),
                "last_price": close, "last_checked_date": check_date,
            }).eq("id", position_id).execute()
            client.table("lab_paper_events").insert({
                "position_id": position_id, "event_type": "TP1", "price": tp1,
                "old_stop": stop, "new_stop": new_stop,
                "note": "TP1 reached; paper stop moved to break-even.",
            }).execute()
            updated += 1
        else:
            client.table("lab_paper_positions").update({
                "last_price": close, "last_checked_date": check_date,
            }).eq("id", position_id).execute()
    return updated


def _decision_state(strategy_score: float, trigger: str, paper_policy: dict, dq: dict, benchmark: bool) -> str:
    if benchmark:
        return "BENCHMARK"
    if dq.get("status") == "RED":
        return "BLOCKED_DATA"
    if strategy_score < 55:
        return "WATCH"
    if paper_policy.get("eligible"):
        return "CONFIRMED"
    if strategy_score < 65:
        return "NEAR_SETUP"
    if str(trigger).upper() != "CONFIRMED":
        return "PRE_BUY"
    return "PRE_BUY"


def main() -> int:
    if not os.getenv("SUPABASE_URL") or not os.getenv("SUPABASE_SECRET_KEY"):
        print("Supabase secrets missing; no opportunity feed persisted")
        return 2

    client = get_supabase_client()
    watch_threshold = float(os.getenv("LAB_WATCH_SCORE", "50"))
    lab_max_position = float(os.getenv("LAB_MAX_POSITION_USD", "10000"))
    max_new_buys = int(os.getenv("LAB_MAX_NEW_BUYS", "12"))
    max_active = int(os.getenv("LAB_MAX_ACTIVE_POSITIONS", "80"))
    max_per_strategy = int(os.getenv("LAB_MAX_ACTIVE_PER_STRATEGY", "24"))

    written = watch_written = opened = lifecycle_updates = 0
    now = datetime.now(timezone.utc)
    candidates: list[dict] = []

    try:
        stale_before = (now - timedelta(days=3)).isoformat()
        client.table("lab_watchlist").update({"active": False}).lt("last_seen_at", stale_before).eq("active", True).execute()
    except Exception as exc:
        print(f"lab_watchlist stale cleanup warning: {exc}")

    try:
        open_positions = client.table("lab_paper_positions").select("*").in_("status", ["OPEN", "TP1_HIT"]).execute().data or []
    except Exception:
        open_positions = []

    try:
        spy_prices = download_prices(MarketDataRequest(symbol="SPY", start="2024-01-01"))
        market_regime = regime_v1(enrich_prices(spy_prices))
    except Exception as exc:
        market_regime = {"state": "UNKNOWN", "error": str(exc)}

    print(f"market_regime={market_regime.get('state', 'UNKNOWN')}")

    for symbol in symbols():
        try:
            prices = download_prices(MarketDataRequest(symbol=symbol, start="2024-01-01"))
            x = enrich_prices(prices)
            if len(x) < 220:
                continue
            last = x.iloc[-1]
            signal_day = x.index[-1].date()
            signal_date = signal_day.isoformat()
            catalyst = _news_and_calendar(symbol)
            lifecycle_updates += _update_existing_positions(client, symbol, last, signal_date)

            for strategy in PRICE_STRATEGIES:
                strategy_score = float(generate_scores(strategy, prices).iloc[-1])
                if strategy_score < watch_threshold:
                    continue

                price = float(last.Close)
                atr = _safe(last.atr14)
                if atr is None or atr <= 0:
                    continue

                ideal_entry, trigger, setup_note = _entry_and_trigger(strategy, last)

                # Research paper execution is deliberately at the observable market
                # close. Keep ideal_entry separately for setup diagnostics. The old
                # code mixed SMA/high20 ideal entry with a stop built from market
                # price, which created false STOP_INVALID / BLOCKED_DATA records.
                execution_entry = price
                risk_per_share = 2.0 * atr
                stop = execution_entry - risk_per_share
                tp1 = execution_entry + 1.5 * risk_per_share
                tp2 = execution_entry + 2.5 * risk_per_share
                max_buy = ideal_entry + 0.8 * atr
                distance_pct = ((price - ideal_entry) / ideal_entry * 100.0) if ideal_entry else None

                qty = risk_based_qty(entry=execution_entry, stop=stop, max_position=lab_max_position)
                if qty <= 0 and 0 < execution_entry <= lab_max_position:
                    qty = 1
                capital = qty * execution_entry
                loss_max = qty * max(execution_entry - stop, 0) + COMMISSION
                rr_net_tp1 = net_rr(entry=execution_entry, stop=stop, target=tp1, qty=qty)
                rr_net_tp2 = net_rr(entry=execution_entry, stop=stop, target=tp2, qty=qty)
                earnings_days = earnings_distance_days(catalyst.get("earnings_date"), signal_day)

                dq = data_quality_check(
                    price=price, entry=execution_entry, max_buy=max(max_buy, execution_entry),
                    stop=stop, tp1=tp1, tp2=tp2, atr=atr,
                    sma50=_safe(last.sma50), sma200=_safe(last.sma200),
                )
                trade_score_value = trade_score(
                    strategy_score=strategy_score, price=price, entry=ideal_entry,
                    max_buy=max_buy, atr=atr, rr_net=rr_net_tp2,
                    trigger=trigger, earnings_days=earnings_days,
                )

                # Keep the old strict gate for diagnosis. It no longer decides alone
                # whether a research paper trade may be opened.
                strict_trade_gate = trade_eligibility(
                    data_quality=dq, trigger=trigger, price=price, max_buy=max_buy,
                    rr_net=rr_net_tp2, earnings_days=earnings_days, event_driven=False,
                )
                paper_policy = classify_paper_tier(
                    strategy_score=strategy_score,
                    trade_score=trade_score_value,
                    trigger=trigger,
                    data_quality=dq,
                    rr_net=rr_net_tp2,
                    price=price,
                    max_buy=max_buy,
                    atr=atr,
                    earnings_days=earnings_days,
                    qty=qty,
                )
                preliminary_portfolio = lab_portfolio_fit(
                    symbol=symbol, strategy=strategy, open_positions=open_positions,
                    opened_this_run=0, max_new_buys=max_new_buys,
                    max_active_positions=max_active,
                    max_active_per_strategy=max_per_strategy,
                )
                state = _decision_state(
                    strategy_score, trigger, paper_policy, dq, symbol in BENCHMARK_ETFS,
                )

                details = {
                    "generated_at": now.isoformat(),
                    "decision_model": "LAB_GATEKEEPER_V2_RESEARCH",
                    "strategy_score": strategy_score,
                    "trade_score": trade_score_value,
                    "paper_tier": paper_policy.get("tier"),
                    "paper_policy": paper_policy,
                    "strict_trade_eligibility": strict_trade_gate,
                    "trade_eligibility": strict_trade_gate,
                    "portfolio_eligibility": preliminary_portfolio,
                    "data_quality": dq,
                    "market_regime": market_regime,
                    "trigger": trigger,
                    "setup_note": setup_note,
                    "ideal_entry": ideal_entry,
                    "execution_entry": execution_entry,
                    "distance_to_entry_pct": distance_pct,
                    "max_buy": max_buy,
                    "tp1": tp1,
                    "qty": qty,
                    "capital": capital,
                    "loss_max": loss_max,
                    "max_position_policy": lab_max_position,
                    "legacy_max_position_policy": MAX_POSITION_USD,
                    "commission_per_side": COMMISSION,
                    "estimated_slippage_bps": ESTIMATED_SLIPPAGE_BPS,
                    "execution_cost_model": "ESTIMATED_COMMISSION_PLUS_SLIPPAGE",
                    "rr_net_tp1": rr_net_tp1,
                    "rr_net_tp2": rr_net_tp2,
                    "sma20": _safe(last.sma20),
                    "sma50": _safe(last.sma50),
                    "sma200": _safe(last.sma200),
                    "rsi14": _safe(last.rsi14),
                    "atr14": atr,
                    "relative_volume": _safe(last.relative_volume),
                    "earnings_date": catalyst.get("earnings_date"),
                    "days_to_earnings": earnings_days,
                    "news": catalyst.get("news", []),
                    "catalyst_quality": catalyst.get("catalyst_quality"),
                    "warning": "Research-only paper execution. News enrichment must be verified before any real trade.",
                }
                payload = {
                    "symbol": symbol, "strategy": strategy, "signal_date": signal_date,
                    "score": strategy_score, "price": price,
                    "proposed_entry": execution_entry, "proposed_stop": stop,
                    "proposed_target": tp2, "status": state, "details": details,
                }
                client.table("lab_paper_signals").upsert(
                    payload, on_conflict="symbol,strategy,signal_date"
                ).execute()
                written += 1

                alert_type, alert_price = _alert_type(state, trigger, price, execution_entry, max_buy)
                _upsert_watchlist(client, {
                    "symbol": symbol, "strategy": strategy, "market": "USA", "status": state,
                    "score": strategy_score, "price": price, "entry": execution_entry,
                    "max_buy": max_buy, "stop": stop, "tp1": tp1, "tp2": tp2,
                    "trigger": trigger, "alert_type": alert_type, "alert_price": alert_price,
                    "distance_to_entry_pct": distance_pct, "reason": setup_note,
                    "signal_date": signal_date, "last_seen_at": now.isoformat(), "active": True,
                    "details": details,
                })
                watch_written += 1

                if paper_policy.get("eligible") and symbol not in BENCHMARK_ETFS:
                    candidates.append({
                        "symbol": symbol,
                        "strategy": strategy,
                        "signal_date": signal_date,
                        "price": execution_entry,
                        "stop": stop,
                        "tp1": tp1,
                        "tp2": tp2,
                        "qty": qty,
                        "tier": paper_policy.get("tier"),
                        "strategy_score": strategy_score,
                        "trade_score": trade_score_value,
                        "details": details,
                    })
        except Exception as exc:
            print(f"{symbol}: {exc}")

    # Rank after the full scan so paper capacity is not consumed simply by the
    # alphabetical order of LAB_SYMBOLS. A first, then B/C, then score quality.
    tier_rank = {"A": 0, "B": 1, "C": 2}
    candidates.sort(key=lambda r: (
        tier_rank.get(str(r.get("tier") or ""), 9),
        -float(r.get("strategy_score") or 0),
        -float(r.get("trade_score") or 0),
    ))

    for candidate in candidates:
        if opened >= max_new_buys:
            break
        portfolio_gate = lab_portfolio_fit(
            symbol=candidate["symbol"], strategy=candidate["strategy"],
            open_positions=open_positions, opened_this_run=opened,
            max_new_buys=max_new_buys, max_active_positions=max_active,
            max_active_per_strategy=max_per_strategy,
        )
        if not portfolio_gate.get("eligible"):
            continue

        details = dict(candidate["details"])
        details["portfolio_eligibility"] = portfolio_gate
        if _open_position_if_needed(
            client, candidate["symbol"], candidate["strategy"], candidate["signal_date"],
            candidate["price"], candidate["stop"], candidate["tp1"], candidate["tp2"],
            candidate["qty"], details,
        ):
            opened += 1
            open_positions.append({
                "symbol": candidate["symbol"], "strategy": candidate["strategy"], "status": "OPEN"
            })
            client.table("lab_paper_signals").update({
                "status": "PAPER_OPEN", "details": details,
            }).eq("symbol", candidate["symbol"]).eq("strategy", candidate["strategy"]).eq(
                "signal_date", candidate["signal_date"]
            ).execute()
            _upsert_watchlist(client, {
                "symbol": candidate["symbol"], "strategy": candidate["strategy"],
                "market": "USA", "status": "PAPER_OPEN",
                "score": candidate["strategy_score"], "price": candidate["price"],
                "entry": candidate["price"], "stop": candidate["stop"],
                "tp1": candidate["tp1"], "tp2": candidate["tp2"],
                "trigger": details.get("trigger"), "alert_type": "PAPER_OPEN",
                "alert_price": candidate["price"], "signal_date": candidate["signal_date"],
                "last_seen_at": now.isoformat(), "active": True,
                "reason": details.get("setup_note"), "max_buy": details.get("max_buy"),
                "distance_to_entry_pct": details.get("distance_to_entry_pct"),
                "details": details,
            })

    print(
        f"opportunity rows={written} watchlist={watch_written} candidates={len(candidates)} "
        f"paper_opened={opened} lifecycle_updates={lifecycle_updates} "
        f"regime={market_regime.get('state', 'UNKNOWN')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
