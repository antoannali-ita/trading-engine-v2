from pathlib import Path

PAGE = Path("pages/2_Feature_Enrichment.py")
STRATEGY_PAGE = Path("pages/2_Strategy_Lab.py")


def test_lab_feat_has_dedicated_visible_page():
    source = PAGE.read_text(encoding="utf-8")
    assert "LAB-FEAT-001" in source
    assert "DATA COLLECTION" in source
    assert "LAB ONLY" in source
    assert "PROD-001" in source
    assert "FROZEN" in source


def test_lab_feat_ui_states_no_core_decision_impact():
    source = PAGE.read_text(encoding="utf-8")
    assert "Impatto CORE" in source
    assert "NESSUNO" in source
    assert "Non è una nona strategia" in source


def test_lab_feat_is_not_registered_as_strategy():
    source = STRATEGY_PAGE.read_text(encoding="utf-8")
    registry = source.split("ACTIVE_STRATEGY_REGISTRY =", 1)[1].split("}", 1)[0]
    assert "LAB-FEAT-001" not in registry
