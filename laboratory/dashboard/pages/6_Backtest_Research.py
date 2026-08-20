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
from lab.ui import STRATEGY_INFO, apply_theme, page_header, render_strategy_card, strategy_health

st.set_page_config(page_title="Strategy Lab", layout="wide", page_icon="🧪")
require_dashboard_auth()
apply_theme()
page_header(
    "Strategy Lab",
    "Capisci quali strategie stanno funzionando, quanto è solido il campione e su quali segnali si basano. Hover su ⓘ per una spiegazione rapida.",
    eyebrow="RESEARCH · BACKTEST · PAPER",
)

try:
    runs = load_lab_backtest_runs()
    results = load_lab_backtest_results()
    paper = load_lab_paper_signals()
except Exception as exc:
    st.error("Tabelle research non disponibili. Eseguire laboratory/sql/02_lab_research_tables.sql su Supabase.")
    st.code(str(exc))
    st.stop()

if results.empty:
    c1, c2, c3 = st.columns(3)
    c1.metric("Backtest run", len(runs))
    c2.metric("Risultati", 0)
    c3.metric("Paper signal", len(paper))
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
        trades=("trades", "sum"),
    )
    .reset_index()
)
summary["health"] = summary.apply(lambda r: strategy_health(r.get("profit_factor"), r.get("trades"), r.get("return_pct"))[0], axis=1)

avg_return = numeric["return_pct"].mean() if "return_pct" in numeric else None
best_row = numeric.loc[numeric["return_pct"].idxmax()] if "return_pct" in numeric and numeric["return_pct"].notna().any() else None
best_pf = numeric["profit_factor"].max() if "profit_factor" in numeric and numeric["profit_factor"].notna().any() else None
robust_count = int((summary["health"] == "Robusta").sum())

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Backtest run", len(runs), help="Sessioni di ricerca salvate nel database.")
c2.metric("Strategie testate", summary["strategy"].nunique())
c3.metric("Strategie robuste", robust_count, help="Etichetta euristica basata su campione, Profit Factor e rendimento. Non è una promozione automatica al Core.")
c4.metric("Return medio", f"{avg_return:.2f}%" if avg_return is not None else "N/D")
c5.metric("PF massimo", f"{best_pf:.2f}" if best_pf is not None else "N/D", help="Profit Factor = profitti lordi / perdite lorde. Va letto insieme a numerosità e OOS.")

if best_row is not None:
    st.info(
        f"**Miglior combinazione del campione:** {best_row.get('symbol', 'N/D')} · "
        f"{STRATEGY_INFO.get(best_row.get('strategy'), {}).get('label', best_row.get('strategy', 'N/D'))} · "
        f"return {best_row.get('return_pct', 0):.2f}% · PF {best_row.get('profit_factor', 0):.2f}. "
        "Non equivale a 'migliore strategia': può essere concentrazione su un singolo ticker."
    )

st.markdown("### Le strategie, in parole umane")
strategy_rows = {row["strategy"]: row for _, row in summary.iterrows()}
ordered = ["trend_continuation", "cross_sectional_momentum", "short_term_reversal", "defensive_low_vol_quality", "pead", "event_driven_mean_reversion", "quality_value_rerating", "macro_intermarket"]
for i in range(0, len(ordered), 2):
    cols = st.columns(2)
    for col, strategy in zip(cols, ordered[i:i+2]):
        with col:
            render_strategy_card(strategy, strategy_rows.get(strategy))

st.markdown("### Come stanno andando")
left, right = st.columns(2)
with left:
    fig_return = px.bar(
        summary.sort_values("return_pct", ascending=False),
        x="strategy", y="return_pct", text_auto=".2f",
        title="Return medio per strategia",
        labels={"return_pct": "Return medio %", "strategy": "Strategia"},
    )
    fig_return.add_hline(y=0, line_dash="dot")
    fig_return.update_layout(height=420, margin=dict(l=10, r=10, t=50, b=10), xaxis_title=None)
    st.plotly_chart(fig_return, use_container_width=True)
with right:
    fig_pf = px.bar(
        summary.sort_values("profit_factor", ascending=False),
        x="strategy", y="profit_factor", text_auto=".2f",
        title="Profit Factor medio",
        labels={"profit_factor": "Profit Factor", "strategy": "Strategia"},
    )
    fig_pf.add_hline(y=1, line_dash="dot")
    fig_pf.add_hline(y=1.5, line_dash="dot")
    fig_pf.update_layout(height=420, margin=dict(l=10, r=10, t=50, b=10), xaxis_title=None)
    st.plotly_chart(fig_pf, use_container_width=True)

st.markdown("### Dove funzionano")
if {"symbol", "strategy", "return_pct"}.issubset(numeric.columns):
    heat = numeric.pivot_table(index="symbol", columns="strategy", values="return_pct", aggfunc="mean")
    if not heat.empty:
        fig_heat = px.imshow(heat, text_auto=".1f", aspect="auto", title="Return % · ticker × strategia", labels={"x": "Strategia", "y": "Ticker", "color": "Return %"})
        fig_heat.update_layout(height=520, margin=dict(l=10, r=10, t=50, b=10))
        st.plotly_chart(fig_heat, use_container_width=True)
        st.caption("Una strategia sana dovrebbe funzionare su più titoli e periodi, non vivere di una singola NVDA fortunata.")

st.markdown("### Robustezza del campione")
if {"win_rate", "profit_factor", "return_pct", "trades", "symbol", "strategy"}.issubset(numeric.columns):
    scatter = numeric.dropna(subset=["win_rate", "profit_factor", "return_pct"]).copy()
    if not scatter.empty:
        fig_scatter = px.scatter(
            scatter, x="win_rate", y="profit_factor", size="trades", color="return_pct",
            hover_name="symbol", hover_data=["strategy", "return_pct", "trades"],
            title="Win rate vs Profit Factor · dimensione bolla = numero trade",
            labels={"win_rate": "Win rate %", "profit_factor": "Profit Factor", "return_pct": "Return %"},
        )
        fig_scatter.add_hline(y=1, line_dash="dot")
        fig_scatter.update_layout(height=500, margin=dict(l=10, r=10, t=50, b=10))
        st.plotly_chart(fig_scatter, use_container_width=True)

st.markdown("### Migliori e peggiori combinazioni")
col_top, col_bottom = st.columns(2)
rank_cols = [c for c in ["symbol", "strategy", "trades", "win_rate", "profit_factor", "return_pct"] if c in numeric]
with col_top:
    st.markdown("**Top 5**")
    st.dataframe(numeric.sort_values("return_pct", ascending=False)[rank_cols].head(5), use_container_width=True, hide_index=True)
with col_bottom:
    st.markdown("**Bottom 5**")
    st.dataframe(numeric.sort_values("return_pct", ascending=True)[rank_cols].head(5), use_container_width=True, hide_index=True)

with st.expander("Metriche medie per strategia"):
    st.dataframe(summary.sort_values("return_pct", ascending=False), use_container_width=True, hide_index=True)
with st.expander("Tutti i risultati"):
    display = [c for c in ["created_at", "symbol", "strategy", "trades", "win_rate", "profit_factor", "return_pct", "data_status"] if c in numeric]
    st.dataframe(numeric[display], use_container_width=True, hide_index=True)

st.markdown("### Paper signals")
if paper.empty:
    st.info("Nessun paper signal attivo. Il Daily Lab li popolerà quando il punteggio supera la soglia configurata.")
else:
    pcols = [c for c in ["created_at", "signal_date", "symbol", "strategy", "score", "price", "proposed_entry", "proposed_stop", "proposed_target", "status"] if c in paper]
    st.dataframe(paper[pcols], use_container_width=True, hide_index=True)

st.caption("Research-only · nessuna strategia viene promossa automaticamente al Core · OOS / walk-forward restano obbligatori prima di fidarsi dei numeri.")
