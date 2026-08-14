import ast
from pathlib import Path

def names(path):
    t=ast.parse(Path(path).read_text()); return {n.name for n in t.body if isinstance(n,ast.FunctionDef)}

def test_usa_core_functions_present():
    n=names('reference/usa_v5_5.py')
    required={'calculate_total_score','decision_engine','gate_status','prebuy_engine','build_entry_plan','trigger_engine','market_regime_engine','save_run'}
    assert required <= n

def test_italy_core_functions_present():
    n=names('reference/italy_v1_2.py')
    required={'calculate_total_score','decision_engine','gate_status','build_entry_plan','trigger_engine','market_regime_engine','is_gem_foreign_listing','save_run'}
    assert required <= n
