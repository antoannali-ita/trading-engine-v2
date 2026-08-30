from __future__ import annotations

from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

from notifications.email_client import send_email
from notifications.whatsapp_client import send_whatsapp


SLOTS = {
    "ITALY": {
        "timezone": "Europe/Rome",
        "open": time(9, 0),
        "close": time(17, 30),
        "hours": {9, 13, 17},
        "minute": 10,
    },
    "USA": {
        "timezone": "America/New_York",
        "open": time(9, 30),
        "close": time(16, 0),
        "hours": {9, 13},
        "minute": 40,
    },
}


def _due_and_open(market: str, now: datetime) -> tuple[bool, datetime]:
    slot = SLOTS[market]
    local = now.astimezone(ZoneInfo(slot["timezone"]))
    clock = local.time().replace(tzinfo=None)
    weekday = local.weekday() < 5
    due = weekday and local.hour in slot["hours"] and slot["minute"] <= local.minute < slot["minute"] + 10
    opened = weekday and slot["open"] <= clock <= slot["close"]
    return bool(due and opened), local


def _html(market: str, local: datetime) -> str:
    return f"""
    <div style="background:#07131d;padding:22px;font-family:Arial,Helvetica,sans-serif">
      <div style="max-width:680px;margin:auto;background:#0b1d2a;border:1px solid #173b52;border-radius:10px;padding:18px;color:#dbe7f0">
        <div style="font-size:18px;font-weight:800;color:#67b2ff;margin-bottom:14px">Trading Engine V2 · Initial Monitoring</div>
        <div style="padding:5px 0"><b>SOURCE:</b> trading-engine-v2</div>
        <div style="padding:5px 0"><b>MARKET:</b> {market}</div>
        <div style="padding:5px 0"><b>SESSION:</b> OPEN</div>
        <div style="padding:5px 0"><b>LOCAL TIME:</b> {local.strftime('%d/%m/%Y %H:%M %Z')}</div>
        <div style="margin-top:14px;padding-top:12px;border-top:1px solid #173b52">✅ Mail channel: heartbeat operativo<br>✅ WhatsApp channel: heartbeat operativo</div>
        <div style="margin-top:14px;font-size:11px;color:#8297a7">V2 · fase iniziale di verifica · nessun ordine automatico.</div>
      </div>
    </div>
    """


def run() -> dict[str, bool]:
    now = datetime.now(timezone.utc)
    sent: dict[str, bool] = {}
    for market in ("ITALY", "USA"):
        due, local = _due_and_open(market, now)
        if not due:
            continue

        subject = f"[V2 HEARTBEAT][{market}] Initial monitoring"
        whatsapp = (
            "🔔 TRADING ENGINE V2 · INITIAL MONITORING\n\n"
            "SOURCE: trading-engine-v2\n"
            f"MARKET: {market}\n"
            "SESSION: OPEN\n"
            f"LOCAL TIME: {local.strftime('%d/%m/%Y %H:%M %Z')}\n\n"
            "✅ Mail channel: heartbeat operativo\n"
            "✅ WhatsApp channel: heartbeat operativo\n"
            "ℹ️ Fase iniziale di verifica · nessun ordine automatico."
        )
        email_ok = bool(send_email(subject, _html(market, local), is_html=True))
        whatsapp_ok = bool(send_whatsapp(whatsapp))
        sent[market] = email_ok and whatsapp_ok
        print(f"V2_HEARTBEAT market={market} local={local.isoformat()} email={email_ok} whatsapp={whatsapp_ok}")

    if not sent:
        print("V2_HEARTBEAT no_due_slot")
    return sent


if __name__ == "__main__":
    run()
