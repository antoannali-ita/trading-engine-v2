from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from orchestrator.persistence import client, utcnow

GITHUB_API = "https://api.github.com"

TARGETS = {
    "CORE_USA": {"repo": "antoannali-ita/trading-engine-v2", "workflow": "master_scan.yml", "ref": "main", "inputs": {"market": "usa"}},
    "CORE_ITALY": {"repo": "antoannali-ita/trading-engine-v2", "workflow": "master_scan.yml", "ref": "main", "inputs": {"market": "italy"}},
    "FAST_USA": {"repo": "antoannali-ita/trading-engine-v2", "workflow": "fast_monitor.yml", "ref": "main", "inputs": {"market": "usa"}},
    "FAST_ITALY": {"repo": "antoannali-ita/trading-engine-v2", "workflow": "fast_monitor.yml", "ref": "main", "inputs": {"market": "italy"}},
    "MULTI_USA": {"repo": "antoannali-ita/trading-engine-multihorizon", "workflow": "multihorizon_scan.yml", "ref": "main", "inputs": {"market": "usa", "strategy": "all"}},
    "MULTI_ITALY": {"repo": "antoannali-ita/trading-engine-multihorizon", "workflow": "multihorizon_scan.yml", "ref": "main", "inputs": {"market": "italy", "strategy": "all"}},
    "TRADINGAGENTS": {"repo": "antoannali-ita/TradingAgents", "workflow": "orchestrator_analysis.yml", "ref": "main", "inputs": {}},
}


def _token() -> str:
    return (os.getenv("ORCHESTRATOR_GITHUB_TOKEN") or "").strip()


def dispatch_workflow(engine_id: str, *, extra_inputs: dict[str, Any] | None = None) -> None:
    token = _token()
    if not token:
        raise RuntimeError("ORCHESTRATOR_GITHUB_TOKEN is missing")
    target = TARGETS.get(engine_id)
    if target is None:
        raise KeyError(f"Unknown engine_id: {engine_id}")
    inputs = dict(target.get("inputs") or {})
    for key, value in (extra_inputs or {}).items():
        if value is not None:
            inputs[key] = str(value)
    body = json.dumps({"ref": target["ref"], "inputs": inputs}).encode("utf-8")
    url = f"{GITHUB_API}/repos/{target['repo']}/actions/workflows/{target['workflow']}/dispatches"
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
            "User-Agent": "trading-engine-v2-orchestrator",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            if response.status not in {200, 201, 204}:
                raise RuntimeError(f"GitHub dispatch returned HTTP {response.status}")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:2000]
        raise RuntimeError(f"GitHub dispatch HTTP {exc.code}: {detail}") from exc


def dispatch_pending_requests(limit: int = 20) -> dict[str, int]:
    db = client()
    if db is None:
        return {"dispatched": 0, "failed": 0}
    rows = (
        db.table("manual_run_requests")
        .select("*")
        .eq("status", "REQUESTED")
        .order("requested_at")
        .limit(limit)
        .execute()
        .data
        or []
    )
    dispatched = failed = 0
    for row in rows:
        request_id = row["request_id"]
        engine_id = str(row.get("engine_id") or "").upper()
        payload = row.get("request_payload") if isinstance(row.get("request_payload"), dict) else {}
        try:
            dispatch_workflow(engine_id, extra_inputs=payload)
            db.table("manual_run_requests").update({
                "status": "DISPATCHED",
                "dispatched_at": utcnow(),
            }).eq("request_id", request_id).execute()
            dispatched += 1
        except Exception as exc:
            db.table("manual_run_requests").update({
                "status": "FAILED",
                "completed_at": utcnow(),
                "error_message": f"{type(exc).__name__}: {exc}"[:4000],
            }).eq("request_id", request_id).execute()
            failed += 1
    return {"dispatched": dispatched, "failed": failed}
