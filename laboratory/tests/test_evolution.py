from lab.evolution import robustness_score, verdict


def test_rejects_tiny_oos_sample():
    parent = {"return_pct": 1.0, "profit_factor": 1.2, "trades": 10, "max_drawdown_pct": -2.0}
    child = {"return_pct": 5.0, "profit_factor": 3.0, "trades": 2, "max_drawdown_pct": -1.0}
    assert verdict(parent, child, 90.0) == "REJECTED"


def test_promotable_requires_better_return_pf_and_controlled_drawdown():
    parent = {"return_pct": 1.0, "profit_factor": 1.2, "trades": 10, "max_drawdown_pct": -3.0}
    child = {"return_pct": 2.0, "profit_factor": 1.5, "trades": 12, "max_drawdown_pct": -3.1}
    assert verdict(parent, child, 75.0) == "PROMOTABLE"


def test_robustness_penalizes_train_oos_sign_flip():
    train = {"return_pct": 5.0}
    good = {"return_pct": 2.0, "profit_factor": 1.5, "trades": 12, "max_drawdown_pct": -2.0}
    bad = {"return_pct": -2.0, "profit_factor": 0.7, "trades": 12, "max_drawdown_pct": -5.0}
    assert robustness_score(train, good) > robustness_score(train, bad)
