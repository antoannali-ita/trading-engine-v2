from lab.paper_policy import classify_paper_tier


def _dq(status="GREEN"):
    return {"status": status, "red": [], "yellow": []}


def test_yellow_cannot_enter_tier_a():
    out = classify_paper_tier(
        strategy_score=90,
        trade_score=90,
        trigger="CONFIRMED",
        data_quality=_dq("YELLOW"),
        rr_net=2.5,
        price=100,
        max_buy=100,
        atr=2,
        earnings_days=20,
        qty=10,
    )
    assert out["tier"] == "B"
    assert "DATA_QUALITY_YELLOW" in out["warnings"]
    assert "DATA_NOT_GREEN_FOR_TIER_A" in out["tier_checks"]["A"]["failed"]


def test_red_is_hard_veto_for_all_tiers():
    out = classify_paper_tier(
        strategy_score=95,
        trade_score=95,
        trigger="CONFIRMED",
        data_quality=_dq("RED"),
        rr_net=3.0,
        price=100,
        max_buy=100,
        atr=2,
        earnings_days=30,
        qty=10,
    )
    assert not out["eligible"]
    assert out["tier"] is None
    assert "DATA_QUALITY_RED" in out["data_gate_failures"]


def test_tier_c_is_explicitly_non_operational():
    out = classify_paper_tier(
        strategy_score=60,
        trade_score=45,
        trigger="WAITING",
        data_quality=_dq("GREEN"),
        rr_net=0.90,
        price=100,
        max_buy=99,
        atr=2,
        earnings_days=4,
        qty=5,
    )
    assert out["eligible"]
    assert out["tier"] == "C"
    assert out["research_only"] is True
    assert out["operational"] is False
    assert out["safety_label"] == "RESEARCH_ONLY_NON_OPERATIONAL"


def test_earnings_thresholds_differ_by_tier():
    # Four days blocks A/B but is intentionally testable in C.
    out = classify_paper_tier(
        strategy_score=90,
        trade_score=90,
        trigger="CONFIRMED",
        data_quality=_dq("GREEN"),
        rr_net=2.5,
        price=100,
        max_buy=100,
        atr=2,
        earnings_days=4,
        qty=10,
    )
    assert out["tier"] == "C"
    assert "EARNINGS_LT_7D" in out["tier_checks"]["A"]["failed"]
    assert "EARNINGS_LT_5D" in out["tier_checks"]["B"]["failed"]


def test_earnings_under_three_days_is_hard_veto():
    out = classify_paper_tier(
        strategy_score=90,
        trade_score=90,
        trigger="CONFIRMED",
        data_quality=_dq("GREEN"),
        rr_net=2.5,
        price=100,
        max_buy=100,
        atr=2,
        earnings_days=2,
        qty=10,
    )
    assert not out["eligible"]
    assert "EARNINGS_LT_3D" in out["policy_hard_failures"]
