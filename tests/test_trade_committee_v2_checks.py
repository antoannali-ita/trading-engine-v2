from trade_committee.research_checks import build_trade_plan, quality_assessment, technical_assessment
from trade_committee.rigor import cross_validate, verify_market_cap, verify_pe


def test_financial_rigor_market_cap_and_pe():
    mc = verify_market_cap(price=100, shares=10_000_000, reported_market_cap=1_000_000_000)
    pe = verify_pe(price=100, eps=5, reported_pe=20)
    assert mc["status"] == "PASS"
    assert mc["deviation_pct"] == 0.0
    assert pe["status"] == "PASS"


def test_cross_validate_flags_large_discrepancy():
    result = cross_validate({"Yahoo": 100, "TradingView": 120}, tolerance_pct=2)
    assert result["status"] == "WARNING"
    assert result["max_deviation_pct"] > 2


def test_quality_assessment_is_deterministic():
    result = quality_assessment({
        "returnOnEquity": 0.20,
        "currentRatio": 1.5,
        "debtToEquity": 40,
        "operatingCashflow": 100,
        "freeCashflow": 80,
        "revenueGrowth": 0.08,
        "earningsGrowth": 0.10,
        "profitMargins": 0.15,
    })
    assert result["score"] == 100.0
    assert result["red_flags"] == []


def test_technical_trend_fail_gate():
    result = technical_assessment({
        "price": 80,
        "sma20": 85,
        "sma50": 90,
        "sma200": 100,
        "rsi14": 45,
        "macd": -1,
        "macd_signal": 0,
    })
    assert result["trend_fail"] is True
    assert result["score"] < 50


def test_trade_plan_includes_fineco_costs_and_rr():
    result = build_trade_plan({
        "price": 100,
        "atr14": 4,
        "support20": 94,
        "resistance60": 115,
        "resistance120": 130,
    })
    assert result["status"] == "REAL"
    assert result["qty"] == 24
    assert result["commission_per_side"] == 18.0
    assert result["stop"] < result["entry"] < result["tp1"] <= result["tp2"]
    assert result["rr1_net"] > 0
