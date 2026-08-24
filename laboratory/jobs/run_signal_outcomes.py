from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

LAB_ROOT = Path(__file__).resolve().parents[1]
SRC = LAB_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from lab.db import get_supabase_client
from lab.market_data import MarketDataRequest, download_prices

HORIZONS = (1, 3, 5, 10, 20, 60)


def _details(row: dict) -> dict:
    value = row.get("details")
    return value if isinstance(value, dict) else {}


def _num(value):
    try:
        if value is None or pd.isna(value):
            return None
        return float(value)
    except Exception:
        return None


def _block_reasons(details: dict) -> list[str]:
    reasons: list[str] = []
    for section, key in (
        ("data_quality", "red"),
        ("trade_eligibility", "failed"),
        ("portfolio_eligibility", "failed"),
    ):
        value = details.get(section)
        if isinstance(value, dict):
            reasons.extend(value.get(key, []) or [])
    policy = details.get("paper_policy")
    if isinstance(policy, dict):
        reasons.extend(policy.get("hard_failed", []) or [])
    return list(dict.fromkeys(str(x) for x in reasons))


def _observation_group(signal: dict, details: dict) -> tuple[str, bool]:
    dq = details.get("data_quality") if isinstance(details.get("data_quality"), dict) else {}
    policy = details.get("paper_policy") if isinstance(details.get("paper_policy"), dict) else {}
    status = str(signal.get("status") or "").upper()
    if str(dq.get("status") or "").upper() == "RED" or status == "BLOCKED_DATA":
        return "DATA_REJECT", True
    if status == "PAPER_OPEN":
        return "ACCEPTED_PAPER", False
    if policy.get("eligible"):
        return "PAPER_ELIGIBLE_NOT_OPENED", False
    return "REJECTED_C_VALID_DATA", False


def _slice_from_signal(prices: pd.DataFrame, signal_date: str) -> pd.DataFrame:
    if prices.empty:
        return prices
    idx = pd.to_datetime(prices.index).tz_localize(None)
    x = prices.copy()
    x.index = idx
    start = pd.Timestamp(signal_date)
    return x.loc[x.index >= start]


def _outcome_payload(signal: dict, prices: pd.DataFrame, spy: pd.DataFrame) -> dict | None:
    entry = _num(signal.get("price"))
    if entry is None or entry <= 0:
        return None

    signal_date = str(signal.get("signal_date"))
    path = _slice_from_signal(prices, signal_date)
    spy_path = _slice_from_signal(spy, signal_date)
    if path.empty:
        return None

    base_close = entry
    details = _details(signal)
    stop = _num(signal.get("proposed_stop"))
    tp2 = _num(signal.get("proposed_target"))
    tp1 = _num(details.get("tp1"))
    risk_per_share = (entry - stop) if stop is not None and entry > stop else None
    observation_group, exclude_from_performance = _observation_group(signal, details)
    paper_tier = details.get("paper_tier") or (details.get("paper_policy") or {}).get("tier")

    payload = {
        "symbol": signal.get("symbol"),
        "strategy": signal.get("strategy"),
        "signal_date": signal_date,
        "source_signal_status": signal.get("status"),
        "strategy_score": _num(details.get("strategy_score", signal.get("score"))),
        "trade_score": _num(details.get("trade_score")),
        "portfolio_fit_score": _num(details.get("portfolio_fit_score")),
        "block_reasons": _block_reasons(details),
        "regime_state": (details.get("market_regime") or {}).get("state") if isinstance(details.get("market_regime"), dict) else None,
        "entry_reference": entry,
        "stop_reference": stop,
        "tp1_reference": tp1,
        "tp2_reference": tp2,
        "risk_per_share": risk_per_share,
        "last_evaluated_at": datetime.now(timezone.utc).isoformat(),
        "details": {
            "method": "CLOSE_HORIZONS_HIGH_LOW_EXCURSIONS_V2",
            "benchmark": "SPY",
            "observation_group": observation_group,
            "exclude_from_performance": exclude_from_performance,
            "paper_tier": paper_tier,
            "risk_key": details.get("risk_key") or f"EQUITY:{str(signal.get('symbol') or '').upper()}",
            "experiment_key": details.get("experiment_key"),
            "safety_label": details.get("safety_label"),
            "shadow_outcome": observation_group == "REJECTED_C_VALID_DATA",
        },
    }

    max_horizon = 0
    for n in HORIZONS:
        if len(path) > n:
            ret = (float(path.iloc[n]["Close"]) / base_close - 1.0) * 100.0
            payload[f"ret_d{n}"] = ret
            max_horizon = max(max_horizon, n)
            if len(spy_path) > n:
                spy_base = float(spy_path.iloc[0]["Close"])
                spy_ret = (float(spy_path.iloc[n]["Close"]) / spy_base - 1.0) * 100.0
                payload[f"excess_ret_d{n}"] = ret - spy_ret

    excursion = path.iloc[1 : min(len(path), 61)]
    if not excursion.empty:
        highs = pd.to_numeric(excursion["High"], errors="coerce")
        lows = pd.to_numeric(excursion["Low"], errors="coerce")
        if highs.notna().any():
            mfe_price = float(highs.max())
            mfe_pos = int(highs.reset_index(drop=True).idxmax()) + 1
            mfe_pct = (mfe_price / entry - 1.0) * 100.0
            payload["mfe_pct"] = mfe_pct
            payload["bars_to_mfe"] = mfe_pos
            if risk_per_share and risk_per_share > 0:
                payload["mfe_r"] = (mfe_price - entry) / risk_per_share
        if lows.notna().any():
            mae_price = float(lows.min())
            mae_pos = int(lows.reset_index(drop=True).idxmin()) + 1
            mae_pct = (mae_price / entry - 1.0) * 100.0
            payload["mae_pct"] = mae_pct
            payload["bars_to_mae"] = mae_pos
            if risk_per_share and risk_per_share > 0:
                payload["mae_r"] = (mae_price - entry) / risk_per_share

    payload["last_horizon"] = max_horizon
    return payload


def main() -> int:
    if not os.getenv("SUPABASE_URL") or not os.getenv("SUPABASE_SECRET_KEY"):
        print("Supabase secrets missing; outcomes skipped")
        return 2

    client = get_supabase_client()
    rows = client.table("lab_paper_signals").select("*").order("signal_date", desc=True).limit(5000).execute().data or []
    if not rows:
        print("no lab_paper_signals to evaluate")
        return 0

    cutoff = (datetime.now(timezone.utc).date() - timedelta(days=120)).isoformat()
    rows = [r for r in rows if str(r.get("signal_date", "")) >= cutoff]
    symbols = sorted({str(r.get("symbol", "")).upper() for r in rows if r.get("symbol")})

    try:
        spy = download_prices(MarketDataRequest(symbol="SPY", start=cutoff))
    except Exception as exc:
        print(f"SPY benchmark download failed: {exc}")
        spy = pd.DataFrame()

    cache: dict[str, pd.DataFrame] = {}
    written = 0
    failed = 0
    for symbol in symbols:
        try:
            cache[symbol] = download_prices(MarketDataRequest(symbol=symbol, start=cutoff))
        except Exception as exc:
            print(f"{symbol}: market data failed: {exc}")
            cache[symbol] = pd.DataFrame()

    for row in rows:
        symbol = str(row.get("symbol", "")).upper()
        try:
            payload = _outcome_payload(row, cache.get(symbol, pd.DataFrame()), spy)
            if payload is None:
                continue
            client.table("lab_signal_outcomes").upsert(
                payload, on_conflict="symbol,strategy,signal_date"
            ).execute()
            written += 1
        except Exception as exc:
            failed += 1
            print(f"outcome {symbol}/{row.get('strategy')}/{row.get('signal_date')}: {exc}")

    print(f"signal outcomes written={written} failed={failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
