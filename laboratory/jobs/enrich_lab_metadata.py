from __future__ import annotations

import os
import sys
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parents[1]
SRC = LAB_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from lab.db import get_supabase_client
from lab.decision_engine import net_rr
from lab.settings import ESTIMATED_SLIPPAGE_BPS

CURRENT_COMMISSION = 12.0
DISCOUNT_COMMISSION = 9.90


def _details(value):
    return dict(value) if isinstance(value, dict) else {}


def _num(value):
    try:
        return float(value) if value is not None else None
    except Exception:
        return None


def _gross_rr(entry: float | None, stop: float | None, target: float | None) -> float | None:
    if entry is None or stop is None or target is None or entry <= stop or target <= entry:
        return None
    risk = entry - stop
    return (target - entry) / risk if risk > 0 else None


def _cost_model(entry, stop, target, qty):
    entry = _num(entry)
    stop = _num(stop)
    target = _num(target)
    try:
        qty = int(qty or 0)
    except Exception:
        qty = 0
    gross = _gross_rr(entry, stop, target)
    current = None
    discount = None
    if entry and stop and target and qty > 0:
        current = net_rr(
            entry=entry, stop=stop, target=target, qty=qty,
            commission=CURRENT_COMMISSION, slippage_bps=ESTIMATED_SLIPPAGE_BPS,
        )
        discount = net_rr(
            entry=entry, stop=stop, target=target, qty=qty,
            commission=DISCOUNT_COMMISSION, slippage_bps=ESTIMATED_SLIPPAGE_BPS,
        )
    return {
        "gross_rr": gross,
        "net_rr_fineco_current_12": current,
        "net_rr_fineco_discount_9_90": discount,
        "commission_per_side_current": CURRENT_COMMISSION,
        "commission_per_side_discount": DISCOUNT_COMMISSION,
        "round_trip_current": 2 * CURRENT_COMMISSION,
        "round_trip_discount": 2 * DISCOUNT_COMMISSION,
        "estimated_slippage_bps": ESTIMATED_SLIPPAGE_BPS,
        "model": "FINECO_SCENARIOS_PLUS_ESTIMATED_SLIPPAGE_V1",
    }


def _enrich_details(symbol, strategy, signal_date, details, entry, stop, target, qty):
    details = _details(details)
    policy = _details(details.get("paper_policy"))
    tier = details.get("paper_tier") or policy.get("tier")
    risk_key = f"EQUITY:{str(symbol).upper()}"
    tier_key = str(tier or "REJECTED")
    experiment_key = f"{str(symbol).upper()}:{strategy}:{tier_key}"

    details["risk_key"] = risk_key
    details["experiment_key"] = experiment_key
    details["paper_tier"] = tier
    details["safety_label"] = policy.get("safety_label") or (
        "RESEARCH_ONLY_NON_OPERATIONAL" if tier == "C" else "PAPER_EXPERIMENT"
    )
    details["non_operational"] = bool(tier == "C")
    details["cost_model"] = _cost_model(entry, stop, target, qty)
    details["cost_model"]["fineco_discount_effective_note"] = (
        "Scenario supplied by user: 9.90 USD per executed order from next month; verify when effective."
    )
    details["metadata_model"] = "LAB_METADATA_V2_1"
    details["source_signal_date"] = signal_date
    return details


def main() -> int:
    if not os.getenv("SUPABASE_URL") or not os.getenv("SUPABASE_SECRET_KEY"):
        print("Supabase secrets missing; metadata enrichment skipped")
        return 2

    client = get_supabase_client()
    signals = (
        client.table("lab_paper_signals")
        .select("*")
        .order("signal_date", desc=True)
        .limit(5000)
        .execute().data or []
    )
    positions = client.table("lab_paper_positions").select("*").limit(5000).execute().data or []
    pos_index = {
        (str(p.get("symbol") or "").upper(), str(p.get("strategy") or ""), str(p.get("source_signal_date") or "")[:10]): p
        for p in positions
    }

    updated_signals = 0
    updated_positions = 0
    for row in signals:
        symbol = str(row.get("symbol") or "").upper()
        strategy = str(row.get("strategy") or "")
        signal_date = str(row.get("signal_date") or "")[:10]
        details = _details(row.get("details"))
        qty = details.get("qty") or 0
        enriched = _enrich_details(
            symbol, strategy, signal_date, details,
            row.get("proposed_entry") or row.get("price"),
            row.get("proposed_stop"), row.get("proposed_target"), qty,
        )
        client.table("lab_paper_signals").update({"details": enriched}).eq(
            "symbol", symbol
        ).eq("strategy", strategy).eq("signal_date", signal_date).execute()
        updated_signals += 1

        p = pos_index.get((symbol, strategy, signal_date))
        if p:
            pdetails = _details(p.get("details"))
            pdetails.update({
                "risk_key": enriched["risk_key"],
                "experiment_key": enriched["experiment_key"],
                "paper_tier": enriched.get("paper_tier"),
                "safety_label": enriched.get("safety_label"),
                "non_operational": enriched.get("non_operational"),
                "cost_model": _cost_model(
                    p.get("entry_price"), p.get("stop_initial"), p.get("tp2"), p.get("qty")
                ),
                "metadata_model": "LAB_METADATA_V2_1",
            })
            client.table("lab_paper_positions").update({"details": pdetails}).eq("id", p["id"]).execute()
            updated_positions += 1

    print(f"metadata signals={updated_signals} positions={updated_positions}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
