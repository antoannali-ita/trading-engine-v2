from engine.analyzer import normalize_candidate


class DummyItalyReference:
    pass


def _cfg():
    return {"market": "italy", "prebuy_enabled": False}


def test_italy_buy_limit_above_max_buy_is_approaching_not_ready():
    candidate = {
        "ticker": "PRY",
        "decision": "BUY_LIMIT",
        "operational_state": "LIMIT_READY",
        "above_max_buy": True,
        "distance_to_max_buy_pct": 4.4,
        "trigger_state": "WAITING",
    }

    out = normalize_candidate(DummyItalyReference(), "italy", candidate, _cfg())

    assert out["decision"] == "WATCH"
    assert out["operational_state"] == "APPROACHING"
    assert out["display_state"] == "WAIT"
    assert out["limit_ready"] is False
    assert "NON INSEGUIRE" in out["veto_reasons"][0]


def test_italy_buy_limit_at_or_below_max_buy_stays_buy_limit():
    candidate = {
        "ticker": "PRY",
        "decision": "BUY_LIMIT",
        "operational_state": "LIMIT_READY",
        "above_max_buy": False,
        "distance_to_max_buy_pct": -0.2,
        "trigger_state": "WAITING",
    }

    out = normalize_candidate(DummyItalyReference(), "italy", candidate, _cfg())

    assert out["decision"] == "BUY_LIMIT"
    assert out["operational_state"] == "LIMIT_READY"
    assert out["display_state"] == "BUY LIMIT"
