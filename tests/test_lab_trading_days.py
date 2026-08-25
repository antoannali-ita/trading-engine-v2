from common_utility.lab_dashboard_metrics import (
    date_label,
    open_trade_state,
    trading_days_elapsed,
)


def test_trading_days_opening_session_is_zero():
    sessions = ["2026-08-21", "2026-08-24", "2026-08-25"]
    assert trading_days_elapsed("2026-08-25T14:35:00Z", "2026-08-25", sessions) == 0


def test_trading_days_friday_to_monday_is_one():
    sessions = ["2026-08-21", "2026-08-24", "2026-08-25"]
    assert trading_days_elapsed("2026-08-21", "2026-08-24", sessions) == 1


def test_non_sessions_are_not_counted():
    sessions = ["2026-07-02", "2026-07-06"]
    assert trading_days_elapsed("2026-07-02", "2026-07-06", sessions) == 1


def test_open_trade_state_prefers_trading_days_age():
    state = open_trade_state(
        100,
        100.01,
        10,
        opened_at="2026-08-20T10:00:00Z",
        trading_days_open=1,
    )
    assert state == "⚪ OPEN · TOO EARLY"


def test_date_label_is_compact_and_missing_safe():
    assert date_label("2026-08-25T14:35:00Z") == "25/08/2026"
    assert date_label(None) == "N/D"
