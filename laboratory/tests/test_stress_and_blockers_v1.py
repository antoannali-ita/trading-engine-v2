from lab.blocker_policy import main_blocker, primary_blocker
from lab.stress_policy import evaluate_live_stress


def test_live_stress_thresholds_are_explicit():
    assert evaluate_live_stress(total_mtm_r=-1.9, worst_open_r=-1.0, open_risk_r=2.9).status == "PASS"
    assert evaluate_live_stress(total_mtm_r=-2.1, worst_open_r=-1.0, open_risk_r=2.0).status == "STRESSED"
    assert evaluate_live_stress(total_mtm_r=-2.1, worst_open_r=-1.3, open_risk_r=2.0).status == "CRITICAL"


def test_blocker_priority_is_deterministic_not_if_order():
    codes = ["TRIGGER_NOT_CONFIRMED", "PRICE_ABOVE_MAX_BUY", "STRATEGY_SCORE_LT_75"]
    assert primary_blocker(codes) == "STRATEGY_SCORE_LT_75"


def test_main_blocker_is_nd_below_minimum_sample():
    result = main_blocker(["TRIGGER_NOT_CONFIRMED"] * 19)
    assert result.code is None
    assert result.reason_code == "INSUFFICIENT_BLOCKER_SAMPLE"


def test_main_blocker_uses_primary_rejected_sample():
    result = main_blocker(["TRIGGER_NOT_CONFIRMED"] * 12 + ["PRICE_ABOVE_MAX_BUY"] * 8)
    assert result.code == "TRIGGER_NOT_CONFIRMED"
    assert result.sample == 20
    assert result.pct == 60.0
