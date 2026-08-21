from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from orchestrator.confluence import compute_confluence, is_positive, signal_family
from orchestrator.dispatcher import dispatch_pending_requests, dispatch_workflow
from orchestrator.notifier import send_qualified_notifications
from orchestrator.persistence import (
    client,
    create_ai_pending,
    ensure_engine_registry,
    recent_ai_analysis,
    recent_signals,
    record_engine_signal,
    stable_signal_id,
    utcnow,
)
from orchestrator.runtime import RunTracker


def _parse_ts(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _has_recent_event(db, event_type: str, market: str, minutes: int) -> bool:
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()
    rows = db.table("system_events").select("event_id,details").eq("event_type", event_type).gte("occurred_at", cutoff).limit(100).execute().data or []
    return any(str((row.get("details") or {}).get("market") or "").upper() == market.upper() for row in rows)


def _recent_base_activity(rows: list[dict], market: str, minutes: int = 30) -> bool:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    for row in rows:
        if str(row.get("market") or "").upper() != market.upper():
            continue
        if signal_family(row) not in {"CORE", "SHORT", "FAST"} or not is_positive(row):
            continue
        ts = _parse_ts(row.get("detected_at") or row.get("created_at"))
        if ts and ts >= cutoff:
            return True
    return False


def _confluence_signal_id(item: dict) -> str:
    source_ids = sorted(item.get("source_signal_ids") or [])
    return stable_signal_id("CONFLUENCE", item["market"], item["ticker"], item["level"], *source_ids)


def _ai_already_requested(ai_rows: list[dict], ticker: str, source_signal_id: str | None) -> bool:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    for row in ai_rows:
        if str(row.get("ticker") or "").upper() != ticker.upper():
            continue
        status = str(row.get("status") or "").upper()
        if status not in {"PENDING", "RUNNING", "SUCCESS"}:
            continue
        if source_signal_id:
            if row.get("source_signal_id") == source_signal_id:
                return True
            continue
        ts = _parse_ts(row.get("started_at") or row.get("created_at"))
        if ts and ts >= cutoff and status in {"PENDING", "RUNNING"}:
            return True
    return False


def run_once() -> dict:
    ensure_engine_registry()
    db = client()
    if db is None:
        raise RuntimeError("SUPABASE_URL/SUPABASE_SECRET_KEY are required for the orchestrator")

    run_id = f"orchestrator-{os.getenv('GITHUB_RUN_ID') or datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    tracker = RunTracker.start("ORCHESTRATOR", "GLOBAL", "CONFLUENCE", run_id)
    stats = {"manual_dispatched": 0, "manual_failed": 0, "multi_dispatched": 0, "ai_dispatched": 0, "confluence": 0, "email_sent": 0, "whatsapp_sent": 0}
    try:
        manual = dispatch_pending_requests()
        stats["manual_dispatched"] = manual["dispatched"]
        stats["manual_failed"] = manual["failed"]

        rows = recent_signals()
        confluences = [item for item in compute_confluence(rows) if item["level"] != "NONE"]
        stats["confluence"] = len(confluences)

        for item in confluences:
            source_ids = sorted(item["source_signal_ids"])
            confluence_id = _confluence_signal_id(item)
            record_engine_signal(
                run_id=run_id, engine_id="ORCHESTRATOR", engine="ORCHESTRATOR", strategy="CONFLUENCE",
                market=item["market"], ticker=item["ticker"], signal_type=item["level"], decision=item["level"],
                score=item["score"], is_actionable=item["eligible_for_ai"],
                source_signal_id=source_ids[0] if source_ids else None,
                metadata={"families": item["families"], "positive_count": item["positive_count"], "multi_horizon_positive": item["multi_horizon_positive"], "source_signal_ids": source_ids},
                signal_id=confluence_id,
            )

        for market in {item["market"] for item in confluences if item["eligible_for_multi"]}:
            if not _recent_base_activity(rows, market) or _has_recent_event(db, "MULTI_DISPATCH", market, 60):
                continue
            engine_id = "MULTI_USA" if market == "USA" else "MULTI_ITALY"
            dispatch_workflow(engine_id)
            tracker.event("MULTI_DISPATCH", f"Dispatched {engine_id}", details={"market": market})
            stats["multi_dispatched"] += 1

        ai_rows = recent_ai_analysis()
        for item in confluences:
            if not item["eligible_for_ai"]:
                continue
            confluence_id = _confluence_signal_id(item)
            if _ai_already_requested(ai_rows, item["ticker"], confluence_id):
                continue
            analysis_id = create_ai_pending(
                ticker=item["ticker"],
                market=item["market"],
                source_signal_id=confluence_id,
                trigger_reason=f"{item['level']} | MULTI={item['multi_horizon_positive']}",
            )
            if not analysis_id:
                continue
            try:
                dispatch_workflow("TRADINGAGENTS", extra_inputs={
                    "ticker": item["ticker"],
                    "market": item["market"].lower(),
                    "analysis_id": analysis_id,
                    "source_signal_id": confluence_id,
                })
                tracker.event("AI_DISPATCH", f"TradingAgents dispatched for {item['ticker']}", details={"market": item["market"], "analysis_id": analysis_id, "source_signal_id": confluence_id})
                stats["ai_dispatched"] += 1
                ai_rows.append({"ticker": item["ticker"], "source_signal_id": confluence_id, "status": "PENDING", "started_at": utcnow()})
            except Exception as exc:
                db.table("ai_analysis").update({"status": "FAILED", "completed_at": utcnow(), "error_message": f"{type(exc).__name__}: {exc}"[:4000]}).eq("analysis_id", analysis_id).execute()
                raise

        notified = send_qualified_notifications()
        stats["email_sent"] = notified["email"]
        stats["whatsapp_sent"] = notified["whatsapp"]

        tracker.finish("SUCCESS", records_processed=len(rows), signals_found=len(confluences))
        return stats
    except Exception as exc:
        tracker.event("ORCHESTRATOR_ERROR", str(exc), severity="ERROR")
        tracker.finish("FAILED", error_message=f"{type(exc).__name__}: {exc}"[:4000])
        raise


def main():
    stats = run_once()
    print("ORCHESTRATOR", stats)


if __name__ == "__main__":
    main()
