from __future__ import annotations

import pandas as pd

from lab.db import get_supabase_client


def _frame(rows) -> pd.DataFrame:
    return pd.DataFrame(rows or [])


def load_engine_runs(limit: int = 200) -> pd.DataFrame:
    supabase = get_supabase_client()
    response = supabase.table("engine_runs").select("*").order("run_timestamp", desc=True).limit(limit).execute()
    return _frame(response.data)


def load_signals(limit: int = 1000) -> pd.DataFrame:
    supabase = get_supabase_client()
    response = supabase.table("signals").select("*").order("created_at", desc=True).limit(limit).execute()
    return _frame(response.data)


def load_signal_outcomes(limit: int = 2000) -> pd.DataFrame:
    supabase = get_supabase_client()
    response = supabase.table("signal_outcomes").select("*").limit(limit).execute()
    return _frame(response.data)


def load_trades(limit: int = 500) -> pd.DataFrame:
    supabase = get_supabase_client()
    response = supabase.table("trades").select("*").order("created_at", desc=True).limit(limit).execute()
    return _frame(response.data)


def load_watchlist(limit: int = 500) -> pd.DataFrame:
    supabase = get_supabase_client()
    response = supabase.table("watchlist").select("*").eq("active", True).order("created_at", desc=True).limit(limit).execute()
    return _frame(response.data)


def load_engine_config(limit: int = 50) -> pd.DataFrame:
    supabase = get_supabase_client()
    response = supabase.table("engine_config").select("*").order("valid_from", desc=True).limit(limit).execute()
    return _frame(response.data)


def load_lab_backtest_runs(limit: int = 100) -> pd.DataFrame:
    response = get_supabase_client().table("lab_backtest_runs").select("*").order("created_at", desc=True).limit(limit).execute()
    return _frame(response.data)


def load_lab_backtest_results(limit: int = 2000) -> pd.DataFrame:
    response = get_supabase_client().table("lab_backtest_results").select("*").order("created_at", desc=True).limit(limit).execute()
    return _frame(response.data)


def load_lab_calibration_results(limit: int = 1000) -> pd.DataFrame:
    response = get_supabase_client().table("lab_calibration_results").select("*").order("created_at", desc=True).limit(limit).execute()
    return _frame(response.data)


def load_lab_paper_signals(limit: int = 1000) -> pd.DataFrame:
    response = get_supabase_client().table("lab_paper_signals").select("*").order("created_at", desc=True).limit(limit).execute()
    return _frame(response.data)


def load_strategy_variants(limit: int = 1000) -> pd.DataFrame:
    response = get_supabase_client().table("lab_strategy_variants").select("*").order("created_at", desc=True).limit(limit).execute()
    return _frame(response.data)


def load_strategy_evaluations(limit: int = 5000) -> pd.DataFrame:
    response = get_supabase_client().table("lab_strategy_evaluations").select("*").order("created_at", desc=True).limit(limit).execute()
    return _frame(response.data)
