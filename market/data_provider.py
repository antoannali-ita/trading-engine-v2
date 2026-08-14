def bind(reference):
    names=("get_yfinance_details","extract_cashflow_line")
    return {n:getattr(reference,n) for n in names}
