def bind(reference):
    names=("parse_portfolio_positions","get_portfolio_sectors","portfolio_fit_score")
    return {n:getattr(reference,n) for n in names}
