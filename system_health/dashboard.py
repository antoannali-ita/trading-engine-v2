from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd
import streamlit as st

from dashboard.data_access import lab_paper_positions, notifications, safe_table_rows, utc_label

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


def _dt(value: Any):
    if not value:
        return None
    try:
        return pd.to_datetime(value, utc=True).to_pydatetime()
    except Exception:
        return None


def _age_minutes(value: Any) -> float | None:
    parsed = _dt(value)
    if parsed is None:
        return None
    return max(0.0, (datetime.now(timezone.utc) - parsed).total_seconds() / 60.0)


def _health_status(row: dict) -> str:
    status = str(row.get("status") or "N/D").upper()
    if status == "RUNNING":
        return "🔵 RUNNING"
    if status == "ERROR":
        return "🔴 ERROR"
    if status == "CANCELLED":
        return "🟠 CANCELLED"
    if status == "SKIPPED":
        return "⚪ SKIPPED"

    module = str(row.get("module") or "")
    age = _age_minutes(row.get("finished_at") or row.get("started_at"))
    limit = EXPECTED_MAX_AGE_MIN.get(module)
    if status == "OK" and age is not None and limit is not None and age > limit:
        return "🟡 STALE"
    if status == "OK":
        return "✅ OK"
    return "⚪ N/D"


def _runs() -> list[dict]:
    try:
        return safe_table_rows("system_run_log", order="started_at", limit=3000)
    except Exception:
        return []


def _latest_by_module(rows: list[dict]) -> list[dict]:
    ordered = sorted(rows, key=lambda r: str(r.get("started_at") or ""), reverse=True)
    seen: set[str] = set()
    out: list[dict] = []
    for row in ordered:
        module = str(row.get("module") or "N/D")
        if module in seen:
            continue
        seen.add(module)
        item = dict(row)
        item["health"] = _health_status(item)
        item["age_min"] = _age_minutes(item.get("finished_at") or item.get("started_at"))
        item["expected_max_age_min"] = EXPECTED_MAX_AGE_MIN.get(module)
        out.append(item)
    return out


def render_system_status() -> None:
    runs = _runs()
    latest = _latest_by_module(runs)
    try:
        notes = notifications(3000)
    except Exception:
        notes = []
    try:
        paper = lab_paper_positions(10000)
    except Exception:
        paper = []

    now = datetime.now(timezone.utc)
    sent = [x for x in notes if str(x.get("status") or "").upper() == "SENT"]
    errors_24 = []
    for item in notes:
        when = _dt(item.get("attempted_at") or item.get("sent_at"))
        if when and (now - when).total_seconds() <= 86400 and str(item.get("status") or "").upper() == "ERROR":
            errors_24.append(item)

    healthy = sum(1 for x in latest if x.get("health") == "✅ OK")
    problems = sum(1 for x in latest if x.get("health") in {"🔴 ERROR", "🟡 STALE", "🟠 CANCELLED"})
    open_paper = sum(1 for x in paper if str(x.get("status") or "").upper() in {"OPEN", "TP1_HIT"})
    closed_paper = sum(1 for x in paper if str(x.get("status") or "").upper() == "CLOSED")

    st.subheader("📡 Stato generale sistemi")
    k = st.columns(6)
    k[0].metric("Sistemi OK", f"{healthy}/{len(latest)}" if latest else "N/D")
    k[1].metric("Problemi", problems if latest else "N/D")
    k[2].metric("Notifiche SENT", len(sent))
    k[3].metric("Errori 24h", len(errors_24))
    k[4].metric("Paper OPEN", open_paper)
    k[5].metric("Paper CLOSED", closed_paper)

    if latest and problems:
        st.error(f"SYSTEM HEALTH: ATTENTION · {problems} modulo/i richiedono controllo.")
    elif latest:
        st.success("SYSTEM HEALTH: OK · tutti i moduli tracciati sono nei limiti configurati.")
    else:
        st.warning("Nessun heartbeat registrato in system_run_log. I dati compariranno dopo il primo run strumentato.")

    if latest:
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

    st.subheader("🕒 Ultime attività")
    timeline = []
    for row in runs[:20]:
        timeline.append({
            "Ora": utc_label(row.get("finished_at") or row.get("started_at")),
            "Tipo": "RUN",
            "Modulo": row.get("module"),
            "Stato": row.get("status"),
            "Dettaglio": row.get("message"),
        })
    for item in notes[:20]:
        timeline.append({
            "Ora": utc_label(item.get("sent_at") or item.get("attempted_at")),
            "Tipo": "NOTIFY",
            "Modulo": item.get("event_type"),
            "Stato": item.get("status"),
            "Dettaglio": f"{item.get('ticker') or '-'} · {item.get('channel') or '-'} · {item.get('provider') or '-'}",
        })
    if timeline:
        st.dataframe(pd.DataFrame(timeline).sort_values("Ora", ascending=False).head(30), hide_index=True, use_container_width=True)

    st.caption(f"Aggiornato: {datetime.now().astimezone().strftime('%d/%m/%Y %H:%M:%S %Z')}")


def render_run_ledger() -> None:
    runs = _runs()
    st.subheader("⚙️ Run & Heartbeat")
    st.caption("Registro operativo dei processi. Serve a distinguere 'non ha inviato nulla' da 'non ha proprio girato'.")
    if not runs:
        st.info("Nessun run disponibile in system_run_log.")
        return

    frame = pd.DataFrame(runs)
    for col in ("started_at", "finished_at"):
        if col in frame.columns:
            frame[col] = frame[col].map(utc_label)
    wanted = [
        "started_at", "finished_at", "module", "component", "workflow", "market", "status",
        "trigger_source", "github_run_id", "processed_count", "action_count", "sent_count",
        "skipped_count", "error_count", "message",
    ]
    st.dataframe(frame[[c for c in wanted if c in frame.columns]], hide_index=True, use_container_width=True)
