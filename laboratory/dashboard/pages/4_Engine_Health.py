import sys
from pathlib import Path

import plotly.express as px
import streamlit as st

LAB_ROOT = Path(__file__).resolve().parents[2]
SRC = LAB_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from lab.auth import require_dashboard_auth
from lab.data import load_engine_config, load_engine_runs, load_signals
from lab.ui import apply_theme, page_header

st.set_page_config(page_title="Trading Lab | Engine Health", layout="wide", page_icon="🩺")
require_dashboard_auth()
apply_theme()
page_header(
    "Engine Health",
    "Controlla se il motore sta girando, quanto sono freschi i dati e dove si accumulano warning. Prima di fidarsi di un BUY, conviene accertarsi che il paziente abbia il polso.",
    eyebrow="SYSTEM MONITORING",
)

try:
    runs = load_engine_runs(500)
    signals = load_signals(3000)
    configs = load_engine_config()
except Exception as exc:
    st.error(str(exc))
    st.stop()

if not signals.empty and "data_quality" in signals:
    dq_bad = int(signals["data_quality"].fillna("").str.upper().isin(["FAIL", "ERROR", "DATA REVIEW", "LOW"]).sum())
else:
    dq_bad = 0

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Run", len(runs), help="Run Core registrati in Supabase.")
c2.metric("Segnali", len(signals))
c3.metric("Data warning", dq_bad, help="FAIL / ERROR / DATA REVIEW / LOW")
c4.metric("Config attiva", str(configs.iloc[0]["config_version"]) if not configs.empty and "config_version" in configs else "N/D")
if not runs.empty:
    c5.metric("Ultimo run", str(runs.iloc[0].get("run_timestamp", "N/D")))
else:
    c5.metric("Ultimo run", "N/D")

if dq_bad == 0:
    st.success("Data quality: nessun warning registrato nei segnali caricati.")
else:
    st.warning(f"Data quality: {dq_bad} segnali richiedono attenzione.")

left, right = st.columns(2)
with left:
    if not signals.empty and "score_total" in signals and signals["score_total"].notna().any():
        fig = px.histogram(signals, x="score_total", nbins=20, title="Distribuzione score")
        fig.update_layout(height=380, margin=dict(l=10, r=10, t=45, b=10))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Score non ancora disponibili.")
with right:
    if not signals.empty and "trigger" in signals:
        trigger_counts = signals["trigger"].fillna("N/D").value_counts().rename_axis("trigger").reset_index(name="count")
        fig = px.bar(trigger_counts, x="trigger", y="count", text="count", title="Trigger")
        fig.update_layout(height=380, margin=dict(l=10, r=10, t=45, b=10), xaxis_title=None, yaxis_title=None)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Trigger non ancora disponibili.")

st.markdown("### Stato segnali")
if not signals.empty and "status" in signals:
    status_counts = signals["status"].fillna("N/D").value_counts().rename_axis("status").reset_index(name="count")
    fig = px.bar(status_counts, x="status", y="count", text="count")
    fig.update_layout(height=340, margin=dict(l=10, r=10, t=20, b=10), xaxis_title=None, yaxis_title=None)
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Nessuno stato disponibile.")

st.markdown("### Ultimi run")
if runs.empty:
    st.info("Nessun run Core registrato.")
else:
    preferred = ["run_timestamp", "run_id", "market", "horizon", "engine_version", "config_version", "universe_size", "candidates_count", "notes"]
    cols = [c for c in preferred if c in runs.columns]
    st.dataframe(runs[cols].head(30), use_container_width=True, hide_index=True)

with st.expander("Configurazione motore"):
    if configs.empty:
        st.info("Nessuna configurazione registrata.")
    else:
        st.dataframe(configs, use_container_width=True, hide_index=True)

st.caption("Questa pagina monitora ciò che è già persistito nel DB. Non sostituisce ancora il controllo dei provider esterni o la freshness automatica, che saranno un layer successivo.")
