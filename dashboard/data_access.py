from __future__ import annotations

import os
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any

from supabase import create_client


@lru_cache(maxsize=1)
def get_client():
    url = (os.getenv("SUPABASE_URL") or "").strip()
    key = (os.getenv("SUPABASE_SECRET_KEY") or "").strip()
    if not url or not key:
        raise RuntimeError("SUPABASE_URL e SUPABASE_SECRET_KEY non configurati")
    return create_client(url, key)


def table_rows(
    table: str,
    *,
    columns: str = "*",
    order: str | None = None,
    desc: bool = True,
    limit: int = 500,
) -> list[dict[str, Any]]:
    q = get_client().table(table).select(columns)
    if order:
        q = q.order(order, desc=desc)
    return q.limit(limit).execute().data or []


def engine_health() -> list[dict[str, Any]]:
    return get_client().table("v_engine_health").select("*").order("engine_id").execute().data or []


def signals(limit: int = 1000) -> list[dict[str, Any]]:
    return table_rows(
        "signals",
        columns="signal_id,run_id,engine_id,engine,strategy,market,ticker,signal_type,decision,conviction,score_total,price,entry,stop,tp1,tp2,is_actionable,source_signal_id,detected_at,metadata",
        order="detected_at",
        limit=limit,
    )


def latest_confluence(limit: int = 300) -> list[dict[str, Any]]:
    return table_rows("v_dashboard_latest_confluence", order="detected_at", limit=limit)


def runs(limit: int = 500) -> list[dict[str, Any]]:
    return table_rows(
        "engine_runs",
        columns="run_id,engine_id,market,strategy,trigger_source,requested_by,started_at,finished_at,status,duration_seconds,records_processed,signals_found,error_message,github_run_id",
        order="started_at",
        limit=limit,
    )


def ai_analysis(limit: int = 500) -> list[dict[str, Any]]:
    # Prefer the compact operational view added by migration 002.
    try:
        return table_rows("v_dashboard_recent_ai", order="started_at", limit=limit)
    except Exception:
        return table_rows("ai_analysis", order="started_at", limit=limit)


def notifications(limit: int = 500) -> list[dict[str, Any]]:
    return table_rows(
        "notification_events",
        columns="notification_id,run_id,signal_id,ticker,event_type,channel,attempted_at,sent_at,status,provider,error_message,payload",
        order="attempted_at",
        limit=limit,
    )


def performance(limit: int = 1000) -> list[dict[str, Any]]:
    return table_rows(
        "performance",
        columns="performance_id,engine_id,strategy,market,ticker,signal_id,period_start,period_end,outcome,entry_price,exit_price,pnl_pct,max_drawdown_pct,max_favorable_excursion_pct,holding_minutes,created_at",
        order="created_at",
        limit=limit,
    )


def performance_summary() -> list[dict[str, Any]]:
    try:
        return table_rows("v_dashboard_performance_summary", limit=500)
    except Exception:
        return []


def manual_requests(limit: int = 200) -> list[dict[str, Any]]:
    return table_rows(
        "manual_run_requests",
        columns="request_id,engine_id,market,strategy,requested_at,requested_by,send_email,send_whatsapp,status,github_run_id,run_id,dispatched_at,started_at,completed_at,error_message",
        order="requested_at",
        limit=limit,
    )


def request_run(engine_id: str, market: str, strategy: str | None, *, send_email: bool, send_whatsapp: bool, requested_by: str = "dashboard") -> dict:
    payload = {
        "engine_id": engine_id,
        "market": market.upper(),
        "strategy": strategy,
        "requested_by": requested_by,
        "send_email": send_email,
        "send_whatsapp": send_whatsapp,
        "status": "REQUESTED",
        "request_payload": {"source": "STREAMLIT_DASHBOARD"},
    }
    rows = get_client().table("manual_run_requests").insert(payload).execute().data or []
    return rows[0] if rows else payload


def utc_label(value: str | None) -> str:
    if not value:
        return "-"
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone().strftime("%d/%m/%Y %H:%M")
    except Exception:
        return str(value)
