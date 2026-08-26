from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "pages" / "2_Laboratory_Overview.py"


def test_near_threshold_is_explicit_and_fixed_at_two_percent():
    source = PAGE.read_text(encoding="utf-8")
    # The 2% threshold remains a fixed Laboratory UI constant.
    assert "NEAR_THRESHOLD_PCT = 2.0" in source
    # The current overview exposes distance-to-stop explicitly in the table/help text.
    assert '"Risk to Stop %"' in source
    assert "Risk to Stop %" in source
