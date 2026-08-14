from engine.risk_reward import compute_gross_rr, compute_net_rr

def test_gross_rr(): assert abs(compute_gross_rr(100,90,120)-2.0)<1e-12
def test_net_rr_commission_drag():
    x=compute_net_rr(100,90,120,20,36); assert x is not None and x<2.0
