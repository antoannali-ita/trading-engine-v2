from typing import Optional

def compute_gross_rr(entry: Optional[float], stop: Optional[float], tp: Optional[float]) -> Optional[float]:
    if None in (entry, stop, tp): return None
    if entry <= stop or tp <= entry: return None
    risk = entry - stop; reward = tp - entry
    return None if risk <= 0 or reward <= 0 else reward / risk

def compute_net_rr(entry: Optional[float], stop: Optional[float], tp: Optional[float], shares: int, round_trip_commission: float) -> Optional[float]:
    if None in (entry, stop, tp) or shares <= 0: return None
    if entry <= stop or tp <= entry: return None
    cps = round_trip_commission / shares
    risk = (entry - stop) + cps
    reward = (tp - entry) - cps
    return None if risk <= 0 or reward <= 0 else reward / risk

def bind(reference):
    # During Phase A these exact baseline functions are the source of truth.
    return {"compute_gross_rr": reference.compute_gross_rr, "compute_net_rr": reference.compute_net_rr}
