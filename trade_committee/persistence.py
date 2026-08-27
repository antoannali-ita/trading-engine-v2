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
    row = {"run_id": run_id, "ticker": ticker.upper(), "status": "RUNNING", "started_at": utc_now()}
    try:
        db.table("trade_committee_runs").insert(row).execute()
        return {"ok": True, "reason": None}
    except Exception as exc:
        return {"ok": False, "reason": f"start_failed:{type(exc).__name__}:{exc}"}


def log_step(run_id: str, step: int, label: str, status: str, note: str = "") -> dict[str, Any]:
    """Optional backend diagnostics. Never rendered as a wall of logs in the operative UI."""
    db, reason = _client()
    if db is None:
        return {"ok": False, "reason": reason}
    normalized = status if status in {"COMPLETE", "WARNING", "FAILED", "RUNNING"} else ("COMPLETE" if status == "REAL" else "WARNING")
    row = {"run_id": run_id, "step_no": int(step), "label": label, "status": normalized, "note": note or None, "logged_at": utc_now()}
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
        "warning_count": (result.get("coverage_summary") or {}).get("partial", 0),
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
    row = {"status": "FAILED", "finished_at": utc_now(), "error_type": type(exc).__name__, "error_message": str(exc)[:2000], "error_trace": trace}
    try:
        db.table("trade_committee_runs").update(row).eq("run_id", run_id).execute()
        return {"ok": True, "reason": None}
    except Exception as db_exc:
        return {"ok": False, "reason": f"fail_log_failed:{type(db_exc).__name__}:{db_exc}"}


def recent_runs(limit: int = 50, ticker: str | None = None, include_payload: bool = False) -> tuple[list[dict[str, Any]], str | None]:
    db, reason = _client()
    if db is None:
        return [], reason
    cols = "run_id,ticker,status,started_at,finished_at,verdict,committee_score,data_confidence,warning_count,error_type,error_message"
    if include_payload:
        cols += ",result_payload"
    try:
        q = db.table("trade_committee_runs").select(cols)
        if ticker:
            q = q.eq("ticker", ticker.upper())
        res = q.order("started_at", desc=True).limit(max(1, min(int(limit), 200))).execute()
        return list(res.data or []), None
    except Exception as exc:
        return [], f"recent_failed:{type(exc).__name__}:{exc}"


def ticker_history(ticker: str, limit: int = 20) -> tuple[list[dict[str, Any]], str | None]:
    """Compact chronological history for user-facing comparison of repeated analyses."""
    rows, err = recent_runs(limit=limit, ticker=ticker, include_payload=True)
    if err:
        return [], err

    out: list[dict[str, Any]] = []
    for row in reversed(rows):
        payload = row.get("result_payload") or {}
        trade = payload.get("trade_plan") or {}
        market = payload.get("market") or {}
        out.append({
            "run_id": row.get("run_id"),
            "when": row.get("finished_at") or row.get("started_at"),
            "status": row.get("status"),
            "verdict": row.get("verdict"),
            "price": payload.get("price"),
            "entry": trade.get("entry"),
            "stop": trade.get("stop"),
            "tp1": trade.get("tp1"),
            "tp2": trade.get("tp2"),
            "rr1_net": trade.get("rr1_net"),
            "rr2_net": trade.get("rr2_net"),
            "committee_score": row.get("committee_score"),
            "data_confidence": row.get("data_confidence"),
            "snapshot_time": market.get("timestamp") or payload.get("run_at"),
        })

    # Add changes versus the immediately previous run. First run has no comparison.
    previous = None
    for item in out:
        if previous:
            for key in ("price", "entry", "stop", "tp1", "tp2", "committee_score", "data_confidence"):
                a, b = item.get(key), previous.get(key)
                item[f"delta_{key}"] = (a - b) if isinstance(a, (int, float)) and isinstance(b, (int, float)) else None
            item["verdict_changed"] = item.get("verdict") != previous.get("verdict")
        else:
            item["verdict_changed"] = False
        previous = item
    return list(reversed(out)), None


def run_steps(run_id: str) -> tuple[list[dict[str, Any]], str | None]:
    db, reason = _client()
    if db is None:
        return [], reason
    try:
        res = db.table("trade_committee_run_steps").select("step_no,label,status,note,logged_at").eq("run_id", run_id).order("step_no").execute()
        return list(res.data or []), None
    except Exception as exc:
        return [], f"steps_failed:{type(exc).__name__}:{exc}"
