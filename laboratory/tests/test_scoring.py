from laboratory.src.lab.scoring import ladder_decision, weighted_score
from laboratory.src.lab.models import Decision


def test_failed_gate_always_rejects():
    assert ladder_decision(99, gates_passed=False) == Decision.REJECT


def test_ladder_boundaries():
    assert ladder_decision(39.99) == Decision.REJECT
    assert ladder_decision(40) == Decision.WATCH
    assert ladder_decision(55) == Decision.INTERESTING
    assert ladder_decision(65) == Decision.PRE_BUY
    assert ladder_decision(75) == Decision.BUY_CANDIDATE
    assert ladder_decision(85) == Decision.HIGH_CONVICTION


def test_weighted_score_is_normalized():
    score = weighted_score({"quality": 80, "technical": 60}, {"quality": 3, "technical": 1})
    assert score == 75
