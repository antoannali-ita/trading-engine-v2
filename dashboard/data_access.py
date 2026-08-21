from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from supabase import create_client


def get_client():
    url = (os.getenv("SUPABASE_URL") or "").strip()
    key = (os.getenv("SUPABASE_SECRET_KEY") or "").strip()
    if not url or not key:
        raise RuntimeError("SUPABASE_URL e SUPABASE_SECRET_KEY non configurati")
    return create_client(url, key)


def table_rows(table: str, *, order: str | None = None, desc: bool = True, limit: int = 500) -> list[dict[str, Any]]:
    q = get_client().table(table).select("*")
    if order:
        q = q.order(order, desc=desc)
    return q.limit(limit).execute().data or []


def engine_health() -> list[dict[str, Any]]:
    return get_client().table("v_engine_health").select("*").order("engine_id").execute().data or []


def signals(limit: int = 1000) -> list[dict[str, Any]]:
    return table_rows("signals", order="detected_at", limit=limit)


def runs(limit: int = 500) -> list[dict[str, Any]]:
    return table_rows("engine_runs", order="started_at", limit=limit)


def ai_analysis(limit: int = 500) -> list[dict[str, Any]]:
    return table_rows("ai_analysis", order="started_at", limit=limit)


def notifications(limit: int = 500) -> list[dict[str, Any]]:
    return table_rows("notification_events", order="attempted_at", limit=limit)


def performance(limit: int = 1000) -> list[dict[str, Any]]:
    return table_rows("performance", order="created_at", limit=limit)


def manual_requests(limit: int = 200) -> list[dict[str, Any]]:
    return table_rows("manual_run_requests", order="requested_at", limit=limit)


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
