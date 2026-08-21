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


def table_rows(table: str, *, columns: str = "*", order: str | None = None, desc: bool = True, limit: int = 500) -> list[dict[str, Any]]:
    q = get_client().table(table).select(columns)
    if order:
        q = q.order(order, desc=desc)
    return q.limit(limit).execute().data or []


def safe_table_rows(table: str, *, columns: str = "*", order: str | None = None, desc: bool = True, limit: int = 500, filters: list[tuple[str, str, Any]] | None = None) -> list[dict[str, Any]]:
    try:
        q = get_client().table(table).select(columns)
        for method, column, value in filters or []:
            q = getattr(q, method)(column, value)
        if order:
            q = q.order(order, desc=desc)
        return q.limit(limit).execute().data or []
    except Exception:
        return []


def engine_health() -> list[dict[str, Any]]:
    rows = get_client().table("v_engine_health").select("*").order("engine_id").execute().data or []
    cleaned: list[dict[str, Any]] = []
    for item in rows:
        row = dict(item)
        has_run = any(row.get(k) for k in ("last_run_at", "last_started_at", "last_finished_at", "last_run_id"))

        # UNKNOWN with no run is not an engine failure: the engine is registered
        # but has not produced a tracked execution yet. Make that explicit.
        if not has_run and str(row.get("computed_health") or "").upper() in {"", "UNKNOWN"}:
            row["computed_health"] = "NOT_RUN"
        if not has_run and str(row.get("registry_status") or "").upper() in {"", "UNKNOWN"}:
            row["registry_status"] = "REGISTERED"

        # Missing schedule metadata is a configuration gap, not a numeric zero.
        # Show N/D instead of Python/SQL None so the operator can distinguish it.
        if row.get("expected_interval_minutes") is None:
            row["expected_interval_minutes"] = "N/D"
        if row.get("next_expected_run_at") is None:
            row["next_expected_run_at"] = "N/D"
        if row.get("last_run_id") is None:
            row["last_run_id"] = "N/D"
        if row.get("last_run_status") is None:
            row["last_run_status"] = "N/D"
        if row.get("duration_seconds") is None:
            row["duration_seconds"] = "N/D"
        if row.get("signals_found") is None:
            row["signals_found"] = "N/D"

        cleaned.append(row)
    return cleaned


def signals(limit: int = 1000) -> list[dict[str, Any]]:
    return table_rows("signals", columns="signal_id,run_id,engine_id,engine,strategy,market,ticker,signal_type,decision,conviction,score_total,price,entry,stop,tp1,tp2,is_actionable,source_signal_id,detected_at,metadata", order="detected_at", limit=limit)


def latest_confluence(limit: int = 300) -> list[dict[str, Any]]:
    try:
        return table_rows("v_dashboard_latest_confluence", order="detected_at", limit=limit)
    except Exception:
        rows = (get_client().table("signals").select("signal_id,run_id,market,ticker,signal_type,decision,conviction,is_actionable,detected_at,metadata").eq("engine", "ORCHESTRATOR").order("detected_at", desc=True).limit(max(limit * 4, 500)).execute().data or [])
        latest: dict[tuple[str, str], dict[str, Any]] = {}
        for row in rows:
            key = (str(row.get("market") or ""), str(row.get("ticker") or ""))
            if key not in latest:
                latest[key] = row
            if len(latest) >= limit:
                break
        return list(latest.values())


def runs(limit: int = 500) -> list[dict[str, Any]]:
    rows = table_rows("engine_runs", columns="run_id,engine_id,market,strategy,trigger_source,requested_by,started_at,finished_at,status,duration_seconds,records_processed,signals_found,error_message,github_run_id", order="started_at", limit=limit)

    # Old scheduler heartbeat rows without engine_id/run timestamps are not real
    # engine executions. Keeping them in "Run recenti" only creates blank noise.
    valid = []
    for item in rows:
        if not item.get("engine_id") or not item.get("run_id"):
            continue
        valid.append(item)
    return valid


def ai_analysis(limit: int = 500) -> list[dict[str, Any]]:
    try:
        return table_rows("v_dashboard_recent_ai", order="started_at", limit=limit)
    except Exception:
        return table_rows("ai_analysis", order="started_at", limit=limit)


def notifications(limit: int = 500) -> list[dict[str, Any]]:
    return table_rows("notification_events", columns="notification_id,run_id,signal_id,ticker,event_type,channel,attempted_at,sent_at,status,provider,error_message,payload", order="attempted_at", limit=limit)


def system_events(limit: int = 300) -> list[dict[str, Any]]:
    return safe_table_rows("system_events", order="occurred_at", limit=limit)


def performance(limit: int = 1000) -> list[dict[str, Any]]:
    return table_rows("performance", columns="performance_id,engine_id,strategy,market,ticker,signal_id,period_start,period_end,outcome,entry_price,exit_price,pnl_pct,max_drawdown_pct,max_favorable_excursion_pct,holding_minutes,created_at", order="created_at", limit=limit)


def performance_summary() -> list[dict[str, Any]]:
    try:
        return table_rows("v_dashboard_performance_summary", limit=500)
    except Exception:
        return []


def manual_requests(limit: int = 200) -> list[dict[str, Any]]:
    return table_rows("manual_run_requests", columns="request_id,engine_id,market,strategy,requested_at,requested_by,send_email,send_whatsapp,status,github_run_id,run_id,dispatched_at,started_at,completed_at,error_message", order="requested_at", limit=limit)


def request_run(engine_id: str, market: str, strategy: str | None, *, send_email: bool, send_whatsapp: bool, requested_by: str = "dashboard") -> dict:
    payload = {"engine_id": engine_id, "market": market.upper(), "strategy": strategy, "requested_by": requested_by, "send_email": send_email, "send_whatsapp": send_whatsapp, "status": "REQUESTED", "request_payload": {"source": "STREAMLIT_DASHBOARD"}}
    rows = get_client().table("manual_run_requests").insert(payload).execute().data or []
    return rows[0] if rows else payload


# Laboratory: compatibilita con le tabelle usate dal sito precedente.
def lab_watchlist(limit: int = 1000) -> list[dict[str, Any]]:
    return safe_table_rows("lab_watchlist", order="score", limit=limit, filters=[("eq", "active", True)])


def lab_paper_positions(limit: int = 1000) -> list[dict[str, Any]]:
    return safe_table_rows("lab_paper_positions", order="opened_at", limit=limit)


def lab_paper_events(limit: int = 2000) -> list[dict[str, Any]]:
    return safe_table_rows("lab_paper_events", order="created_at", limit=limit)


def lab_paper_signals(limit: int = 1000) -> list[dict[str, Any]]:
    return safe_table_rows("lab_paper_signals", order="created_at", limit=limit)


def lab_backtest_runs(limit: int = 200) -> list[dict[str, Any]]:
    return safe_table_rows("lab_backtest_runs", order="created_at", limit=limit)


def lab_backtest_results(limit: int = 2000) -> list[dict[str, Any]]:
    return safe_table_rows("lab_backtest_results", order="created_at", limit=limit)


def lab_calibration_results(limit: int = 1000) -> list[dict[str, Any]]:
    return safe_table_rows("lab_calibration_results", order="created_at", limit=limit)


def lab_signal_outcomes(limit: int = 5000) -> list[dict[str, Any]]:
    return safe_table_rows("lab_signal_outcomes", order="signal_date", limit=limit)


def lab_strategy_variants(limit: int = 1000) -> list[dict[str, Any]]:
    return safe_table_rows("lab_strategy_variants", order="created_at", limit=limit)


def lab_strategy_evaluations(limit: int = 5000) -> list[dict[str, Any]]:
    return safe_table_rows("lab_strategy_evaluations", order="created_at", limit=limit)


def core_high_conviction(limit: int = 500) -> list[dict[str, Any]]:
    return safe_table_rows("core_high_conviction_signals", order="created_at", limit=limit, filters=[("eq", "active", True)])


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
