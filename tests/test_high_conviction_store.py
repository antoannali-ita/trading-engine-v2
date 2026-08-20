from state.high_conviction_store import classify_high_conviction


def test_usa_buy_states_are_high_conviction():
    assert classify_high_conviction("usa", {"decision": "BUY_NOW"}) == "BUY NOW"
    assert classify_high_conviction("usa", {"decision": "BUY_LIMIT"}) == "BUY LIMIT"


def test_usa_prebuy_high_requires_eligible_score_8():
    base = {"decision": "WAIT", "display_state": "PRE-BUY", "prebuy_eligible": True}
    assert classify_high_conviction("usa", {**base, "prebuy_score": 10}) == "PRE-BUY HIGH"
    assert classify_high_conviction("usa", {**base, "prebuy_score": 8}) == "PRE-BUY HIGH"
    assert classify_high_conviction("usa", {**base, "prebuy_score": 7}) is None
    assert classify_high_conviction("usa", {**base, "prebuy_score": 10, "prebuy_eligible": False}) is None


def test_italy_uses_existing_operational_semantics():
    assert classify_high_conviction("italy", {"decision": "WAIT", "operational_state": "READY_FOR_TRIGGER"}) == "PRE-BUY HIGH"
    assert classify_high_conviction("italy", {"decision": "WAIT", "operational_state": "SCORE_MARGINAL"}) == "PRE-BUY HIGH"
    assert classify_high_conviction("italy", {"decision": "WAIT", "operational_state": "WAIT_RR"}) is None
