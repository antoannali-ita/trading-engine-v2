def bind(reference):
    names=("change_state","attach_history_states")
    return {n:getattr(reference,n) for n in names}
