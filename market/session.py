from __future__ import annotations

from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo


MARKET_RULES = {
    "usa": {
        "timezone": "America/New_York",
        "open": time(9, 30),
        "close": time(16, 0),
    },
    "italy": {
        "timezone": "Europe/Rome",
        "open": time(9, 0),
        "close": time(17, 30),
    },
}


def regular_session_status(market: str, now: datetime | None = None):
    market = market.lower()
    rule = MARKET_RULES[market]
    tz = ZoneInfo(rule["timezone"])
    utc_now = now or datetime.now(timezone.utc)
    if utc_now.tzinfo is None:
        utc_now = utc_now.replace(tzinfo=timezone.utc)
    local_now = utc_now.astimezone(tz)
    local_clock = local_now.time().replace(tzinfo=None)
    weekday_open = local_now.weekday() < 5
    in_hours = weekday_open and rule["open"] <= local_clock <= rule["close"]
    return {
        "market": market,
        "market_session_open": in_hours,
        "market_local_time": local_now.isoformat(),
        "market_holiday": False,
        "market_in_hours": in_hours,
        "timezone": rule["timezone"],
    }


def status(reference=None, market: str | None = None):
    """Return a normalized session status.

    Italy keeps the frozen reference calendar when available. Other markets use
    the generic DST-aware regular-session gate instead of defaulting to OPEN.
    """
    if reference is not None and hasattr(reference, "italian_market_session_status"):
        return reference.italian_market_session_status()
    if market is None:
        raise ValueError("market is required when the reference has no session helper")
    return regular_session_status(market)
