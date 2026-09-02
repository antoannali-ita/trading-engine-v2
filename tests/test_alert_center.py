from datetime import datetime, timedelta, timezone

from alert_center.engine import evaluate_alert, is_equivalent_recent_notification
from alert_center.runner import _legacy_to_platform_row, _market_session_open, _triggered


def test_price_above_and_below():
    assert evaluate_alert("PRICE_ABOVE", 100, 100).triggered
    assert not evaluate_alert("PRICE_ABOVE", 100, 99.99).triggered
    assert evaluate_alert("PRICE_BELOW", 100, 99.99).triggered
    assert not evaluate_alert("PRICE_BELOW", 100, 100.01).triggered


def test_fineco_notification_suppresses_nearby_alert_within_window():
    now = datetime.now(timezone.utc)
    alert = {
        "ticker": "MSFT",
        "condition_type": "PRICE_ABOVE",
        "trigger_level": 525,
        "dedup_minutes": 180,
        "tolerance_pct": 0.0025,
    }
    notifications = [{
        "ticker": "MSFT",
        "channel": "WHATSAPP",
        "status": "SENT",
        "sent_at": (now - timedelta(minutes=45)).isoformat(),
        "payload": {"source": "FINECO", "trigger_level": 525.25},
    }]
    assert is_equivalent_recent_notification(alert, notifications, now=now)


def test_old_or_different_level_is_not_duplicate():
    now = datetime.now(timezone.utc)
    alert = {
        "ticker": "MSFT",
        "condition_type": "PRICE_ABOVE",
        "trigger_level": 525,
        "dedup_minutes": 180,
        "tolerance_pct": 0.0025,
    }
    old = [{
        "ticker": "MSFT",
        "channel": "WHATSAPP",
        "status": "SENT",
        "sent_at": (now - timedelta(hours=4)).isoformat(),
        "payload": {"source": "FINECO", "trigger_level": 525},
    }]
    far = [{
        "ticker": "MSFT",
        "channel": "WHATSAPP",
        "status": "SENT",
        "sent_at": (now - timedelta(minutes=20)).isoformat(),
        "payload": {"source": "FINECO", "trigger_level": 530},
    }]
    assert not is_equivalent_recent_notification(alert, old, now=now)
    assert not is_equivalent_recent_notification(alert, far, now=now)


def test_alert_center_requires_same_condition_when_not_fineco():
    now = datetime.now(timezone.utc)
    alert = {
        "ticker": "CSCO",
        "condition_type": "PRICE_BELOW",
        "trigger_level": 108.90,
        "dedup_minutes": 180,
        "tolerance_pct": 0.0025,
    }
    notifications = [{
        "ticker": "CSCO",
        "channel": "WHATSAPP",
        "status": "SENT",
        "sent_at": (now - timedelta(minutes=10)).isoformat(),
        "payload": {"source": "ALERT_CENTER", "condition_type": "PRICE_ABOVE", "trigger_level": 108.90},
    }]
    assert not is_equivalent_recent_notification(alert, notifications, now=now)


def test_platform_trigger_types_and_italia_market_alias():
    assert _triggered({"alert_type": "PRICE_ABOVE", "threshold": 100}, 101)[0]
    assert _triggered({"alert_type": "PRICE_BELOW", "threshold": 100}, 99)[0]
    assert _triggered({"alert_type": "ENTRY_ZONE", "threshold_min": 98, "threshold_max": 102}, 100)[0]
    assert _market_session_open("ITALIA", datetime(2026, 9, 2, 10, 0, tzinfo=timezone.utc))


def test_legacy_alert_maps_to_platform_source_of_truth():
    now = datetime(2026, 9, 2, 12, 0, tzinfo=timezone.utc)
    row = _legacy_to_platform_row({
        "ticker": "csco",
        "market": "ITALY",
        "condition_type": "PRICE_BELOW",
        "trigger_level": "108.90",
        "expires_at": "2026-10-01T00:00:00+00:00",
    }, now)
    assert row["ticker"] == "CSCO"
    assert row["market"] == "ITALIA"
    assert row["alert_type"] == "PRICE_BELOW"
    assert row["threshold"] == 108.9
    assert row["status"] == "ACTIVE"
