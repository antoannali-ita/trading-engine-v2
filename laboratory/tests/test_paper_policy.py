from lab.paper_policy import classify_paper_tier, lab_portfolio_fit


def _dq():
    return {"status": "GREEN", "blocked": False}


def test_tier_a_high_quality():
    out = classify_paper_tier(
        strategy_score=82, trade_score=80, trigger="CONFIRMED",
        data_quality=_dq(), rr_net=2.1, price=100, max_buy=101,
        atr=2, earnings_days=20, qty=10,
    )
    assert out["eligible"] is True
    assert out["tier"] == "A"


def test_tier_b_relaxes_rr_but_keeps_trigger():
    out = classify_paper_tier(
        strategy_score=70, trade_score=62, trigger="CONFIRMED",
        data_quality=_dq(), rr_net=1.3, price=101, max_buy=100.5,
        atr=2, earnings_days=10, qty=10,
    )
    assert out["eligible"] is True
    assert out["tier"] == "B"


def test_tier_c_can_test_waiting_trigger():
    out = classify_paper_tier(
        strategy_score=60, trade_score=48, trigger="WAITING",
        data_quality=_dq(), rr_net=1.0, price=101, max_buy=100,
        atr=2, earnings_days=None, qty=5,
    )
    assert out["eligible"] is True
    assert out["tier"] == "C"


def test_data_quality_red_is_hard_veto():
    out = classify_paper_tier(
        strategy_score=90, trade_score=90, trigger="CONFIRMED",
        data_quality={"status": "RED", "blocked": True}, rr_net=3,
        price=100, max_buy=101, atr=2, earnings_days=30, qty=10,
    )
    assert out["eligible"] is False
    assert "DATA_QUALITY_RED" in out["hard_failed"]


def test_same_symbol_different_strategy_is_allowed():
    positions = [{"symbol": "NVDA", "strategy": "trend_continuation", "status": "OPEN"}]
    out = lab_portfolio_fit(
        symbol="NVDA", strategy="short_term_reversal", open_positions=positions,
        opened_this_run=0,
    )
    assert out["eligible"] is True


def test_same_symbol_same_strategy_is_duplicate():
    positions = [{"symbol": "NVDA", "strategy": "trend_continuation", "status": "OPEN"}]
    out = lab_portfolio_fit(
        symbol="NVDA", strategy="trend_continuation", open_positions=positions,
        opened_this_run=0,
    )
    assert out["eligible"] is False
    assert "DUPLICATE_SYMBOL_STRATEGY" in out["failed"]
