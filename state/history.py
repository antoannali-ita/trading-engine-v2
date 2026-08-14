def bind(reference):
    names=("history_health","get_previous_snapshot","get_previous_selected_tickers")
    return {n:getattr(reference,n) for n in names}
