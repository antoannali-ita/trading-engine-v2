from __future__ import annotations

import os
from datetime import datetime

import pandas as pd
import streamlit as st

from dashboard.data_access import (
    ai_analysis,
    engine_health,
    latest_confluence,
    manual_requests,
    notifications,
    performance,
    performance_summary,
    request_run,
    runs,
    signals,
    utc_label,
)

st.set_page_config(page_title="Trading Engine Control Center", page_icon="📈", layout="wide")


def require_access() -> None:
    expected = (os.getenv("DASHBOARD_PASSWORD") or "").strip()
    if not expected:
        return
    if st.session_state.get("dashboard_auth"):
        return
    st.title("Trading Engine Control Center")
    pwd = st.text_input("Password", type="password")
    if st.button("Accedi", type="primary"):
        if pwd == expected:
            st.session_state["dashboard_auth"] = True
            st.rerun()
        st.error("Password non valida")
    st.stop()


def as_df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def badge(value: str | None) -> str:
    v = str(value or "UNKNOWN").upper()
    icon = {
        "HEALTHY": "🟢", "SUCCESS": "🟢", "SENT": "🟢", "CONFIRM": "🟢",
        "RUNNING": "🔵", "PENDING": "🟡", "REQUESTED": "🟡", "DISPATCHED": "🔵",
        "DEGRADED": "🟠", "CAUTION": "🟠", "NEUTRAL": "⚪", "STALE": "🟠",
        "FAILED": "🔴", "VETO": "🔴", "DISABLED": "⚫",
    }.get(v, "⚪")
    return f"{icon} {v}"


@st.cache_data(ttl=30, show_spinner=False)
def load_snapshot() -> dict:
    return {
        "health": engine_health(),
        "signals": signals(1200),
        "confluence": latest_confluence(300),
        "runs": runs(600),
        "ai": ai_analysis(400),
        "notifications": notifications(600),
        "performance": performance(1200),
        "performance_summary": performance_summary(),
        "requests": manual_requests(250),
        "loaded_at": datetime.now().isoformat(timespec="seconds"),
    }


def decision_board(conf_df: pd.DataFrame, ai_df: pd.DataFrame) -> pd.DataFrame:
    if conf_df.empty:
        return pd.DataFrame()
    view = conf_df.copy()
    if not ai_df.empty and {"ticker", "market"}.issubset(ai_df.columns):
        ai = ai_df.copy()
        ai = ai.sort_values("started_at", ascending=False) if "started_at" in ai.columns else ai
        ai = ai.drop_duplicates(subset=["market", "ticker"], keep="first")
        keep = [c for c in ["market", "ticker", "status", "alignment", "confidence", "verdict", "summary", "completed_at"] if c in ai.columns]
        ai = ai[keep].rename(columns={
            "status": "ai_status", "alignment": "ai_alignment", "confidence": "ai_confidence",
            "verdict": "ai_verdict", "summary": "ai_summary", "completed_at": "ai_completed_at",
        })
        view = view.merge(ai, on=["market", "ticker"], how="left")
    return view


require_access()

head_l, head_r = st.columns([5, 1])
with head_l:
    st.title("Trading Engine Control Center")
    st.caption("CORE + FAST + Multi-Horizon + TradingAgents + Orchestrator | Supabase come memoria centrale")
with head_r:
    if st.button("↻ Aggiorna dati", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

try:
    snap = load_snapshot()
except Exception as exc:
    st.error(f"Connessione dati non disponibile: {type(exc).__name__}: {exc}")
    st.stop()

health_rows = snap["health"]
sig_rows = snap["signals"]
conf_rows = snap["confluence"]
run_rows = snap["runs"]
ai_rows = snap["ai"]
notif_rows = snap["notifications"]
perf_rows = snap["performance"]
perf_summary_rows = snap["performance_summary"]
request_rows = snap["requests"]

health_df = as_df(health_rows)
sig_df = as_df(sig_rows)
conf_df = as_df(conf_rows)
run_df = as_df(run_rows)
ai_df = as_df(ai_rows)
notif_df = as_df(notif_rows)
perf_df = as_df(perf_rows)
perf_summary_df = as_df(perf_summary_rows)
request_df = as_df(request_rows)
decision_df = decision_board(conf_df, ai_df)

healthy = sum(str(r.get("computed_health") or r.get("registry_status") or "").upper() == "HEALTHY" for r in health_rows)
failed = sum(str(r.get("computed_health") or r.get("registry_status") or "").upper() in {"FAILED", "STALE", "DEGRADED"} for r in health_rows)
actionable = sum(bool(r.get("is_actionable")) for r in conf_rows)
ai_pending = sum(str(r.get("status") or "").upper() in {"PENDING", "RUNNING"} for r in ai_rows)

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Motori healthy", f"{healthy}/{len(health_rows)}")
c2.metric("Motori da verificare", failed)
c3.metric("Confluenze actionable", actionable)
c4.metric("AI in lavorazione", ai_pending)
c5.metric("Richieste manuali", sum(str(r.get("status") or "") in {"REQUESTED", "DISPATCHED", "RUNNING"} for r in request_rows))

pages = st.tabs([
    "Overview", "Decisioni", "Motori", "Segnali", "TradingAgents", "Run & Log",
    "Esegui ora", "Performance", "Notifiche", "Architettura"
])

with pages[0]:
    st.subheader("Situazione generale")
    if not health_df.empty:
        view = health_df.copy()
        status_col = "computed_health" if "computed_health" in view.columns else "registry_status"
        view["stato"] = view[status_col].map(badge)
        for col in ["last_started_at", "last_finished_at", "last_run_at", "next_expected_run_at"]:
            if col in view.columns:
                view[col] = view[col].map(utc_label)
        cols = [c for c in ["engine_id", "strategy", "market", "horizon", "stato", "last_started_at", "last_finished_at", "signals_found"] if c in view.columns]
        st.dataframe(view[cols], use_container_width=True, hide_index=True)

    left, right = st.columns(2)
    with left:
        st.subheader("Confluenze più recenti")
        if not conf_df.empty:
            cols = [c for c in ["detected_at", "market", "ticker", "signal_type", "conviction", "is_actionable"] if c in conf_df.columns]
            st.dataframe(conf_df[cols].head(25), use_container_width=True, hide_index=True)
        else:
            st.info("Nessuna confluenza registrata ancora.")
    with right:
        st.subheader("Run per motore")
        if not run_df.empty and "engine_id" in run_df.columns:
            st.bar_chart(run_df.groupby("engine_id").size().sort_values(ascending=False))

with pages[1]:
    st.subheader("Decision Board")
    st.caption("Vista unificata: confluence dei motori + ultimo giudizio TradingAgents.")
    if decision_df.empty:
        st.info("Nessuna decisione aggregata disponibile.")
    else:
        only_action = st.checkbox("Solo decisioni actionable", value=True, key="decision_action")
        view = decision_df.copy()
        if only_action and "is_actionable" in view.columns:
            view = view[view["is_actionable"] == True]
        if "ai_alignment" in view.columns:
            view["AI"] = view["ai_alignment"].map(badge)
        cols = [c for c in ["detected_at", "market", "ticker", "signal_type", "conviction", "is_actionable", "AI", "ai_confidence", "ai_verdict", "ai_summary"] if c in view.columns]
        st.dataframe(view[cols].head(100), use_container_width=True, hide_index=True)

with pages[2]:
    st.subheader("Motori e scheduler")
    if health_df.empty:
        st.info("Registry vuoto.")
    else:
        view = health_df.copy()
        status_col = "computed_health" if "computed_health" in view.columns else "registry_status"
        view[status_col] = view[status_col].map(badge)
        for col in ["last_run_at", "last_started_at", "last_finished_at", "next_expected_run_at"]:
            if col in view.columns:
                view[col] = view[col].map(utc_label)
        st.dataframe(view, use_container_width=True, hide_index=True)
    st.markdown("""
    **Ruoli:** CORE seleziona il medio periodo; FAST sorveglia le zone operative; Multi-Horizon verifica più orizzonti; TradingAgents è una seconda opinione AI; ORCHESTRATOR unisce i risultati, evita duplicati, attiva i livelli successivi e centralizza gli alert.
    """)

with pages[3]:
    st.subheader("Segnali")
    if sig_df.empty:
        st.info("Nessun segnale registrato.")
    else:
        filters = st.columns(4)
        market_values = ["TUTTI"] + sorted(sig_df["market"].dropna().astype(str).unique().tolist()) if "market" in sig_df.columns else ["TUTTI"]
        engine_values = ["TUTTI"] + sorted(sig_df["engine"].dropna().astype(str).unique().tolist()) if "engine" in sig_df.columns else ["TUTTI"]
        m = filters[0].selectbox("Mercato", market_values)
        e = filters[1].selectbox("Engine", engine_values)
        ticker = filters[2].text_input("Ticker contiene").strip().upper()
        only_action = filters[3].checkbox("Solo actionable")
        view = sig_df.copy()
        if m != "TUTTI": view = view[view["market"].astype(str) == m]
        if e != "TUTTI": view = view[view["engine"].astype(str) == e]
        if ticker and "ticker" in view.columns: view = view[view["ticker"].astype(str).str.upper().str.contains(ticker, regex=False)]
        if only_action and "is_actionable" in view.columns: view = view[view["is_actionable"] == True]
        cols = [c for c in ["detected_at", "market", "ticker", "engine", "strategy", "signal_type", "decision", "conviction", "price", "entry", "stop", "tp1", "tp2", "is_actionable"] if c in view.columns]
        st.dataframe(view[cols].head(300), use_container_width=True, hide_index=True)
        if "signal_type" in view.columns and not view.empty:
            st.bar_chart(view["signal_type"].fillna("UNKNOWN").value_counts())

with pages[4]:
    st.subheader("TradingAgents")
    if ai_df.empty:
        st.info("Nessuna analisi AI registrata.")
    else:
        cols = [c for c in ["started_at", "completed_at", "market", "ticker", "status", "alignment", "confidence", "verdict", "summary", "trigger_reason", "entry", "stop", "tp1", "tp2", "error_message"] if c in ai_df.columns]
        st.dataframe(ai_df[cols].head(200), use_container_width=True, hide_index=True)
        if "alignment" in ai_df.columns:
            st.bar_chart(ai_df["alignment"].fillna("PENDING").value_counts())

with pages[5]:
    st.subheader("Run motori")
    if not run_df.empty:
        cols = [c for c in ["started_at", "finished_at", "engine_id", "market", "strategy", "trigger_source", "status", "duration_seconds", "records_processed", "signals_found", "error_message"] if c in run_df.columns]
        st.dataframe(run_df[cols].head(300), use_container_width=True, hide_index=True)
    st.subheader("Richieste manuali")
    if not request_df.empty:
        cols = [c for c in ["requested_at", "engine_id", "market", "strategy", "requested_by", "status", "github_run_id", "run_id", "completed_at", "error_message"] if c in request_df.columns]
        st.dataframe(request_df[cols].head(200), use_container_width=True, hide_index=True)

with pages[6]:
    st.subheader("Esecuzione manuale")
    st.warning("Il browser inserisce una richiesta su Supabase. L'Orchestrator la prende in carico e lancia il workflow GitHub corretto; nessun token GitHub viene esposto al client.")
    engines = [r for r in health_rows if str(r.get("engine_id") or "").upper() not in {"ORCHESTRATOR", "TRADINGAGENTS"}]
    labels = [f"{r.get('engine_id')} | {r.get('strategy')} | {r.get('market')}" for r in engines]
    selected_label = st.selectbox("Motore", labels) if labels else None
    send_email = st.checkbox("Email finale", value=True)
    send_wa = st.checkbox("WhatsApp finale", value=False)
    requested_by = st.text_input("Richiesto da", value="Antonio")
    if st.button("ESEGUI ORA", type="primary", disabled=not selected_label):
        idx = labels.index(selected_label)
        row = engines[idx]
        created = request_run(str(row.get("engine_id")), str(row.get("market")), str(row.get("strategy") or ""), send_email=send_email, send_whatsapp=send_wa, requested_by=requested_by)
        st.cache_data.clear()
        st.success(f"Richiesta creata: {created.get('request_id', 'OK')} - stato REQUESTED")

with pages[7]:
    st.subheader("Performance delle strategie")
    if not perf_summary_df.empty:
        st.caption("Statistiche aggregate per strategia, mercato e orizzonte.")
        st.dataframe(perf_summary_df, use_container_width=True, hide_index=True)
        if {"strategy", "avg_pnl_pct"}.issubset(perf_summary_df.columns):
            chart = perf_summary_df.copy()
            chart["avg_pnl_pct"] = pd.to_numeric(chart["avg_pnl_pct"], errors="coerce")
            st.bar_chart(chart.groupby("strategy")["avg_pnl_pct"].mean().dropna())
    elif perf_df.empty:
        st.info("I dati compariranno dopo l'esecuzione del performance worker.")
    if not perf_df.empty:
        cols = [c for c in ["created_at", "engine_id", "strategy", "market", "ticker", "outcome", "entry_price", "exit_price", "pnl_pct", "max_drawdown_pct", "max_favorable_excursion_pct", "holding_minutes"] if c in perf_df.columns]
        st.dataframe(perf_df[cols].head(400), use_container_width=True, hide_index=True)

with pages[8]:
    st.subheader("Notifiche")
    if notif_df.empty:
        st.info("Nessuna notifica registrata.")
    else:
        cols = [c for c in ["attempted_at", "sent_at", "ticker", "event_type", "channel", "status", "provider", "error_message"] if c in notif_df.columns]
        st.dataframe(notif_df[cols].head(400), use_container_width=True, hide_index=True)
        if {"channel", "status"}.issubset(notif_df.columns):
            st.bar_chart(notif_df.groupby(["channel", "status"]).size().unstack(fill_value=0))

with pages[9]:
    st.subheader("Architettura logica")
    st.graphviz_chart('''
    digraph TradingEngine {
      rankdir=LR;
      node [shape=box, style="rounded"];
      core [label="CORE 3-6M\nTrading Engine V2"];
      fast [label="FAST Monitor\nTrading Engine V2"];
      db [label="Supabase\nSignals / Runs / AI / Events / Performance", shape=cylinder];
      orch [label="ORCHESTRATOR\nConfluence + Dispatch + Dedup"];
      multi [label="Multi-Horizon\nSHORT 1-3M / FAST 5-20D"];
      ai [label="TradingAgents\nSecond Opinion AI"];
      notify [label="Email + WhatsApp"];
      web [label="Streamlit Dashboard\nControl Center"];
      gh [label="GitHub Actions"];
      core -> db; fast -> db; db -> orch; orch -> gh; gh -> multi; multi -> db; orch -> ai; ai -> db; orch -> notify; db -> web; web -> db; web -> orch [label="manual_run_requests"];
    }
    ''', use_container_width=True)
    st.markdown("**Sequenza tipica:** CORE/FAST → Supabase → confluence → Multi-Horizon → TradingAgents se qualificato → decisione finale → notifica → misurazione performance.")

st.caption(f"Snapshot dati: {snap['loaded_at']} | Pagina: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
