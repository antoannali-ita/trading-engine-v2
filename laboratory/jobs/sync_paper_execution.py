from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LAB_ROOT = Path(__file__).resolve().parents[1]
SRC = LAB_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from lab.db import get_supabase_client
from lab.risk_metrics import build_risk_basis, mtm_r, open_risk_and_locked_profit_r, realized_r_from_fills
from lab.settings import USA_COMMISSION_USD

ACTIVE_STATUSES = {"OPEN", "TP1_HIT"}


def _dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(str(value)) if value else {}
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except Exception:
        return None


def _version(row: dict[str, Any]) -> str:
    details = _dict(row.get("details"))
    return str(row.get("strategy_version") or details.get("strategy_version") or details.get("version") or "UNVERSIONED")


def _side(row: dict[str, Any]) -> str:
    details = _dict(row.get("details"))
    return str(row.get("side") or details.get("side") or "LONG").upper()


def _schema_available(client) -> bool:
    try:
        client.table("lab_paper_fills").select("id").limit(1).execute()
        return True
    except Exception:
        return False


def _existing_fills(client, position_id: int) -> list[dict[str, Any]]:
    return client.table("lab_paper_fills").select("*").eq("position_id", position_id).order("executed_at").execute().data or []


def _insert_fill(client, position: dict[str, Any], *, fill_type: str, qty: int, price: float, commission: float, executed_at: str, details: dict[str, Any] | None = None) -> None:
    client.table("lab_paper_fills").insert({
        "position_id": int(position["id"]),
        "strategy": position.get("strategy"),
        "strategy_version": _version(position),
        "symbol": position.get("symbol"),
        "side": _side(position),
        "fill_type": fill_type,
        "qty": int(qty),
        "price": float(price),
        "commission": float(commission),
        "slippage_bps": _float(_dict(position.get("details")).get("estimated_slippage_bps")),
        "executed_at": executed_at,
        "details": details or {},
    }).execute()


def _exit_fill_type(reason: Any) -> str:
    value = str(reason or "").upper()
    if value == "TP2":
        return "TP2"
    if value == "STOP":
        return "STOP"
    return "MANUAL_EXIT"


def main() -> int:
    if not os.getenv("SUPABASE_URL") or not os.getenv("SUPABASE_SECRET_KEY"):
        print("Supabase secrets missing; execution sync skipped")
        return 2
    client = get_supabase_client()
    if not _schema_available(client):
        print("SCHEMA_MISSING: Laboratory 2.2 migration not applied; execution sync skipped safely")
        return 0

    positions = client.table("lab_paper_positions").select("*").order("opened_at").limit(20000).execute().data or []
    updated = entry_fills = exit_fills = 0

    for p in positions:
        try:
            position_id = int(p["id"])
            details = _dict(p.get("details"))
            fill_price = _float(p.get("fill_price")) or _float(details.get("execution_entry")) or _float(p.get("entry_price"))
            stop_initial = _float(p.get("stop_initial"))
            qty = int(p.get("qty") or 0)
            if fill_price is None or stop_initial is None or qty <= 0:
                continue
            atr = _float(p.get("atr14_at_entry")) or _float(details.get("atr14"))
            basis = build_risk_basis(side=_side(p), fill_price=fill_price, stop_initial=stop_initial, atr14=atr)
            fills = _existing_fills(client, position_id)
            fill_types = {str(f.get("fill_type") or "").upper() for f in fills}

            if "ENTRY" not in fill_types:
                _insert_fill(
                    client, p, fill_type="ENTRY", qty=qty, price=fill_price,
                    commission=_float(p.get("commission_entry")) or USA_COMMISSION_USD,
                    executed_at=str(p.get("opened_at") or datetime.now(timezone.utc).isoformat()),
                    details={"backfilled": True, "source": "lab_paper_positions"},
                )
                entry_fills += 1
                fills = _existing_fills(client, position_id)

            status = str(p.get("status") or "").upper()
            patch: dict[str, Any] = {
                "side": basis.side,
                "strategy_version": _version(p),
                "ideal_entry": _float(p.get("ideal_entry")) or _float(details.get("ideal_entry")),
                "fill_price": fill_price,
                "atr14_at_entry": atr,
                "raw_initial_risk": basis.raw_initial_risk,
                "normalized_initial_risk": basis.normalized_initial_risk,
                "risk_floor_applied": basis.risk_floor_applied,
            }

            if status in ACTIVE_STATUSES:
                current = _float(p.get("last_price")) or fill_price
                risk_r, locked_r = open_risk_and_locked_profit_r(basis=basis, stop_current=_float(p.get("stop_current")))
                patch.update({
                    "mtm_r": mtm_r(basis=basis, current_price=current),
                    "open_risk_r": risk_r,
                    "locked_profit_r": locked_r,
                    "realized_r": None,
                })
            elif status == "CLOSED":
                has_exit = any(str(f.get("fill_type") or "").upper() in {"TP1", "TP2", "STOP", "MANUAL_EXIT"} for f in fills)
                exit_price = _float(p.get("exit_price")) or _float(p.get("last_price"))
                if not has_exit and exit_price is not None:
                    _insert_fill(
                        client, p, fill_type=_exit_fill_type(p.get("exit_reason")), qty=qty, price=exit_price,
                        commission=USA_COMMISSION_USD,
                        executed_at=str(p.get("closed_at") or datetime.now(timezone.utc).isoformat()),
                        details={"backfilled": True, "source": "lab_paper_positions", "exit_reason": p.get("exit_reason")},
                    )
                    exit_fills += 1
                    fills = _existing_fills(client, position_id)
                exits = [f for f in fills if str(f.get("fill_type") or "").upper() in {"TP1", "TP2", "STOP", "MANUAL_EXIT"}]
                realized = realized_r_from_fills(
                    basis=basis,
                    initial_qty=qty,
                    exit_fills=exits,
                    entry_cost=_float(p.get("commission_entry")) or USA_COMMISSION_USD,
                )
                patch.update({"realized_r": realized, "mtm_r": None, "open_risk_r": 0, "locked_profit_r": 0})

            client.table("lab_paper_positions").update(patch).eq("id", position_id).execute()
            updated += 1
        except Exception as exc:
            print(f"position {p.get('id')}: {type(exc).__name__}: {exc}")
            return 1

    print(f"execution sync positions={updated} entry_fills={entry_fills} exit_fills={exit_fills}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
