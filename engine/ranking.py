def bind(reference):
    names=("operational_rank_key","select_ranked")
    return {n:getattr(reference,n) for n in names}
