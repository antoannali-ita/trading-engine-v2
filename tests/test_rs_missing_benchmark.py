import pandas as pd
from engine.indicators import classify_rs_safe


class Ref:
    @staticmethod
    def classify_rs(candidate):
        return "STRONG"


def test_missing_benchmark_returns_nd():
    assert classify_rs_safe(Ref, {"rs_1m": 10}, None) == "N/D"
    assert classify_rs_safe(Ref, {"rs_1m": 10}, pd.DataFrame()) == "N/D"


def test_available_benchmark_delegates_to_reference():
    df = pd.DataFrame({"Close": [1.0, 1.1]})
    assert classify_rs_safe(Ref, {"rs_1m": 10}, df) == "STRONG"
