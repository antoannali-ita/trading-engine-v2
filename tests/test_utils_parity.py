import ast
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from engine import utils

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "reference/usa_v5_5.py"


def _load_reference_function(name):
    text = BASELINE.read_text(encoding="utf-8")
    tree = ast.parse(text)
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    ns = {
        "Any": Any,
        "Optional": Optional,
        "pd": pd,
        "math": math,
        "re": re,
        "datetime": datetime,
        "timezone": timezone,
    }
    # safe_int dipende da safe_float.
    if name == "safe_int":
        ns["safe_float"] = _load_reference_function("safe_float")
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(BASELINE), "exec"), ns)
    return ns[name]


def test_common_utils_match_usa_baseline_on_representative_inputs():
    cases = {
        "safe_float": [(None,), ("12.5",)],
        "safe_int": [("12.9",)],
        "clamp": [(12, 0, 10)],
        "first_not_none": [(None, None, 7)],
        "fmt_price": [(1234.5,)],
        "fmt_pct": [(-3.25,)],
        "fmt_num": [(1234.567, 1)],
        "html_escape": [('<a x="1">&</a>',)],
        "normalize_percent": [(0.23,)],
        "normalize_debt_to_equity": [(35,)],
    }
    for name, argsets in cases.items():
        ref_fn = _load_reference_function(name)
        new_fn = getattr(utils, name)
        for args in argsets:
            assert new_fn(*args) == ref_fn(*args), (name, args)


def test_extract_unknown_field_matches_baseline():
    ref_fn = _load_reference_function("extract_unknown_field")
    err = Exception('Unknown field "foo_bar"')
    assert utils.extract_unknown_field(err) == ref_fn(err)
