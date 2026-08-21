from __future__ import annotations

import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from supabase import create_client


def _client():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SECRET_KEY")
    if not url or not key:
        return None
    return create_client(url, key)


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def trigger_source() -> str:
    value = (os.getenv("TRIGGER_SOURCE") or "").strip().upper()
    if value:
        return value
    event_name = (os.getenv("GITHUB_EVENT_NAME") or "").lower()
    return "MANUAL_GITHUB" if event_name == "workflow_dispatch" else "SCHEDULE"


def _manual_request_id() -> str | None:
    value = (os.getenv("MANUAL_REQUEST_ID") or "").strip()
    return value or None


@dataclass
class RunTracker:
    engine_id: str
    market: str
    strategy: str
    run_id: str
    started_monotonic: float
    client: Any = None
    manual_request_id: str | None = None

    @classmethod
    def start(cls, engine_id: str, market: str, strategy: str, run_id: str):
        client = _client()
        request_id = _manual_request_id()
        tracker = cls(engine_id, market.upper(), strategy.upper(), run_id, time.monotonic(), client, request_id)
        if client is None:
            return tracker
        github_run_id = int(os.getenv("GITHUB_RUN_ID")) if os.getenv("GITHUB_RUN_ID", "").isdigit() else None
        payload = {
            "run_id": run_id,
            "run_timestamp": utcnow(),
            "engine_id": engine_id,
            "market": market.upper(),
            "strategy": strategy.upper(),
            "trigger_source": "MANUAL_WEB" if request_id else trigger_source(),
            "requested_by": os.getenv("REQUESTED_BY"),
            "started_at": utcnow(),
            "status": "RUNNING",
            "github_run_id": github_run_id,
        }
        client.table("engine_runs").upsert(payload, on_conflict="run_id").execute()
        client.table("engine_registry").update({"last_run_at": utcnow(), "status": "RUNNING"}).eq("engine_id", engine_id).execute()
        if request_id:
            client.table("manual_run_requests").update({
                "status": "RUNNING",
                "started_at": utcnow(),
                "run_id": run_id,
                "github_run_id": github_run_id,
            }).eq("request_id", request_id).execute()
        return tracker

    def event(self, event_type: str, message: str, severity: str = "INFO", details: dict | None = None):
        if self.client is None:
            return
        self.client.table("system_events").insert({
            "engine_id": self.engine_id,
            "run_id": self.run_id,
            "severity": severity,
            "event_type": event_type,
            "message": message,
            "details": details or {},
        }).execute()

    def finish(self, status: str, *, records_processed: int | None = None, signals_found: int | None = None, error_message: str | None = None):
        if self.client is None:
            return
        elapsed = round(time.monotonic() - self.started_monotonic, 3)
        payload = {
            "finished_at": utcnow(),
            "status": status,
            "duration_seconds": elapsed,
            "records_processed": records_processed,
            "signals_found": signals_found,
            "error_message": error_message,
        }
        self.client.table("engine_runs").update(payload).eq("run_id", self.run_id).execute()
        registry_status = "HEALTHY" if status == "SUCCESS" else "FAILED"
        self.client.table("engine_registry").update({"last_run_at": utcnow(), "status": registry_status}).eq("engine_id", self.engine_id).execute()
        if self.manual_request_id:
            self.client.table("manual_run_requests").update({
                "status": "SUCCESS" if status == "SUCCESS" else "FAILED",
                "completed_at": utcnow(),
                "error_message": error_message,
            }).eq("request_id", self.manual_request_id).execute()


def record_notification(*, run_id: str | None, signal_id: str | None = None, ticker: str | None = None,
                        event_type: str, channel: str, status: str, provider: str | None = None,
                        error_message: str | None = None, payload: dict | None = None):
    client = _client()
    if client is None:
        return
    row = {
        "run_id": run_id,
        "signal_id": signal_id,
        "ticker": ticker,
        "event_type": event_type,
        "channel": channel.upper(),
        "status": status.upper(),
        "provider": provider,
        "error_message": error_message,
        "payload": payload or {},
    }
    if status.upper() == "SENT":
        row["sent_at"] = utcnow()
    client.table("notification_events").insert(row).execute()
