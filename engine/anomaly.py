def bind(reference):
    names=("resolve_next_earnings_date","detect_corporate_action_inconsistency","data_anomaly_engine")
    return {n:getattr(reference,n) for n in names}
