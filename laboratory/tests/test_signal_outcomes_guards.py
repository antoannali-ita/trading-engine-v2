import importlib.util
from pathlib import Path


JOB_PATH = Path(__file__).resolve().parents[1] / "jobs" / "run_signal_outcomes.py"
SPEC = importlib.util.spec_from_file_location("run_signal_outcomes_job", JOB_PATH)
JOB = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(JOB)


class _Response:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, rows, ranges):
        self.rows = rows
        self.ranges = ranges
        self.cutoff = None
        self.start = 0
        self.end = -1

    def select(self, *_args, **_kwargs):
        return self

    def gte(self, _column, cutoff):
        self.cutoff = cutoff
        return self

    def order(self, *_args, **_kwargs):
        return self

    def range(self, start, end):
        self.start = start
        self.end = end
        self.ranges.append((start, end))
        return self

    def execute(self):
        rows = self.rows
        if self.cutoff is not None:
            rows = [r for r in rows if str(r.get("signal_date") or "") >= self.cutoff]
        return _Response(rows[self.start : self.end + 1])


class _Client:
    def __init__(self, rows):
        self.rows = rows
        self.ranges = []

    def table(self, name):
        assert name == "lab_paper_signals"
        return _Query(self.rows, self.ranges)


def test_recent_signal_loader_pages_until_window_is_complete():
    rows = [
        {"signal_date": "2026-08-26", "symbol": "A"},
        {"signal_date": "2026-08-25", "symbol": "B"},
        {"signal_date": "2026-08-24", "symbol": "C"},
        {"signal_date": "2026-08-23", "symbol": "D"},
        {"signal_date": "2026-08-22", "symbol": "E"},
        {"signal_date": "2026-01-01", "symbol": "OLD"},
    ]
    client = _Client(rows)

    loaded = JOB._load_recent_signals(client, "2026-08-22", page_size=2)

    assert [r["symbol"] for r in loaded] == ["A", "B", "C", "D", "E"]
    assert client.ranges == [(0, 1), (2, 3), (4, 5)]
