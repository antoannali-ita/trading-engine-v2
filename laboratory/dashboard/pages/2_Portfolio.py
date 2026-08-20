import sys
from pathlib import Path

import pandas as pd
import streamlit as st

LAB_ROOT = Path(__file__).resolve().parents[2]
SRC = LAB_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from lab.auth import require_dashboard_auth
from lab.data import (
    load_lab_paper_events,
    load_lab_paper_positions,
    load_lab_watchlist,
    load_trades,
)
from lab.settings import CAPITAL_TOTAL_BASE, MAX_POSITION_USD, USA_COMMISSION_USD
from lab.ui import apply_theme, company_name, fmt_money, fmt_pct, fmt_score, localize_table, page_header

st.set_page_config(page_title="Trading Lab | Portafoglio", layout="wide", page_icon="💼")
require_dashboard_auth()
apply_theme()
page_header(
    "Portafoglio simulato e lista di osservazione",
    "Posizioni simulate, avvisi e candidati generati dal Laboratory. Le eventuali posizioni reali del Core restano separate e non vengono create dai segnali Lab.",
    eyebrow="LAB · SIMULAZIONI · AVVISI · RISCHIO",
)

try:
    lab_watch = load_lab_watchlist()
    paper_positions = load_lab_paper_positions()
    paper_events = load_lab_paper_events()
except Exception as exc:
    st.error("Le tabelle operative del Lab non sono disponibili su Supabase.")
    st.code(str(exc))
    st.stop()

try:
    real_trades = load_trades()
except Exception:
    real_trades = pd.DataFrame()

open_paper = paper_positions.copy()
if not paper_positions.empty and "status" in paper_positions:
    open_paper = paper_positions[paper_positions["status"].fillna("").astype(str).str.upper().isin(["OPEN", "TP1_HIT"])]

paper_capital = pd.to_numeric(open_paper.get("capital"), errors="coerce").fillna(0).sum() if not open_paper.empty and "capital" in open_paper else 0.0
paper_net = pd.to_numeric(paper_positions.get("net_pnl"), errors="coerce").fillna(0).sum() if not paper_positions.empty and "net_pnl" in paper_positions else 0.0
prebuy_count = 0
if not lab_watch.empty and "status" in lab_watch:
    prebuy_count = int(lab_watch["status"].fillna("").astype(str).str.upper().isin(["PRE_BUY", "PAPER_OPEN"]).sum())

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Capitale Lab", f"{CAPITAL_TOTAL_BASE:,.0f}")
c2.metric("Posizione massima", fmt_money(MAX_POSITION_USD))
c3.metric("Posizioni simulate aperte", len(open_paper))
c4.metric("Capitale simulato", fmt_money(paper_capital))
c5.metric("P&L simulato chiuso", fmt_money(paper_net))
c6.metric("Candidati osservati", len(lab_watch))

st.caption(
    f"Commissione USA simulata: {fmt_money(USA_COMMISSION_USD)} per lato. "
    "Il portafoglio simulato è solo ricerca e non invia ordini a Fineco."
)

st.markdown("### 🧪 Posizioni simulate aperte")
if open_paper.empty:
    st.info(
        "Nessuna posizione simulata aperta in questo momento. Una posizione viene aperta solo quando il Lab supera tutti i controlli e la conferma è valida; osservazione e pre-acquisto non vengono forzati in operazioni."
    )
else:
    display = open_paper.copy()
    if "symbol" in display:
        display.insert(display.columns.get_loc("symbol") + 1, "azienda", display["symbol"].map(company_name))
    for col in ["entry_price", "capital", "stop_initial", "stop_current", "tp1", "tp2", "last_price", "exit_price", "gross_pnl", "net_pnl"]:
        if col in display:
            display[col] = display[col].map(fmt_money)
    if "return_pct" in display:
        display["return_pct"] = display["return_pct"].map(fmt_pct)
    preferred = ["symbol", "azienda", "strategy", "status", "qty", "capital", "entry_price", "last_price", "stop_current", "tp1", "tp2", "source_signal_date", "opened_at", "last_checked_date"]
    cols = [c for c in preferred if c in display.columns]
    st.dataframe(localize_table(display[cols]), use_container_width=True, hide_index=True)

st.markdown("### 🎯 Lista di osservazione e avvisi")
if lab_watch.empty:
    st.info("Nessun candidato Lab sopra la soglia di osservazione nell'ultimo aggiornamento disponibile.")
else:
    display = lab_watch.copy()
    if "symbol" in display:
        display.insert(display.columns.get_loc("symbol") + 1, "azienda", display["symbol"].map(company_name))
    for col in ["price", "entry", "max_buy", "stop", "tp1", "tp2", "alert_price"]:
        if col in display:
            display[col] = display[col].map(fmt_money)
    if "distance_to_entry_pct" in display:
        display["distance_to_entry_pct"] = display["distance_to_entry_pct"].map(fmt_pct)
    if "score" in display:
        display["score"] = display["score"].map(fmt_score)
    preferred = ["symbol", "azienda", "strategy", "status", "score", "trigger", "alert_type", "alert_price", "price", "entry", "max_buy", "distance_to_entry_pct", "reason", "signal_date", "last_seen_at"]
    cols = [c for c in preferred if c in display.columns]
    st.dataframe(localize_table(display[cols]), use_container_width=True, hide_index=True)
    st.caption(f"Candidati in pre-acquisto o simulazione approvata: {prebuy_count}")

st.markdown("### 🧾 Cronologia delle simulazioni")
if paper_events.empty:
    st.caption("Nessun evento di simulazione ancora registrato.")
else:
    display = paper_events.copy()
    for col in ["price", "old_stop", "new_stop"]:
        if col in display:
            display[col] = display[col].map(fmt_money)
    preferred = ["created_at", "position_id", "event_type", "price", "old_stop", "new_stop", "note"]
    cols = [c for c in preferred if c in display.columns]
    st.dataframe(localize_table(display[cols]).head(100), use_container_width=True, hide_index=True)

with st.expander("Posizioni REALI Core · separate dal Lab", expanded=False):
    if real_trades.empty:
        st.caption("Nessuna posizione reale registrata nel database Core. Questo non impedisce al portafoglio simulato del Lab di funzionare.")
    else:
        real = real_trades.copy()
        if "ticker" in real:
            real.insert(real.columns.get_loc("ticker") + 1, "azienda", real["ticker"].map(company_name))
        for col in ["entry_price", "stop_current", "tp1", "tp2", "exit_price", "gross_pnl", "net_pnl"]:
            if col in real:
                real[col] = real[col].map(fmt_money)
        if "return_pct" in real:
            real["return_pct"] = real["return_pct"].map(fmt_pct)
        preferred = ["ticker", "azienda", "market", "trade_status", "qty", "entry_price", "stop_current", "tp1", "tp2", "net_pnl", "return_pct"]
        cols = [c for c in preferred if c in real.columns]
        st.dataframe(localize_table(real[cols]), use_container_width=True, hide_index=True)

st.caption("Fonte principale di questa pagina: Strategy Lab. Segnali, lista di osservazione e posizioni simulate restano separati dal monitoraggio Core e dagli ordini reali.")
