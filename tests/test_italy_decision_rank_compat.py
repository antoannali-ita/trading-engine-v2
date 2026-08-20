from engine.analyzer import load_reference


def test_italy_reference_has_decision_rank_after_load():
    ref = load_reference({"reference_module": "reference.italy_v1_2"})
    assert ref.DECISION_RANK == {
        "BUY_NOW": 6,
        "BUY_LIMIT": 5,
        "WAIT": 4,
        "WATCH": 3,
        "AVOID": 1,
        "DATA_INSUFFICIENT": 0,
    }
