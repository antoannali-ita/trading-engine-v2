from datetime import datetime, timezone

import pandas as pd

from orchestrator.coordinator import _ai_already_requested, _confluence_signal_id
from orchestrator.dispatcher import TARGETS
from orchestrator.notifier import _matching_confluence
from orchestrator.performance_worker import _window_stats


def test_multi_dispatch_inputs_match_workflow_contract():
    for engine_id in ("MULTI_USA", "MULTI_ITALY"):
        target = TARGETS[engine_id]
        assert target["inputs"]["notifications"] == "false"
        assert target["allowed_inputs"] == {"market", "strategy", "notifications", "request_id"}


def test_ai_dedupe_is_exact_per_confluence():
    ai_rows = [
        {
            "ticker": "NVDA",
            "source_signal_id": "confluence-old",
            "status": "SUCCESS",
            "started_at": datetime.now(timezone.utc).isoformat(),
        }
    ]
    assert _ai_already_requested(ai_rows, "NVDA", "confluence-old") is True
    assert _ai_already_requested(ai_rows, "NVDA", "confluence-new") is False


def test_confluence_signal_id_is_stable_across_source_order():
    a = {
        "market": "USA",
        "ticker": "NVDA",
        "level": "DOUBLE_CONFIRMATION",
        "source_signal_ids": ["fast-1", "core-1"],
    }
    b = {**a, "source_signal_ids": ["core-1", "fast-1"]}
    assert _confluence_signal_id(a) == _confluence_signal_id(b)


def test_notifier_prefers_exact_confluence_source_id():
    rows = [
        {
            "signal_id": "newer",
            "ticker": "NVDA",
            "market": "USA",
            "detected_at": "2026-08-21T12:00:00+00:00",
            "metadata": {"source_signal_ids": ["base-new"]},
        },
        {
            "signal_id": "target",
            "ticker": "NVDA",
            "market": "USA",
            "detected_at": "2026-08-21T11:00:00+00:00",
            "metadata": {"source_signal_ids": ["base-old"]},
        },
    ]
    ai = {"ticker": "NVDA", "market": "USA", "source_signal_id": "target"}
    assert _matching_confluence(ai, rows)["signal_id"] == "target"


def test_notifier_supports_legacy_base_signal_source_id():
    rows = [
        {
            "signal_id": "target",
            "ticker": "NVDA",
            "market": "USA",
            "detected_at": "2026-08-21T11:00:00+00:00",
            "metadata": {"source_signal_ids": ["base-old", "fast-old"]},
        }
    ]
    ai = {"ticker": "NVDA", "market": "USA", "source_signal_id": "base-old"}
    assert _matching_confluence(ai, rows)["signal_id"] == "target"


def test_performance_uses_sessions_and_true_peak_to_trough_drawdown():
    idx = pd.to_datetime([
        "2026-08-24",
        "2026-08-25",
        "2026-08-26",
        "2026-08-27",
        "2026-08-28",
    ])
    hist = pd.DataFrame(
        {
            "Close": [110.0, 120.0, 90.0, 105.0, 115.0],
            "High": [112.0, 125.0, 100.0, 108.0, 118.0],
            "Low": [100.0, 108.0, 85.0, 95.0, 100.0],
        },
        index=idx,
    )
    stats = _window_stats(hist, sessions=5, entry=100.0)
    assert round(stats["pnl_pct"], 4) == 15.0
    assert round(stats["mfe_pct"], 4) == 25.0
    # Peak close 120 to trough close 90 = -25%, not merely -10% versus entry.
    assert round(stats["mdd_pct"], 4) == -25.0
