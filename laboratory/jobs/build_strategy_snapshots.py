from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

LAB_ROOT = Path(__file__).resolve().parents[1]
SRC = LAB_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from lab.db import get_supabase_client
from lab.strategy_aggregator import aggregate_all_strategies, position_r_metrics, strategy_version
from lab.snapshot_writer import SnapshotWriteError, write_atomic_snapshot

ACTIVE_STATUSES = {"OPEN", "TP1_HIT"}


def _dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(str(value)) if value else {}
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except Exception:
        return None


def _session(row: dict[str, Any]) -> str | None:
    value = row.get("signal_date") or row.get("source_signal_date") or row.get("opened_at") or row.get("created_at")
    return str(value)[:10] if value else None


def _freshness(latest_date: str | None, *, max_calendar_days: int = 3) -> str:
    if not latest_date:
        return "N/D"
    try:
        age = (date.today() - date.fromisoformat(latest_date[:10])).days
        return "FRESH" if age <= max_calendar_days else "STALE"
    except Exception:
        return "N/D"


def _variant_map(client) -> dict[str, str]:
    try:
        rows = client.table("lab_strategy_variants").select("parent_strategy,variant_id,status,created_at").order("created_at", desc=True).execute().data or []
    except Exception:
        return {}
    out: dict[str, str] = {}
    for row in rows:
        strategy = str(row.get("parent_strategy") or "")
        status = str(row.get("status") or "").upper()
        if not strategy or strategy in out or status in {"REJECTED", "ARCHIVED", "DISABLED"}:
            continue
        out[strategy] = str(row.get("variant_id") or "UNVERSIONED")
    return out


def _apply_versions(rows: list[dict[str, Any]], versions: dict[str, str]) -> list[dict[str, Any]]:
    out = []
    for raw in rows:
        row = dict(raw)
        if not row.get("strategy_version"):
            strategy = str(row.get("strategy") or "")
            if strategy in versions:
                row["strategy_version"] = versions[strategy]
        out.append(row)
    return out


def _tier(signal: dict[str, Any]) -> str | None:
    details = _dict(signal.get("details"))
    policy = _dict(details.get("paper_policy"))
    value = details.get("paper_tier") or policy.get("tier")
    return str(value) if value else None


def _paper_pnl(positions: list[dict[str, Any]]) -> float:
    total = 0.0
    for p in positions:
        status = str(p.get("status") or "").upper()
        if status == "CLOSED":
            total += _float(p.get("net_pnl")) or 0.0
            continue
        if status not in ACTIVE_STATUSES:
            continue
        fill = _float(p.get("fill_price")) or _float(p.get("entry_price"))
        current = _float(p.get("last_price")) or fill
        qty = int(p.get("qty") or 0)
        if fill is not None and current is not None and qty > 0:
            total += (current - fill) * qty - (_float(p.get("commission_entry")) or 0.0)
    return total


def _ticker_rows(positions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for p in positions:
        if str(p.get("status") or "").upper() not in ACTIVE_STATUSES:
            continue
        details = _dict(p.get("details"))
        metrics = position_r_metrics(p)
        entry = _float(p.get("fill_price")) or _float(p.get("entry_price"))
        current = _float(p.get("last_price")) or entry
        ret = ((current - entry) / entry * 100.0) if entry and current is not None else None
        opened = str(p.get("opened_at") or "")[:10]
        try:
            # Approximation only in the snapshot. Overview continues to use verified SPY sessions.
            trading_days = max((date.today() - date.fromisoformat(opened)).days, 0) if opened else None
        except Exception:
            trading_days = None
        rows.append({
            "strategy": p.get("strategy"),
            "strategy_version": strategy_version(p),
            "symbol": p.get("symbol"),
            "tier": details.get("paper_tier") or _dict(details.get("paper_policy")).get("tier"),
            "state": p.get("status"),
            "side": p.get("side") or details.get("side") or "LONG",
            "fill_price": entry,
            "current_price": current,
            "stop_current": _float(p.get("stop_current")) or _float(p.get("stop_initial")),
            "tp1": _float(p.get("tp1")),
            "tp2": _float(p.get("tp2")),
            "trading_days": trading_days,
            "net_return_pct": ret,
            "mtm_r": metrics.get("mtm_r"),
            "open_risk_r": metrics.get("open_risk_r"),
            "locked_profit_r": metrics.get("locked_profit_r"),
        })
    return rows


def main() -> int:
    if not os.getenv("SUPABASE_URL") or not os.getenv("SUPABASE_SECRET_KEY"):
        print("Supabase secrets missing; snapshot not built")
        return 2
    client = get_supabase_client()
    try:
        signals = client.table("lab_paper_signals").select("*").order("created_at", desc=True).limit(10000).execute().data or []
        positions = client.table("lab_paper_positions").select("*").order("opened_at", desc=True).limit(10000).execute().data or []
        outcomes = client.table("lab_signal_outcomes").select("*").order("signal_date", desc=True).limit(10000).execute().data or []
    except Exception as exc:
        print(f"FATAL snapshot source read: {type(exc).__name__}: {exc}")
        return 1

    sessions = sorted({x for x in (_session(s) for s in signals) if x})
    if not sessions:
        print("No Laboratory sessions; snapshot skipped")
        return 0
    session = sessions[-1]
    session_signals = [s for s in signals if _session(s) == session]

    versions = _variant_map(client)
    signals_v = _apply_versions(signals, versions)
    positions_v = _apply_versions(positions, versions)
    session_signals_v = [s for s in signals_v if _session(s) == session]

    summaries = aggregate_all_strategies(signals=signals_v, positions=positions_v, outcomes=outcomes)
    active_summaries = [s for s in summaries if s.get("signals") or s.get("open") or s.get("closed")]
    tickers = _ticker_rows(positions_v)

    data_valid = valid_setups = triggered = paper_opened = data_rejects = 0
    tiers = {"A": 0, "B": 0, "C": 0}
    for s in session_signals_v:
        details = _dict(s.get("details"))
        dq = _dict(details.get("data_quality"))
        dq_red = str(dq.get("status") or "").upper() == "RED"
        data_rejects += int(dq_red)
        data_valid += int(not dq_red)
        score = _float(details.get("strategy_score")) or _float(s.get("score")) or 0.0
        valid_setups += int(not dq_red and score >= 55)
        triggered += int(str(details.get("trigger") or "").upper() == "CONFIRMED")
        paper_opened += int(str(s.get("status") or "").upper() == "PAPER_OPEN")
        tier = _tier(s)
        if tier in tiers:
            tiers[tier] += 1

    active_positions = [p for p in positions_v if str(p.get("status") or "").upper() in ACTIVE_STATUSES]
    closed_positions = [p for p in positions_v if str(p.get("status") or "").upper() == "CLOSED"]
    mtm_total = sum(float(s.get("mtm_r") or 0.0) for s in active_summaries)
    risk_total = sum(float(s.get("open_risk_r") or 0.0) for s in active_summaries)
    locked_total = sum(float(s.get("locked_profit_r") or 0.0) for s in active_summaries)

    raw_status = _freshness(session)
    checked_dates = [str(p.get("last_checked_date"))[:10] for p in active_positions if p.get("last_checked_date")]
    lifecycle_latest = max(checked_dates) if checked_dates else None
    lifecycle_status = _freshness(lifecycle_latest)
    run_status = "OK" if raw_status == "FRESH" and lifecycle_status in {"FRESH", "N/D"} else "WARNING"
    data_status = "GREEN" if data_rejects == 0 else "YELLOW"

    control = {
        "run_status": run_status,
        "data_status": data_status,
        "raw_freshness_status": raw_status,
        "lifecycle_freshness_status": lifecycle_status,
        "snapshot_freshness_status": "FRESH",
        "signals": len(session_signals_v),
        "data_valid": data_valid,
        "valid_setups": valid_setups,
        "triggered": triggered,
        "tier_a": tiers["A"],
        "tier_b": tiers["B"],
        "tier_c": tiers["C"],
        "paper_opened": paper_opened,
        "open_positions": len(active_positions),
        "closed_positions": len(closed_positions),
        "data_rejects": data_rejects,
        "mtm_r": mtm_total,
        "open_risk_r": risk_total,
        "locked_profit_r": locked_total,
        "paper_net_pnl": _paper_pnl(positions_v),
    }

    try:
        run_id = write_atomic_snapshot(
            client,
            session=session,
            control_row=control,
            strategy_rows=active_summaries,
            ticker_rows=tickers,
            source_run_id=os.getenv("GITHUB_RUN_ID"),
            details={"model": "LABORATORY_2_2", "versions": versions},
        )
    except SnapshotWriteError as exc:
        text = str(exc)
        if "lab_aggregation_runs" in text or "lab_control_snapshot_daily" in text:
            print("SCHEMA_MISSING: apply laboratory/sql/07_lab_2_2_architecture.sql before enabling snapshots")
            return 3
        print(f"FATAL snapshot write: {type(exc).__name__}: {exc}")
        return 1

    print(f"snapshot COMPLETED aggregation_run_id={run_id} session={session} strategies={len(active_summaries)} tickers={len(tickers)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
