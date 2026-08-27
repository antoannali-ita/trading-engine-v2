from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "pages" / "5_Trade_Committee.py"
ENGINE = ROOT / "trade_committee" / "orchestrator.py"
CHECKS = ROOT / "trade_committee" / "research_checks.py"
POLICY = ROOT / "trade_committee" / "policy.py"
DOC = ROOT / "docs" / "TRADE_COMMITTEE.md"


def test_trade_committee_is_manual_and_research_only():
    source = PAGE.read_text(encoding="utf-8")
    assert "ANALIZZA" in source
    assert "Nessun ordine automatico" in source
    assert "CORE invariato" in source


def test_trade_committee_v22_validates_core_instead_of_rebuilding_trade():
    source = ENGINE.read_text(encoding="utf-8")
    assert "TRADE_COMMITTEE_V2_2" in source
    assert "CORE Trade Plan" in source
    assert "Trade Thesis Validation" in source
    assert "Official Filings" in source
    assert "Portfolio Context" in source
    assert "coverage_summary" in source
    assert "Trade Validation Score" in source


def test_page_removes_persistent_run_log_and_adds_chart():
    source = PAGE.read_text(encoding="utf-8")
    assert "build_price_chart" in source
    assert "st.plotly_chart" in source
    assert "Run Log / Diagnostics" not in source
    assert "recent_runs" not in source
    assert "Copertura reale dell'analisi" in source
    assert "Core Data Confidence" in source
    assert "Enrichment Coverage" in source


def test_checks_include_explicit_sources_and_portfolio_context():
    source = CHECKS.read_text(encoding="utf-8")
    assert 'YAHOO_SOURCE = "Yahoo Finance / yfinance"' in source
    assert 'SEC_SOURCE = "SEC EDGAR"' in source
    assert 'TRADINGVIEW_SOURCE = "TradingView Screener"' in source
    assert "production_portfolio.json" in source
    assert "FTSEMIB.MI" in source
    assert '"SPY"' in source


def test_policy_has_closed_warning_taxonomy_and_hard_vetoes():
    source = POLICY.read_text(encoding="utf-8")
    assert "class CheckClass" in source
    assert "CORE_WARNING" in source
    assert "SOFT_WARNING" in source
    assert "ENRICHMENT_ND" in source
    assert "class HardVeto" in source
    assert "TRIGGER_INVALID" in source
    assert "PRICE_ABOVE_MAX_BUY" in source
    assert "RR_NET_LT_MIN" in source


def test_documentation_keeps_scores_separate():
    source = DOC.read_text(encoding="utf-8")
    assert "ENGINE SCORE != TRADE VALIDATION SCORE != CORE DATA CONFIDENCE" in source
    assert "non sostituisce CORE/Multi-Horizon" in source
    assert "Tutto ciò che non appartiene all'enum HARD VETO non può bloccare automaticamente APPROVE" in source
