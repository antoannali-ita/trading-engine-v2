from engine.market_rules import financial_adjustment_enabled


def bind(reference):
    return {"value_trap_engine": reference.value_trap_engine}


__all__ = ["bind", "financial_adjustment_enabled"]
