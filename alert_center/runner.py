from __future__ import annotations

import os
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

import yfinance as yf
from supabase import create_client

from alert_center.engine import evaluate_alert, is_equivalent_recent_notification
from fineco_alert_bridge.whatsapp import send_callmebot


MARKET_HOURS = {
    "ITALY": {"timezone": "Europe/Rome", "open": time(9, 0), "close": time(17, 30)},
    "USA": {"timezone": "America/New_York", "open": time(9, 30), "close": time(16, 0)},
}


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
    if market.upper() == "ITALY" and not ticker.endswith(".MI"):
        return f"{ticker}.MI"
    return ticker


def _last_price(ticker: str, market: str) -> float:
    symbol = _yf_symbol(ticker, market)
    hist = yf.Ticker(symbol).history(period="1d", interval="1m", auto_adjust=False)
    if hist.empty:
        hist = yf.Ticker(symbol).history(period="5d", interval="1d", auto_adjust=False)
    if hist.empty:
        raise RuntimeError(f"Prezzo non disponibile per {symbol}")
    return float(hist["Close"].dropna().iloc[-1])


def _recent_notifications(client, ticker: str) -> list[dict]:
    return (
        client.table("notification_events")
        .select("ticker,event_type,channel,attempted_at,sent_at,status,payload")
        .eq("ticker", ticker.upper())
        .order("attempted_at", desc=True)
        .limit(200)
        .execute().data
        or []
    )


def _notification_payload(alert: dict, price: float, source: str) -> dict:
    return {
        "source": source,
        "alert_id": alert.get("alert_id"),
        "ticker": alert.get("ticker"),
        "market": alert.get("market"),
        "condition_type": alert.get("condition_type"),
        "trigger_level": float(alert.get("trigger_level")),
        "trigger_price": price,
        "note": alert.get("note"),
    }


def _message(alert: dict, price: float) -> str:
    op = ">=" if alert.get("condition_type") == "PRICE_ABOVE" else "<="
    note = str(alert.get("note") or "").strip()
    lines = [
        "🚨 ALERT CENTER",
        "",
        f"{str(alert.get('ticker') or '').upper()} | {str(alert.get('market') or '').upper()}",
        f"Condizione: prezzo {op} {float(alert.get('trigger_level')):.2f}",
        f"Prezzo rilevato: {price:.2f}",
        f"Origine: {str(alert.get('source') or 'MANUAL').upper()}",
    ]
    if note:
        lines.append(f"Nota: {note}")
    return "\n".join(lines)


def process_active_alerts() -> dict[str, int]:
    client = _client()
    now = datetime.now(timezone.utc)
    rows = (
        client.table("trading_alerts")
        .select("*")
        .eq("status", "ACTIVE")
        .order("created_at")
        .limit(1000)
        .execute().data
        or []
    )

    stats = {"active": len(rows), "checked": 0, "triggered": 0, "sent": 0, "suppressed": 0, "expired": 0, "skipped_session": 0, "errors": 0}

    for alert in rows:
        alert_id = alert["alert_id"]
        try:
            expires_at = alert.get("expires_at")
            if expires_at:
                expiry = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
                if expiry.tzinfo is None:
                    expiry = expiry.replace(tzinfo=timezone.utc)
                if expiry <= now:
                    client.table("trading_alerts").update({"status": "EXPIRED", "last_checked_at": now.isoformat()}).eq("alert_id", alert_id).execute()
                    stats["expired"] += 1
                    continue

            market = str(alert.get("market") or "USA").upper()
            if not _market_session_open(market, now):
                stats["skipped_session"] += 1
                continue

            price = _last_price(str(alert["ticker"]), market)
            stats["checked"] += 1
            decision = evaluate_alert(alert["condition_type"], alert["trigger_level"], price)
            client.table("trading_alerts").update({"last_price": price, "last_checked_at": now.isoformat()}).eq("alert_id", alert_id).execute()
            if not decision.triggered:
                continue

            stats["triggered"] += 1
            recent = _recent_notifications(client, str(alert["ticker"]))
            payload = _notification_payload(alert, price, "ALERT_CENTER")
            if is_equivalent_recent_notification(alert, recent, now=now):
                client.table("notification_events").insert({
                    "ticker": str(alert["ticker"]).upper(),
                    "event_type": "ALERT_DUPLICATE_SUPPRESSED",
                    "channel": "WHATSAPP",
                    "status": "SKIPPED",
                    "provider": "DEDUP",
                    "payload": payload,
                }).execute()
                client.table("trading_alerts").update({
                    "status": "TRIGGERED" if not alert.get("repeatable") else "ACTIVE",
                    "triggered_at": now.isoformat(),
                }).eq("alert_id", alert_id).execute()
                stats["suppressed"] += 1
                continue

            send_callmebot(_message(alert, price))
            sent_at = datetime.now(timezone.utc).isoformat()
            client.table("notification_events").insert({
                "ticker": str(alert["ticker"]).upper(),
                "event_type": "ALERT_TRIGGERED",
                "channel": "WHATSAPP",
                "sent_at": sent_at,
                "status": "SENT",
                "provider": "CALLMEBOT",
                "payload": payload,
            }).execute()
            client.table("trading_alerts").update({
                "status": "TRIGGERED" if not alert.get("repeatable") else "ACTIVE",
                "triggered_at": sent_at,
                "last_notification_at": sent_at,
            }).eq("alert_id", alert_id).execute()
            stats["sent"] += 1
        except Exception as exc:
            stats["errors"] += 1
            client.table("trading_alerts").update({
                "status": "ERROR",
                "last_checked_at": now.isoformat(),
                "metadata": {**(alert.get("metadata") or {}), "last_error": f"{type(exc).__name__}: {exc}"},
            }).eq("alert_id", alert_id).execute()
            print(f"ALERT_ERROR {alert.get('ticker')} {type(exc).__name__}: {exc}")

    print("alert_center " + " ".join(f"{k}={v}" for k, v in stats.items()))
    return stats


if __name__ == "__main__":
    process_active_alerts()
