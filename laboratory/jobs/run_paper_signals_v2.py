from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

LAB_ROOT = Path(__file__).resolve().parents[1]
SRC = LAB_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

import run_paper_signals as base
from lab.indicators import enrich_prices
from lab.market_data import MarketDataRequest, download_prices
from lab.strategies import STRATEGIES, generate_scores

COOLDOWN_SESSIONS = 7
PRICE_STRATEGIES = [name for name, spec in STRATEGIES.items() if spec.generator is not None]


def _safe(v):
    return base._safe(v)


def _strategy_family(strategy: str) -> tuple[str, str]:
    if strategy.startswith("short_term_reversal_rsi"):
        return "short_term_reversal", strategy.rsplit("_", 1)[-1].upper()
    if strategy == "defensive_low_vol":
        return "defensive_low_vol", "BASE"
    return strategy, "BASE"


def _entry_and_trigger(strategy: str, last) -> tuple[float, str, str, dict]:
    price = float(last.Close)
    sma20, sma50, sma200 = _safe(last.sma20), _safe(last.sma50), _safe(last.sma200)
    high20 = _safe(last.high20)
    rsi = _safe(last.rsi14)
    ret1 = _safe(last.ret_1d)
    diagnostics: dict = {}

    if strategy == "trend_continuation":
        entry = sma50 or sma20 or price
        base_ok = sma50 is not None and sma200 is not None and price > sma50 > sma200
        buffer_ok = sma50 is not None and sma200 is not None and price > (sma50 * 1.005) and sma50 > sma200
        diagnostics.update({
            "trend_buffer_0_confirmed": bool(base_ok),
            "trend_buffer_0_5pct_confirmed": bool(buffer_ok),
            "trend_buffer_primary": "buffer_0",
            "trend_buffer_shadow": "buffer_0_5pct",
        })
        return entry, "CONFIRMED" if base_ok else "WAITING", "Pullback/continuazione sopra SMA50>SMA200", diagnostics

    if strategy == "cross_sectional_momentum":
        entry = high20 or price
        confirmed = high20 is not None and price >= high20
        return entry, "CONFIRMED" if confirmed else "WAITING", "Breakout del massimo 20 giorni", diagnostics

    if strategy.startswith("short_term_reversal_rsi"):
        threshold = 35.0 if strategy.endswith("rsi35") else 45.0
        entry = price
        confirmed = (ret1 is not None and ret1 > 0) and (rsi is not None and rsi < threshold)
        diagnostics.update({"reversal_rsi_threshold": threshold, "reversal_score_depth_points": 20.0})
        return entry, "CONFIRMED" if confirmed else "WAITING", f"Stabilizzazione dopo eccesso ribassista RSI<{threshold:.0f}", diagnostics

    entry = sma20 or price
    confirmed = sma200 is not None and price > sma200
    return entry, "CONFIRMED" if confirmed else "WAITING", "Low-vol sopra trend strutturale", diagnostics


def _cross_sectional_scores(frames: dict[str, pd.DataFrame]) -> dict[str, dict]:
    rows = []
    for symbol, x in frames.items():
        if x.empty:
            continue
        last = x.iloc[-1]
        r20, r60, r120 = _safe(last.ret_20d), _safe(last.ret_60d), _safe(last.ret_120d)
        if None in (r20, r60, r120):
            continue
        rows.append({"symbol": symbol, "ret20": r20, "ret60": r60, "ret120": r120})
    if len(rows) < 5:
        return {}
    df = pd.DataFrame(rows).set_index("symbol")
    df["pct20"] = df["ret20"].rank(pct=True) * 100.0
    df["pct60"] = df["ret60"].rank(pct=True) * 100.0
    df["pct120"] = df["ret120"].rank(pct=True) * 100.0
    df["score"] = df["pct20"] * 0.30 + df["pct60"] * 0.35 + df["pct120"] * 0.35
    out = {}
    for symbol, row in df.iterrows():
        out[symbol] = {
            "score": float(row["score"]),
            "pct20": float(row["pct20"]),
            "pct60": float(row["pct60"]),
            "pct120": float(row["pct120"]),
            "universe_n": int(len(df)),
        }
    return out


def _business_sessions_between(start: str, end: str) -> int:
    try:
        s = pd.Timestamp(start).normalize()
        e = pd.Timestamp(end).normalize()
        if e <= s:
            return 0
        return max(len(pd.bdate_range(s, e)) - 1, 0)
    except Exception:
        return COOLDOWN_SESSIONS


def _cooldown_ok(client, symbol: str, strategy: str, signal_date: str) -> tuple[bool, dict]:
    try:
        response = (
            client.table("lab_paper_positions")
            .select("source_signal_date,status,closed_at,opened_at")
            .eq("symbol", symbol)
            .eq("strategy", strategy)
            .order("source_signal_date", desc=True)
            .limit(1)
            .execute()
        )
        if not response.data:
            return True, {"cooldown_sessions": COOLDOWN_SESSIONS, "prior_position": False}
        prior = response.data[0]
        prior_date = prior.get("source_signal_date") or prior.get("opened_at")
        if not prior_date:
            return True, {"cooldown_sessions": COOLDOWN_SESSIONS, "prior_position": True, "prior_date": None}
        sessions = _business_sessions_between(str(prior_date)[:10], signal_date)
        active = str(prior.get("status") or "").upper() in {"OPEN", "TP1_HIT"}
        ok = (not active) and sessions >= COOLDOWN_SESSIONS
        return ok, {
            "cooldown_sessions": COOLDOWN_SESSIONS,
            "prior_position": True,
            "prior_status": prior.get("status"),
            "prior_date": str(prior_date)[:10],
            "sessions_since_prior": sessions,
            "cooldown_pass": ok,
        }
    except Exception as exc:
        print(f"cooldown warning {symbol}/{strategy}: {exc}")
        return True, {"cooldown_sessions": COOLDOWN_SESSIONS, "cooldown_check": "ERROR_FAIL_OPEN", "error": str(exc)}


def main() -> int:
    if not os.getenv("SUPABASE_URL") or not os.getenv("SUPABASE_SECRET_KEY"):
        print("Supabase secrets missing; no opportunity feed persisted")
        return 2

    client = base.get_supabase_client()
    watch_threshold = float(os.getenv("LAB_WATCH_SCORE", "50"))
    lab_max_position = base._runtime_max_position()
    max_new_buys = int(os.getenv("LAB_MAX_NEW_BUYS", "12"))
    max_active = int(os.getenv("LAB_MAX_ACTIVE_POSITIONS", "80"))
    max_per_strategy = int(os.getenv("LAB_MAX_ACTIVE_PER_STRATEGY", "24"))
    now = datetime.now(timezone.utc)
    configured_symbols = base.symbols()
    candidates: list[dict] = []
    written = watch_written = opened = lifecycle_updates = 0
    failures = 0

    try:
        open_positions = client.table("lab_paper_positions").select("*").in_("status", ["OPEN", "TP1_HIT"]).execute().data or []
    except Exception as exc:
        print(f"FATAL: cannot read active paper positions: {exc}")
        return 1

    try:
        spy_prices = download_prices(MarketDataRequest(symbol="SPY", start="2024-01-01"))
        market_regime = base.regime_v1(enrich_prices(spy_prices))
    except Exception as exc:
        market_regime = {"state": "UNKNOWN", "error": str(exc)}

    frames: dict[str, pd.DataFrame] = {}
    raw_prices: dict[str, pd.DataFrame] = {}
    for symbol in configured_symbols:
        try:
            prices = download_prices(MarketDataRequest(symbol=symbol, start="2024-01-01"))
            x = enrich_prices(prices)
            if len(x) < 220:
                continue
            raw_prices[symbol] = prices
            frames[symbol] = x
        except Exception as exc:
            failures += 1
            print(f"prefetch {symbol}: {exc}")

    xs_scores = _cross_sectional_scores(frames)
    print(f"market_regime={market_regime.get('state', 'UNKNOWN')} cross_sectional_universe={len(xs_scores)}")

    for symbol, x in frames.items():
        try:
            prices = raw_prices[symbol]
            last = x.iloc[-1]
            signal_day = x.index[-1].date()
            signal_date = signal_day.isoformat()
            catalyst = base._news_and_calendar(symbol)
            lifecycle_updates += base._update_existing_positions(client, symbol, last, signal_date)

            for strategy in PRICE_STRATEGIES:
                xs_meta = None
                if strategy == "cross_sectional_momentum":
                    xs_meta = xs_scores.get(symbol)
                    if not xs_meta:
                        continue
                    strategy_score = float(xs_meta["score"])
                else:
                    strategy_score = float(generate_scores(strategy, prices).iloc[-1])
                if strategy_score < watch_threshold:
                    continue

                price = float(last.Close)
                atr = _safe(last.atr14)
                if atr is None or atr <= 0:
                    continue

                ideal_entry, trigger, setup_note, experiment_diag = _entry_and_trigger(strategy, last)
                execution_entry = price
                risk_per_share = 2.0 * atr
                stop = execution_entry - risk_per_share
                tp1 = execution_entry + 1.5 * risk_per_share
                tp2 = execution_entry + 2.5 * risk_per_share
                max_buy = ideal_entry + 0.8 * atr
                distance_pct = ((price - ideal_entry) / ideal_entry * 100.0) if ideal_entry else None

                qty = base.risk_based_qty(entry=execution_entry, stop=stop, max_position=lab_max_position)
                if qty <= 0 and 0 < execution_entry <= lab_max_position:
                    qty = 1
                capital = qty * execution_entry
                loss_max = qty * max(execution_entry - stop, 0) + base.COMMISSION
                rr_net_tp1 = base.net_rr(entry=execution_entry, stop=stop, target=tp1, qty=qty)
                rr_net_tp2 = base.net_rr(entry=execution_entry, stop=stop, target=tp2, qty=qty)
                earnings_days = base.earnings_distance_days(catalyst.get("earnings_date"), signal_day)

                dq = base.data_quality_check(
                    price=price, entry=execution_entry, max_buy=max(max_buy, execution_entry),
                    stop=stop, tp1=tp1, tp2=tp2, atr=atr,
                    sma50=_safe(last.sma50), sma200=_safe(last.sma200),
                )
                trade_score_value = base.trade_score(
                    strategy_score=strategy_score, price=price, entry=ideal_entry,
                    max_buy=max_buy, atr=atr, rr_net=rr_net_tp2,
                    trigger=trigger, earnings_days=earnings_days,
                )
                strict_trade_gate = base.trade_eligibility(
                    data_quality=dq, trigger=trigger, price=price, max_buy=max_buy,
                    rr_net=rr_net_tp2, earnings_days=earnings_days, event_driven=False,
                )
                paper_policy = base.classify_paper_tier(
                    strategy_score=strategy_score, trade_score=trade_score_value,
                    trigger=trigger, data_quality=dq, rr_net=rr_net_tp2,
                    price=price, max_buy=max_buy, atr=atr,
                    earnings_days=earnings_days, qty=qty,
                )
                preliminary_portfolio = base.lab_portfolio_fit(
                    symbol=symbol, strategy=strategy, open_positions=open_positions,
                    opened_this_run=0, max_new_buys=max_new_buys,
                    max_active_positions=max_active, max_active_per_strategy=max_per_strategy,
                )
                state = base._decision_state(strategy_score, trigger, paper_policy, dq, symbol in base.BENCHMARK_ETFS)
                family, variant = _strategy_family(strategy)
                risk_key = f"EQUITY:{symbol}"
                tier = paper_policy.get("tier") or "N/D"

                details = {
                    "generated_at": now.isoformat(),
                    "decision_model": "LAB_GATEKEEPER_V2_RESEARCH",
                    "strategy_score": strategy_score,
                    "trade_score": trade_score_value,
                    "strategy_family": family,
                    "strategy_variant": variant,
                    "paper_tier": tier,
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
                    "commission_per_side": base.COMMISSION,
                    "estimated_slippage_bps": base.ESTIMATED_SLIPPAGE_BPS,
                    "execution_cost_model": "ESTIMATED_COMMISSION_PLUS_SLIPPAGE",
                    "rr_net_tp1": rr_net_tp1,
                    "rr_net_tp2": rr_net_tp2,
                    "sma20": _safe(last.sma20), "sma50": _safe(last.sma50), "sma200": _safe(last.sma200),
                    "rsi14": _safe(last.rsi14), "atr14": atr, "relative_volume": _safe(last.relative_volume),
                    "earnings_date": catalyst.get("earnings_date"), "days_to_earnings": earnings_days,
                    "news": catalyst.get("news", []), "catalyst_quality": catalyst.get("catalyst_quality"),
                    "risk_key": risk_key,
                    "experiment_key": f"{symbol}:{strategy}:{tier}",
                    "cooldown_sessions": COOLDOWN_SESSIONS,
                    "warning": "Research-only paper execution. No automatic Production promotion.",
                    **experiment_diag,
                }
                if xs_meta:
                    details["cross_sectional"] = xs_meta
                    details["cross_sectional_method"] = "SAME_DATE_UNIVERSE_PERCENTILE"

                payload = {
                    "symbol": symbol, "strategy": strategy, "signal_date": signal_date,
                    "score": strategy_score, "price": price,
                    "proposed_entry": execution_entry, "proposed_stop": stop,
                    "proposed_target": tp2, "status": state, "details": details,
                }
                client.table("lab_paper_signals").upsert(payload, on_conflict="symbol,strategy,signal_date").execute()
                written += 1

                alert_type, alert_price = base._alert_type(state, trigger, price, execution_entry, max_buy)
                base._upsert_watchlist(client, {
                    "symbol": symbol, "strategy": strategy, "market": "USA", "status": state,
                    "score": strategy_score, "price": price, "entry": execution_entry,
                    "max_buy": max_buy, "stop": stop, "tp1": tp1, "tp2": tp2,
                    "trigger": trigger, "alert_type": alert_type, "alert_price": alert_price,
                    "distance_to_entry_pct": distance_pct, "reason": setup_note,
                    "signal_date": signal_date, "last_seen_at": now.isoformat(), "active": True,
                    "details": details,
                })
                watch_written += 1

                if paper_policy.get("eligible") and symbol not in base.BENCHMARK_ETFS:
                    candidates.append({
                        "symbol": symbol, "strategy": strategy, "signal_date": signal_date,
                        "price": execution_entry, "stop": stop, "tp1": tp1, "tp2": tp2,
                        "qty": qty, "tier": tier, "strategy_score": strategy_score,
                        "trade_score": trade_score_value, "details": details,
                    })
        except Exception as exc:
            failures += 1
            print(f"{symbol}: {exc}")

    tier_rank = {"A": 0, "B": 1, "C": 2}
    candidates.sort(key=lambda r: (
        tier_rank.get(str(r.get("tier") or ""), 9),
        -float(r.get("strategy_score") or 0),
        -float(r.get("trade_score") or 0),
    ))

    for candidate in candidates:
        if opened >= max_new_buys:
            break
        portfolio_gate = base.lab_portfolio_fit(
            symbol=candidate["symbol"], strategy=candidate["strategy"],
            open_positions=open_positions, opened_this_run=opened,
            max_new_buys=max_new_buys, max_active_positions=max_active,
            max_active_per_strategy=max_per_strategy,
        )
        if not portfolio_gate.get("eligible"):
            continue
        cooldown_ok, cooldown_detail = _cooldown_ok(
            client, candidate["symbol"], candidate["strategy"], candidate["signal_date"]
        )
        details = dict(candidate["details"])
        details["portfolio_eligibility"] = portfolio_gate
        details["cooldown"] = cooldown_detail
        if not cooldown_ok:
            client.table("lab_paper_signals").update({
                "status": "COOLDOWN", "details": details,
            }).eq("symbol", candidate["symbol"]).eq("strategy", candidate["strategy"]).eq(
                "signal_date", candidate["signal_date"]
            ).execute()
            continue

        if base._open_position_if_needed(
            client, candidate["symbol"], candidate["strategy"], candidate["signal_date"],
            candidate["price"], candidate["stop"], candidate["tp1"], candidate["tp2"],
            candidate["qty"], details,
        ):
            opened += 1
            open_positions.append({"symbol": candidate["symbol"], "strategy": candidate["strategy"], "status": "OPEN"})
            client.table("lab_paper_signals").update({"status": "PAPER_OPEN", "details": details}).eq(
                "symbol", candidate["symbol"]
            ).eq("strategy", candidate["strategy"]).eq("signal_date", candidate["signal_date"]).execute()

    print(
        f"V2 opportunity rows={written} watchlist={watch_written} candidates={len(candidates)} "
        f"paper_opened={opened} lifecycle_updates={lifecycle_updates} failures={failures} "
        f"regime={market_regime.get('state', 'UNKNOWN')}"
    )
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
