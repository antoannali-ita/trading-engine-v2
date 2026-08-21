from __future__ import annotations

import os
from datetime import datetime

import pandas as pd
import streamlit as st

from dashboard.data_access import (
    ai_analysis,
    engine_health,
    manual_requests,
    notifications,
    performance,
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
        else:
            st.error("Password non valida")
    st.stop()


def as_df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def badge(value: str | None) -> str:
    v = str(value or "UNKNOWN").upper()
    icon = {
        "HEALTHY": "🟢", "SUCCESS": "🟢", "SENT": "🟢", "CONFIRM": "🟢",
        "RUNNING": "🔵", "PENDING": "🟡", "REQUESTED": "🟡", "DISPATCHED": "🔵",
        "DEGRADED": "🟠", "CAUTION": "🟠", "NEUTRAL": "⚪",
        "FAILED": "🔴", "VETO": "🔴", "STALE": "🟠", "DISABLED": "⚫",
    }.get(v, "⚪")
    return f"{icon} {v}"


require_access()

st.title("Trading Engine Control Center")
st.caption("CORE + FAST + Multi-Horizon + TradingAgents + Orchestrator | Supabase come memoria centrale")

try:
    health_rows = engine_health()
except Exception as exc:
    st.error(f"Connessione dati non disponibile: {type(exc).__name__}: {exc}")
    st.stop()

health_df = as_df(health_rows)
sig_rows = signals(1500)
run_rows = runs(800)
ai_rows = ai_analysis(600)
notif_rows = notifications(800)
perf_rows = performance(1500)
request_rows = manual_requests(300)

sig_df = as_df(sig_rows)
run_df = as_df(run_rows)
ai_df = as_df(ai_rows)
notif_df = as_df(notif_rows)
perf_df = as_df(perf_rows)
request_df = as_df(request_rows)

healthy = sum(str(r.get("computed_health") or r.get("registry_status") or "").upper() == "HEALTHY" for r in health_rows)
failed = sum(str(r.get("computed_health") or r.get("registry_status") or "").upper() in {"FAILED", "STALE", "DEGRADED"} for r in health_rows)
actionable = sum(bool(r.get("is_actionable")) for r in sig_rows)
ai_pending = sum(str(r.get("status") or "").upper() in {"PENDING", "RUNNING"} for r in ai_rows)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Motori healthy", f"{healthy}/{len(health_rows)}")
c2.metric("Motori da verificare", failed)
c3.metric("Segnali actionable", actionable)
c4.metric("AI in lavorazione", ai_pending)

pages = st.tabs([
    "Overview", "Motori", "Segnali", "TradingAgents", "Run & Log",
    "Esegui ora", "Performance", "Notifiche", "Architettura"
])

with pages[0]:
    st.subheader("Situazione generale")
    if not health_df.empty:
        view = health_df.copy()
        if "computed_health" in view.columns:
            view["stato"] = view["computed_health"].map(badge)
        elif "registry_status" in view.columns:
            view["stato"] = view["registry_status"].map(badge)
        for col in ["last_started_at", "last_finished_at", "last_run_at", "next_expected_run_at"]:
            if col in view.columns:
                view[col] = view[col].map(utc_label)
        cols = [c for c in ["engine_id", "strategy", "market", "horizon", "stato", "last_started_at", "last_finished_at", "signals_found"] if c in view.columns]
        st.dataframe(view[cols], use_container_width=True, hide_index=True)

    st.subheader("Conferme più recenti")
    if not sig_df.empty:
        conf = sig_df[sig_df.get("engine", pd.Series(dtype=str)).astype(str).str.upper().eq("ORCHESTRATOR")].copy() if "engine" in sig_df.columns else pd.DataFrame()
        if not conf.empty:
            cols = [c for c in ["detected_at", "market", "ticker", "signal_type", "conviction", "is_actionable"] if c in conf.columns]
            st.dataframe(conf[cols].head(30), use_container_width=True, hide_index=True)
        else:
            st.info("Nessuna confluenza registrata ancora.")

    if not run_df.empty and "engine_id" in run_df.columns:
        st.subheader("Run recenti per motore")
        counts = run_df.groupby("engine_id").size().sort_values(ascending=False)
        st.bar_chart(counts)

with pages[1]:
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
    **Ruoli**
    - **CORE**: motore principale 3-6 mesi, qualità e selezione primaria.
    - **FAST**: monitor ravvicinato durante la sessione regolare, intercetta ingresso/stop/zone operative.
    - **Multi-Horizon**: secondo livello indipendente, SHORT 1-3M e FAST 5-20D in modalità shadow/controllo.
    - **TradingAgents**: seconda opinione AI solo su segnali già qualificati.
    - **ORCHESTRATOR**: legge Supabase, calcola confluence, evita duplicati, decide quando attivare i motori successivi e centralizza gli alert.
    """)

with pages[2]:
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
            st.subheader("Distribuzione stati")
            st.bar_chart(view["signal_type"].fillna("UNKNOWN").value_counts())

with pages[3]:
    st.subheader("TradingAgents")
    if ai_df.empty:
        st.info("Nessuna analisi AI registrata.")
    else:
        cols = [c for c in ["started_at", "completed_at", "market", "ticker", "status", "alignment", "confidence", "verdict", "summary", "trigger_reason", "entry", "stop", "tp1", "tp2"] if c in ai_df.columns]
        st.dataframe(ai_df[cols].head(200), use_container_width=True, hide_index=True)
        if "alignment" in ai_df.columns:
            st.subheader("Distribuzione giudizi")
            st.bar_chart(ai_df["alignment"].fillna("PENDING").value_counts())

with pages[4]:
    st.subheader("Run motori")
    if not run_df.empty:
        cols = [c for c in ["started_at", "finished_at", "engine_id", "market", "strategy", "trigger_source", "status", "duration_seconds", "records_processed", "signals_found", "error_message"] if c in run_df.columns]
        st.dataframe(run_df[cols].head(300), use_container_width=True, hide_index=True)
    else:
        st.info("Nessun run disponibile.")

    st.subheader("Richieste manuali")
    if not request_df.empty:
        cols = [c for c in ["requested_at", "engine_id", "market", "strategy", "requested_by", "status", "github_run_id", "completed_at", "error_message"] if c in request_df.columns]
        st.dataframe(request_df[cols].head(200), use_container_width=True, hide_index=True)

with pages[5]:
    st.subheader("Esecuzione manuale")
    st.warning("Il pulsante non esegue codice dal browser: crea una richiesta controllata su Supabase. L'orchestratore la prende in carico e lancia il workflow GitHub corretto.")
    engines = [r for r in health_rows if str(r.get("engine_id") or "").upper() not in {"ORCHESTRATOR"}]
    labels = [f"{r.get('engine_id')} | {r.get('strategy')} | {r.get('market')}" for r in engines]
    selected_label = st.selectbox("Motore", labels) if labels else None
    send_email = st.checkbox("Email finale", value=True)
    send_wa = st.checkbox("WhatsApp finale", value=False)
    requested_by = st.text_input("Richiesto da", value="Antonio")
    if st.button("ESEGUI ORA", type="primary", disabled=not selected_label):
        idx = labels.index(selected_label)
        row = engines[idx]
        created = request_run(
            str(row.get("engine_id")), str(row.get("market")), str(row.get("strategy") or ""),
            send_email=send_email, send_whatsapp=send_wa, requested_by=requested_by,
        )
        st.success(f"Richiesta creata: {created.get('request_id', 'OK')} - stato REQUESTED")

with pages[6]:
    st.subheader("Performance delle strategie")
    if perf_df.empty:
        st.info("La tabella performance è pronta; i dati compaiono dopo l'esecuzione del worker di valutazione.")
    else:
        cols = [c for c in ["created_at", "engine_id", "strategy", "market", "ticker", "outcome", "entry_price", "exit_price", "pnl_pct", "max_drawdown_pct", "max_favorable_excursion_pct", "holding_minutes"] if c in perf_df.columns]
        st.dataframe(perf_df[cols].head(400), use_container_width=True, hide_index=True)
        if "strategy" in perf_df.columns and "pnl_pct" in perf_df.columns:
            perf_numeric = perf_df.copy()
            perf_numeric["pnl_pct"] = pd.to_numeric(perf_numeric["pnl_pct"], errors="coerce")
            by_strategy = perf_numeric.groupby("strategy")["pnl_pct"].mean().dropna().sort_values(ascending=False)
            if not by_strategy.empty:
                st.subheader("P/L medio per strategia")
                st.bar_chart(by_strategy)

with pages[7]:
    st.subheader("Notifiche")
    if notif_df.empty:
        st.info("Nessuna notifica registrata.")
    else:
        cols = [c for c in ["attempted_at", "sent_at", "ticker", "event_type", "channel", "status", "provider", "error_message"] if c in notif_df.columns]
        st.dataframe(notif_df[cols].head(400), use_container_width=True, hide_index=True)
        if "channel" in notif_df.columns and "status" in notif_df.columns:
            pivot = notif_df.groupby(["channel", "status"]).size().unstack(fill_value=0)
            st.bar_chart(pivot)

with pages[8]:
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

    st.markdown("""
    **Regola chiave:** Supabase è la memoria condivisa. Nessun motore deve dipendere dal processo Python di un altro motore. GitHub Actions esegue, Supabase conserva, l'Orchestrator decide, il sito osserva e richiede azioni.

    **Sequenza tipica:** CORE/FAST → segnale → Supabase → confluence → Multi-Horizon → nuova conferma → TradingAgents solo se qualificato → decisione finale → notifica → performance successiva.
    """)

st.caption(f"Ultimo refresh pagina: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
