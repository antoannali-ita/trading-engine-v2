from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Mapping


SNAPSHOT_SCHEMA_VERSION = "TC_CORE_SNAPSHOT_V1"


CORE_FIELDS = (
    "market",
    "ticker",
    "company_name",
    "sector",
    "price",
    "quality_score",
    "opportunity_score",
    "score_components",
    "data_coverage_pct",
    "technical_state",
    "rs_state",
    "ideal_entry",
    "buy_zone_low",
    "buy_zone_high",
    "max_buy",
    "stop",
    "tp1",
    "tp2",
    "net_rr_tp1",
    "net_rr_tp2",
    "trigger_state",
    "trigger_reason",
    "shares",
    "invested",
    "net_risk_total",
    "data_quality",
    "data_anomaly_flags",
    "data_review_required",
    "corporate_action_status",
    "earnings_date",
    "days_to_earnings",
    "decision",
    "operational_state",
    "display_state",
    "gate_status",
    "failed_gates",
    "veto_reasons",
    "warnings",
)


@dataclass(frozen=True)
class CoreSnapshot:
    payload: dict[str, Any]
    snapshot_hash: str
    schema_version: str = SNAPSHOT_SCHEMA_VERSION


def _canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str, ensure_ascii=False)


def build_core_snapshot(source: Mapping[str, Any], *, engine_version: str | None = None) -> CoreSnapshot:
    payload = {key: deepcopy(source.get(key)) for key in CORE_FIELDS if key in source}
    payload["schema_version"] = SNAPSHOT_SCHEMA_VERSION
    if engine_version:
        payload["engine_version"] = engine_version
    digest = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    return CoreSnapshot(payload=payload, snapshot_hash=digest)


def snapshot_value(snapshot: CoreSnapshot | Mapping[str, Any] | None, key: str, fallback: Any = None) -> Any:
    if snapshot is None:
        return fallback
    payload = snapshot.payload if isinstance(snapshot, CoreSnapshot) else snapshot
    value = payload.get(key)
    return fallback if value is None else value


def snapshot_payload(snapshot: CoreSnapshot | Mapping[str, Any] | None) -> dict[str, Any] | None:
    if snapshot is None:
        return None
    if isinstance(snapshot, CoreSnapshot):
        return deepcopy(snapshot.payload)
    return deepcopy(dict(snapshot))


def snapshot_hash(snapshot: CoreSnapshot | Mapping[str, Any] | None) -> str | None:
    if snapshot is None:
        return None
    if isinstance(snapshot, CoreSnapshot):
        return snapshot.snapshot_hash
    return hashlib.sha256(_canonical_json(dict(snapshot)).encode("utf-8")).hexdigest()
