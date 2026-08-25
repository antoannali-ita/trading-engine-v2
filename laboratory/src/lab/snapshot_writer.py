from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable


class SnapshotWriteError(RuntimeError):
    pass


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def latest_completed_run(client) -> dict[str, Any] | None:
    response = (
        client.table("lab_aggregation_runs")
        .select("*")
        .eq("status", "COMPLETED")
        .order("completed_at", desc=True)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None


def write_atomic_snapshot(
    client,
    *,
    session: str,
    control_row: dict[str, Any],
    strategy_rows: Iterable[dict[str, Any]],
    ticker_rows: Iterable[dict[str, Any]],
    source_run_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> int:
    """Persist a complete Laboratory snapshot and publish only after validation.

    PostgREST cannot wrap independent HTTP requests in one SQL transaction, so
    publication is made atomic at the application level: every row references a
    PENDING aggregation_run_id and dashboards consume only COMPLETED runs. A
    failed run may leave private rows behind, but they are never visible to the
    dashboard's latest-completed query.
    """
    strategies = list(strategy_rows)
    tickers = list(ticker_rows)
    expected_rows = 1 + len(strategies) + len(tickers)
    run_payload = {
        "session": session,
        "status": "PENDING",
        "source_run_id": source_run_id,
        "expected_rows": expected_rows,
        "written_rows": 0,
        "validation_status": "PENDING",
        "details": details or {},
    }
    response = client.table("lab_aggregation_runs").insert(run_payload).execute()
    if not response.data:
        raise SnapshotWriteError("aggregation run insert returned no row")
    run_id = int(response.data[0]["id"])
    written = 0

    try:
        control = dict(control_row)
        control.update({"aggregation_run_id": run_id, "session": session, "updated_at": _iso_now()})
        control.pop("id", None)
        client.table("lab_control_snapshot_daily").insert(control).execute()
        written += 1

        if strategies:
            payload = []
            for row in strategies:
                item = dict(row)
                item.update({"aggregation_run_id": run_id, "session": session, "updated_at": _iso_now()})
                item.pop("id", None)
                # UI-only helper is not part of the persisted schema.
                item.pop("main_blocker_label", None)
                item.pop("tier_a", None)
                item.pop("tier_b", None)
                item.pop("tier_c", None)
                item.pop("triggered", None)
                item.pop("data_rejects", None)
                payload.append(item)
            result = client.table("lab_strategy_summary_daily").insert(payload).execute()
            written += len(result.data or payload)

        if tickers:
            payload = []
            for row in tickers:
                item = dict(row)
                item.update({"aggregation_run_id": run_id, "session": session, "updated_at": _iso_now()})
                item.pop("id", None)
                payload.append(item)
            result = client.table("lab_strategy_ticker_snapshot").insert(payload).execute()
            written += len(result.data or payload)

        validation_status = "PASS" if written == expected_rows else "FAIL_ROW_COUNT"
        if validation_status != "PASS":
            raise SnapshotWriteError(f"snapshot row count mismatch: expected={expected_rows} written={written}")

        client.table("lab_aggregation_runs").update({
            "status": "COMPLETED",
            "completed_at": _iso_now(),
            "written_rows": written,
            "validation_status": validation_status,
            "error_message": None,
        }).eq("id", run_id).execute()
        return run_id
    except Exception as exc:
        try:
            client.table("lab_aggregation_runs").update({
                "status": "FAILED",
                "completed_at": _iso_now(),
                "written_rows": written,
                "validation_status": "FAILED",
                "error_message": f"{type(exc).__name__}: {exc}",
            }).eq("id", run_id).execute()
        except Exception:
            pass
        if isinstance(exc, SnapshotWriteError):
            raise
        raise SnapshotWriteError(str(exc)) from exc
