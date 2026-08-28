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


STALE_AFTER_DAYS = 3


def main() -> int:
    if not os.getenv("SUPABASE_URL") or not os.getenv("SUPABASE_SECRET_KEY"):
        print("Supabase secrets missing; watchlist cleanup skipped")
        return 2

    client = get_supabase_client()
    stale_before = (datetime.now(timezone.utc) - timedelta(days=STALE_AFTER_DAYS)).isoformat()

    try:
        client.table("lab_watchlist").update({"active": False}).lt(
            "last_seen_at", stale_before
        ).eq("active", True).execute()
    except Exception as exc:
        print(f"FATAL: lab_watchlist stale cleanup failed: {exc}")
        return 1

    try:
        remaining = (
            client.table("lab_watchlist")
            .select("symbol,strategy,last_seen_at")
            .lt("last_seen_at", stale_before)
            .eq("active", True)
            .limit(10)
            .execute()
            .data
            or []
        )
    except Exception as exc:
        print(f"FATAL: cannot verify lab_watchlist stale cleanup: {exc}")
        return 1

    if remaining:
        print(f"FATAL: stale active watchlist rows remain after cleanup: {remaining}")
        return 1

    print(f"lab_watchlist stale cleanup verified; cutoff={stale_before}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
