import pytest

from lab.decision_engine import regime_adjusted_stop_multiplier


@pytest.mark.parametrize("state", ["BULL_QUIET", "RANGE_NEUTRAL", "UNKNOWN", None, "SOMETHING_UNSEEN"])
def test_calm_or_unknown_regimes_keep_base_multiplier(state):
    assert regime_adjusted_stop_multiplier(state, base=2.0) == 2.0


@pytest.mark.parametrize("state", ["BULL_VOLATILE", "BEAR_HIGH_VOL", "bull_volatile", "bear_high_vol"])
def test_high_volatility_regimes_widen_the_stop(state):
    assert regime_adjusted_stop_multiplier(state, base=2.0) == 2.5


def test_never_returns_less_than_base_even_with_a_custom_base():
    # Widening only, never tightening: a custom, already-wide base must never
    # be narrowed by a "calmer" table entry.
    assert regime_adjusted_stop_multiplier("BULL_QUIET", base=3.0) == 3.0
    assert regime_adjusted_stop_multiplier("BEAR_HIGH_VOL", base=3.0) == 3.0


def test_unknown_state_defaults_safely():
    assert regime_adjusted_stop_multiplier("TOTALLY_UNRECOGNIZED_STATE") == 2.0
