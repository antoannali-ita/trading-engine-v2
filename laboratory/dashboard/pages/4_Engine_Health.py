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

st.set_page_config(page_title="Trading Lab | Engine Health", layout="wide")
require_dashboard_auth()
st.title("Engine Health")

try:
    runs = load_engine_runs(500)
    signals = load_signals(3000)
    configs = load_engine_config()
except Exception as exc:
    st.error(str(exc))
    st.stop()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Run disponibili", len(runs))
c2.metric("Segnali disponibili", len(signals))
if not signals.empty and "data_quality" in signals:
    dq_bad = signals["data_quality"].fillna("").str.upper().isin(["FAIL", "ERROR", "DATA REVIEW", "LOW"]).sum()
    c3.metric("Data quality warning", int(dq_bad))
else:
    c3.metric("Data quality warning", "N/D")
if not configs.empty and "config_version" in configs:
    c4.metric("Config attiva", str(configs.iloc[0]["config_version"]))
else:
    c4.metric("Config attiva", "N/D")

if not signals.empty and "score_total" in signals and signals["score_total"].notna().any():
    st.subheader("Distribuzione score")
    fig = px.histogram(signals, x="score_total", nbins=20)
    st.plotly_chart(fig, use_container_width=True)

if not signals.empty and "trigger" in signals:
    st.subheader("Trigger")
    trigger_counts = signals["trigger"].fillna("N/D").value_counts().rename_axis("trigger").reset_index(name="count")
    st.dataframe(trigger_counts, use_container_width=True, hide_index=True)

if not signals.empty and "status" in signals:
    st.subheader("Stati")
    status_counts = signals["status"].fillna("N/D").value_counts().rename_axis("status").reset_index(name="count")
    st.dataframe(status_counts, use_container_width=True, hide_index=True)

st.subheader("Ultimi run")
if runs.empty:
    st.info("Nessun run.")
else:
    preferred = ["run_timestamp", "run_id", "market", "horizon", "engine_version", "config_version", "universe_size", "candidates_count", "notes"]
    cols = [c for c in preferred if c in runs.columns]
    st.dataframe(runs[cols], use_container_width=True, hide_index=True)
