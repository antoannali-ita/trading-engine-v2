def bind(reference):
    names=("decision_engine","gate_status","operational_state")
    out={n:getattr(reference,n) for n in names if hasattr(reference,n)}
    if hasattr(reference,"display_state"): out["display_state"]=reference.display_state
    return out
