from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "pages" / "2_Laboratory_Overview.py"


def test_near_threshold_is_explicit_and_fixed_at_two_percent():
    source = PAGE.read_text(encoding="utf-8")
    assert "NEAR_THRESHOLD_PCT = 2.0" in source
    assert "NEAR STOP · ≤" in source
    assert "NEAR TP1 · ≤" in source
    assert "NEAR TP2 · ≤" in source
    assert "not ATR-based" in source
