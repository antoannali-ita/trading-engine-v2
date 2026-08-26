from __future__ import annotations

import os
import traceback
from datetime import datetime, timezone
from typing import Any


def _client():
    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_SECRET_KEY", "").strip()
    if not url or not key:
        return None, "supabase_not_configured"
    try:
        from supabase import create_client
    except Exception as exc:
        return None, f"supabase_import:{type(exc).__name__}:{exc}"
    try:
        return create_client(url, key), None
    except Exception as exc:
        return None, f"supabase_client:{type(exc).__name__}:{exc}"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_run_id(ticker: str) -> str:
    return f"TC-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}-{ticker.upper()}"


def start_run(run_id: str, ticker: str) -> dict[str, Any]:
    db, reason = _client()
    if db is None:
        return {"ok": False, "reason": reason}
    row = {
        "run_id": run_id,
        "ticker": ticker.upper(),
        "status": "RUNNING",
        "started_at": utc_now(),
    }
    try:
        db.table("trade_committee_runs").insert(row).execute()
        return {"ok": True, "reason": None}
    except Exception as exc:
        return {"ok": False, "reason": f"start_failed:{type(exc).__name__}:{exc}"}


def log_step(run_id: str, step: int, label: str, status: str, note: str = "") -> dict[str, Any]:
    db, reason = _client()
    if db is None:
        return {"ok": False, "reason": reason}
    row = {
        "run_id": run_id,
        "step_no": int(step),
        "label": label,
        "status": status,
        "note": note or None,
        "logged_at": utc_now(),
    }
    try:
        db.table("trade_committee_run_steps").upsert(row, on_conflict="run_id,step_no").execute()
        return {"ok": True, "reason": None}
    except Exception as exc:
        return {"ok": False, "reason": f"step_failed:{type(exc).__name__}:{exc}"}


def finish_run(run_id: str, result: dict[str, Any]) -> dict[str, Any]:
    db, reason = _client()
    if db is None:
        return {"ok": False, "reason": reason}
    row = {
        "status": "COMPLETE",
        "finished_at": utc_now(),
        "verdict": result.get("verdict"),
        "committee_score": result.get("committee_score"),
        "data_confidence": result.get("data_confidence"),
        "warning_count": result.get("warning_count", 0),
        "result_payload": result,
    }
    try:
        db.table("trade_committee_runs").update(row).eq("run_id", run_id).execute()
        return {"ok": True, "reason": None}
    except Exception as exc:
        return {"ok": False, "reason": f"finish_failed:{type(exc).__name__}:{exc}"}


def fail_run(run_id: str, exc: BaseException) -> dict[str, Any]:
    db, reason = _client()
    if db is None:
        return {"ok": False, "reason": reason}
    trace = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))[-12000:]
    row = {
        "status": "FAILED",
        "finished_at": utc_now(),
        "error_type": type(exc).__name__,
        "error_message": str(exc)[:2000],
        "error_trace": trace,
    }
    try:
        db.table("trade_committee_runs").update(row).eq("run_id", run_id).execute()
        return {"ok": True, "reason": None}
    except Exception as db_exc:
        return {"ok": False, "reason": f"fail_log_failed:{type(db_exc).__name__}:{db_exc}"}


def recent_runs(limit: int = 20) -> tuple[list[dict[str, Any]], str | None]:
    db, reason = _client()
    if db is None:
        return [], reason
    try:
        res = db.table("trade_committee_runs").select(
            "run_id,ticker,status,started_at,finished_at,verdict,committee_score,data_confidence,warning_count,error_type,error_message"
        ).order("started_at", desc=True).limit(max(1, min(int(limit), 100))).execute()
        return list(res.data or []), None
    except Exception as exc:
        return [], f"recent_failed:{type(exc).__name__}:{exc}"


def run_steps(run_id: str) -> tuple[list[dict[str, Any]], str | None]:
    db, reason = _client()
    if db is None:
        return [], reason
    try:
        res = db.table("trade_committee_run_steps").select(
            "step_no,label,status,note,logged_at"
        ).eq("run_id", run_id).order("step_no").execute()
        return list(res.data or []), None
    except Exception as exc:
        return [], f"steps_failed:{type(exc).__name__}:{exc}"
