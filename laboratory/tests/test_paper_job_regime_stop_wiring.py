import importlib.util
from pathlib import Path

JOB_PATH = Path(__file__).resolve().parents[1] / "jobs" / "run_paper_signals.py"
SPEC = importlib.util.spec_from_file_location("run_paper_signals_regime_wiring", JOB_PATH)
JOB = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(JOB)


def test_regime_adjusted_stop_multiplier_is_imported_and_wired():
    # The job must use the shared, tested regime_adjusted_stop_multiplier
    # rather than a hardcoded 2.0x, so that a HIGH-volatility regime widens
    # the stop consistently with the standalone unit tests.
    assert JOB.regime_adjusted_stop_multiplier("BULL_QUIET") == 2.0
    assert JOB.regime_adjusted_stop_multiplier("BEAR_HIGH_VOL") == 2.5


def test_source_uses_regime_multiplier_for_risk_per_share():
    source = JOB_PATH.read_text(encoding="utf-8")
    assert "stop_atr_mult = regime_adjusted_stop_multiplier(market_regime.get(\"state\"))" in source
    assert "risk_per_share = stop_atr_mult * atr" in source
    # Guard against silently reintroducing the old hardcoded multiplier.
    assert "risk_per_share = 2.0 * atr" not in source
