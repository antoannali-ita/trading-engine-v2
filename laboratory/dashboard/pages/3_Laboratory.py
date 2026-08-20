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
from lab.data import load_lab_signal_outcomes
from lab.ui import apply_theme, company_name, fmt_num, fmt_pct, fmt_score, page_header

st.set_page_config(page_title="Trading Lab | Signal Outcomes", layout="wide", page_icon="📊")
require_dashboard_auth()
apply_theme()
page_header(
    "Signal Outcomes",
    "Feedback loop del Laboratory: misura tutti i segnali, anche WATCH, BLOCKED e PRE-BUY, per capire cosa funziona e quanto costano i nostri filtri.",
    eyebrow="LAB · D1-D60 · MFE/MAE · COUNTERFACTUAL",
)

try:
    outcomes = load_lab_signal_outcomes(5000)
except Exception as exc:
    st.error("La tabella lab_signal_outcomes non è leggibile.")
    st.code(str(exc))
    st.stop()

if outcomes.empty:
    st.info("La tabella Outcomes esiste ma non contiene ancora righe. Il workflow giornaliero ora esegue automaticamente run_signal_outcomes.py dopo il feed opportunità.")
    st.stop()

for col in [
    "strategy_score", "trade_score", "portfolio_fit_score",
    "ret_d1", "ret_d3", "ret_d5", "ret_d10", "ret_d20", "ret_d60",
    "excess_ret_d1", "excess_ret_d3", "excess_ret_d5", "excess_ret_d10", "excess_ret_d20", "excess_ret_d60",
    "mfe_pct", "mae_pct", "mfe_r", "mae_r", "last_horizon",
]:
    if col in outcomes:
        outcomes[col] = pd.to_numeric(outcomes[col], errors="coerce")

with st.container(border=True):
    c1, c2, c3 = st.columns(3)
    strategies = sorted(outcomes["strategy"].dropna().astype(str).unique().tolist()) if "strategy" in outcomes else []
    statuses = sorted(outcomes["source_signal_status"].dropna().astype(str).unique().tolist()) if "source_signal_status" in outcomes else []
    regimes = sorted(outcomes["regime_state"].dropna().astype(str).unique().tolist()) if "regime_state" in outcomes else []
    selected_strategies = c1.multiselect("Strategia", strategies, default=strategies)
    selected_statuses = c2.multiselect("Stato segnale", statuses, default=statuses)
    selected_regimes = c3.multiselect("Regime", regimes, default=regimes)

view = outcomes.copy()
if selected_strategies:
    view = view[view["strategy"].astype(str).isin(selected_strategies)]
if selected_statuses:
    view = view[view["source_signal_status"].astype(str).isin(selected_statuses)]
if selected_regimes:
    view = view[view["regime_state"].astype(str).isin(selected_regimes)]

m1, m2, m3, m4, m5, m6 = st.columns(6)
m1.metric("Segnali misurati", len(view))
m2.metric("D+20 medio", fmt_pct(view["ret_d20"].mean()) if "ret_d20" in view and view["ret_d20"].notna().any() else "N/D")
m3.metric("D+20 vs SPY", fmt_pct(view["excess_ret_d20"].mean()) if "excess_ret_d20" in view and view["excess_ret_d20"].notna().any() else "N/D")
m4.metric("MFE medio", fmt_pct(view["mfe_pct"].mean()) if "mfe_pct" in view and view["mfe_pct"].notna().any() else "N/D")
m5.metric("MAE medio", fmt_pct(view["mae_pct"].mean()) if "mae_pct" in view and view["mae_pct"].notna().any() else "N/D")
m6.metric("Orizzonte max", f"D+{int(view['last_horizon'].max())}" if "last_horizon" in view and view["last_horizon"].notna().any() else "N/D")

if "strategy" in view and "ret_d20" in view and view["ret_d20"].notna().any():
    stats = (
        view.groupby("strategy", dropna=False)
        .agg(
            n=("symbol", "count"),
            avg_d5=("ret_d5", "mean"),
            avg_d20=("ret_d20", "mean"),
            avg_excess_d20=("excess_ret_d20", "mean"),
            median_mfe_r=("mfe_r", "median"),
            median_mae_r=("mae_r", "median"),
        )
        .reset_index()
        .sort_values(["avg_excess_d20", "n"], ascending=[False, False])
    )

    left, right = st.columns(2)
    with left:
        fig = px.bar(stats, x="strategy", y="avg_d20", text_auto=".2f", hover_data=["n"], title="Return medio D+20")
        fig.add_hline(y=0, line_dash="dot")
        fig.update_layout(height=390, margin=dict(l=10, r=10, t=45, b=10), xaxis_title=None, yaxis_title="%")
        st.plotly_chart(fig, use_container_width=True)
    with right:
        fig = px.bar(stats, x="strategy", y="avg_excess_d20", text_auto=".2f", hover_data=["n"], title="Excess return D+20 vs SPY")
        fig.add_hline(y=0, line_dash="dot")
        fig.update_layout(height=390, margin=dict(l=10, r=10, t=45, b=10), xaxis_title=None, yaxis_title="%")
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("### Diagnostica per strategia")
    stats_display = stats.copy()
    for col in ["avg_d5", "avg_d20", "avg_excess_d20"]:
        if col in stats_display:
            stats_display[col] = stats_display[col].map(fmt_pct)
    for col in ["median_mfe_r", "median_mae_r"]:
        if col in stats_display:
            stats_display[col] = stats_display[col].map(lambda v: fmt_num(v, 2))
    st.dataframe(stats_display, use_container_width=True, hide_index=True)

st.markdown("### Accepted vs blocked / counterfactual")
if "block_reasons" in view:
    blocked_mask = view["block_reasons"].apply(lambda x: isinstance(x, list) and len(x) > 0)
    accepted = view[~blocked_mask]
    blocked = view[blocked_mask]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Senza blocchi", len(accepted))
    c2.metric("Con blocchi", len(blocked))
    c3.metric("D+20 accepted", fmt_pct(accepted["ret_d20"].mean()) if "ret_d20" in accepted and accepted["ret_d20"].notna().any() else "N/D")
    c4.metric("D+20 blocked", fmt_pct(blocked["ret_d20"].mean()) if "ret_d20" in blocked and blocked["ret_d20"].notna().any() else "N/D")

st.markdown("### Ultimi outcomes")
display = view.copy()
if "symbol" in display:
    display.insert(display.columns.get_loc("symbol") + 1, "azienda", display["symbol"].map(company_name))
for col in ["strategy_score", "trade_score", "portfolio_fit_score"]:
    if col in display:
        display[col] = display[col].map(fmt_score)
for col in ["ret_d1", "ret_d3", "ret_d5", "ret_d10", "ret_d20", "ret_d60", "excess_ret_d20", "mfe_pct", "mae_pct"]:
    if col in display:
        display[col] = display[col].map(fmt_pct)
for col in ["mfe_r", "mae_r"]:
    if col in display:
        display[col] = display[col].map(lambda v: fmt_num(v, 2))
preferred = [
    "signal_date", "symbol", "azienda", "strategy", "source_signal_status", "strategy_score", "trade_score",
    "portfolio_fit_score", "regime_state", "ret_d1", "ret_d3", "ret_d5", "ret_d10", "ret_d20", "ret_d60",
    "excess_ret_d20", "mfe_pct", "mae_pct", "mfe_r", "mae_r", "bars_to_mfe", "bars_to_mae", "block_reasons",
]
cols = [c for c in preferred if c in display.columns]
st.dataframe(display[cols].head(500), use_container_width=True, hide_index=True)

st.caption("Gli outcomes misurano anche i segnali respinti: servono a valutare il costo/opportunità dei gate senza trasformare automaticamente un buon risultato controfattuale in una regola da eliminare.")
