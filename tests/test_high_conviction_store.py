from state.high_conviction_store import _payload, classify_high_conviction


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


def test_payload_accepts_core_level_aliases():
    row = _payload(
        "RUN1",
        "usa",
        {
            "ticker": "CSCO",
            "ideal_entry": 109.23,
            "max_entry": 111.77,
            "stop_loss": 104.35,
            "target1": 124.71,
            "target2": 129.88,
            "entry_low": 107.86,
            "entry_high": 110.60,
            "rr_net_tp1": 2.12,
            "rr_net_tp2": 2.92,
            "position_risk_usd": 143.33,
        },
        "PRE-BUY HIGH",
    )
    assert row["entry"] == 109.23
    assert row["max_buy"] == 111.77
    assert row["stop"] == 104.35
    assert row["tp1"] == 124.71
    assert row["tp2"] == 129.88
    assert row["buy_zone_low"] == 107.86
    assert row["buy_zone_high"] == 110.60
    assert row["net_rr_tp1"] == 2.12
    assert row["net_rr_tp2"] == 2.92
    assert row["risk_usd"] == 143.33
