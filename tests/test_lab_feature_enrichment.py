from datetime import datetime, timezone

import pytest

from laboratory.feature_enrichment import (
    CANDIDATE_FEATURES,
    FEATURE_SET_VERSION,
    build_feature_snapshot,
)


def test_feature_enrichment_preserves_raw_continuous_values():
    snapshot = build_feature_snapshot(
        market="USA",
        symbol="ABC",
        strategy="trend_continuation",
        strategy_version="v2.0",
        raw_features={"relative_volume": 1.43, "atr14": 2.1},
        observed_at=datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc),
    )
    assert snapshot.values["relative_volume"] == 1.43
    assert snapshot.values["atr14"] == 2.1
    assert snapshot.values["relative_strength_3m"] is None
    assert snapshot.feature_set_version == FEATURE_SET_VERSION


def test_benchmark_is_fixed_by_market():
    usa = build_feature_snapshot(
        market="USA", symbol="ABC", strategy="s", strategy_version="v1", raw_features={}
    )
    italy = build_feature_snapshot(
        market="ITALY", symbol="ABC", strategy="s", strategy_version="v1", raw_features={}
    )
    assert usa.benchmark_symbol == "SPY"
    assert italy.benchmark_symbol == "FTSEMIB"


def test_unknown_market_fails_instead_of_guessing_benchmark():
    with pytest.raises(ValueError):
        build_feature_snapshot(
            market="GLOBAL", symbol="ABC", strategy="s", strategy_version="v1", raw_features={}
        )


def test_feature_layer_contains_no_decision_or_threshold_fields():
    forbidden = {"decision", "score", "entry", "stop", "max_buy", "qty", "threshold"}
    assert forbidden.isdisjoint(set(CANDIDATE_FEATURES))
