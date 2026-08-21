from __future__ import annotations

from datetime import datetime, timedelta, timezone

from notifications.email_client import send_email
from notifications.whatsapp_client import send_whatsapp
from orchestrator.persistence import client
from orchestrator.runtime import record_notification


def _parse_ts(value):
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _already_notified(db, signal_id: str, channel: str) -> bool:
    rows = (
        db.table("notification_events")
        .select("notification_id")
        .eq("signal_id", signal_id)
        .eq("event_type", "FINAL_DECISION")
        .eq("channel", channel)
        .eq("status", "SENT")
        .limit(1)
        .execute()
        .data
        or []
    )
    return bool(rows)


def _matching_confluence(ai: dict, confluences: list[dict]) -> dict | None:
    source_signal_id = str(ai.get("source_signal_id") or "").strip()
    ticker = str(ai.get("ticker") or "").upper()
    market = str(ai.get("market") or "").upper()

    if source_signal_id:
        for row in confluences:
            if str(row.get("signal_id") or "") == source_signal_id:
                return row
        # Backward compatibility for AI rows created before confluence ids became the source id.
        for row in confluences:
            metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
            if source_signal_id in set(metadata.get("source_signal_ids") or []):
                return row

    matches = [
        row for row in confluences
        if str(row.get("ticker") or "").upper() == ticker
        and str(row.get("market") or "").upper() == market
    ]
    if not matches:
        return None
    matches.sort(key=lambda row: _parse_ts(row.get("detected_at")) or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return matches[0]


def _render(confluence: dict, ai: dict) -> tuple[str, str, str]:
    level = str(confluence.get("decision") or confluence.get("signal_type") or "SIGNAL")
    alignment = str(ai.get("alignment") or "NEUTRAL")
    ticker = str(confluence.get("ticker") or ai.get("ticker") or "")
    market = str(confluence.get("market") or ai.get("market") or "")
    score = confluence.get("conviction") or confluence.get("score_total")
    final = "CONFIRMED" if alignment == "CONFIRM" else alignment
    subject = f"[ORCHESTRATOR][{market}] {ticker} | {level} | {final}"
    summary = str(ai.get("summary") or ai.get("verdict") or "").strip()
    body = (
        f"<h2>{ticker} — {final}</h2>"
        f"<p><strong>Mercato:</strong> {market}<br>"
        f"<strong>Confluenza motori:</strong> {level}<br>"
        f"<strong>Score:</strong> {score if score is not None else 'n/d'}<br>"
        f"<strong>TradingAgents:</strong> {alignment}</p>"
        f"<p>{summary}</p>"
        "<hr><small>Fonte: trading-engine-v2 orchestrator. Nessun ordine automatico.</small>"
    )
    whatsapp = f"{ticker} {market}\n{level}\nTradingAgents: {alignment}\nFinale: {final}"
    return subject, body, whatsapp


def send_qualified_notifications(hours: int = 24) -> dict[str, int]:
    db = client()
    if db is None:
        return {"email": 0, "whatsapp": 0}
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    analyses = (
        db.table("ai_analysis")
        .select("*")
        .eq("status", "SUCCESS")
        .gte("completed_at", cutoff)
        .order("completed_at", desc=True)
        .limit(100)
        .execute()
        .data
        or []
    )
    confluences = (
        db.table("signals")
        .select("*")
        .eq("engine", "ORCHESTRATOR")
        .eq("is_actionable", True)
        .gte("detected_at", cutoff)
        .order("detected_at", desc=True)
        .limit(300)
        .execute()
        .data
        or []
    )
    stats = {"email": 0, "whatsapp": 0}
    for ai in analyses:
        signal = _matching_confluence(ai, confluences)
        if not signal:
            continue
        signal_id = signal.get("signal_id")
        ticker = str(signal.get("ticker") or ai.get("ticker") or "").upper()
        if not signal_id:
            continue
        subject, html, wa_text = _render(signal, ai)
        if not _already_notified(db, signal_id, "EMAIL"):
            sent = bool(send_email(subject, html, is_html=True))
            record_notification(run_id=signal.get("run_id"), signal_id=signal_id, ticker=ticker, event_type="FINAL_DECISION", channel="EMAIL", status="SENT" if sent else "FAILED", provider="GMAIL", payload={"analysis_id": ai.get("analysis_id"), "alignment": ai.get("alignment")})
            stats["email"] += int(sent)
        if not _already_notified(db, signal_id, "WHATSAPP"):
            sent = bool(send_whatsapp(wa_text))
            record_notification(run_id=signal.get("run_id"), signal_id=signal_id, ticker=ticker, event_type="FINAL_DECISION", channel="WHATSAPP", status="SENT" if sent else "FAILED", provider="CALLMEBOT", payload={"analysis_id": ai.get("analysis_id"), "alignment": ai.get("alignment")})
            stats["whatsapp"] += int(sent)
    return stats
