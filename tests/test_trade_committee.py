from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "pages" / "5_Trade_Committee.py"
ENGINE = ROOT / "trade_committee" / "orchestrator.py"
CHECKS = ROOT / "trade_committee" / "research_checks.py"
DOC = ROOT / "docs" / "TRADE_COMMITTEE.md"


def test_trade_committee_is_manual_and_research_only():
    source = PAGE.read_text(encoding="utf-8")
    assert "ANALIZZA" in source
    assert "Nessun ordine automatico" in source
    assert "CORE invariato" in source


def test_trade_committee_v2_uses_real_source_coverage():
    source = ENGINE.read_text(encoding="utf-8")
    assert "TRADE_COMMITTEE_V2" in source
    assert "Market & Technical" in source
    assert "Official Filings" in source
    assert "Portfolio Context" in source
    assert "Bull / Bear / Inversion Review" in source
    assert "coverage_summary" in source


def test_page_removes_persistent_run_log_and_adds_chart():
    source = PAGE.read_text(encoding="utf-8")
    assert "build_price_chart" in source
    assert "st.plotly_chart" in source
    assert "Run Log / Diagnostics" not in source
    assert "recent_runs" not in source
    assert "Copertura reale dell'analisi" in source


def test_checks_include_free_sources_and_portfolio_context():
    source = CHECKS.read_text(encoding="utf-8")
    assert "Yahoo Finance" in source
    assert "SEC EDGAR" in source
    assert "TradingView Screener" in source
    assert "production_portfolio.json" in source
    assert "FTSEMIB.MI" in source
    assert '"SPY"' in source


def test_documentation_keeps_scores_separate():
    source = DOC.read_text(encoding="utf-8")
    assert "ENGINE SCORE != COMMITTEE SCORE != DATA CONFIDENCE" in source
    assert "non sostituisce CORE/Multi-Horizon" in source
