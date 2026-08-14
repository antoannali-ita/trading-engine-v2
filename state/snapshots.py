def bind(reference):
    names=("json_safe","save_run")
    return {n:getattr(reference,n) for n in names}
