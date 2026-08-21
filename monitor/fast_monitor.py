from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, time, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import yfinance as yf
import yaml

from notifications.whatsapp_client import send_whatsapp
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
    """Return True only during the regular cash session for the requested market.

    Time-zone conversion is DST-aware. Exchange holidays are also protected by the
    fresh-quote check below: on a holiday yfinance has no fresh regular-session bar.
    """
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
        # prepost=False is intentional: operational alerts use regular-session prices only.
        h = yf.Ticker(y).history(
            period="1d",
            interval="5m",
            auto_adjust=True,
            prepost=False,
        )
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


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--market", choices=["usa", "italy"], required=True)
    a = p.parse_args()
    cfg = load_cfg(a.market)

    # Do not turn yesterday's close (or pre-market data) into a fresh operational alert.
    if not market_session_open(a.market):
        print(f"SKIP {a.market.upper()}: regular market session closed")
        return

    sm = StateManager(f"data/fast_state_{a.market}.json")
    for c in latest_selected(cfg["db_path"]):
        t = c.get("ticker")
        px, quote_ts = current_quote(t, a.market)
        if px is None:
            continue
        if not quote_is_fresh(quote_ts):
            print(f"SKIP STALE {a.market.upper()} {t}: quote_ts={quote_ts}")
            continue

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

        key = f"{a.market}:{t}:fast_state"

        # Missing cache/state must never create a false 'new' signal after a runner restart.
        if key not in sm.state:
            print(f"INIT {t} {px:.2f} {state}")
            sm.set(key, state)
            continue

        if sm.changed(key, state):
            previous_state = sm.state.get(key)
            print(t, px, f"{previous_state}->{state}")
            sm.set(key, state)
            if cfg.get("send_whatsapp") and state in {"STOP", "IN_BUY_ZONE"}:
                send_whatsapp(
                    f"{a.market.upper()} {t}: {previous_state} -> {state} @ {px:.2f}"
                )


if __name__ == "__main__":
    main()
