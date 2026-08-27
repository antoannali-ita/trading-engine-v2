from pathlib import Path
import json

from trade_committee.core_snapshot import build_core_snapshot
from trade_committee.policy import CheckClass, HardVeto, evaluate_verdict
from trade_committee.technical_normalization import normalize_market_bundle, wilder_rsi

import pandas as pd


FIXTURE = Path(__file__).resolve().parent / "fixtures" / "crus_core_snapshot_20260826.json"


def test_perfect_candidate_can_be_approved():
    result = evaluate_verdict(
        committee_score=82,
        check_classes=[CheckClass.COMPLETE] * 8,
        hard_vetoes=[],
    )
    assert result.verdict == "APPROVE"


def test_structural_missing_enrichment_does_not_block_approve():
    result = evaluate_verdict(
        committee_score=82,
        check_classes=[CheckClass.COMPLETE] * 6 + [CheckClass.ENRICHMENT_ND] * 4,
        hard_vetoes=[],
    )
    assert result.verdict == "APPROVE"
    assert result.data_confidence == 100.0


def test_hard_veto_always_blocks_approve():
    result = evaluate_verdict(
        committee_score=99,
        check_classes=[CheckClass.COMPLETE] * 10,
        hard_vetoes=[HardVeto.TRIGGER_INVALID],
    )
    assert result.verdict == "REJECT_HARD_VETO"


def test_multiple_core_warnings_without_hard_veto_still_reaches_wait_not_reject():
    result = evaluate_verdict(
        committee_score=68,
        check_classes=[CheckClass.CORE_WARNING] * 4 + [CheckClass.ENRICHMENT_ND] * 3,
        hard_vetoes=[],
    )
    assert result.verdict.startswith("WAIT")
    assert result.verdict != "REJECT_HARD_VETO"


def test_crus_historical_fixture_is_hashable_and_has_no_hard_veto_by_construction():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    snapshot = build_core_snapshot(payload, engine_version=payload.get("engine_version"))
    assert snapshot.payload["ticker"] == "CRUS"
    assert len(snapshot.snapshot_hash) == 64
    assert snapshot.payload["trigger_state"] == "CONFIRMED"
    assert snapshot.payload["veto_reasons"] == []


def test_wilder_rsi_reference_is_bounded():
    close = pd.Series([44, 44.15, 43.9, 44.35, 44.8, 45.1, 44.75, 45.2, 45.6, 45.4, 45.9, 46.1, 45.8, 46.3, 46.7, 46.5, 46.9, 47.2, 47.0, 47.4])
    value = wilder_rsi(close, 14)
    assert value is not None
    assert 0 <= value <= 100


def test_intraday_rvol_is_not_penalized_as_full_day():
    idx = pd.date_range("2026-08-01", periods=20, freq="D")
    hist = pd.DataFrame({"Close": range(100, 120), "Volume": [1000] * 19 + [200]}, index=idx)
    market = {"history": hist, "volume": 200, "avg_volume20": 960, "relative_volume": 200 / 960}
    now = pd.Timestamp("2026-08-27 11:00:00", tz="America/New_York").to_pydatetime()
    result = normalize_market_bundle(market, now=now)
    assert result["rvol_status"] == "PARTIAL_SESSION"
    assert result["relative_volume"] is None
    assert result["relative_volume_partial"] is not None


def test_closed_market_rvol_is_full_day():
    idx = pd.date_range("2026-08-01", periods=20, freq="D")
    hist = pd.DataFrame({"Close": range(100, 120), "Volume": [1000] * 20}, index=idx)
    market = {"history": hist, "volume": 1000, "avg_volume20": 1000, "relative_volume": 1.0}
    now = pd.Timestamp("2026-08-27 17:00:00", tz="America/New_York").to_pydatetime()
    result = normalize_market_bundle(market, now=now)
    assert result["rvol_status"] == "FULL_SESSION"
    assert result["relative_volume"] == 1.0
