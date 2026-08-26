from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "pages" / "5_Trade_Committee.py"
ENGINE = ROOT / "trade_committee" / "orchestrator.py"
DOC = ROOT / "docs" / "TRADE_COMMITTEE.md"
CHART = ROOT / "trade_committee" / "charting.py"


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


def test_trade_committee_exposes_interactive_chart():
    page = PAGE.read_text(encoding="utf-8")
    chart = CHART.read_text(encoding="utf-8")
    assert "Grafico tecnico" in page
    assert "st.plotly_chart" in page
    assert "Candlestick" in chart
    assert "SMA20" in chart and "SMA50" in chart and "SMA200" in chart
    assert "Entry" in chart and "Stop" in chart and "TP1" in chart and "TP2" in chart
