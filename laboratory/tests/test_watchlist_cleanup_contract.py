from pathlib import Path


LAB_ROOT = Path(__file__).resolve().parents[1]
CLEANUP = LAB_ROOT / "jobs" / "cleanup_watchlist_stale.py"
REPO_ROOT = LAB_ROOT.parent
SCHEDULED = REPO_ROOT / ".github" / "workflows" / "lab_paper_scheduler.yml"
MANUAL = REPO_ROOT / ".github" / "workflows" / "lab_paper_daily.yml"


def test_cleanup_deactivates_and_verifies_stale_rows():
    source = CLEANUP.read_text(encoding="utf-8")
    assert 'client.table("lab_watchlist").update({"active": False})' in source
    assert '.lt("last_seen_at", stale_before)' in source
    assert '.eq("active", True)' in source
    assert "stale active watchlist rows remain after cleanup" in source
    assert "return 1" in source


def test_both_v2_workflows_run_cleanup_verifier():
    for path in (SCHEDULED, MANUAL):
        source = path.read_text(encoding="utf-8")
        assert "python jobs/cleanup_watchlist_stale.py" in source
        assert source.index("run_paper_signals_v2.py") < source.index("cleanup_watchlist_stale.py")
        assert source.index("cleanup_watchlist_stale.py") < source.index("enrich_lab_metadata.py")
