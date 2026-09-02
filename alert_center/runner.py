from __future__ import annotations

import os
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import yfinance as yf
from supabase import create_client

from fineco_alert_bridge.whatsapp import send_callmebot


MARKET_HOURS = {
    "ITALY": {"timezone": "Europe/Rome", "open": time(9, 0), "close": time(17, 30)},
    "ITALIA": {"timezone": "Europe/Rome", "open": time(9, 0), "close": time(17, 30)},
    "USA": {"timezone": "America/New_York", "open": time(9, 30), "close": time(16, 0)},
}

SUPPORTED_TYPES = {"PRICE_ABOVE", "PRICE_BELOW", "MAX_BUY", "ENTRY_ZONE"}


def _market_session_open(market: str, now: datetime | None = None) -> bool:
    market = str(market or "").upper()
    rule = MARKET_HOURS.get(market)
    if rule is None:
        return False
    local = (now or datetime.now(timezone.utc)).astimezone(ZoneInfo(rule["timezone"]))
    if local.weekday() >= 5:
        return False
    clock = local.time().replace(tzinfo=None)
    return rule["open"] <= clock <= rule["close"]


def _client():
    url = (os.getenv("SUPABASE_URL") or "").strip()
    key = (os.getenv("SUPABASE_SECRET_KEY") or "").strip()
    if not url or not key:
        raise RuntimeError("SUPABASE_URL e SUPABASE_SECRET_KEY non configurati")
    return create_client(url, key)


def _yf_symbol(ticker: str, market: str) -> str:
    ticker = ticker.upper().strip()
    if market.upper() in {"ITALY", "ITALIA"} and not ticker.endswith(".MI"):
        return f"{ticker}.MI"
    return ticker


def _legacy_key(row: dict) -> tuple[str, str, str, float | None]:
    market = str(row.get("market") or "USA").upper()
    if market == "ITALY":
        market = "ITALIA"
    return (
        market,
        str(row.get("ticker") or "").upper().strip(),
        str(row.get("condition_type") or row.get("alert_type") or "").upper(),
        _num(row.get("trigger_level") if "trigger_level" in row else row.get("threshold")),
    )


def _legacy_to_platform_row(row: dict, now: datetime) -> dict:
    market, ticker, alert_type, threshold = _legacy_key(row)
    expires = _parse_dt(row.get("expires_at")) or now + timedelta(days=30)
    return {
        "ticker": ticker,
        "market": market,
        "alert_type": alert_type,
        "condition": str(row.get("note") or "Migrazione Alert Center legacy"),
        "threshold": threshold,
        "status": "ACTIVE",
        "priority": 70,
        "notification_policy": "BUY_PREBUY_HIGH",
        "valid_until": expires.isoformat(),
        "next_check_at": now.isoformat(),
    }


def _restore_legacy_alerts_if_needed(client, now: datetime) -> int:
    """Recover the Alert Center rules archived during the platform cutover.

    Migration 014 archived and dropped the legacy table before its live rules were
    copied to alert_platform.alerts.  The cutover therefore left the new runtime
    source empty.  Recovery is idempotent and only restores still-valid ACTIVE or
    ERROR rules that do not already exist in the platform.
    """
    platform = client.schema("alert_platform").table("alerts")
    existing = (
        platform.select("id,market,ticker,alert_type,threshold,status")
        .limit(5000)
        .execute().data
        or []
    )
    active = [row for row in existing if str(row.get("status") or "").upper() == "ACTIVE"]
    if active:
        return 0

    try:
        archived = (
            client.table("trading_alerts_legacy_archive")
            .select("alert_id,ticker,market,condition_type,trigger_level,status,note,expires_at,updated_at")
            .in_("status", ["ACTIVE", "ERROR"])
            .order("updated_at", desc=True)
            .limit(5000)
            .execute().data
            or []
        )
    except Exception as exc:
        print(f"LEGACY_RECOVERY_WARNING {type(exc).__name__}: {exc}")
        return 0

    existing_by_key = {_legacy_key(row): row for row in existing}
    restored = 0
    seen: set[tuple[str, str, str, float | None]] = set()
    for legacy in archived:
        expires = _parse_dt(legacy.get("expires_at"))
        if expires is not None and expires <= now:
            continue
        key = _legacy_key(legacy)
        if not key[1] or key[2] not in {"PRICE_ABOVE", "PRICE_BELOW"} or key[3] is None or key in seen:
            continue
        seen.add(key)
        current = existing_by_key.get(key)
        payload = _legacy_to_platform_row(legacy, now)
        try:
            if current is None:
                platform.insert(payload).execute()
                restored += 1
            elif str(current.get("status") or "").upper() == "V3_FAILED":
                platform.update({
                    "status": "ACTIVE",
                    "valid_until": payload["valid_until"],
                    "next_check_at": payload["next_check_at"],
                    "updated_at": now.isoformat(),
                }).eq("id", current["id"]).execute()
                restored += 1
        except Exception as exc:
            print(f"LEGACY_PLATFORM_INSERT_BLOCKED {type(exc).__name__}: {exc}")
            break

    if restored:
        print(f"LEGACY_ALERTS_RESTORED count={restored}")
    return restored


def _load_legacy_runtime_alerts(client, now: datetime) -> list[dict]:
    """Read archived rules as an emergency runtime source until DB grants are fixed."""
    rows = (
        client.table("trading_alerts_legacy_archive")
        .select("alert_id,ticker,market,condition_type,trigger_level,status,note,expires_at,last_price,last_checked_at,created_at,updated_at")
        .in_("status", ["ACTIVE", "ERROR"])
        .order("updated_at", desc=True)
        .limit(5000)
        .execute().data
        or []
    )
    result: list[dict] = []
    seen: set[tuple[str, str, str, float | None]] = set()
    for row in rows:
        expires = _parse_dt(row.get("expires_at"))
        if expires is not None and expires <= now:
            continue
        key = _legacy_key(row)
        if not key[1] or key[2] not in {"PRICE_ABOVE", "PRICE_BELOW"} or key[3] is None or key in seen:
            continue
        seen.add(key)
        result.append({
            "id": str(row.get("alert_id") or ""),
            "ticker": key[1],
            "market": key[0],
            "alert_type": key[2],
            "threshold": key[3],
            "threshold_min": None,
            "threshold_max": None,
            "status": "ACTIVE",
            "valid_until": expires.isoformat() if expires else (now + timedelta(days=30)).isoformat(),
            "next_check_at": None,
            "last_price": row.get("last_price"),
            "last_price_at": row.get("last_checked_at"),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
            "_legacy": True,
        })
    print(f"LEGACY_RUNTIME_FALLBACK active={len(result)}")
    return result


def _persist_alert(client, platform_table, alert: dict, values: dict) -> None:
    alert_id = str(alert.get("id") or "")
    if not alert.get("_legacy"):
        platform_table.update(values).eq("id", alert_id).execute()
        return

    legacy_values: dict = {}
    if "status" in values:
        status = str(values["status"])
        legacy_values["status"] = "ERROR" if status == "V3_FAILED" else status
    if "last_price" in values:
        legacy_values["last_price"] = values["last_price"]
    if "last_price_at" in values:
        legacy_values["last_checked_at"] = values["last_price_at"]
    if "updated_at" in values:
        legacy_values["updated_at"] = values["updated_at"]
    if legacy_values:
        try:
            client.table("trading_alerts_legacy_archive").update(legacy_values).eq("alert_id", alert_id).execute()
        except Exception as exc:
            print(f"LEGACY_STATUS_WARNING {type(exc).__name__}: {exc}")


def _last_price(ticker: str, market: str) -> float:
    symbol = _yf_symbol(ticker, market)
    hist = yf.Ticker(symbol).history(period="1d", interval="1m", auto_adjust=False)
    if hist.empty:
        hist = yf.Ticker(symbol).history(period="5d", interval="1d", auto_adjust=False)
    if hist.empty:
        raise RuntimeError(f"Prezzo non disponibile per {symbol}")
    return float(hist["Close"].dropna().iloc[-1])


def _parse_dt(value) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def _num(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def _triggered(alert: dict, price: float) -> tuple[bool, str]:
    alert_type = str(alert.get("alert_type") or "").upper()
    threshold = _num(alert.get("threshold"))
    low = _num(alert.get("threshold_min"))
    high = _num(alert.get("threshold_max"))

    if alert_type == "PRICE_ABOVE":
        return (threshold is not None and price >= threshold, f">= {threshold}")
    if alert_type in {"PRICE_BELOW", "MAX_BUY"}:
        return (threshold is not None and price <= threshold, f"<= {threshold}")
    if alert_type == "ENTRY_ZONE":
        if low is None or high is None:
            return False, "ENTRY_ZONE incompleta"
        lo, hi = sorted((low, high))
        return lo <= price <= hi, f"tra {lo} e {hi}"
    return False, f"tipo non supportato: {alert_type or 'N/D'}"


def _message(alert: dict, price: float, condition: str) -> str:
    ticker = str(alert.get("ticker") or "").upper()
    market = str(alert.get("market") or "USA").upper()
    alert_type = str(alert.get("alert_type") or "N/D").upper()
    return "\n".join(
        [
            "🚨 ALERT CENTER",
            "",
            f"{ticker} | {market}",
            f"Tipo: {alert_type}",
            f"Condizione: {condition}",
            f"Prezzo rilevato: {price:.2f}",
            "Origine: ALERT_PLATFORM",
        ]
    )


def _recent_sent_for_alert(client, alert_id: str) -> bool:
    """Best-effort duplicate guard using notification_events payload."""
    try:
        rows = (
            client.table("notification_events")
            .select("status,channel,sent_at,payload")
            .eq("channel", "WHATSAPP")
            .eq("status", "SENT")
            .order("sent_at", desc=True)
            .limit(200)
            .execute().data
            or []
        )
    except Exception:
        return False

    cutoff = datetime.now(timezone.utc) - timedelta(hours=3)
    for row in rows:
        sent_at = _parse_dt(row.get("sent_at"))
        if sent_at is None or sent_at < cutoff:
            continue
        payload = row.get("payload") or {}
        if isinstance(payload, dict) and str(payload.get("alert_id") or "") == str(alert_id):
            return True
    return False


def _log_notification(client, alert: dict, price: float, condition: str, status: str, event_type: str) -> None:
    payload = {
        "source": "ALERT_PLATFORM",
        "alert_id": str(alert.get("id") or ""),
        "ticker": str(alert.get("ticker") or "").upper(),
        "market": str(alert.get("market") or "USA").upper(),
        "alert_type": str(alert.get("alert_type") or "").upper(),
        "threshold": alert.get("threshold"),
        "threshold_min": alert.get("threshold_min"),
        "threshold_max": alert.get("threshold_max"),
        "trigger_price": price,
        "condition": condition,
    }
    row = {
        "ticker": payload["ticker"],
        "event_type": event_type,
        "channel": "WHATSAPP",
        "status": status,
        "provider": "CALLMEBOT" if status == "SENT" else "DEDUP",
        "payload": payload,
    }
    if status == "SENT":
        row["sent_at"] = datetime.now(timezone.utc).isoformat()
    try:
        client.table("notification_events").insert(row).execute()
    except Exception as exc:
        print(f"NOTIFICATION_LOG_WARNING {type(exc).__name__}: {exc}")


def process_active_alerts() -> dict[str, int]:
    """Process alert_platform.alerts, the dashboard and runtime source of truth."""
    client = _client()
    now = datetime.now(timezone.utc)
    table = client.schema("alert_platform").table("alerts")

    restored = _restore_legacy_alerts_if_needed(client, now)

    rows = (
        table.select(
            "id,ticker,market,alert_type,threshold,threshold_min,threshold_max,status,"
            "valid_until,next_check_at,last_price,last_price_at,last_price_provider,created_at,updated_at"
        )
        .eq("status", "ACTIVE")
        .order("created_at")
        .limit(1000)
        .execute().data
        or []
    )
    if not rows:
        rows = _load_legacy_runtime_alerts(client, now)

    stats = {
        "active": len(rows),
        "checked": 0,
        "triggered": 0,
        "sent": 0,
        "suppressed": 0,
        "expired": 0,
        "not_due": 0,
        "skipped_session": 0,
        "errors": 0,
        "restored": restored,
    }

    for alert in rows:
        alert_id = str(alert.get("id") or "")
        ticker = str(alert.get("ticker") or "").upper()
        try:
            alert_type = str(alert.get("alert_type") or "").upper()
            if alert_type not in SUPPORTED_TYPES:
                _persist_alert(client, table, alert, {"status": "V3_FAILED", "updated_at": now.isoformat()})
                stats["errors"] += 1
                print(f"ALERT_UNSUPPORTED {ticker} type={alert_type}")
                continue

            valid_until = _parse_dt(alert.get("valid_until"))
            if valid_until is not None and valid_until <= now:
                _persist_alert(client, table, alert, {"status": "EXPIRED", "updated_at": now.isoformat()})
                stats["expired"] += 1
                continue

            next_check = _parse_dt(alert.get("next_check_at"))
            if next_check is not None and next_check > now:
                stats["not_due"] += 1
                continue

            market = str(alert.get("market") or "USA").upper()
            if not _market_session_open(market, now):
                stats["skipped_session"] += 1
                continue

            price = _last_price(ticker, market)
            stats["checked"] += 1
            next_check_at = (now + timedelta(minutes=25)).isoformat()
            _persist_alert(client, table, alert,
                {
                    "last_price": price,
                    "last_price_at": now.isoformat(),
                    "last_price_provider": "YFINANCE",
                    "next_check_at": next_check_at,
                    "updated_at": now.isoformat(),
                },
            )

            fired, condition = _triggered(alert, price)
            if not fired:
                continue

            stats["triggered"] += 1
            if _recent_sent_for_alert(client, alert_id):
                _persist_alert(client, table, alert, {"status": "TRIGGERED", "updated_at": now.isoformat()})
                _log_notification(client, alert, price, condition, "SKIPPED", "ALERT_DUPLICATE_SUPPRESSED")
                stats["suppressed"] += 1
                continue

            try:
                send_callmebot(_message(alert, price, condition))
            except Exception as exc:
                retry_at = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
                _persist_alert(client, table, alert, {
                    "status": "ACTIVE",
                    "next_check_at": retry_at,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                })
                stats["errors"] += 1
                print(f"ALERT_NOTIFICATION_RETRY {ticker} {type(exc).__name__}: {exc}")
                continue
            sent_at = datetime.now(timezone.utc).isoformat()
            _log_notification(client, alert, price, condition, "SENT", "ALERT_TRIGGERED")
            _persist_alert(client, table, alert,
                {
                    "status": "TRIGGERED",
                    "last_price": price,
                    "last_price_at": sent_at,
                    "last_price_provider": "YFINANCE",
                    "updated_at": sent_at,
                },
            )
            stats["sent"] += 1
            print(f"ALERT_SENT {ticker} type={alert_type} price={price:.4f}")
        except Exception as exc:
            stats["errors"] += 1
            print(f"ALERT_ERROR {ticker} id={alert_id} {type(exc).__name__}: {exc}")
            try:
                _persist_alert(client, table, alert, {
                    "status": "ACTIVE",
                    "next_check_at": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                })
            except Exception as update_exc:
                print(f"ALERT_ERROR_STATUS_UPDATE_FAILED {ticker} {type(update_exc).__name__}: {update_exc}")

    print("alert_center " + " ".join(f"{k}={v}" for k, v in stats.items()))
    return stats


if __name__ == "__main__":
    process_active_alerts()
