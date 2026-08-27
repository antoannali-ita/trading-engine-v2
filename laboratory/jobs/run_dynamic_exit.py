from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parents[1]
SRC = LAB_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from lab.db import get_supabase_client
from lab.dynamic_exit import POLICY_VERSION, evaluate
from lab.indicators import enrich_prices
from lab.market_data import MarketDataRequest, download_prices


def _enabled() -> bool:
    return os.getenv("LAB_DYNAMIC_EXIT_ENABLED", "1").strip().lower() not in {"0", "false", "no", "off"}


def _event_payload(position_id: int, event: dict, price: float | None, state: dict) -> dict:
    return {
        "position_id": position_id,
        "event_type": event["event_type"],
        "price": price,
        "old_stop": event.get("old_stop"),
        "new_stop": event.get("new_stop"),
        "note": f"{POLICY_VERSION}: {event.get('reason') or 'N/D'}",
        "details": {
            "policy_version": POLICY_VERSION,
            "reason": event.get("reason"),
            "target_mode": state.get("target_mode"),
            "old_tp2": event.get("old_tp2"),
            "new_tp2": event.get("new_tp2"),
        },
    }


def main() -> int:
    if not _enabled():
        print("dynamic exit disabled")
        return 0
    if not os.getenv("SUPABASE_URL") or not os.getenv("SUPABASE_SECRET_KEY"):
        print("Supabase secrets missing; dynamic exit not persisted")
        return 2

    client = get_supabase_client()
    positions = (
        client.table("lab_paper_positions")
        .select("*")
        .in_("status", ["OPEN", "TP1_HIT"])
        .execute()
        .data
        or []
    )
    if not positions:
        print("dynamic exit: no active positions")
        return 0

    symbols = sorted({str(p.get("symbol") or "").upper() for p in positions if p.get("symbol")})
    frames = {}
    failures = 0
    for symbol in symbols:
        try:
            prices = download_prices(MarketDataRequest(symbol=symbol, start="2024-01-01"))
            frame = enrich_prices(prices)
            if frame.empty:
                raise RuntimeError("empty enriched price frame")
            frames[symbol] = frame
        except Exception as exc:
            failures += 1
            print(f"dynamic exit market data {symbol}: {exc}")

    changed = initialized = events_written = 0
    now_iso = datetime.now(timezone.utc).isoformat()

    for p in positions:
        symbol = str(p.get("symbol") or "").upper()
        frame = frames.get(symbol)
        if frame is None:
            continue
        try:
            decision = evaluate(p, frame, now_iso=now_iso)
            details = dict(p.get("details") or {}) if isinstance(p.get("details"), dict) else {}
            was_dynamic = isinstance(details.get("dynamic_exit"), dict)
            details["exit_variant"] = POLICY_VERSION
            details["dynamic_exit"] = decision["state"]

            update_payload = {"details": details}
            if decision.get("stop_current") is not None:
                update_payload["stop_current"] = decision["stop_current"]
            if decision.get("tp2_current") is not None:
                # Keep the existing tp2 column as the current operational target.
                # The original target is preserved in details.dynamic_exit.tp2_initial.
                update_payload["tp2"] = decision["tp2_current"]

            client.table("lab_paper_positions").update(update_payload).eq("id", p["id"]).execute()
            if not was_dynamic:
                initialized += 1
                client.table("lab_paper_events").insert({
                    "position_id": p["id"],
                    "event_type": "EXIT_POLICY_INITIALIZED",
                    "price": decision["snapshot"].get("close"),
                    "old_stop": p.get("stop_current") or p.get("stop_initial"),
                    "new_stop": decision.get("stop_current"),
                    "note": f"Position enrolled in {POLICY_VERSION}; original stop/TP2 preserved in details.",
                    "details": {"policy_version": POLICY_VERSION, "target_mode": decision.get("target_mode")},
                }).execute()
                events_written += 1

            for event in decision.get("events") or []:
                client.table("lab_paper_events").insert(
                    _event_payload(p["id"], event, decision["snapshot"].get("close"), decision["state"])
                ).execute()
                events_written += 1

            if decision.get("changed"):
                changed += 1
        except Exception as exc:
            failures += 1
            print(f"dynamic exit {symbol} position={p.get('id')}: {exc}")

    print(
        f"dynamic_exit policy={POLICY_VERSION} active={len(positions)} initialized={initialized} "
        f"changed={changed} events={events_written} failures={failures}"
    )
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
