from pathlib import Path


JOB_PATH = Path(__file__).resolve().parents[1] / "jobs" / "run_paper_signals_v2.py"


def test_v2_runner_cleans_stale_watchlist_rows():
    source = JOB_PATH.read_text(encoding="utf-8")
    assert 'client.table("lab_watchlist").update({"active": False})' in source
    assert 'timedelta(days=3)' in source


def test_v2_runner_updates_open_positions_outside_candidate_universe():
    source = JOB_PATH.read_text(encoding="utf-8")
    assert "base._extra_lifecycle_symbols(configured_symbols, open_positions)" in source
    assert "base._update_existing_positions(client, lifecycle_symbol" in source
