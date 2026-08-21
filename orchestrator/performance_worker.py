from __future__ import annotations

from datetime import datetime, timedelta, timezone

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


def _window_stats(symbol: str, start: datetime, end: datetime, entry: float):
    hist = yf.download(
        symbol,
        start=start.date().isoformat(),
        end=(end + timedelta(days=2)).date().isoformat(),
        auto_adjust=True,
        progress=False,
    )
    if hist is None or hist.empty:
        return None
    close = hist["Close"].dropna()
    high = hist["High"].dropna()
    low = hist["Low"].dropna()
    if close.empty:
        return None
    exit_price = float(close.iloc[-1])
    max_price = float(high.max()) if not high.empty else exit_price
    min_price = float(low.min()) if not low.empty else exit_price
    return {
        "exit_price": exit_price,
        "pnl_pct": (exit_price / entry - 1.0) * 100.0,
        "mfe_pct": (max_price / entry - 1.0) * 100.0,
        "mdd_pct": (min_price / entry - 1.0) * 100.0,
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

        for label, days in HORIZONS.items():
            outcome = f"MARK_{label}"
            if outcome in existing:
                continue
            target = detected + timedelta(days=days)
            if now < target:
                continue
            try:
                stats = _window_stats(symbol, detected, target, entry)
                if not stats:
                    continue
                db.table("performance").insert({
                    "engine_id": row.get("engine_id") or row.get("engine") or "UNKNOWN",
                    "strategy": row.get("strategy"),
                    "market": str(market).upper(),
                    "ticker": str(ticker).upper(),
                    "signal_id": signal_id,
                    "period_start": detected.isoformat(),
                    "period_end": target.isoformat(),
                    "outcome": outcome,
                    "entry_price": entry,
                    "exit_price": stats["exit_price"],
                    "pnl_pct": round(stats["pnl_pct"], 4),
                    "max_drawdown_pct": round(stats["mdd_pct"], 4),
                    "max_favorable_excursion_pct": round(stats["mfe_pct"], 4),
                    "holding_minutes": int((target - detected).total_seconds() // 60),
                    "metrics": {"source": "yfinance", "symbol": symbol, "horizon": label},
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
