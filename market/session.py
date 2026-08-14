def status(reference):
    if hasattr(reference,"italian_market_session_status"):
        return reference.italian_market_session_status()
    return {"market_session_open": True, "market_local_time": None, "market_holiday": False, "market_in_hours": True}
