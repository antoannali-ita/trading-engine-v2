from datetime import datetime, timezone

from trade_committee.governance import (
    classify_freshness,
    resolve_final_decision,
    snapshot_sha256,
    verify_snapshot,
)


def test_core_wait_cannot_be_overridden_by_committee():
    result = resolve_final_decision("WAIT", "APPROVE", critical_evidence_ok=True)
    assert result.verdict == "WAIT_CORE"


def test_core_buy_committee_pass_approves():
    result = resolve_final_decision("BUY_LIMIT", "PASS", critical_evidence_ok=True)
    assert result.verdict == "APPROVE"


def test_core_buy_hard_veto_rejects():
    result = resolve_final_decision("BUY", "HARD_VETO", critical_evidence_ok=True)
    assert result.verdict == "REJECT_COMMITTEE"


def test_missing_critical_evidence_waits():
    result = resolve_final_decision("BUY", "PASS", critical_evidence_ok=False)
    assert result.verdict == "WAIT_DATA"


def test_conflict_precedes_committee_approval():
    result = resolve_final_decision("BUY", "PASS", critical_evidence_ok=True, data_conflict=True)
    assert result.verdict == "WAIT_CONFLICT"


def test_stale_snapshot_waits():
    result = resolve_final_decision("BUY", "PASS", critical_evidence_ok=True, stale_snapshot=True)
    assert result.verdict == "WAIT_STALE"


def test_snapshot_hash_is_stable_and_detects_changes():
    payload = {"ticker": "TSM", "entry": 400.0, "stop": 380.0, "core_version": "v1"}
    digest = snapshot_sha256(payload)
    assert verify_snapshot(payload, digest)
    changed = dict(payload, stop=381.0)
    assert not verify_snapshot(changed, digest)


def test_freshness_uses_metric_specific_ttl():
    now = datetime(2026, 8, 27, 8, 0, tzinfo=timezone.utc)
    assert classify_freshness("2026-08-27T07:55:00+00:00", 600, now=now) == "REAL"
    assert classify_freshness("2026-08-27T07:00:00+00:00", 600, now=now) == "STALE"
