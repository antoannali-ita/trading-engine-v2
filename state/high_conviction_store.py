from __future__ import annotations

import math
import os
from datetime import date, datetime, timezone
from typing import Any, Dict, Iterable, Optional


def _num(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        number = float(value)
        return number if math.isfinite(number) else None
    except Exception:
        return None


def _text(value: Any) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    return s or None


def _pick(c: Dict[str, Any], *keys: str) -> Any:
    """Return the first present, non-null Core field across engine aliases."""
    for key in keys:
        if key in c and c.get(key) is not None:
            return c.get(key)
    return None


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    try:
        return _json_safe(value.item())
    except Exception:
        pass
    try:
        if hasattr(value, "isoformat"):
            return value.isoformat()
    except Exception:
        pass
    return str(value)


def _company_name(c: Dict[str, Any]) -> Optional[str]:
    return _text(_pick(c, "company_name", "description", "name"))


def classify_high_conviction(market: str, c: Dict[str, Any]) -> Optional[str]:
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
        if operational in {"READY_FOR_TRIGGER", "SCORE_MARGINAL"}:
            return "PRE-BUY HIGH"
        return None

    return None


def _buy_requirements(market: str, c: Dict[str, Any], reference=None, regime: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    regime = regime if isinstance(regime, dict) else {}
    score_min = _num(getattr(reference, "MIN_SCORE_BUY", None)) if reference is not None else None
    rr_tp1_min = _num(getattr(reference, "MIN_NET_RR_TP1", None)) if reference is not None else None
    rr_tp2_min = _num(regime.get("min_net_rr"))
    if rr_tp2_min is None and reference is not None:
        rr_tp2_min = _num(getattr(reference, "MIN_NET_RR_NORMAL", None))

    return {
        "market": market.upper(),
        "market_regime": _text(regime.get("regime") or regime.get("state")),
        "score_min": score_min,
        "rr_tp1_min": rr_tp1_min,
        "rr_tp2_min": rr_tp2_min,
        "trigger_required": "CONFIRMED",
        "max_buy": _num(_pick(c, "max_buy", "max_entry")),
        "prebuy_high_min": 8.0 if market.strip().lower() == "usa" else None,
        "data_quality_required": "NOT_RED",
        "structure_required": "PASS",
        "sizing_required": "PASS",
        "source": "CORE_REFERENCE_AND_REGIME",
    }


def _payload(
    run_id: str,
    market: str,
    c: Dict[str, Any],
    signal_class: str,
    *,
    reference=None,
    regime: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    failed = _pick(c, "failed_gates", "prebuy_missing") or []
    if not isinstance(failed, list):
        failed = [str(failed)]

    raw_payload = _json_safe(c)
    if not isinstance(raw_payload, dict):
        raw_payload = {"raw": raw_payload}
    raw_payload["_buy_requirements"] = _buy_requirements(market, c, reference=reference, regime=regime)

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
        "opportunity_score": _num(_pick(c, "opportunity_score", "score_total", "score")),
        "signal_price": _num(_pick(c, "price", "last", "close")),
        "buy_zone_low": _num(_pick(c, "buy_zone_low", "buy_range_low", "entry_low")),
        "buy_zone_high": _num(_pick(c, "buy_zone_high", "buy_range_high", "entry_high")),
        "entry": _num(_pick(c, "entry", "ideal_entry", "entry_price", "proposed_entry")),
        "max_buy": _num(_pick(c, "max_buy", "max_entry")),
        "stop": _num(_pick(c, "stop", "stop_loss", "proposed_stop")),
        "tp1": _num(_pick(c, "tp1", "target1")),
        "tp2": _num(_pick(c, "tp2", "target2", "target", "proposed_target")),
        "gross_rr_tp1": _num(_pick(c, "gross_rr_tp1", "rr_gross_tp1")),
        "net_rr_tp1": _num(_pick(c, "net_rr_tp1", "rr_net_tp1")),
        "gross_rr_tp2": _num(_pick(c, "gross_rr_tp2", "rr_gross_tp2")),
        "net_rr_tp2": _num(_pick(c, "net_rr_tp2", "rr_net_tp2", "net_rr", "rr")),
        "trigger": _text(_pick(c, "trigger_state", "trigger")),
        "missing_gates": _json_safe(failed),
        "risk_usd": _num(_pick(c, "risk_usd", "position_risk_usd", "loss_max", "max_loss")),
        "risk_pct": _num(_pick(c, "risk_pct", "position_risk_pct")),
        "coverage_pct": _num(_pick(c, "data_coverage_pct", "coverage_pct")),
        "change_state": _text(c.get("change_state")),
        "active": True,
        "payload": raw_payload,
    }


def persist_high_conviction(
    run_id: Optional[str],
    market: str,
    selected: Iterable[Dict[str, Any]],
    *,
    reference=None,
    regime: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
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
            rows.append(_payload(rid, market, c, signal_class, reference=reference, regime=regime))

    try:
        db = create_client(url, key)
        if rows:
            db.table("core_high_conviction_signals").upsert(rows, on_conflict="run_id,market,ticker").execute()
            db.table("core_high_conviction_signals").update({"active": False}).eq("market", market_norm).eq("active", True).neq("run_id", rid).execute()
        else:
            db.table("core_high_conviction_signals").update({"active": False}).eq("market", market_norm).eq("active", True).execute()
        return {"written": len(rows), "skipped": False, "reason": None}
    except Exception as exc:
        return {"written": 0, "skipped": True, "reason": f"persist_failed:{type(exc).__name__}:{exc}"}
