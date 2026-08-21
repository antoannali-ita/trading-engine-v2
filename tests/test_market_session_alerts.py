from datetime import datetime, timezone

from market.session import regular_session_status
from monitor.fast_monitor import market_session_open, quote_is_fresh


def utc(y, m, d, hh, mm=0):
    return datetime(y, m, d, hh, mm, tzinfo=timezone.utc)


def test_usa_closed_before_regular_session_summer():
    # 2026-08-21 12:00 UTC = 08:00 New York
    assert market_session_open("usa", utc(2026, 8, 21, 12, 0)) is False


def test_usa_open_during_regular_session_summer():
    # 2026-08-21 14:00 UTC = 10:00 New York
    assert market_session_open("usa", utc(2026, 8, 21, 14, 0)) is True


def test_italy_open_during_regular_session_summer():
    # 2026-08-21 08:00 UTC = 10:00 Rome
    assert market_session_open("italy", utc(2026, 8, 21, 8, 0)) is True


def test_weekend_is_closed():
    assert market_session_open("usa", utc(2026, 8, 22, 15, 0)) is False
    assert regular_session_status("italy", utc(2026, 8, 22, 10, 0))["market_session_open"] is False


def test_stale_quote_is_rejected():
    now = utc(2026, 8, 21, 14, 0)
    assert quote_is_fresh(utc(2026, 8, 21, 13, 30), now) is False


def test_recent_quote_is_accepted():
    now = utc(2026, 8, 21, 14, 0)
    assert quote_is_fresh(utc(2026, 8, 21, 13, 50), now) is True
