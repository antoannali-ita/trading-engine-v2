from pathlib import Path


LAB_ROOT = Path(__file__).resolve().parents[1]
SYNC = LAB_ROOT / "jobs" / "sync_watchlist_final_state.py"
REPO_ROOT = LAB_ROOT.parent
SCHEDULED = REPO_ROOT / ".github" / "workflows" / "lab_paper_scheduler.yml"
MANUAL = REPO_ROOT / ".github" / "workflows" / "lab_paper_daily.yml"


def test_final_state_sync_copies_signal_status_and_details_only_to_active_watchlist():
    source = SYNC.read_text(encoding="utf-8")
    assert '"status": row.get("status")' in source
    assert '"details": row.get("details")' in source
    assert 'client.table("lab_watchlist").update(payload)' in source
    assert '.eq("active", True)' in source
    assert "return 0 if failed == 0 else 1" in source


def test_final_state_sync_uses_latest_signal_per_symbol_strategy():
    source = SYNC.read_text(encoding="utf-8")
    assert "def _latest_by_key" in source
    assert "signal_date >" in source
    assert '.gte("signal_date", cutoff)' in source
    assert ".range(start, start + PAGE_SIZE - 1)" in source


def test_both_v2_workflows_sync_after_enrichment_before_outcomes():
    for path in (SCHEDULED, MANUAL):
        source = path.read_text(encoding="utf-8")
        assert "python jobs/sync_watchlist_final_state.py" in source
        assert source.index("enrich_lab_metadata.py") < source.index("sync_watchlist_final_state.py")
        assert source.index("sync_watchlist_final_state.py") < source.index("run_signal_outcomes.py")
