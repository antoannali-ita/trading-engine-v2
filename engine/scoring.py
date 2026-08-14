from engine.market_rules import financial_adjustment_enabled

SCORE_FUNCTIONS = (
    "coverage_cap", "score_valuation", "score_business_quality", "score_growth_quality",
    "score_financial_strength", "score_earnings_quality", "score_catalyst_expectations",
    "score_technical", "score_volume_rs", "score_entry_rr", "calculate_total_score",
)

def bind(reference):
    return {name: getattr(reference, name) for name in SCORE_FUNCTIONS}

__all__ = ["bind", "financial_adjustment_enabled"]
