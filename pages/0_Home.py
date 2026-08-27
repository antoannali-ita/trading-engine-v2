from __future__ import annotations

import streamlit as st

try:
    from dashboard.data_access import engine_health, latest_confluence, notifications, lab_watchlist
except ModuleNotFoundError:
    from data_access import engine_health, latest_confluence, notifications, lab_watchlist  # type: ignore

st.title("🏠 Home")
st.caption("Vista sintetica del Trading Engine. Il dettaglio storico resta disponibile in App completa.")

try:
    health = engine_health()
    conf = latest_confluence(250)
    notif = notifications(250)
    watch = lab_watchlist(500)
except Exception as exc:
    st.error(f"Dati non disponibili: {type(exc).__name__}: {exc}")
    st.stop()

healthy = sum(str(r.get("computed_health") or r.get("registry_status") or "").upper() == "HEALTHY" for r in health)
issues = sum(str(r.get("computed_health") or r.get("registry_status") or "").upper() in {"FAILED", "STALE", "DEGRADED"} for r in health)
actionable = sum(bool(r.get("is_actionable")) for r in conf)
active_watch = len(watch)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Motori healthy", f"{healthy}/{len(health)}")
c2.metric("Da verificare", issues)
c3.metric("Actionable", actionable)
c4.metric("Watchlist attiva", active_watch)

st.subheader("🎯 Candidati recenti")
rows = []
for r in conf[:20]:
    rows.append({
        "Ticker": r.get("ticker"),
        "Mercato": r.get("market"),
        "Segnale": r.get("signal_type"),
        "Decisione": r.get("decision"),
        "Conviction": r.get("conviction"),
        "Actionable": r.get("is_actionable"),
        "Data": r.get("detected_at"),
    })
if rows:
    st.dataframe(rows, hide_index=True, use_container_width=True)
else:
    st.info("Nessun candidato recente disponibile.")

st.subheader("🔔 Ultime notifiche ticker")
notified = []
for r in notif:
    ticker = str(r.get("ticker") or "").strip().upper()
    if not ticker or ticker in {"N/D", "REPORT"}:
        continue
    notified.append({
        "Ticker": ticker,
        "Canale": r.get("channel"),
        "Stato": r.get("status"),
        "Inviata": r.get("sent_at") or r.get("attempted_at"),
    })
    if len(notified) >= 15:
        break
if notified:
    st.dataframe(notified, hide_index=True, use_container_width=True)
else:
    st.caption("Nessuna notifica ticker recente.")
