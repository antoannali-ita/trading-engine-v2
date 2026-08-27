from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

DATA_STATUSES = {"REAL", "PARTIAL", "STALE", "N/D", "N/A", "FAILED"}
CORE_BLOCKING_STATES = {"WAIT", "WATCH", "PRE_BUY", "PRE-BUY", "REJECT", "AVOID"}
CORE_BUY_STATES = {"BUY", "BUY_NOW", "BUY_LIMIT", "IN_BUY_ZONE", "LIMIT_READY"}
COMMITTEE_HARD_VETO = {"HARD_VETO", "REJECT_COMMITTEE", "REJECT_COMPANY"}


@dataclass(frozen=True)
class FinalDecision:
    verdict: str
    reason: str


def canonical_snapshot(payload: Mapping[str, Any]) -> str:
    """Stable JSON representation used for integrity checks."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def snapshot_sha256(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_snapshot(payload).encode("utf-8")).hexdigest()


def verify_snapshot(payload: Mapping[str, Any], expected_sha256: str) -> bool:
    return snapshot_sha256(payload) == expected_sha256


def resolve_final_decision(
    core_state: str | None,
    committee_state: str | None,
    *,
    critical_evidence_ok: bool,
    data_conflict: bool = False,
    stale_snapshot: bool = False,
) -> FinalDecision:
    """Pure asymmetric final gate.

    Invariant: the Committee can veto a CORE buy, but can never create a buy
    that CORE did not authorize.
    """
    core = (core_state or "N/D").strip().upper()
    committee = (committee_state or "N/D").strip().upper()

    if core not in CORE_BUY_STATES:
        return FinalDecision("WAIT_CORE", f"CORE non autorizza il trade: {core}")
    if stale_snapshot:
        return FinalDecision("WAIT_STALE", "Snapshot CORE scaduto: richiedere un nuovo snapshot")
    if data_conflict:
        return FinalDecision("WAIT_CONFLICT", "Conflitto tra snapshot CORE e dato osservato")
    if not critical_evidence_ok:
        return FinalDecision("WAIT_DATA", "Critical Evidence incompleta o non valida")
    if committee in COMMITTEE_HARD_VETO:
        return FinalDecision("REJECT_COMMITTEE", f"Hard veto Committee: {committee}")
    if committee in {"PASS", "APPROVE"}:
        return FinalDecision("APPROVE", "CORE autorizza e il Committee non rileva hard veto")
    return FinalDecision("WAIT_DATA", f"Committee non conclusivo: {committee}")


def classify_freshness(timestamp: str | None, ttl_seconds: int | None, *, now: datetime | None = None) -> str:
    """Return REAL/STALE/N/D for a timestamped metric.

    TTL is metric-specific and must be supplied by the caller. There is no
    project-wide magic freshness threshold.
    """
    if not timestamp:
        return "N/D"
    if ttl_seconds is None:
        return "REAL"
    try:
        dt = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
    except Exception:
        return "N/D"
    current = now or datetime.now(timezone.utc)
    return "STALE" if (current - dt).total_seconds() > ttl_seconds else "REAL"


def evidence_record(value: Any, *, status: str, source: str, timestamp: str | None, ttl_seconds: int | None = None, note: str = "") -> dict[str, Any]:
    normalized = status.upper()
    if normalized not in DATA_STATUSES:
        raise ValueError(f"Unsupported evidence status: {status}")
    if normalized == "REAL" and timestamp and ttl_seconds is not None:
        normalized = classify_freshness(timestamp, ttl_seconds)
    return {
        "value": value,
        "status": normalized,
        "source": source,
        "timestamp": timestamp,
        "ttl_seconds": ttl_seconds,
        "note": note,
    }
