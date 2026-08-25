from lab.verdict_engine import evaluate_verdict, maturity_for_closed


def test_maturity_boundaries_are_frozen():
    assert maturity_for_closed(9) == "UNDERTESTED"
    assert maturity_for_closed(10) == "EARLY"
    assert maturity_for_closed(29) == "EARLY"
    assert maturity_for_closed(30) == "DEVELOPING"
    assert maturity_for_closed(50) == "EVALUABLE"


def test_early_never_becomes_working():
    result = evaluate_verdict(
        closed_count=8,
        net_pf=3.0,
        expectancy_r=1.2,
        avg_net_return_pct=5.0,
        stress_status="PASS",
    )
    assert result.verdict == "EARLY"


def test_working_requires_closed_edge_and_no_live_stress():
    ok = evaluate_verdict(
        closed_count=35,
        net_pf=1.30,
        expectancy_r=0.12,
        avg_net_return_pct=0.4,
        stress_status="PASS",
    )
    stressed = evaluate_verdict(
        closed_count=35,
        net_pf=1.30,
        expectancy_r=0.12,
        avg_net_return_pct=0.4,
        stress_status="STRESSED",
    )
    assert ok.verdict == "WORKING"
    assert stressed.verdict == "WATCH"


def test_negative_expectancy_with_sufficient_sample_is_weak():
    result = evaluate_verdict(
        closed_count=35,
        net_pf=1.10,
        expectancy_r=-0.02,
        avg_net_return_pct=0.1,
        stress_status="PASS",
    )
    assert result.verdict == "WEAK"


def test_data_issue_precedes_everything():
    result = evaluate_verdict(
        closed_count=80,
        net_pf=2.0,
        expectancy_r=0.5,
        avg_net_return_pct=1.0,
        stress_status="PASS",
        data_issue=True,
    )
    assert result.verdict == "DATA_ISSUE"
