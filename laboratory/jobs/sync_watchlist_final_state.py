from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parents[1]
SRC = LAB_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from lab.db import get_supabase_client


LOOKBACK_DAYS = 7
PAGE_SIZE = 1000


def _latest_by_key(rows: list[dict]) -> dict[tuple[str, str], dict]:
    """Return the newest signal for every symbol/strategy pair."""
    latest: dict[tuple[str, str], dict] = {}
    for row in rows:
        symbol = str(row.get("symbol") or "").upper().strip()
        strategy = str(row.get("strategy") or "").strip()
        signal_date = str(row.get("signal_date") or "")[:10]
        if not symbol or not strategy or not signal_date:
            continue
        key = (symbol, strategy)
        current = latest.get(key)
        if current is None or signal_date > str(current.get("signal_date") or "")[:10]:
            latest[key] = row
    return latest


def _load_recent_signals(client, cutoff: str) -> list[dict]:
    rows: list[dict] = []
    start = 0
    while True:
        response = (
            client.table("lab_paper_signals")
            .select("symbol,strategy,signal_date,status,details")
            .gte("signal_date", cutoff)
            .order("signal_date", desc=True)
            .range(start, start + PAGE_SIZE - 1)
            .execute()
        )
        batch = response.data or []
        rows.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
        start += PAGE_SIZE
    return rows


def main() -> int:
    if not os.getenv("SUPABASE_URL") or not os.getenv("SUPABASE_SECRET_KEY"):
        print("Supabase secrets missing; final watchlist sync skipped")
        return 2

    client = get_supabase_client()
    cutoff = (datetime.now(timezone.utc).date() - timedelta(days=LOOKBACK_DAYS)).isoformat()

    try:
        rows = _load_recent_signals(client, cutoff)
    except Exception as exc:
        print(f"FATAL: cannot load recent lab_paper_signals for watchlist sync: {exc}")
        return 1

    latest = _latest_by_key(rows)
    updated = 0
    failed = 0
    for (symbol, strategy), row in latest.items():
        try:
            payload = {
                "status": row.get("status"),
                "signal_date": str(row.get("signal_date") or "")[:10],
                "details": row.get("details") if isinstance(row.get("details"), dict) else {},
            }
            client.table("lab_watchlist").update(payload).eq("symbol", symbol).eq(
                "strategy", strategy
            ).eq("active", True).execute()
            updated += 1
        except Exception as exc:
            failed += 1
            print(f"watchlist final sync {symbol}/{strategy}: {exc}")

    print(f"final watchlist sync updated={updated} failed={failed} cutoff={cutoff}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
