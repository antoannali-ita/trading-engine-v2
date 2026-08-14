def available(reference) -> bool:
    return hasattr(reference, "prebuy_engine")

def bind(reference):
    return {"prebuy_engine": reference.prebuy_engine} if available(reference) else {}
