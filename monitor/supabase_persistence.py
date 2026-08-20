from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from supabase import create_client


WATCH_STATES = {
    "WATCH", "WAIT", "PRE-BUY", "PRE_BUY", "PRE_BUY_HIGH",
    "BUY LIMIT", "BUY_LIMIT", "BUY NOW", "BUY_NOW", "SHADOW_BUY",
}


def _client():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SECRET_KEY")
    if not url or not key:
        return None
    return create_client(url, key)


def _num(value: Any):
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: Any):
    try:
        if value is None or value == "":
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _pick(c: dict[str, Any], *keys: str):
    for key in keys:
        if key in c and c.get(key) is not None:
            return c.get(key)
    return None


def _state(*values: Any) -> str:
    for value in values:
        if value is not None:
            return str(value).strip().upper().replace("_", " ")
    return "N/D"


def _watch_alert(c: dict[str, Any]) -> tuple[str, float | None]:
    price = _num(_pick(c, "price", "last", "close"))
    entry = _num(_pick(c, "entry", "ideal_entry", "entry_price"))
    max_buy = _num(_pick(c, "max_buy", "max_entry"))
    trigger = _state(_pick(c, "trigger", "trigger_state"))

    if entry is not None:
        if price is not None and price <= entry:
            return "ENTRY_REACHED", entry
        return "ENTRY_APPROACH", entry
    if max_buy is not None:
        return "MAX_BUY_MONITOR", max_buy
    if trigger not in {"N/D", ""}:
        return "TRIGGER_MONITOR", price
    return "PRICE_MONITOR", price


def _persist_watchlist(client, rows: list[dict[str, Any]], market: str) -> int:
    # Watchlist is a current-state projection. Historical signal detail remains in signals.
    try:
        client.table("watchlist").update({"active": False}).eq("market", market).eq("active", True).execute()
    except Exception as exc:
        print(f"WATCHLIST deactivate warning: {exc}")

    watch_rows: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc)
    for row in rows:
        state = _state(row.get("status"), row.get("decision"))
        decision = _state(row.get("decision"))
        if state not in WATCH_STATES and decision not in WATCH_STATES:
            continue
        raw = row.get("raw_data") if isinstance(row.get("raw_data"), dict) else {}
        alert_type, alert_price = _watch_alert({**raw, **row})
        reason = row.get("reason") or raw.get("reason") or raw.get("why") or raw.get("rationale") or ""
        watch_rows.append({
            "ticker": row["ticker"],
            "market": market,
            "status": row.get("status") or row.get("decision") or "WATCH",
            "alert_type": alert_type,
            "alert_price": alert_price,
            "reason": str(reason)[:4000],
            "source_signal_id": row["signal_id"],
            "created_at": now.isoformat(),
            "expires_at": (now + timedelta(days=30)).isoformat(),
            "active": True,
        })
    if watch_rows:
        client.table("watchlist").insert(watch_rows).execute()
    return len(watch_rows)


def _portfolio_positions_from_env() -> list[dict[str, Any]]:
    raw = os.getenv("PORTFOLIO_POSITIONS_JSON", "").strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"PORTFOLIO sync warning: invalid JSON ({exc})")
        return []
    if isinstance(data, dict):
        data = data.get("positions", data.get("portfolio", []))
    return data if isinstance(data, list) else []


def _persist_portfolio(client) -> int:
    """Sync only explicitly supplied real portfolio positions.

    Never creates real positions from engine signals. Missing tickers are not auto-closed.
    """
    positions = _portfolio_positions_from_env()
    synced = 0
    for p in positions:
        if not isinstance(p, dict):
            continue
        ticker = str(_pick(p, "ticker", "symbol") or "").upper().strip()
        if not ticker:
            continue
        market = str(_pick(p, "market") or ("ITALY" if ticker.endswith(".MI") else "USA")).upper()
        qty = _int(_pick(p, "qty", "quantity", "shares"))
        entry = _num(_pick(p, "entry_price", "avg_price", "average_price", "pmc", "price"))
        if qty is None or qty <= 0 or entry is None or entry <= 0:
            print(f"PORTFOLIO sync skipped {ticker}: qty/entry missing")
            continue

        payload = {
            "ticker": ticker,
            "market": market,
            "broker": str(_pick(p, "broker") or "Fineco"),
            "order_type": "PORTFOLIO_SYNC",
            "qty": qty,
            "entry_price": entry,
            "stop_initial": _num(_pick(p, "stop_initial", "stop")),
            "stop_current": _num(_pick(p, "stop_current", "stop")),
            "tp1": _num(_pick(p, "tp1", "target1")),
            "tp2": _num(_pick(p, "tp2", "target2")),
            "commission_entry": _num(_pick(p, "commission_entry")),
            "trade_status": "OPEN",
        }
        existing = (
            client.table("trades")
            .select("id")
            .eq("ticker", ticker)
            .eq("market", market)
            .eq("trade_status", "OPEN")
            .limit(1)
            .execute()
        )
        if existing.data:
            client.table("trades").update(payload).eq("id", existing.data[0]["id"]).execute()
        else:
            payload["entry_date"] = _pick(p, "entry_date", "date") or datetime.now(timezone.utc).isoformat()
            client.table("trades").insert(payload).execute()
        synced += 1
    return synced


def persist_scan(result: dict[str, Any], cfg: dict[str, Any]) -> None:
    client = _client()
    if client is None:
        print("SUPABASE persistence skipped: secrets missing")
        return
    if result.get("skipped"):
        return

    market = str(result.get("market") or cfg.get("market") or "").upper()
    run_id = result.get("run_id") or datetime.now(timezone.utc).strftime("CORE_%Y%m%dT%H%M%SZ")
    candidates = result.get("candidates") or []
    selected = result.get("selected") or []
    regime = result.get("regime") or {}

    run_payload = {
        "run_id": run_id,
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "market": market,
        "horizon": "3-6M",
        "engine_version": "CORE-2.0",
        "config_version": str(cfg.get("version") or cfg.get("config_version") or "core-current"),
        "universe_size": len(candidates),
        "candidates_count": len(selected),
        "notes": json.dumps({"regime": regime}, default=str)[:12000],
    }
    client.table("engine_runs").upsert(run_payload, on_conflict="run_id").execute()

    rows = []
    source = candidates if candidates else selected
    for idx, c in enumerate(source):
        ticker = str(c.get("ticker") or "").upper().strip()
        if not ticker:
            continue
        signal_id = f"{run_id}_{ticker}_{idx}"
        score = _pick(c, "opportunity_score", "score_total", "score")
        decision = _pick(c, "decision", "display_state")
        status = _pick(c, "display_state", "decision", "status")
        row = {
            "signal_id": signal_id,
            "run_id": run_id,
            "market": market,
            "ticker": ticker,
            "horizon": "3-6M",
            "price": _num(_pick(c, "price", "last", "close")),
            "status": None if status is None else str(status),
            "decision": None if decision is None else str(decision),
            "setup": None if _pick(c, "setup", "setup_type") is None else str(_pick(c, "setup", "setup_type")),
            "trigger": None if _pick(c, "trigger", "trigger_state") is None else str(_pick(c, "trigger", "trigger_state")),
            "score_total": _num(score),
            "entry": _num(_pick(c, "entry", "ideal_entry", "entry_price")),
            "buy_range_low": _num(_pick(c, "buy_range_low", "entry_low")),
            "buy_range_high": _num(_pick(c, "buy_range_high", "entry_high")),
            "max_buy": _num(_pick(c, "max_buy", "max_entry")),
            "stop": _num(_pick(c, "stop", "stop_loss")),
            "tp1": _num(_pick(c, "tp1", "target1")),
            "tp2": _num(_pick(c, "tp2", "target2", "target")),
            "rr_net_tp1": _num(_pick(c, "rr_net_tp1", "net_rr_tp1")),
            "rr_net_tp2": _num(_pick(c, "rr_net_tp2", "net_rr", "rr")),
            "qty": _int(_pick(c, "qty", "shares")),
            "capital": _num(_pick(c, "capital", "position_value")),
            "loss_max": _num(_pick(c, "loss_max", "max_loss")),
            "sma20": _num(_pick(c, "sma20", "SMA20")),
            "sma50": _num(_pick(c, "sma50", "SMA50")),
            "sma200": _num(_pick(c, "sma200", "SMA200")),
            "rsi14": _num(_pick(c, "rsi14", "rsi", "RSI")),
            "atr14": _num(_pick(c, "atr14", "atr", "ATR")),
            "relative_volume": _num(_pick(c, "relative_volume", "rel_volume", "rvol")),
            "earnings_date": _pick(c, "earnings_date", "next_earnings"),
            "days_to_earnings": _int(_pick(c, "days_to_earnings", "earnings_days")),
            "data_quality": str(_pick(c, "data_quality", "data_status") or "N/D"),
            "reason": str(_pick(c, "reason", "why", "rationale") or ""),
            "raw_data": c,
        }
        rows.append(row)

    if rows:
        client.table("signals").upsert(rows, on_conflict="signal_id").execute()

    watch_count = _persist_watchlist(client, rows, market)
    portfolio_count = _persist_portfolio(client)
    print(
        f"SUPABASE persisted run={run_id} signals={len(rows)} "
        f"watchlist={watch_count} portfolio_open_synced={portfolio_count}"
    )
