from datetime import datetime, timezone

from orchestrator.confluence import compute_confluence, signal_family


def _row(engine, strategy, ticker, signal_type, *, actionable=True, score=80, market="USA"):
    return {
        "signal_id": f"{engine}-{strategy}-{ticker}",
        "engine": engine,
        "strategy": strategy,
        "ticker": ticker,
        "market": market,
        "signal_type": signal_type,
        "decision": signal_type,
        "is_actionable": actionable,
        "conviction": score,
        "detected_at": datetime.now(timezone.utc).isoformat(),
    }


def test_single_double_triple_confirmation():
    rows = [
        _row("CORE", "CORE", "NVDA", "PRE_BUY_HIGH", score=84),
        _row("SHORT", "SHORT_1_3M", "NVDA", "SHADOW_BUY", score=78),
        _row("FAST", "FAST_5_20D", "NVDA", "IN_BUY_ZONE", score=72),
    ]
    result = compute_confluence(rows)
    assert result[0]["level"] == "TRIPLE_CONFIRMATION"
    assert result[0]["families"] == ["CORE", "FAST", "SHORT"]
    assert result[0]["eligible_for_ai"] is True


def test_multihorizon_is_validation_not_duplicate_base_engine():
    rows = [
        _row("CORE", "CORE", "NVDA", "PRE_BUY_HIGH"),
        _row("MULTI_HORIZON", "SHORT_1_3M", "NVDA", "SHADOW_BUY"),
    ]
    result = compute_confluence(rows)[0]
    assert signal_family(rows[1]) == "MULTI_HORIZON"
    assert result["level"] == "SINGLE_SIGNAL"
    assert result["multi_horizon_positive"] is True
    assert result["eligible_for_ai"] is True


def test_non_actionable_rows_do_not_create_confirmation():
    rows = [
        _row("CORE", "CORE", "MSFT", "WATCH", actionable=False),
        _row("FAST", "FAST", "MSFT", "NORMAL", actionable=False),
    ]
    result = compute_confluence(rows)[0]
    assert result["level"] == "NONE"
    assert result["eligible_for_ai"] is False
