from pathlib import Path

from trade_committee.persistence import make_run_id

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "pages" / "5_Trade_Committee.py"
MIGRATION = ROOT / "supabase" / "migrations" / "004_trade_committee_run_log.sql"


def test_run_id_is_unique_style_and_contains_ticker():
    rid = make_run_id("csco")
    assert rid.startswith("TC-")
    assert rid.endswith("-CSCO")


def test_page_exposes_persistent_run_diagnostics():
    source = PAGE.read_text(encoding="utf-8")
    assert "Run Log / Diagnostics" in source
    assert "start_run" in source
    assert "log_step" in source
    assert "finish_run" in source
    assert "fail_run" in source
    assert "recent_runs" in source


def test_schema_is_append_only_per_run_and_has_steps():
    source = MIGRATION.read_text(encoding="utf-8")
    assert "trade_committee_runs" in source
    assert "trade_committee_run_steps" in source
    assert "run_id text not null unique" in source
    assert "unique(run_id, step_no)" in source
    assert "enable row level security" in source.lower()
