from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OVERVIEW = ROOT / "pages" / "2_Laboratory_Overview.py"
STRATEGY_WRAPPER = ROOT / "dashboard" / "pages" / "2_Strategy_Parameters.py"
OLD_STRATEGY_WRAPPER = ROOT / "dashboard" / "pages" / "2_Strategie_Parametri.py"


def test_open_paper_positions_include_company_column():
    source = OVERVIEW.read_text(encoding="utf-8")
    assert '"Company": company_names.get(ticker, "N/D")' in source
    assert '["Ticker", "Company", "Strategy", "Tier"' in source


def test_strategy_parameters_menu_wrapper_is_english_and_import_safe():
    source = STRATEGY_WRAPPER.read_text(encoding="utf-8")
    assert STRATEGY_WRAPPER.is_file()
    assert not OLD_STRATEGY_WRAPPER.exists()
    assert "sys.path.insert(0, str(ROOT))" in source
    assert 'ROOT / "pages" / "2_Strategie_Parametri.py"' in source
