from engine.market_rules import should_exclude_gem


def bind(reference):
    names=("build_discovery_where","run_single_tv_lens","run_tradingview_discovery","is_otc_like","passes_survival","build_candidate","build_candidates")
    out={n:getattr(reference,n) for n in names}
    for n in ("is_gem_foreign_listing","build_universe_exclusion_candidate","to_yfinance_ticker","to_tv_symbol"):
        if hasattr(reference,n): out[n]=getattr(reference,n)
    return out


__all__ = ["bind", "should_exclude_gem"]
