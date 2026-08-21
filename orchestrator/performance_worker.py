from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import yfinance as yf

from orchestrator.persistence import client


HORIZONS = {
    "1D": 1,
    "5D": 5,
    "20D": 20,
    "60D": 60,
}


def _parse_ts(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _yf_symbol(ticker: str, market: str) -> str:
    ticker = ticker.upper().strip()
    if market.upper() == "ITALY" and "." not in ticker:
        return ticker + ".MI"
    return ticker


def _existing_keys(db, signal_id: str) -> set[str]:
    rows = db.table("performance").select("outcome").eq("signal_id", signal_id).execute().data or []
    return {str(r.get("outcome") or "") for r in rows}


def _series(hist: pd.DataFrame, field: str) -> pd.Series:
    data = hist[field]
    if isinstance(data, pd.DataFrame):
        if data.shape[1] != 1:
            raise ValueError(f"Unexpected multi-symbol history for {field}")
        data = data.iloc[:, 0]
    return pd.to_numeric(data, errors="coerce").dropna()


def _future_history(symbol: str, detected: datetime, now: datetime) -> pd.DataFrame:
    hist = yf.download(
        symbol,
        start=detected.date().isoformat(),
        end=(now + timedelta(days=2)).date().isoformat(),
        auto_adjust=True,
        progress=False,
    )
    if hist is None or hist.empty:
        return pd.DataFrame()
    idx = pd.to_datetime(hist.index)
    # Performance starts from the first completed session after signal detection.
    mask = idx.date > detected.date()
    return hist.loc[mask].sort_index()


def _window_stats(hist: pd.DataFrame, sessions: int, entry: float):
    if hist is None or hist.empty:
        return None
    close = _series(hist, "Close")
    high = _series(hist, "High")
    if len(close) < sessions:
        return None

    close_window = close.iloc[:sessions]
    high_window = high.iloc[:sessions] if not high.empty else close_window
    exit_price = float(close_window.iloc[-1])
    max_price = float(high_window.max()) if not high_window.empty else exit_price

    path = pd.Series([float(entry), *[float(v) for v in close_window.tolist()]], dtype="float64")
    rolling_peak = path.cummax()
    drawdowns = (path / rolling_peak - 1.0) * 100.0
    max_drawdown = float(drawdowns.min())

    end_value = close_window.index[-1]
    if isinstance(end_value, pd.Timestamp):
        period_end = end_value.to_pydatetime()
    else:
        period_end = pd.Timestamp(end_value).to_pydatetime()
    if period_end.tzinfo is None:
        period_end = period_end.replace(tzinfo=timezone.utc)
    else:
        period_end = period_end.astimezone(timezone.utc)

    return {
        "exit_price": exit_price,
        "pnl_pct": (exit_price / entry - 1.0) * 100.0,
        "mfe_pct": (max_price / entry - 1.0) * 100.0,
        "mdd_pct": max_drawdown,
        "period_end": period_end,
    }


def run() -> dict:
    db = client()
    if db is None:
        raise RuntimeError("SUPABASE_URL/SUPABASE_SECRET_KEY required")

    now = datetime.now(timezone.utc)
    signals = (
        db.table("signals")
        .select("signal_id,engine_id,engine,strategy,market,ticker,price,entry,detected_at,is_actionable")
        .eq("is_actionable", True)
        .order("detected_at", desc=True)
        .limit(1000)
        .execute()
        .data
        or []
    )

    inserted = 0
    skipped = 0
    errors = 0

    for row in signals:
        signal_id = row.get("signal_id")
        ticker = row.get("ticker")
        market = row.get("market") or "USA"
        detected = _parse_ts(row.get("detected_at"))
        entry = row.get("entry") or row.get("price")
        if not signal_id or not ticker or not detected or entry in (None, 0):
            skipped += 1
            continue
        try:
            entry = float(entry)
        except Exception:
            skipped += 1
            continue

        existing = _existing_keys(db, signal_id)
        symbol = _yf_symbol(str(ticker), str(market))

        try:
            hist = _future_history(symbol, detected, now)
        except Exception as exc:
            errors += 1
            print(f"PERFORMANCE WARN {ticker}: {type(exc).__name__}: {exc}")
            continue
        if hist.empty:
            continue

        for label, sessions in HORIZONS.items():
            outcome = f"MARK_{label}"
            if outcome in existing:
                continue
            try:
                stats = _window_stats(hist, sessions, entry)
                if not stats:
                    continue
                period_end = stats["period_end"]
                db.table("performance").insert({
                    "engine_id": row.get("engine_id") or row.get("engine") or "UNKNOWN",
                    "strategy": row.get("strategy"),
                    "market": str(market).upper(),
                    "ticker": str(ticker).upper(),
                    "signal_id": signal_id,
                    "period_start": detected.isoformat(),
                    "period_end": period_end.isoformat(),
                    "outcome": outcome,
                    "entry_price": entry,
                    "exit_price": stats["exit_price"],
                    "pnl_pct": round(stats["pnl_pct"], 4),
                    "max_drawdown_pct": round(stats["mdd_pct"], 4),
                    "max_favorable_excursion_pct": round(stats["mfe_pct"], 4),
                    "holding_minutes": max(0, int((period_end - detected).total_seconds() // 60)),
                    "metrics": {
                        "source": "yfinance",
                        "symbol": symbol,
                        "horizon": label,
                        "horizon_basis": "trading_sessions",
                        "max_drawdown_method": "close_peak_to_trough_from_entry",
                    },
                }).execute()
                inserted += 1
            except Exception as exc:
                errors += 1
                print(f"PERFORMANCE WARN {ticker} {label}: {type(exc).__name__}: {exc}")

    result = {"signals": len(signals), "inserted": inserted, "skipped": skipped, "errors": errors}
    print("PERFORMANCE", result)
    return result


if __name__ == "__main__":
    run()
