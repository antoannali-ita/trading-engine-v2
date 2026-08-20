from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional


def _num(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _text(value: Any) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    return s or None


def _company_name(c: Dict[str, Any]) -> Optional[str]:
    return _text(c.get("company_name") or c.get("description") or c.get("name"))


def classify_high_conviction(market: str, c: Dict[str, Any]) -> Optional[str]:
    """Map existing Core outputs to dashboard classes without changing trading logic."""
    m = market.strip().lower()
    decision = str(c.get("decision") or "").upper().replace(" ", "_")
    display_state = str(c.get("display_state") or "").upper().replace("_", " ")
    operational = str(c.get("operational_state") or "").upper()

    if decision == "BUY_NOW":
        return "BUY NOW"
    if decision == "BUY_LIMIT" or operational == "LIMIT_READY":
        return "BUY LIMIT"

    if m == "usa":
        score = _num(c.get("prebuy_score"))
        eligible = bool(c.get("prebuy_eligible"))
        if display_state == "PRE-BUY" and eligible and score is not None and score >= 8:
            return "PRE-BUY HIGH"
        return None

    if m == "italy":
        # Italy keeps its own engine semantics. These are existing high-priority
        # operational states, merely presented under one dashboard label.
        if operational in {"READY_FOR_TRIGGER", "SCORE_MARGINAL"}:
            return "PRE-BUY HIGH"
        return None

    return None


def _payload(run_id: str, market: str, c: Dict[str, Any], signal_class: str) -> Dict[str, Any]:
    failed = c.get("failed_gates") or c.get("prebuy_missing") or []
    if not isinstance(failed, list):
        failed = [str(failed)]

    return {
        "run_id": run_id,
        "market": market.upper(),
        "ticker": _text(c.get("ticker")),
        "company_name": _company_name(c),
        "signal_class": signal_class,
        "decision": _text(c.get("decision")),
        "display_state": _text(c.get("display_state")),
        "operational_state": _text(c.get("operational_state")),
        "prebuy_score": _num(c.get("prebuy_score")),
        "prebuy_label": _text(c.get("prebuy_label")),
        "prebuy_eligible": bool(c.get("prebuy_eligible")) if c.get("prebuy_eligible") is not None else None,
        "quality_score": _num(c.get("quality_score")),
        "opportunity_score": _num(c.get("opportunity_score", c.get("score"))),
        "signal_price": _num(c.get("price")),
        "buy_zone_low": _num(c.get("buy_zone_low", c.get("buy_range_low"))),
        "buy_zone_high": _num(c.get("buy_zone_high", c.get("buy_range_high"))),
        "entry": _num(c.get("entry")),
        "max_buy": _num(c.get("max_buy")),
        "stop": _num(c.get("stop")),
        "tp1": _num(c.get("tp1")),
        "tp2": _num(c.get("tp2")),
        "gross_rr_tp1": _num(c.get("gross_rr_tp1")),
        "net_rr_tp1": _num(c.get("net_rr_tp1", c.get("rr_net_tp1"))),
        "gross_rr_tp2": _num(c.get("gross_rr_tp2")),
        "net_rr_tp2": _num(c.get("net_rr_tp2", c.get("rr_net_tp2"))),
        "trigger": _text(c.get("trigger_state", c.get("trigger"))),
        "missing_gates": failed,
        "risk_usd": _num(c.get("risk_usd", c.get("position_risk_usd"))),
        "risk_pct": _num(c.get("risk_pct", c.get("position_risk_pct"))),
        "coverage_pct": _num(c.get("data_coverage_pct", c.get("coverage_pct"))),
        "change_state": _text(c.get("change_state")),
        "active": True,
        "payload": c,
    }


def persist_high_conviction(run_id: Optional[str], market: str, selected: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Best-effort Supabase persistence. Never blocks or alters the Core decision flow."""
    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_SECRET_KEY", "").strip()
    if not url or not key:
        return {"written": 0, "skipped": True, "reason": "supabase_not_configured"}

    try:
        from supabase import create_client
    except Exception as exc:
        return {"written": 0, "skipped": True, "reason": f"supabase_import:{exc}"}

    rid = run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    market_norm = market.upper()
    rows = []
    for c in selected:
        signal_class = classify_high_conviction(market, c)
        if signal_class:
            rows.append(_payload(rid, market, c, signal_class))

    try:
        db = create_client(url, key)
        # Only the newest run for this market is active. History is preserved.
        db.table("core_high_conviction_signals").update({"active": False}).eq("market", market_norm).eq("active", True).execute()
        if rows:
            db.table("core_high_conviction_signals").upsert(rows, on_conflict="run_id,market,ticker").execute()
        return {"written": len(rows), "skipped": False, "reason": None}
    except Exception as exc:
        # Telemetry must never break a production scan or notification.
        return {"written": 0, "skipped": True, "reason": f"persist_failed:{type(exc).__name__}:{exc}"}
