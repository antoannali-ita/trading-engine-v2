from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

POSITIVE_STATES = {
    "BUY_NOW",
    "BUY_LIMIT",
    "PRE_BUY_HIGH",
    "SHADOW_BUY",
    "BUY_CONFIRMATION",
    "CONFIRMED",
    "IN_BUY_ZONE",
}


def _norm(value: Any) -> str:
    return str(value or "").strip().upper().replace(" ", "_").replace("-", "_")


def signal_family(row: dict) -> str:
    engine = _norm(row.get("engine"))
    strategy = _norm(row.get("strategy"))
    # Multi-Horizon stays an independent validation layer even when one of its
    # internal strategies is named CORE/SHORT/FAST.
    if engine == "MULTI_HORIZON":
        return "MULTI_HORIZON"
    if engine in {"CORE", "SHORT", "FAST"}:
        return engine
    if "CORE" in strategy:
        return "CORE"
    if "SHORT" in strategy:
        return "SHORT"
    if "FAST" in strategy:
        return "FAST"
    return engine or strategy or "UNKNOWN"


def is_positive(row: dict) -> bool:
    if bool(row.get("is_actionable")):
        return True
    return _norm(row.get("decision")) in POSITIVE_STATES or _norm(row.get("signal_type") or row.get("status")) in POSITIVE_STATES


def compute_confluence(rows: list[dict], *, lookback_hours: int = 36, now: datetime | None = None) -> list[dict]:
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=lookback_hours)
    latest: dict[tuple[str, str, str], dict] = {}

    for row in rows:
        if _norm(row.get("engine")) == "ORCHESTRATOR":
            continue
        market = _norm(row.get("market"))
        ticker = _norm(row.get("ticker"))
        family = signal_family(row)
        if not market or not ticker or family == "UNKNOWN":
            continue
        raw_ts = row.get("detected_at") or row.get("created_at")
        try:
            ts = datetime.fromisoformat(str(raw_ts).replace("Z", "+00:00")) if raw_ts else now
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
        except Exception:
            ts = now
        if ts < cutoff:
            continue
        key = (market, ticker, family)
        previous = latest.get(key)
        if previous is None or str(raw_ts or "") > str(previous.get("detected_at") or previous.get("created_at") or ""):
            latest[key] = row

    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for (market, ticker, _), row in latest.items():
        grouped[(market, ticker)].append(row)

    out: list[dict] = []
    for (market, ticker), candidates in grouped.items():
        positive = [r for r in candidates if is_positive(r)]
        families = sorted({signal_family(r) for r in positive if signal_family(r) in {"CORE", "SHORT", "FAST"}})
        multi_positive = any(signal_family(r) == "MULTI_HORIZON" and is_positive(r) for r in candidates)
        count = len(families)
        if count <= 0:
            level = "NONE"
        elif count == 1:
            level = "SINGLE_SIGNAL"
        elif count == 2:
            level = "DOUBLE_CONFIRMATION"
        else:
            level = "TRIPLE_CONFIRMATION"
        scores = [float(r.get("conviction") or r.get("score_total")) for r in positive if r.get("conviction") is not None or r.get("score_total") is not None]
        out.append({
            "market": market,
            "ticker": ticker,
            "level": level,
            "families": families,
            "positive_count": count,
            "multi_horizon_positive": multi_positive,
            "score": round(sum(scores) / len(scores), 2) if scores else None,
            "source_signal_ids": [r.get("signal_id") for r in positive if r.get("signal_id")],
            "eligible_for_multi": count >= 1,
            "eligible_for_ai": count >= 2 or (count >= 1 and multi_positive),
        })
    return sorted(out, key=lambda x: (x["eligible_for_ai"], x["positive_count"], x.get("score") or 0), reverse=True)
