from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from engine.analyzer import run_full_scan
from monitor.master_scan import load_cfg


def _pick(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = row.get(key)
        if value is not None:
            return value
    return None


def _normalise(row: dict[str, Any], rank: int) -> dict[str, Any]:
    return {
        "rank": rank,
        "ticker": str(_pick(row, "ticker", "name") or "").upper(),
        "decision": _pick(row, "decision", "operational_state", "display_state"),
        "score": _pick(row, "opportunity_score", "score_total", "score"),
        "quality_score": _pick(row, "quality_score"),
        "factor_score": _pick(row, "factor_score"),
        "price": _pick(row, "price", "current_price"),
        "entry": _pick(row, "entry", "ideal_entry", "entry_ideal"),
        "buy_low": _pick(row, "buy_zone_low", "buy_low"),
        "buy_high": _pick(row, "buy_zone_high", "buy_high"),
        "max_buy": _pick(row, "max_buy"),
        "stop": _pick(row, "stop", "stop_loss"),
        "tp1": _pick(row, "tp1", "target_1"),
        "tp2": _pick(row, "tp2", "target_2"),
        "net_rr_tp2": _pick(row, "net_rr_tp2", "rr_net_tp2", "rr_net"),
        "trigger": _pick(row, "trigger", "trigger_state"),
        "state": _pick(row, "display_state", "operational_state"),
        "data_quality": _pick(row, "data_quality", "data_quality_status"),
    }


def export_market(market: str, output: str, top_n: int = 10) -> dict[str, Any]:
    cfg = load_cfg(market)
    # Read-only parity run. Never send notifications or persist runtime state.
    cfg["send_email"] = False
    cfg["send_whatsapp"] = False
    cfg["dry_run"] = True
    result = run_full_scan(cfg, persist=False)

    payload: dict[str, Any] = {
        "engine": "V2",
        "market": market.upper(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "skipped": bool(result.get("skipped")),
        "skip_reason": result.get("skip_reason"),
        "counts": {
            "candidates": len(result.get("candidates") or []),
            "selected": len(result.get("selected") or []),
        },
        "top": [],
    }
    if not payload["skipped"]:
        payload["top"] = [
            _normalise(row, rank)
            for rank, row in enumerate((result.get("selected") or [])[:top_n], start=1)
        ]

    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(json.dumps(payload, indent=2, default=str))
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--market", choices=["usa", "italy"], required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--top", type=int, default=10)
    args = parser.parse_args()
    export_market(args.market, args.output, max(1, args.top))


if __name__ == "__main__":
    main()
