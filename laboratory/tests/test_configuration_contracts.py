from pathlib import Path

from lab.settings import MAX_POSITION_USD


REPO_ROOT = Path(__file__).resolve().parents[2]


def _text(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def test_declared_lab_position_cap_is_5k():
    assert MAX_POSITION_USD == 5_000.0


def test_scheduled_lab_workflow_uses_declared_5k_cap():
    workflow = _text(".github/workflows/lab_paper_scheduler.yml")
    assert 'LAB_MAX_POSITION_USD: "5000"' in workflow


def test_v2_scheduler_keeps_research_caps_explicit():
    workflow = _text(".github/workflows/lab_paper_scheduler.yml")
    assert 'LAB_MAX_NEW_BUYS: "12"' in workflow
    assert 'LAB_MAX_ACTIVE_POSITIONS: "80"' in workflow
    assert 'LAB_MAX_ACTIVE_PER_STRATEGY: "24"' in workflow


def test_v2_scheduler_builds_dashboard_snapshots_after_feed():
    workflow = _text(".github/workflows/lab_paper_scheduler.yml")
    assert "python jobs/run_paper_signals_v2.py" in workflow
    assert "python jobs/enrich_lab_metadata.py" in workflow
    assert "python jobs/run_signal_outcomes.py" in workflow
    assert "python jobs/sync_paper_execution.py" in workflow
    assert "python jobs/build_strategy_snapshots.py" in workflow


def test_v2_scheduler_records_heartbeat_start_and_finish():
    workflow = _text(".github/workflows/lab_paper_scheduler.yml")
    assert "system_health/run_log.py start --module LABORATORY --component PAPER_V2" in workflow
    assert "system_health/run_log.py finish --module LABORATORY --component PAPER_V2" in workflow
    assert "if: always()" in workflow
    assert '--status "${{ job.status }}"' in workflow


def test_legacy_daily_workflow_is_manual_only_and_uses_5k_cap():
    workflow = _text(".github/workflows/lab_paper_daily.yml")
    assert "schedule:" not in workflow
    assert 'LAB_MAX_POSITION_USD: "5000"' in workflow


def test_legacy_manual_workflow_matches_v2_operational_pipeline():
    workflow = _text(".github/workflows/lab_paper_daily.yml")
    assert "group: strategy-lab-daily-opportunity-feed" in workflow
    assert 'LAB_MAX_NEW_BUYS: "12"' in workflow
    assert 'LAB_MAX_ACTIVE_POSITIONS: "80"' in workflow
    assert 'LAB_MAX_ACTIVE_PER_STRATEGY: "24"' in workflow
    assert "python jobs/run_paper_signals_v2.py" in workflow
    assert "python jobs/enrich_lab_metadata.py" in workflow
    assert "python jobs/run_signal_outcomes.py" in workflow
    assert "python jobs/sync_paper_execution.py" in workflow
    assert "python jobs/build_strategy_snapshots.py" in workflow


def test_legacy_manual_workflow_records_heartbeat_start_and_finish():
    workflow = _text(".github/workflows/lab_paper_daily.yml")
    assert "system_health/run_log.py start --module LABORATORY --component PAPER_V2_MANUAL" in workflow
    assert "system_health/run_log.py finish --module LABORATORY --component PAPER_V2_MANUAL" in workflow
    assert "if: always()" in workflow
    assert '--status "${{ job.status }}"' in workflow
