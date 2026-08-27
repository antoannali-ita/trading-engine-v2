from pathlib import Path

from trade_committee.persistence import make_run_id

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "pages" / "5_Trade_Committee.py"
MIGRATION = ROOT / "supabase" / "migrations" / "004_trade_committee_run_log.sql"


def test_legacy_run_id_helper_remains_valid():
    rid = make_run_id("csco")
    assert rid.startswith("TC-")
    assert rid.endswith("-CSCO")


def test_v2_page_does_not_expose_persistent_run_diagnostics():
    source = PAGE.read_text(encoding="utf-8")
    assert "Run Log / Diagnostics" not in source
    assert "start_run" not in source
    assert "log_step" not in source
    assert "finish_run" not in source
    assert "fail_run" not in source
    assert "recent_runs" not in source


def test_legacy_schema_remains_versioned_for_migration_history():
    source = MIGRATION.read_text(encoding="utf-8")
    assert "trade_committee_runs" in source
    assert "trade_committee_run_steps" in source
    assert "run_id text not null unique" in source
    assert "unique(run_id, step_no)" in source
    assert "enable row level security" in source.lower()
