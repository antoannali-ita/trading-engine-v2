from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "pages" / "5_Trade_Committee.py"
ENGINE = ROOT / "trade_committee" / "orchestrator.py"
DOC = ROOT / "docs" / "TRADE_COMMITTEE.md"


def test_trade_committee_is_manual_and_research_only():
    source = PAGE.read_text(encoding="utf-8")
    assert "MANUAL · RESEARCH ONLY" in source
    assert "AVVIA ANALISI" in source
    assert "APPROVE / WAIT / REJECT" in source


def test_trade_committee_has_sixteen_steps_and_no_broker_execution():
    source = ENGINE.read_text(encoding="utf-8")
    assert 'done(16,"Final Investment Committee")' in source
    assert "nessun ordine reale" in source
    assert "RESEARCH ONLY" in source


def test_documentation_keeps_scores_separate():
    source = DOC.read_text(encoding="utf-8")
    assert "ENGINE SCORE != COMMITTEE SCORE != DATA CONFIDENCE" in source
    assert "non sostituisce CORE/Multi-Horizon" in source
