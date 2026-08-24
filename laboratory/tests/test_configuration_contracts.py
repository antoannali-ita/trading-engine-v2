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


def test_legacy_daily_workflow_is_manual_only_and_uses_5k_cap():
    workflow = _text(".github/workflows/lab_paper_daily.yml")
    assert "schedule:" not in workflow
    assert 'LAB_MAX_POSITION_USD: "5000"' in workflow
