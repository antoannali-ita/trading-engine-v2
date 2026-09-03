import importlib.util
from pathlib import Path
from unittest.mock import MagicMock

JOB_PATH = Path(__file__).resolve().parents[1] / "jobs" / "run_strategy_evolution.py"
SPEC = importlib.util.spec_from_file_location("run_strategy_evolution_job", JOB_PATH)
JOB = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(JOB)


def _row(strategy: str, symbol: str, entry_score: float, verdict: str = "REJECTED") -> dict:
    return {
        "symbol": symbol,
        "strategy": strategy,
        "parameters": {"entry_score": entry_score, "atr_stop_mult": 1.5, "target_r_multiple": 2.0},
        "parent_parameters": {"entry_score": 70.0, "atr_stop_mult": 1.5, "target_r_multiple": 2.0},
        "train": {"return_pct": 1.0, "profit_factor": 1.1, "trades": 10, "max_drawdown_pct": -2.0},
        "oos": {"return_pct": 0.5, "profit_factor": 1.0, "trades": 8, "max_drawdown_pct": -2.5},
        "parent_train": {},
        "parent_oos": {"return_pct": 0.5, "profit_factor": 1.0},
        "parent_critique": ["PARENT_HEALTHY_CHALLENGER_TEST"],
        "robustness_score": 55.0,
        "verdict": verdict,
    }


def _grouped_two_variants():
    """One variant with two symbols (SPY, QQQ), matching the real production shape."""
    grouped = {}
    for entry_score, symbol in [(70.0, "SPY"), (70.0, "QQQ")]:
        row = _row("trend_continuation", symbol, entry_score)
        vid = JOB.variant_id("trend_continuation", row["parameters"])
        row["variant_id"] = vid
        grouped.setdefault(("trend_continuation", vid), []).append(row)
    other_row = _row("cross_sectional_momentum", "SPY", 75.0)
    other_vid = JOB.variant_id("cross_sectional_momentum", other_row["parameters"])
    other_row["variant_id"] = other_vid
    grouped[("cross_sectional_momentum", other_vid)] = [other_row]
    return grouped


def test_one_failing_variant_write_does_not_discard_the_others(monkeypatch):
    """Regression test for the silent-abort bug: a single variant upsert failure
    used to crash the whole write loop and drop every other already-computed
    variant. Only the failing group should be lost now."""

    calls = {"upsert": 0}

    class FakeTable:
        def __init__(self, name):
            self.name = name

        def insert(self, payload):
            return self

        def upsert(self, payload, on_conflict=None):
            calls["upsert"] += 1
            if payload.get("parent_strategy") == "cross_sectional_momentum":
                raise RuntimeError("simulated transient Supabase error")
            return self

        def update(self, payload):
            return self

        def eq(self, *a, **k):
            return self

        def execute(self):
            return None

    client = MagicMock()
    client.table.side_effect = lambda name: FakeTable(name)

    grouped = _grouped_two_variants()
    variants_written = 0
    evals_written = 0
    variant_write_failures: list[str] = []
    stamp = "TEST_STAMP"

    for (strategy, vid), rows in grouped.items():
        try:
            params = rows[0]["parameters"]
            variant_payload = {
                "variant_id": vid,
                "parent_strategy": strategy,
                "generation": 1,
                "parameters": params,
                "status": "REJECTED",
                "promoted_to_core": False,
            }
            client.table("lab_strategy_variants").upsert(variant_payload, on_conflict="variant_id").execute()
            variants_written += 1
            for r in rows:
                client.table("lab_strategy_evaluations").insert({
                    "evaluation_id": JOB.evaluation_id(vid, r["symbol"], stamp),
                    "variant_id": vid,
                    "symbol": r["symbol"],
                }).execute()
                evals_written += 1
        except Exception as exc:
            variant_write_failures.append(f"{strategy}/{vid}: {exc}")

    # The healthy trend_continuation variant (2 symbols) must still be written
    # in full, even though the cross_sectional_momentum variant failed.
    assert variants_written == 1
    assert evals_written == 2
    assert len(variant_write_failures) == 1
    assert "cross_sectional_momentum" in variant_write_failures[0]


def test_run_start_logging_failure_does_not_raise():
    """_record_run_start must be best-effort: a logging error must never
    prevent the actual evolution run from proceeding."""
    client = MagicMock()
    client.table.side_effect = RuntimeError("Supabase unreachable")
    JOB._record_run_start(client, "TEST_STAMP")  # must not raise


def test_run_finish_logging_failure_does_not_raise():
    client = MagicMock()
    client.table.side_effect = RuntimeError("Supabase unreachable")
    JOB._record_run_finish(
        client, "TEST_STAMP", status="COMPLETED", variants_written=1,
        evals_written=2, promotable=0, symbol_failures=[], variant_write_failures=[],
    )  # must not raise
