from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .core_snapshot import CoreSnapshot, build_core_snapshot


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SNAPSHOT_DIR = ROOT / "data" / "snapshots"


def _candidate_rows(payload: Any):
    if isinstance(payload, list):
        for row in payload:
            if isinstance(row, dict):
                yield row
        return
    if not isinstance(payload, dict):
        return
    for key in ("selected", "candidates", "results", "opportunities", "rows"):
        rows = payload.get(key)
        if isinstance(rows, list):
            for row in rows:
                if isinstance(row, dict):
                    yield row
    # Some snapshots can be a ticker-keyed dictionary.
    for key, value in payload.items():
        if isinstance(value, dict) and str(value.get("ticker", key)).strip():
            if "price" in value or "decision" in value or "operational_state" in value:
                candidate = dict(value)
                candidate.setdefault("ticker", key)
                yield candidate


def find_latest_core_snapshot(ticker: str, snapshot_dir: Path | None = None) -> tuple[CoreSnapshot | None, str | None]:
    """Return the newest persisted CORE candidate for ticker, read-only.

    The resolver deliberately accepts a few historical snapshot envelopes so the
    Committee can consume frozen CORE output without coupling to one save_run format.
    """
    symbol = ticker.strip().upper()
    root = snapshot_dir or DEFAULT_SNAPSHOT_DIR
    if not root.exists():
        return None, "snapshot_dir_missing"

    files = sorted(root.rglob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for path in files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for row in _candidate_rows(payload):
            if str(row.get("ticker", "")).upper() != symbol:
                continue
            version = None
            if isinstance(payload, dict):
                version = payload.get("version") or payload.get("strategy") or payload.get("engine_version")
            version = version or row.get("version") or row.get("strategy")
            snapshot = build_core_snapshot(row, engine_version=str(version) if version else None)
            return snapshot, str(path.relative_to(ROOT))
    return None, "ticker_not_found"
