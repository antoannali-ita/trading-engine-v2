import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

LAB_ROOT = Path(__file__).resolve().parents[2]
SRC = LAB_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from lab.auth import require_dashboard_auth
from lab.data import load_signal_outcomes, load_signals
from lab.ui import apply_theme, page_header

st.set_page_config(page_title="Trading Lab | Outcomes", layout="wide", page_icon="📊")
require_dashboard_auth()
apply_theme()
page_header(
    "Signal Outcomes",
    "Misura cosa è successo dopo i segnali del Core: rendimento, target raggiunti e stop. È il ponte tra 'sembrava un buon setup' e 'ha davvero funzionato'.",
    eyebrow="POST-SIGNAL ANALYTICS",
)

try:
    signals = load_signals(5000)
    outcomes = load_signal_outcomes(5000)
except Exception as exc:
    st.error(str(exc))
    st.stop()

if signals.empty or outcomes.empty:
    st.info("Servono segnali Core e outcomes per questa pagina. L'aggiornamento automatico D+1/D+3/D+5/D+10/D+20/D+60 non è ancora collegato, quindi qui è corretto vedere poco o nulla per ora.")
    st.stop()

joined = signals.merge(outcomes, on="signal_id", how="inner", suffixes=("", "_outcome"))

with st.container(border=True):
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

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Campione", len(view))
m2.metric("Return medio 20d", f"{view['return_d20'].dropna().mean():.2f}%" if "return_d20" in view and view["return_d20"].notna().any() else "N/D")
m3.metric("TP1 hit", f"{100 * view['hit_tp1'].fillna(False).mean():.1f}%" if "hit_tp1" in view else "N/D")
m4.metric("TP2 hit", f"{100 * view['hit_tp2'].fillna(False).mean():.1f}%" if "hit_tp2" in view else "N/D")
m5.metric("Stop hit", f"{100 * view['hit_stop'].fillna(False).mean():.1f}%" if "hit_stop" in view else "N/D")

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

    left, right = st.columns(2)
    with left:
        fig = px.bar(stats, x="setup", y="avg_return_20d", text_auto=".2f", hover_data=["n"], title="Return medio a 20 giorni")
        fig.add_hline(y=0, line_dash="dot")
        fig.update_layout(height=400, margin=dict(l=10, r=10, t=45, b=10), xaxis_title=None)
        st.plotly_chart(fig, use_container_width=True)
    with right:
        melted = stats.melt(id_vars=["setup", "n"], value_vars=["tp1_hit", "tp2_hit", "stop_hit"], var_name="esito", value_name="percentuale")
        fig = px.bar(melted, x="setup", y="percentuale", color="esito", barmode="group", title="Target e stop hit rate")
        fig.update_layout(height=400, margin=dict(l=10, r=10, t=45, b=10), xaxis_title=None, yaxis_title="%")
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("### Setup ranking")
    st.dataframe(stats, use_container_width=True, hide_index=True)

with st.expander("Dataset completo"):
    preferred = ["created_at", "ticker", "market", "horizon", "status", "setup", "score_total", "return_d5", "return_d20", "return_d60", "mfe_20d", "mae_20d", "hit_tp1", "hit_tp2", "hit_stop"]
    cols = [c for c in preferred if c in view.columns]
    st.dataframe(view[cols], use_container_width=True, hide_index=True)

st.caption("Questa pagina diventerà molto più potente quando collegheremo l'outcome updater automatico e avremo abbastanza storico reale dei segnali Core.")
