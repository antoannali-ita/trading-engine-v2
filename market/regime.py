def bind(reference):
    names=("fetch_market_hist","market_regime_engine")
    out={n:getattr(reference,n) for n in names}
    if hasattr(reference,"get_ftsemib_benchmark_hist"):
        out["get_ftsemib_benchmark_hist"]=reference.get_ftsemib_benchmark_hist
    return out
