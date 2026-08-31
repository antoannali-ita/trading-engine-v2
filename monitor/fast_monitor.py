from __future__ import annotations

import argparse
import json
import os
import sqlite3
from datetime import datetime, time, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import yfinance as yf
import yaml

from notifications.whatsapp_client import send_whatsapp
from orchestrator.persistence import record_engine_signal
from orchestrator.runtime import RunTracker, record_notification
from state.state_manager import StateManager


MARKET_HOURS = {
    "usa": {
        "timezone": "America/New_York",
        "open": time(9, 30),
        "close": time(16, 0),
    },
    "italy": {
        "timezone": "Europe/Rome",
        "open": time(9, 0),
        "close": time(17, 30),
    },
}

MAX_QUOTE_AGE_MINUTES = 20
WHATSAPP_DECISIONS = {"PRE_BUY", "PRE_BUY_HIGH", "BUY_NOW", "BUY_LIMIT", "SHADOW_BUY", "BUY"}


def load_cfg(market):
    root = Path(__file__).resolve().parents[1]
    return {
        **(yaml.safe_load((root / "config/common.yaml").read_text()) or {}),
        **(yaml.safe_load((root / f"config/{market}.yaml").read_text()) or {}),
    }


def latest_selected(db_path):
    p = Path(db_path)
    if not p.exists():
        return []
    with sqlite3.connect(p) as con:
        row = con.execute("SELECT run_id FROM runs ORDER BY run_ts DESC LIMIT 1").fetchone()
        if not row:
            return []
        rows = con.execute(
            "SELECT payload_json FROM candidate_snapshots WHERE run_id=? AND selected=1",
            (row[0],),
        ).fetchall()
    out = []
    for (s,) in rows:
        try:
            out.append(json.loads(s))
        except Exception:
            pass
    return out


def market_session_open(market: str, now: datetime | None = None) -> bool:
    rule = MARKET_HOURS[market]
    tz = ZoneInfo(rule["timezone"])
    local_now = (now or datetime.now(timezone.utc)).astimezone(tz)
    if local_now.weekday() >= 5:
        return False
    local_time = local_now.time().replace(tzinfo=None)
    return rule["open"] <= local_time <= rule["close"]


def current_quote(ticker: str, market: str):
    y = ticker if market == "usa" or "." in ticker else ticker + ".MI"
    try:
        h = yf.Ticker(y).history(period="1d", interval="5m", auto_adjust=True, prepost=False)
        close = h["Close"].dropna() if not h.empty else None
        if close is None or close.empty:
            return None, None
        ts = close.index[-1]
        if hasattr(ts, "to_pydatetime"):
            ts = ts.to_pydatetime()
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return float(close.iloc[-1]), ts.astimezone(timezone.utc)
    except Exception as exc:
        print(f"QUOTE WARN {market.upper()} {ticker}: {type(exc).__name__}: {exc}")
        return None, None


def quote_is_fresh(quote_ts: datetime | None, now: datetime | None = None) -> bool:
    if quote_ts is None:
        return False
    now_utc = now or datetime.now(timezone.utc)
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)
    age_seconds = (now_utc.astimezone(timezone.utc) - quote_ts.astimezone(timezone.utc)).total_seconds()
    return 0 <= age_seconds <= MAX_QUOTE_AGE_MINUTES * 60


def _candidate_decision(candidate: dict) -> str:
    for key in ("decision", "display_state", "status", "state"):
        value = str(candidate.get(key) or "").upper().strip().replace("-", "_").replace(" ", "_")
        if value:
            return value
    return ""


def should_notify_fast_whatsapp(candidate: dict, state: str) -> bool:
    return _candidate_decision(candidate) in WHATSAPP_DECISIONS and state == "IN_BUY_ZONE"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--market", choices=["usa", "italy"], required=True)
    a = p.parse_args()
    market = a.market
    cfg = load_cfg(market)
    engine_id = f"FAST_{market.upper()}"
    run_id = f"fast-{market}-{os.getenv('GITHUB_RUN_ID') or datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    tracker = RunTracker.start(engine_id, market, "FAST", run_id)
    processed = signals_found = 0

    try:
        if not market_session_open(market):
            print(f"SKIP {market.upper()}: regular market session closed")
            tracker.event("SESSION_CLOSED", "Regular market session closed")
            tracker.finish("SUCCESS", records_processed=0, signals_found=0)
            return

        sm = StateManager(f"data/fast_state_{market}.json")
        for c in latest_selected(cfg["db_path"]):
            t = c.get("ticker")
            if not t:
                continue
            px, quote_ts = current_quote(t, market)
            if px is None:
                continue
            if not quote_is_fresh(quote_ts):
                print(f"SKIP STALE {market.upper()} {t}: quote_ts={quote_ts}")
                continue

            processed += 1
            low = c.get("buy_zone_low")
            high = c.get("buy_zone_high")
            maxb = c.get("max_buy")
            stop = c.get("stop")
            state = "NORMAL"
            if stop is not None and px <= stop:
                state = "STOP"
            elif low is not None and high is not None and low <= px <= high:
                state = "IN_BUY_ZONE"
            elif maxb is not None and px > maxb:
                state = "ABOVE_MAX_BUY"

            key = f"{market}:{t}:fast_state"
            previous_state = sm.state.get(key)
            actionable = should_notify_fast_whatsapp(c, state)
            signal_id = record_engine_signal(
                run_id=run_id,
                engine_id=engine_id,
                engine="FAST",
                strategy="FAST_INTRADAY",
                market=market,
                ticker=t,
                signal_type=state,
                decision=state,
                score=c.get("score_total") or c.get("score"),
                price=px,
                is_actionable=actionable,
                metadata={
                    "previous_state": previous_state,
                    "core_decision": _candidate_decision(c),
                    "buy_zone_low": low,
                    "buy_zone_high": high,
                    "max_buy": maxb,
                    "stop": stop,
                    "quote_ts": quote_ts.isoformat() if quote_ts else None,
                },
            )
            if actionable:
                signals_found += 1

            if key not in sm.state:
                print(f"INIT {t} {px:.2f} {state}")
                sm.set(key, state)
                continue

            if sm.changed(key, state):
                print(t, px, f"{previous_state}->{state}")
                sm.set(key, state)
                if should_notify_fast_whatsapp(c, state):
                    if cfg.get("send_whatsapp"):
                        try:
                            decision = _candidate_decision(c)
                            sent = bool(send_whatsapp(f"{market.upper()} {t}: {decision} | {previous_state} -> {state} @ {px:.2f}"))
                            record_notification(
                                run_id=run_id,
                                signal_id=signal_id,
                                ticker=t,
                                event_type=state,
                                channel="WHATSAPP",
                                status="SENT" if sent else "FAILED",
                                provider="CALLMEBOT",
                                payload={"core_decision": decision, "previous_state": previous_state, "state": state, "price": px},
                            )
                        except Exception as exc:
                            record_notification(
                                run_id=run_id,
                                signal_id=signal_id,
                                ticker=t,
                                event_type=state,
                                channel="WHATSAPP",
                                status="FAILED",
                                provider="CALLMEBOT",
                                error_message=f"{type(exc).__name__}: {exc}",
                            )
                            raise
                    else:
                        record_notification(
                            run_id=run_id,
                            signal_id=signal_id,
                            ticker=t,
                            event_type=state,
                            channel="WHATSAPP",
                            status="SKIPPED",
                            provider="CALLMEBOT",
                            payload={"reason": "send_whatsapp disabled"},
                        )

        tracker.finish("SUCCESS", records_processed=processed, signals_found=signals_found)
    except Exception as exc:
        tracker.event("FAST_ERROR", str(exc), severity="ERROR")
        tracker.finish("FAILED", records_processed=processed, signals_found=signals_found, error_message=f"{type(exc).__name__}: {exc}"[:4000])
        raise


if __name__ == "__main__":
    main()
