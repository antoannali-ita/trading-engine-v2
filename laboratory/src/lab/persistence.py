from __future__ import annotations

from typing import Any, Iterable

from lab.db import get_supabase_client


def insert_engine_run(run: dict[str, Any]) -> dict[str, Any]:
    """Insert one engine run and return the stored row."""
    supabase = get_supabase_client()
    response = supabase.table("engine_runs").insert(run).execute()
    rows = response.data or []
    return rows[0] if rows else {}


def upsert_signal(signal: dict[str, Any]) -> dict[str, Any]:
    """Upsert one signal by signal_id."""
    supabase = get_supabase_client()
    response = supabase.table("signals").upsert(signal, on_conflict="signal_id").execute()
    rows = response.data or []
    return rows[0] if rows else {}


def upsert_signals(signals: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Upsert a batch of signals by signal_id."""
    payload = list(signals)
    if not payload:
        return []
    supabase = get_supabase_client()
    response = supabase.table("signals").upsert(payload, on_conflict="signal_id").execute()
    return response.data or []


def upsert_signal_outcome(outcome: dict[str, Any]) -> dict[str, Any]:
    supabase = get_supabase_client()
    response = supabase.table("signal_outcomes").upsert(outcome, on_conflict="signal_id").execute()
    rows = response.data or []
    return rows[0] if rows else {}


def add_watchlist_item(item: dict[str, Any]) -> dict[str, Any]:
    supabase = get_supabase_client()
    response = supabase.table("watchlist").insert(item).execute()
    rows = response.data or []
    return rows[0] if rows else {}
