from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from supabase import create_client


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


def persist_scan(result: dict[str, Any], cfg: dict[str, Any]) -> None:
    client = _client()
    if client is None:
        print("SUPABASE persistence skipped: secrets missing")
        return
    if result.get("skipped"):
        return

    market = str(result.get("market") or cfg.get("market") or "").upper()
    run_id = result.get("run_id") or datetime.now(timezone.utc).strftime("CORE_%Y%m%dT%H%M%SZ")
    engine_id = f"CORE_{market}"
    candidates = result.get("candidates") or []
    selected = result.get("selected") or []
    regime = result.get("regime") or {}

    run_payload = {
        "run_id": run_id,
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "engine_id": engine_id,
        "strategy": "CORE",
        "market": market,
        "horizon": "3-6M",
        "engine_version": "CORE-2.0",
        "config_version": str(cfg.get("version") or cfg.get("config_version") or "core-current"),
        "universe_size": len(candidates),
        "candidates_count": len(selected),
        "records_processed": len(candidates),
        "signals_found": len(selected),
        "notes": json.dumps({"regime": regime}, default=str)[:12000],
    }
    client.table("engine_runs").upsert(run_payload, on_conflict="run_id").execute()

    rows = []
    source = candidates if candidates else selected
    selected_tickers = {str(x.get("ticker") or "").upper().strip() for x in selected}
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
            "engine_id": engine_id,
            "engine": "CORE",
            "strategy": "CORE",
            "market": market,
            "ticker": ticker,
            "horizon": "3-6M",
            "price": _num(_pick(c, "price", "last", "close")),
            "status": None if status is None else str(status),
            "decision": None if decision is None else str(decision),
            "signal_type": None if status is None else str(status),
            "setup": None if _pick(c, "setup", "setup_type") is None else str(_pick(c, "setup", "setup_type")),
            "trigger": None if _pick(c, "trigger", "trigger_state") is None else str(_pick(c, "trigger", "trigger_state")),
            "score_total": _num(score),
            "conviction": _num(score),
            "is_actionable": ticker in selected_tickers and str(decision or "") in {"BUY_NOW", "BUY_LIMIT"},
            "entry": _num(_pick(c, "entry", "ideal_entry", "entry_price")),
            "buy_range_low": _num(_pick(c, "buy_range_low", "buy_zone_low", "entry_low")),
            "buy_range_high": _num(_pick(c, "buy_range_high", "buy_zone_high", "entry_high")),
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
    print(f"SUPABASE persisted run={run_id} engine={engine_id} signals={len(rows)}")
