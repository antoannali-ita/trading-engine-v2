import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

LAB_ROOT = Path(__file__).resolve().parents[2]
SRC = LAB_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from lab.data import load_signal_outcomes, load_signals

st.set_page_config(page_title="Trading Lab | Laboratory", layout="wide")
st.title("Laboratory | Signal Outcomes")

try:
    signals = load_signals(5000)
    outcomes = load_signal_outcomes(5000)
except Exception as exc:
    st.error(str(exc))
    st.stop()

if signals.empty or outcomes.empty:
    st.info("Servono segnali e outcomes per calcolare la performance del laboratorio.")
    st.stop()

joined = signals.merge(outcomes, on="signal_id", how="inner", suffixes=("", "_outcome"))

c1, c2, c3 = st.columns(3)
setup_values = sorted(joined["setup"].dropna().unique().tolist()) if "setup" in joined else []
status_values = sorted(joined["status"].dropna().unique().tolist()) if "status" in joined else []
horizon_values = sorted(joined["horizon"].dropna().unique().tolist()) if "horizon" in joined else []
setups = c1.multiselect("Setup", setup_values, default=setup_values)
statuses = c2.multiselect("Stato", status_values, default=status_values)
horizons = c3.multiselect("Horizon", horizon_values, default=horizon_values)

view = joined.copy()
if setups:
    view = view[view["setup"].isin(setups)]
if statuses:
    view = view[view["status"].isin(statuses)]
if horizons:
    view = view[view["horizon"].isin(horizons)]

m1, m2, m3, m4 = st.columns(4)
m1.metric("Campione", len(view))
if "return_d20" in view:
    m2.metric("Return medio 20d", f"{view['return_d20'].dropna().mean():.2f}%" if view['return_d20'].notna().any() else "N/D")
else:
    m2.metric("Return medio 20d", "N/D")
if "hit_tp1" in view:
    m3.metric("TP1 hit", f"{100 * view['hit_tp1'].fillna(False).mean():.1f}%")
else:
    m3.metric("TP1 hit", "N/D")
if "hit_stop" in view:
    m4.metric("Stop hit", f"{100 * view['hit_stop'].fillna(False).mean():.1f}%")
else:
    m4.metric("Stop hit", "N/D")

if "setup" in view and "return_d20" in view and view["return_d20"].notna().any():
    stats = (
        view.groupby("setup", dropna=False)
        .agg(
            n=("signal_id", "count"),
            avg_return_20d=("return_d20", "mean"),
            median_return_20d=("return_d20", "median"),
            tp1_hit=("hit_tp1", "mean"),
            tp2_hit=("hit_tp2", "mean"),
            stop_hit=("hit_stop", "mean"),
        )
        .reset_index()
        .sort_values(["avg_return_20d", "n"], ascending=[False, False])
    )
    for col in ["tp1_hit", "tp2_hit", "stop_hit"]:
        stats[col] = stats[col] * 100
    st.subheader("Performance per setup")
    st.dataframe(stats, use_container_width=True, hide_index=True)
    fig = px.bar(stats, x="setup", y="avg_return_20d", hover_data=["n"], title="Return medio a 20 giorni per setup")
    st.plotly_chart(fig, use_container_width=True)

st.subheader("Dataset laboratorio")
preferred = [
    "created_at", "ticker", "market", "horizon", "status", "setup", "score_total",
    "return_d5", "return_d20", "return_d60", "mfe_20d", "mae_20d",
    "hit_tp1", "hit_tp2", "hit_stop"
]
cols = [c for c in preferred if c in view.columns]
st.dataframe(view[cols], use_container_width=True, hide_index=True)
