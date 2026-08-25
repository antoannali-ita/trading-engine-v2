from common_utility.production_portfolio_metrics import (
    distance_pct,
    distance_to_stop_pct,
    invested_pct,
    pnl_pct,
    risk_to_stop_usd,
    target_distance_pct,
    target_gap_usd,
    target_status,
    usd_to_eur,
    weight_pct,
)


def test_usd_to_eur_uses_usd_eur_rate():
    assert usd_to_eur(1000, 0.86) == 860.0
    assert usd_to_eur(1000, 0) is None


def test_target_and_stop_distances_are_directionally_clear():
    assert round(distance_pct(110, 100), 2) == 10.0
    assert round(distance_to_stop_pct(100, 95), 2) == 5.0
    assert round(distance_to_stop_pct(100, 105), 2) == -5.0


def test_target_progress_is_negative_below_and_positive_above():
    assert round(target_distance_pct(100, 110), 2) == -9.09
    assert round(target_distance_pct(121, 110), 2) == 10.0
    assert target_gap_usd(100, 110) == -10.0
    assert target_gap_usd(121, 110) == 11.0
    assert target_status(100, 110) == "BELOW TARGET"
    assert target_status(110, 110) == "🎯 TARGET HIT"
    assert target_status(121, 110) == "🎯 TARGET HIT"


def test_target_progress_handles_missing_values():
    assert target_distance_pct(None, 110) is None
    assert target_distance_pct(100, 0) is None
    assert target_gap_usd(None, 110) is None
    assert target_status(None, 110) == "N/D"


def test_portfolio_pnl_and_weights():
    assert round(pnl_pct(1100, 1000), 2) == 10.0
    assert round(weight_pct(2500, 10000), 2) == 25.0
    assert round(invested_pct(19600, 35000), 2) == 56.0


def test_risk_to_stop_never_goes_negative():
    assert risk_to_stop_usd(10, 100, 95) == 50.0
    assert risk_to_stop_usd(10, 100, 105) == 0.0
    assert risk_to_stop_usd(10, 100, None) is None
