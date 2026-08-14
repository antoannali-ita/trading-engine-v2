"""Parity-safe access to indicator functions from the frozen baseline.
Phase B can replace wrappers one function at a time after parity tests pass.
"""
from engine.market_rules import rs_state_when_benchmark_missing


def bind(reference):
    return {
        "compute_rsi": reference.compute_rsi,
        "compute_atr": reference.compute_atr,
        "pct_return": reference.pct_return,
        "classify_technical_state": reference.classify_technical_state,
        "classify_rs": reference.classify_rs,
    }


def classify_rs_safe(reference, candidate, benchmark_hist):
    """Explicit provider-failure guardrail for modular Phase B code."""
    missing = rs_state_when_benchmark_missing(benchmark_hist)
    if missing is not None:
        return missing
    return reference.classify_rs(candidate)


__all__ = ["bind", "classify_rs_safe", "rs_state_when_benchmark_missing"]
