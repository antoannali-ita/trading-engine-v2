from __future__ import annotations

import csv
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from supabase import create_client

TABLES = [
    "lab_watchlist",
    "lab_paper_positions",
    "lab_paper_events",
    "lab_paper_signals",
    "lab_signal_outcomes",
    "lab_backtest_runs",
    "lab_backtest_results",
    "lab_calibration_results",
    "lab_strategy_variants",
    "lab_strategy_evaluations",
    "lab_evolution_runs",
    "core_high_conviction_signals",
    "engine_runs",
    "signals",
    "performance",
]

PAGE_SIZE = 1000


def _client():
    url = (os.getenv("SUPABASE_URL") or "").strip()
    key = (os.getenv("SUPABASE_SECRET_KEY") or "").strip()
    if not url or not key:
        raise RuntimeError("SUPABASE_URL e SUPABASE_SECRET_KEY non configurati")
    return create_client(url, key)


def fetch_all(client, table: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    start = 0
    while True:
        end = start + PAGE_SIZE - 1
        batch = client.table(table).select("*").range(start, end).execute().data or []
        rows.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
        start += PAGE_SIZE
    return rows


def _serialize(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row.keys():
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)

    with path.open("w", encoding="utf-8-sig", newline="") as f:
        if not fieldnames:
            f.write("")
            return
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: _serialize(row.get(k)) for k in fieldnames})


def main() -> None:
    client = _client()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root = Path("artifacts")
    export_dir = root / f"lab_export_{stamp}"
    export_dir.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, Any] = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "tables": {},
    }

    for table in TABLES:
        try:
            rows = fetch_all(client, table)
            write_csv(export_dir / f"{table}.csv", rows)
            manifest["tables"][table] = {"status": "OK", "rows": len(rows)}
            print(f"OK {table}: {len(rows)} rows")
        except Exception as exc:
            manifest["tables"][table] = {
                "status": "ERROR",
                "rows": 0,
                "error": f"{type(exc).__name__}: {exc}",
            }
            print(f"ERROR {table}: {type(exc).__name__}: {exc}")

    with (export_dir / "manifest.json").open("w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2, sort_keys=True)

    archive = shutil.make_archive(str(export_dir), "zip", root_dir=export_dir)
    print(f"ARCHIVE={archive}")

    # Fail only if every requested table failed. Partial exports remain useful
    # and the manifest records exactly what was missing.
    ok_count = sum(1 for item in manifest["tables"].values() if item["status"] == "OK")
    if ok_count == 0:
        raise RuntimeError("Nessuna tabella esportata: controllare secret/permessi Supabase")


if __name__ == "__main__":
    main()
