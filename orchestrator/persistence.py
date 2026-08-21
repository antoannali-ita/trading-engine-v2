from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from typing import Any

from supabase import create_client


def client():
    url = (os.getenv("SUPABASE_URL") or "").strip()
    key = (os.getenv("SUPABASE_SECRET_KEY") or "").strip()
    if not url or not key:
        return None
    return create_client(url, key)


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_signal_id(*parts: Any) -> str:
    raw = "|".join(str(p or "") for p in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def record_engine_signal(
    *,
    run_id: str,
    engine_id: str,
    engine: str,
    strategy: str,
    market: str,
    ticker: str,
    signal_type: str,
    decision: str | None = None,
    score: float | None = None,
    price: float | None = None,
    is_actionable: bool = False,
    source_signal_id: str | None = None,
    metadata: dict | None = None,
    signal_id: str | None = None,
) -> str | None:
    db = client()
    if db is None:
        return None
    ticker = str(ticker or "").upper().strip()
    if not ticker:
        return None
    signal_id = signal_id or stable_signal_id(run_id, engine_id, strategy, ticker, signal_type)
    row = {
        "signal_id": signal_id,
        "run_id": run_id,
        "engine_id": engine_id,
        "engine": engine.upper(),
        "strategy": strategy.upper(),
        "market": market.upper(),
        "ticker": ticker,
        "signal_type": str(signal_type or "UNKNOWN").upper(),
        "status": str(signal_type or "UNKNOWN").upper(),
        "decision": None if decision is None else str(decision).upper(),
        "score_total": score,
        "conviction": score,
        "price": price,
        "is_actionable": bool(is_actionable),
        "source_signal_id": source_signal_id,
        "metadata": metadata or {},
        "detected_at": utcnow(),
    }
    db.table("signals").upsert(row, on_conflict="signal_id").execute()
    return signal_id


def ensure_engine_registry() -> None:
    db = client()
    if db is None:
        return
    rows = [
        {"engine_id": "MULTI_USA", "repository": "antoannali-ita/trading-engine-multihorizon", "workflow_file": "multihorizon_scan.yml", "strategy": "MULTI_HORIZON", "market": "USA", "horizon": "MULTI", "enabled": True, "schedule_type": "ORCHESTRATED", "status": "UNKNOWN"},
        {"engine_id": "MULTI_ITALY", "repository": "antoannali-ita/trading-engine-multihorizon", "workflow_file": "multihorizon_scan.yml", "strategy": "MULTI_HORIZON", "market": "ITALY", "horizon": "MULTI", "enabled": True, "schedule_type": "ORCHESTRATED", "status": "UNKNOWN"},
        {"engine_id": "TRADINGAGENTS", "repository": "antoannali-ita/TradingAgents", "workflow_file": "orchestrator_analysis.yml", "strategy": "AI_SECOND_OPINION", "market": "GLOBAL", "horizon": "ON_DEMAND", "enabled": True, "schedule_type": "ORCHESTRATED", "status": "UNKNOWN"},
        {"engine_id": "ORCHESTRATOR", "repository": "antoannali-ita/trading-engine-v2", "workflow_file": "orchestrator_tick.yml", "strategy": "CONFLUENCE", "market": "GLOBAL", "horizon": "EVENT", "enabled": True, "schedule_type": "GITHUB_ACTIONS", "status": "UNKNOWN"},
    ]
    db.table("engine_registry").upsert(rows, on_conflict="engine_id").execute()


def recent_signals(limit: int = 1000) -> list[dict]:
    db = client()
    if db is None:
        return []
    response = db.table("signals").select("*").order("detected_at", desc=True).limit(limit).execute()
    return response.data or []


def recent_ai_analysis(limit: int = 500) -> list[dict]:
    db = client()
    if db is None:
        return []
    response = db.table("ai_analysis").select("*").order("started_at", desc=True).limit(limit).execute()
    return response.data or []


def create_ai_pending(*, ticker: str, market: str, source_signal_id: str | None, trigger_reason: str) -> str | None:
    db = client()
    if db is None:
        return None
    response = db.table("ai_analysis").insert({
        "ticker": ticker.upper(),
        "market": market.upper(),
        "source_signal_id": source_signal_id,
        "trigger_reason": trigger_reason,
        "provider": "TRADINGAGENTS",
        "status": "PENDING",
    }).execute()
    rows = response.data or []
    return str(rows[0].get("analysis_id")) if rows else None
