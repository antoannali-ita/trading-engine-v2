import importlib.util
from pathlib import Path


JOB_PATH = Path(__file__).resolve().parents[1] / "jobs" / "run_paper_signals.py"
SPEC = importlib.util.spec_from_file_location("run_paper_signals_job", JOB_PATH)
JOB = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(JOB)


def test_runtime_max_position_defaults_to_declared_5k(monkeypatch):
    monkeypatch.delenv("LAB_MAX_POSITION_USD", raising=False)
    assert JOB._runtime_max_position() == 5_000.0


def test_runtime_max_position_honors_explicit_override(monkeypatch):
    monkeypatch.setenv("LAB_MAX_POSITION_USD", "4500")
    assert JOB._runtime_max_position() == 4_500.0


def test_extra_lifecycle_symbols_do_not_expand_candidate_universe():
    configured = ["AAPL", "MSFT"]
    open_positions = [
        {"symbol": "AAPL", "status": "OPEN"},
        {"symbol": "UNH", "status": "OPEN"},
        {"symbol": "CVS", "status": "TP1_HIT"},
        {"symbol": "TSM", "status": "CLOSED"},
    ]
    assert JOB._extra_lifecycle_symbols(configured, open_positions) == ["CVS", "UNH"]
