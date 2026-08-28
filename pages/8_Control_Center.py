from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd
import streamlit as st

from dashboard.data_access import lab_paper_positions, notifications, safe_table_rows, utc_label

st.set_page_config(page_title="Control Center", page_icon="📡", layout="wide")
st.title("📡 Control Center")
st.caption("Operational health: process heartbeat, notifications, alerts and Laboratory state. Read-only.")

EXPECTED_MAX_AGE_MIN = {
    "FINECO_BRIDGE": 25,
    "ALERT_CENTER": 20,
    "FAST_MONITOR_USA": 20,
    "FAST_MONITOR_ITALY": 20,
    "ORCHESTRATOR": 35,
    "MASTER_SCAN": 24 * 60,
    "LAB_PAPER": 4 * 60,
    "DYNAMIC_EXIT": 4 * 60,
}


def dt(value: Any):
    if not value:
        return None
    try:
        parsed = pd.to_datetime(value, utc=True)
        return parsed.to_pydatetime()
    except Exception:
        return None


def age_minutes(value: Any) -> float | None:
    parsed = dt(value)
    if parsed is None:
        return None
    return max(0.0, (datetime.now(timezone.utc) - parsed).total_seconds() / 60.0)


def health_status(row: dict) -> str:
    status = str(row.get("status") or "N/D").upper()
    if status == "RUNNING":
        return "🔵 RUNNING"
    if status in {"ERROR", "CANCELLED"}:
        return "🔴 ERROR" if status == "ERROR" else "🟠 CANCELLED"
    module = str(row.get("module") or "")
    age = age_minutes(row.get("finished_at") or row.get("started_at"))
    limit = EXPECTED_MAX_AGE_MIN.get(module)
    if status == "OK" and age is not None and limit is not None and age > limit:
        return "🟡 STALE"
    if status == "OK":
        return "✅ OK"
    if status == "SKIPPED":
        return "⚪ SKIPPED"
    return "⚪ N/D"


def latest_by_module(rows: list[dict]) -> list[dict]:
    ordered = sorted(rows, key=lambda r: str(r.get("started_at") or ""), reverse=True)
    seen = set()
    out = []
    for row in ordered:
        module = str(row.get("module") or "N/D")
        if module in seen:
            continue
        seen.add(module)
        item = dict(row)
        item["health"] = health_status(item)
        item["age_min"] = age_minutes(item.get("finished_at") or item.get("started_at"))
        item["expected_max_age_min"] = EXPECTED_MAX_AGE_MIN.get(module)
        out.append(item)
    return out


def get_runs() -> list[dict]:
    try:
        return safe_table_rows("system_run_log", order="started_at", limit=3000)
    except Exception:
        return []


def get_alerts() -> list[dict]:
    try:
        return safe_table_rows("trading_alerts", order="created_at", limit=3000)
    except Exception:
        return []


def get_paper() -> list[dict]:
    try:
        return lab_paper_positions(10000)
    except Exception:
        return []


def get_notifications() -> list[dict]:
    try:
        return notifications(3000)
    except Exception:
        return []


runs = get_runs()
latest = latest_by_module(runs)
notes = get_notifications()
alerts = get_alerts()
paper = get_paper()

sent = [x for x in notes if str(x.get("status") or "").upper() == "SENT"]
errors_24 = []
now = datetime.now(timezone.utc)
for x in notes:
    when = dt(x.get("attempted_at") or x.get("sent_at"))
    if when and (now - when).total_seconds() <= 86400 and str(x.get("status") or "").upper() == "ERROR":
        errors_24.append(x)

healthy = sum(1 for x in latest if x.get("health") == "✅ OK")
problem = sum(1 for x in latest if x.get("health") in {"🔴 ERROR", "🟡 STALE", "🟠 CANCELLED"})
open_paper = sum(1 for x in paper if str(x.get("status") or "").upper() in {"OPEN", "TP1_HIT"})
closed_paper = sum(1 for x in paper if str(x.get("status") or "").upper() == "CLOSED")

k = st.columns(8)
k[0].metric("Systems OK", f"{healthy}/{len(latest)}" if latest else "N/D")
k[1].metric("Problems", problem if latest else "N/D")
k[2].metric("Notifications SENT", len(sent))
k[3].metric("Errors 24h", len(errors_24))
k[4].metric("Active Alerts", sum(1 for x in alerts if str(x.get("status") or "").upper() == "ACTIVE"))
k[5].metric("Triggered Alerts", sum(1 for x in alerts if str(x.get("status") or "").upper() == "TRIGGERED"))
k[6].metric("Paper OPEN", open_paper)
k[7].metric("Paper CLOSED", closed_paper)

if latest and problem:
    st.error(f"SYSTEM HEALTH: ATTENTION · {problem} module/i richiedono controllo.")
elif latest:
    st.success("SYSTEM HEALTH: OK · tutti i moduli tracciati sono nei limiti configurati.")
else:
    st.warning("Heartbeat non ancora disponibile. Eseguire la migration 006 e attendere il primo run strumentato.")

overview, runs_tab, notify_tab, trading_tab = st.tabs(["🏠 Overview", "⚙️ Runs & Heartbeat", "📨 Notifications", "🧪 Trading Systems"])

with overview:
    st.subheader("Stato sistemi")
    if not latest:
        st.info("Nessun heartbeat registrato.")
    else:
        frame = pd.DataFrame(latest)
        frame["Ultimo run"] = frame.apply(lambda r: utc_label(r.get("finished_at") or r.get("started_at")), axis=1)
        frame["Età min"] = frame["age_min"].round(1)
        frame["Atteso max min"] = frame["expected_max_age_min"]
        frame["Processati"] = frame.get("processed_count", 0)
        frame["Azioni"] = frame.get("action_count", 0)
        frame["Inviati"] = frame.get("sent_count", 0)
        frame["Errori"] = frame.get("error_count", 0)
        show = frame.rename(columns={"module": "Modulo", "component": "Componente", "workflow": "Workflow", "health": "Stato"})
        wanted = ["Modulo", "Componente", "Workflow", "Ultimo run", "Stato", "Età min", "Atteso max min", "Processati", "Azioni", "Inviati", "Errori", "message"]
        st.dataframe(show[[c for c in wanted if c in show.columns]], hide_index=True, use_container_width=True)

    st.subheader("Ultime attività")
    timeline = []
    for r in runs[:20]:
        timeline.append({"Ora": utc_label(r.get("finished_at") or r.get("started_at")), "Tipo": "RUN", "Modulo": r.get("module"), "Stato": r.get("status"), "Dettaglio": r.get("message")})
    for n in notes[:20]:
        timeline.append({"Ora": utc_label(n.get("sent_at") or n.get("attempted_at")), "Tipo": "NOTIFY", "Modulo": n.get("event_type"), "Stato": n.get("status"), "Dettaglio": f"{n.get('ticker') or '-'} · {n.get('channel') or '-'} · {n.get('provider') or '-'}"})
    if timeline:
        timeline_df = pd.DataFrame(timeline).sort_values("Ora", ascending=False).head(30)
        st.dataframe(timeline_df, hide_index=True, use_container_width=True)

with runs_tab:
    st.subheader("Execution ledger")
    if not runs:
        st.info("Nessun run disponibile in system_run_log.")
    else:
        rf = pd.DataFrame(runs)
        for col in ("started_at", "finished_at"):
            if col in rf.columns:
                rf[col] = rf[col].map(utc_label)
        wanted = ["started_at", "finished_at", "module", "component", "workflow", "market", "status", "trigger_source", "github_run_id", "processed_count", "action_count", "sent_count", "skipped_count", "error_count", "message"]
        st.dataframe(rf[[c for c in wanted if c in rf.columns]], hide_index=True, use_container_width=True)

with notify_tab:
    st.subheader("Notification events")
    if not notes:
        st.info("Nessuna notifica registrata.")
    else:
        nf = pd.DataFrame(notes)
        for col in ("attempted_at", "sent_at"):
            if col in nf.columns:
                nf[col] = nf[col].map(utc_label)
        wanted = ["sent_at", "attempted_at", "ticker", "event_type", "channel", "status", "provider", "error_message", "payload"]
        st.dataframe(nf[[c for c in wanted if c in nf.columns]], hide_index=True, use_container_width=True)

with trading_tab:
    a, b = st.columns(2)
    with a:
        st.subheader("Alert Center")
        if alerts:
            af = pd.DataFrame(alerts)
            for col in ("last_checked_at", "triggered_at", "last_notification_at", "expires_at"):
                if col in af.columns:
                    af[col] = af[col].map(utc_label)
            wanted = ["ticker", "condition_type", "trigger_level", "last_price", "status", "source", "last_checked_at", "triggered_at", "last_notification_at"]
            st.dataframe(af[[c for c in wanted if c in af.columns]], hide_index=True, use_container_width=True)
        else:
            st.info("Nessun alert disponibile.")
    with b:
        st.subheader("Laboratory Paper")
        summary = pd.DataFrame([
            {"Voce": "Totale", "Valore": len(paper)},
            {"Voce": "OPEN / TP1_HIT", "Valore": open_paper},
            {"Voce": "CLOSED", "Valore": closed_paper},
            {"Voce": "Dynamic Exit", "Valore": sum(1 for p in paper if "DYNAMIC_EXIT_V1" in str(p.get("details") or ""))},
        ])
        st.dataframe(summary, hide_index=True, use_container_width=True)
        if paper:
            pf = pd.DataFrame(paper)
            wanted = ["symbol", "strategy", "status", "fill_price", "last_price", "stop_current", "tp1", "tp2", "opened_at", "closed_at", "exit_reason"]
            st.dataframe(pf[[c for c in wanted if c in pf.columns]], hide_index=True, use_container_width=True)

st.caption(f"Updated: {datetime.now().astimezone().strftime('%d/%m/%Y %H:%M:%S %Z')}")
