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
from lab.data import load_lab_backtest_results, load_lab_backtest_runs, load_lab_paper_signals

st.set_page_config(page_title="Backtest Research", layout="wide")
require_dashboard_auth()
st.title("Backtest Research")
st.caption("Research-only. Nessun ordine reale viene inviato.")

try:
    runs = load_lab_backtest_runs()
    results = load_lab_backtest_results()
    paper = load_lab_paper_signals()
except Exception as exc:
    st.error("Tabelle research non disponibili. Eseguire laboratory/sql/02_lab_research_tables.sql su Supabase.")
    st.code(str(exc))
    st.stop()

if results.empty:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Backtest run", len(runs))
    c2.metric("Risultati", 0)
    c3.metric("Paper signal", len(paper))
    c4.metric("Return medio", "N/D")
    st.info("Nessun backtest salvato ancora.")
    st.stop()

numeric = results.copy()
for col in ["win_rate", "profit_factor", "return_pct", "trades", "net_pnl"]:
    if col in numeric:
        numeric[col] = pd.to_numeric(numeric[col], errors="coerce")

summary = (
    numeric.groupby("strategy", dropna=False)
    .agg(
        win_rate=("win_rate", "mean"),
        profit_factor=("profit_factor", "mean"),
        return_pct=("return_pct", "mean"),
        trades=("trades", "mean"),
    )
    .reset_index()
)

avg_return = numeric["return_pct"].mean() if "return_pct" in numeric else None
best_row = numeric.loc[numeric["return_pct"].idxmax()] if "return_pct" in numeric and numeric["return_pct"].notna().any() else None
best_pf = numeric["profit_factor"].max() if "profit_factor" in numeric and numeric["profit_factor"].notna().any() else None

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Backtest run", len(runs))
c2.metric("Risultati", len(results))
c3.metric("Paper signal", len(paper))
c4.metric("Return medio", f"{avg_return:.2f}%" if avg_return is not None else "N/D")
c5.metric("PF massimo", f"{best_pf:.2f}" if best_pf is not None else "N/D")

if best_row is not None:
    st.success(
        f"Miglior combinazione del campione: {best_row.get('symbol', 'N/D')} · "
        f"{best_row.get('strategy', 'N/D')} · return {best_row.get('return_pct', 0):.2f}% · "
        f"PF {best_row.get('profit_factor', 0):.2f}"
    )

st.subheader("Panoramica strategie")
left, right = st.columns(2)
with left:
    fig_return = px.bar(
        summary.sort_values("return_pct", ascending=False),
        x="strategy",
        y="return_pct",
        title="Return medio per strategia",
        labels={"return_pct": "Return medio %", "strategy": "Strategia"},
    )
    fig_return.add_hline(y=0, line_dash="dot")
    st.plotly_chart(fig_return, use_container_width=True)

with right:
    fig_pf = px.bar(
        summary.sort_values("profit_factor", ascending=False),
        x="strategy",
        y="profit_factor",
        title="Profit Factor medio per strategia",
        labels={"profit_factor": "Profit Factor", "strategy": "Strategia"},
    )
    fig_pf.add_hline(y=1, line_dash="dot")
    st.plotly_chart(fig_pf, use_container_width=True)

st.subheader("Mappa ticker × strategia")
if {"symbol", "strategy", "return_pct"}.issubset(numeric.columns):
    heat = numeric.pivot_table(index="symbol", columns="strategy", values="return_pct", aggfunc="mean")
    if not heat.empty:
        fig_heat = px.imshow(
            heat,
            text_auto=".1f",
            aspect="auto",
            title="Return % per ticker e strategia",
            labels={"x": "Strategia", "y": "Ticker", "color": "Return %"},
        )
        st.plotly_chart(fig_heat, use_container_width=True)

st.subheader("Qualità del setup")
if {"win_rate", "profit_factor", "return_pct", "trades", "symbol", "strategy"}.issubset(numeric.columns):
    scatter = numeric.dropna(subset=["win_rate", "profit_factor", "return_pct"]).copy()
    if not scatter.empty:
        fig_scatter = px.scatter(
            scatter,
            x="win_rate",
            y="profit_factor",
            size="trades",
            hover_name="symbol",
            hover_data=["strategy", "return_pct", "trades"],
            title="Win rate vs Profit Factor",
            labels={"win_rate": "Win rate %", "profit_factor": "Profit Factor"},
        )
        fig_scatter.add_hline(y=1, line_dash="dot")
        st.plotly_chart(fig_scatter, use_container_width=True)

st.subheader("Top / Bottom combinazioni")
col_top, col_bottom = st.columns(2)
rank_cols = [c for c in ["symbol", "strategy", "trades", "win_rate", "profit_factor", "return_pct"] if c in numeric]
with col_top:
    st.markdown("**Top 5 per return**")
    st.dataframe(
        numeric.sort_values("return_pct", ascending=False)[rank_cols].head(5),
        use_container_width=True,
        hide_index=True,
    )
with col_bottom:
    st.markdown("**Bottom 5 per return**")
    st.dataframe(
        numeric.sort_values("return_pct", ascending=True)[rank_cols].head(5),
        use_container_width=True,
        hide_index=True,
    )

with st.expander("Dettaglio medio per strategia", expanded=False):
    st.dataframe(summary.sort_values("return_pct", ascending=False), use_container_width=True, hide_index=True)

with st.expander("Tutti i risultati", expanded=False):
    display = [c for c in ["created_at", "symbol", "strategy", "trades", "win_rate", "profit_factor", "return_pct", "data_status"] if c in numeric]
    st.dataframe(numeric[display], use_container_width=True, hide_index=True)

st.subheader("Paper signals")
if paper.empty:
    st.info("Nessun paper signal attivo.")
else:
    pcols = [c for c in ["created_at", "signal_date", "symbol", "strategy", "score", "price", "proposed_entry", "proposed_stop", "proposed_target", "status"] if c in paper]
    st.dataframe(paper[pcols], use_container_width=True, hide_index=True)
