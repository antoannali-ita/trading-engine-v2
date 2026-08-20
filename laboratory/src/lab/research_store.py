from __future__ import annotations

import math
import os
from typing import Iterable

from .db import get_supabase_client


def supabase_configured() -> bool:
    return bool(os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_SECRET_KEY"))


def _clean(value):
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def start_backtest_run(run_id: str, symbols: list[str], strategies: list[str], mode: str = "BATCH") -> None:
    client = get_supabase_client()
    client.table("lab_backtest_runs").insert({
        "run_id": run_id,
        "mode": mode,
        "engine_version": "lab-v1",
        "symbols": symbols,
        "strategies": strategies,
        "status": "RUNNING",
    }).execute()


def save_backtest_results(run_id: str, rows: Iterable[dict]) -> None:
    payload = []
    for row in rows:
        payload.append({
            "run_id": run_id,
            "symbol": row.get("symbol"),
            "strategy": row.get("strategy"),
            "trades": _clean(row.get("trades")),
            "win_rate": _clean(row.get("win_rate")),
            "avg_return_pct": _clean(row.get("avg_return_pct")),
            "profit_factor": _clean(row.get("profit_factor")),
            "net_pnl": _clean(row.get("net_pnl")),
            "return_pct": _clean(row.get("return_pct")),
            "final_equity": _clean(row.get("final_equity")),
            "data_status": row.get("data_status", "OK"),
            "error": row.get("error"),
            "metrics": {k: _clean(v) for k, v in row.items()},
        })
    if payload:
        get_supabase_client().table("lab_backtest_results").insert(payload).execute()


def finish_backtest_run(run_id: str, status: str, notes: str | None = None) -> None:
    get_supabase_client().table("lab_backtest_runs").update({"status": status, "notes": notes}).eq("run_id", run_id).execute()
