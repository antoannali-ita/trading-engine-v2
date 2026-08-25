import math

from lab.risk_metrics import (
    build_risk_basis,
    mtm_r,
    open_risk_and_locked_profit_r,
    realized_r_from_fills,
)


def test_long_and_short_r_are_symmetric():
    long = build_risk_basis(side="LONG", fill_price=100, stop_initial=95, atr14=10)
    short = build_risk_basis(side="SHORT", fill_price=100, stop_initial=105, atr14=10)
    assert mtm_r(basis=long, current_price=105) == 1.0
    assert mtm_r(basis=short, current_price=95) == 1.0


def test_risk_floor_is_explicit_not_silent():
    basis = build_risk_basis(side="LONG", fill_price=100, stop_initial=99.5, atr14=5)
    assert basis.raw_initial_risk == 0.5
    assert basis.normalized_initial_risk == 1.0
    assert basis.risk_floor_applied is True


def test_partial_exits_are_quantity_weighted():
    basis = build_risk_basis(side="LONG", fill_price=100, stop_initial=95, atr14=10)
    value = realized_r_from_fills(
        basis=basis,
        initial_qty=100,
        exit_fills=[
            {"qty": 50, "price": 105, "commission": 0},
            {"qty": 50, "price": 100, "commission": 0},
        ],
    )
    assert value == 0.5


def test_dynamic_stop_splits_capital_risk_and_locked_profit():
    basis = build_risk_basis(side="LONG", fill_price=100, stop_initial=95, atr14=10)
    risk, locked = open_risk_and_locked_profit_r(basis=basis, stop_current=102.5)
    assert risk == 0.0
    assert locked == 0.5
