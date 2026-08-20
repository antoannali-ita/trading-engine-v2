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
    load_engine_config,
    load_engine_runs,
    load_lab_paper_events,
    load_lab_paper_positions,
    load_lab_watchlist,
    load_signals,
    load_strategy_evaluations,
    load_strategy_variants,
)
from lab.settings import MAX_POSITION_USD
from lab.ui import apply_theme, fmt_money, localize_table, page_header

st.set_page_config(page_title="Trading Lab | Stato del motore", layout="wide", page_icon="🩺")
require_dashboard_auth()
apply_theme()
page_header(
    "Stato del motore",
    "Controlli di salute del Laboratory: persistenza, freschezza, ciclo delle simulazioni, evoluzione delle strategie e coerenza della configurazione.",
    eyebrow="QUALITÀ LAB · DATI · PERSISTENZA",
)

errors = []

def _safe_load(label, fn):
    try:
        return fn()
    except Exception as exc:
        errors.append((label, str(exc)))
        return pd.DataFrame()

runs = _safe_load("engine_runs", lambda: load_engine_runs(500))
signals = _safe_load("signals", lambda: load_signals(3000))
configs = _safe_load("engine_config", load_engine_config)
watch = _safe_load("lab_watchlist", lambda: load_lab_watchlist(3000))
positions = _safe_load("lab_paper_positions", lambda: load_lab_paper_positions(3000))
events = _safe_load("lab_paper_events", lambda: load_lab_paper_events(5000))
variants = _safe_load("lab_strategy_variants", lambda: load_strategy_variants(3000))
evaluations = _safe_load("lab_strategy_evaluations", lambda: load_strategy_evaluations(10000))

open_paper = positions.copy()
if not positions.empty and "status" in positions:
    open_paper = positions[positions["status"].fillna("").astype(str).str.upper().isin(["OPEN", "TP1_HIT"])]

latest_lab = pd.NaT
if not watch.empty and "last_seen_at" in watch:
    latest_lab = pd.to_datetime(watch["last_seen_at"], errors="coerce", utc=True).max()

st.markdown("### Stato del sistema")
c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Candidati Lab", len(watch))
c2.metric("Posizioni simulate aperte", len(open_paper))
c3.metric("Eventi simulati", len(events))
c4.metric("Varianti strategiche", len(variants))
c5.metric("Valutazioni", len(evaluations))
c6.metric("Errori tabelle", len(errors))

if errors:
    st.error("Alcune sorgenti non sono leggibili.")
    for label, message in errors:
        st.code(f"{label}: {message}")
else:
    st.success("Tabelle operative del Laboratory e relativi loader leggibili.")

st.markdown("### Freschezza dei dati Lab")
if pd.isna(latest_lab):
    st.warning("Nessun timestamp Lab disponibile: il flusso giornaliero non ha ancora popolato la lista di osservazione.")
else:
    now = pd.Timestamp.now(tz="UTC")
    age_hours = (now - latest_lab).total_seconds() / 3600.0
    a, b = st.columns(2)
    a.metric("Ultimo aggiornamento Lab", str(latest_lab))
    b.metric("Età dei dati", f"{age_hours:.1f} h")
    if age_hours > 72:
        st.error("Dati Lab obsoleti: oltre 72 ore.")
    elif age_hours > 30:
        st.warning("Dati Lab non recenti: verifica calendario e scheduler prima di considerarli operativi.")
    else:
        st.success("Dati Lab recenti.")

st.markdown("### Controlli anomalie sulle simulazioni")
anomalies = []
if not watch.empty:
    for _, row in watch.iterrows():
        entry = pd.to_numeric(row.get("entry"), errors="coerce")
        max_buy = pd.to_numeric(row.get("max_buy"), errors="coerce")
        stop = pd.to_numeric(row.get("stop"), errors="coerce")
        tp1 = pd.to_numeric(row.get("tp1"), errors="coerce")
        tp2 = pd.to_numeric(row.get("tp2"), errors="coerce")
        symbol = row.get("symbol", "N/D")
        strategy = row.get("strategy", "N/D")
        if pd.notna(entry) and pd.notna(max_buy) and entry > max_buy:
            anomalies.append(f"{symbol}/{strategy}: ingresso > prezzo massimo")
        if pd.notna(entry) and pd.notna(stop) and stop >= entry:
            anomalies.append(f"{symbol}/{strategy}: stop >= ingresso")
        if pd.notna(tp1) and pd.notna(tp2) and tp1 > tp2:
            anomalies.append(f"{symbol}/{strategy}: TP1 > TP2")

if not open_paper.empty:
    for _, row in open_paper.iterrows():
        qty = pd.to_numeric(row.get("qty"), errors="coerce")
        capital = pd.to_numeric(row.get("capital"), errors="coerce")
        if pd.notna(qty) and qty <= 0:
            anomalies.append(f"{row.get('symbol', 'N/D')}/{row.get('strategy', 'N/D')}: quantità <= 0")
        if pd.notna(capital) and capital > MAX_POSITION_USD + 0.01:
            anomalies.append(f"{row.get('symbol', 'N/D')}/{row.get('strategy', 'N/D')}: capitale {fmt_money(capital)} > limite {fmt_money(MAX_POSITION_USD)}")

if anomalies:
    st.error(f"Anomalie operative: {len(anomalies)}")
    for item in anomalies[:50]:
        st.write(f"- {item}")
else:
    st.success("Nessuna anomalia strutturale rilevata sulla lista di osservazione o sulle posizioni simulate aperte.")

st.markdown("### Evoluzione delle strategie")
if variants.empty:
    st.info("Nessuna variante ancora persistita. Il job di evoluzione delle strategie può popolare questa sezione.")
else:
    promoted = int(variants.get("promoted_to_core", pd.Series(dtype=bool)).fillna(False).astype(bool).sum()) if "promoted_to_core" in variants else 0
    verdict_counts = evaluations.get("verdict", pd.Series(dtype=object)).fillna("N/D").value_counts() if not evaluations.empty and "verdict" in evaluations else pd.Series(dtype=int)
    x1, x2, x3, x4 = st.columns(4)
    x1.metric("Varianti totali", len(variants))
    x2.metric("Promosse al Core", promoted)
    x3.metric("Valutazioni promovibili", int(verdict_counts.get("PROMOTABLE", 0)))
    x4.metric("Valutazioni scartate", int(verdict_counts.get("REJECTED", 0)))
    show = [c for c in ["created_at", "variant_id", "parent_strategy", "generation", "status", "promoted_to_core", "mutation_reason"] if c in variants.columns]
    st.dataframe(localize_table(variants[show]).head(30), use_container_width=True, hide_index=True)

st.markdown("### Configurazione")
if configs.empty:
    st.warning("Nessuna configurazione registrata in engine_config.")
elif "max_position" in configs.columns:
    db_max = pd.to_numeric(configs.iloc[0].get("max_position"), errors="coerce")
    if pd.notna(db_max) and abs(float(db_max) - MAX_POSITION_USD) > 0.01:
        st.warning(f"CONFIGURAZIONE NON COERENTE: limite Lab = {fmt_money(MAX_POSITION_USD)}, engine_config DB = {fmt_money(db_max)}. Il Lab usa la propria regola; il Core resta separato.")
    elif pd.notna(db_max):
        st.success(f"Limite posizione coerente: {fmt_money(db_max)}")

with st.expander("Osservazione Core", expanded=False):
    st.write(f"Esecuzioni Core registrate: {len(runs)}")
    st.write(f"Segnali Core registrati: {len(signals)}")
    if not runs.empty:
        cols = [c for c in ["run_timestamp", "run_id", "market", "horizon", "engine_version", "candidates_count"] if c in runs.columns]
        st.dataframe(localize_table(runs[cols]).head(20), use_container_width=True, hide_index=True)

st.caption("Stato del motore del Laboratory. Gli errori del Lab non vengono nascosti dietro metriche Core e le posizioni simulate non sono posizioni reali.")
