import ast
from pathlib import Path

def names(path):
    tree=ast.parse(Path(path).read_text()); return {n.name for n in tree.body if isinstance(n,ast.FunctionDef)}

def test_usa_prebuy_exists(): assert 'prebuy_engine' in names('reference/usa_v5_5.py')
def test_italy_prebuy_not_silently_added(): assert 'prebuy_engine' not in names('reference/italy_v1_2.py')
