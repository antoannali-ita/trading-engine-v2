from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class AlertDecision:
    triggered: bool
    reason: str


def _num(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(Decimal(str(value)))
    except Exception:
        return None


def evaluate_alert(condition_type: str, trigger_level: Any, current_price: Any) -> AlertDecision:
    level = _num(trigger_level)
    price = _num(current_price)
    if level is None or price is None:
        return AlertDecision(False, "INVALID_PRICE")

    condition = str(condition_type or "").upper()
    if condition == "PRICE_ABOVE":
        return AlertDecision(price >= level, "PRICE_ABOVE" if price >= level else "WAITING")
    if condition == "PRICE_BELOW":
        return AlertDecision(price <= level, "PRICE_BELOW" if price <= level else "WAITING")
    return AlertDecision(False, "UNSUPPORTED_CONDITION")


def is_equivalent_recent_notification(
    alert: dict[str, Any],
    notifications: list[dict[str, Any]],
    *,
    now: datetime | None = None,
) -> bool:
    """Return True when an equivalent WhatsApp was already accepted recently.

    Fineco emails do not reliably expose the original operator (> or <), so Fineco-origin
    notifications are matched by ticker + nearby trigger level + time window. Alert-Center
    notifications additionally require the same condition type.
    """
    now = now or datetime.now(timezone.utc)
    dedup_minutes = int(alert.get("dedup_minutes") or 180)
    if dedup_minutes <= 0:
        return False
    cutoff = now - timedelta(minutes=dedup_minutes)

    ticker = str(alert.get("ticker") or "").upper()
    condition = str(alert.get("condition_type") or "").upper()
    level = _num(alert.get("trigger_level"))
    tolerance_pct = _num(alert.get("tolerance_pct")) or 0.0025
    if not ticker or level is None:
        return False

    tolerance = max(abs(level) * tolerance_pct, 0.01)

    for row in notifications:
        if str(row.get("ticker") or "").upper() != ticker:
            continue
        if str(row.get("channel") or "").upper() != "WHATSAPP":
            continue
        if str(row.get("status") or "").upper() != "SENT":
            continue

        sent_raw = row.get("sent_at") or row.get("attempted_at")
        try:
            sent_at = datetime.fromisoformat(str(sent_raw).replace("Z", "+00:00"))
            if sent_at.tzinfo is None:
                sent_at = sent_at.replace(tzinfo=timezone.utc)
        except Exception:
            continue
        if sent_at < cutoff:
            continue

        payload = row.get("payload") or {}
        if not isinstance(payload, dict):
            continue
        existing_level = _num(payload.get("trigger_level") or payload.get("fineco_price") or payload.get("price"))
        if existing_level is None or abs(existing_level - level) > tolerance:
            continue

        source = str(payload.get("source") or "").upper()
        existing_condition = str(payload.get("condition_type") or "").upper()
        if source == "FINECO" or existing_condition == condition:
            return True

    return False
