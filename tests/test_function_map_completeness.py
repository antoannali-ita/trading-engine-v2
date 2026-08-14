import ast
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAP = ROOT / "FUNCTION_MAP.csv"
REFERENCES = [ROOT / "reference/usa_v5_5.py", ROOT / "reference/italy_v1_2.py"]


def _top_level_functions(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _rows():
    with MAP.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_every_reference_function_is_mapped():
    reference_functions = set().union(*(_top_level_functions(p) for p in REFERENCES))
    mapped = {row["function"] for row in _rows()}
    assert reference_functions == mapped, {
        "unmapped": sorted(reference_functions - mapped),
        "stale_map_entries": sorted(mapped - reference_functions),
    }


def test_no_unmapped_classification():
    bad = [row for row in _rows() if "UNMAPPED" in row["classification"].upper()]
    assert not bad, bad


def test_every_declared_destination_file_exists():
    missing = sorted({row["destination"] for row in _rows() if not (ROOT / row["destination"]).is_file()})
    assert not missing, missing
