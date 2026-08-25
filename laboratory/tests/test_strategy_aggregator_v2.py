from lab.strategy_aggregator import aggregate_strategy, position_r_metrics


def _details(score=80, tier="A", failed=None):
    return {
        "strategy_version": "v1",
        "strategy_score": score,
        "trigger": "CONFIRMED",
        "atr14": 5,
        "data_quality": {"status": "GREEN"},
        "paper_policy": {
            "eligible": tier is not None,
            "tier": tier,
            "tier_checks": {"A": {"failed": failed or []}},
        },
    }


def test_position_metrics_use_fill_and_dynamic_stop():
    p = {
        "strategy": "s",
        "status": "OPEN",
        "entry_price": 100,
        "fill_price": 100,
        "stop_initial": 95,
        "stop_current": 102.5,
        "last_price": 105,
        "details": _details(),
    }
    m = position_r_metrics(p)
    assert m["mtm_r"] == 1.0
    assert m["open_risk_r"] == 0.0
    assert m["locked_profit_r"] == 0.5


def test_summary_never_marks_early_working():
    signals = [
        {"strategy": "s", "status": "PAPER_OPEN", "details": _details()}
        for _ in range(8)
    ]
    positions = []
    for i in range(8):
        positions.append({
            "strategy": "s",
            "strategy_version": "v1",
            "status": "CLOSED",
            "entry_price": 100,
            "stop_initial": 95,
            "exit_price": 106,
            "return_pct": 6,
            "details": _details(),
        })
    result = aggregate_strategy(
        strategy="s",
        strategy_version_value="v1",
        signals=signals,
        positions=positions,
        outcomes=[],
    )
    assert result["closed"] == 8
    assert result["verdict"] == "EARLY"
    assert result["maturity"] == "UNDERTESTED"


def test_main_blocker_requires_minimum_rejected_sample():
    signals = [
        {"strategy": "s", "details": _details(tier=None, failed=["TRIGGER_NOT_CONFIRMED"])}
        for _ in range(19)
    ]
    result = aggregate_strategy(
        strategy="s",
        strategy_version_value="v1",
        signals=signals,
        positions=[],
        outcomes=[],
    )
    assert result["main_blocker"] is None
    assert result["blocker_sample"] == 19
