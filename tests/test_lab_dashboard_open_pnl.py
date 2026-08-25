import pytest
from common_utility.lab_dashboard_metrics import open_net_pnl, estimated_round_trip_cost, gross_price_return_pct

def test_open_net_pnl_entry_cost_only():
    assert open_net_pnl(100.0, 100.0, 10, 9.90, 5.0) == pytest.approx(-10.40)

def test_round_trip_cost_is_separate():
    assert estimated_round_trip_cost(100.0, 100.0, 10, 9.90, 5.0) == pytest.approx(20.80)

def test_price_move_not_contaminated_by_costs():
    assert gross_price_return_pct(310.34, 310.35) > 0
