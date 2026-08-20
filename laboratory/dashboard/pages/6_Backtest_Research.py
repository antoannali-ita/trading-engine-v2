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
from lab.data import load_lab_backtest_results, load_lab_backtest_runs, load_lab_calibration_results, load_lab_paper_signals
from lab.ui import STRATEGY_INFO, apply_theme, page_header, render_strategy_card, strategy_health

st.set_page_config(page_title="Strategy Lab", layout="wide", page_icon="🧪")
require_dashboard_auth()
apply_theme()
page_header(
    "Strategy Lab",
    "Capisci quali strategie stanno funzionando, quali titoli hanno risposto meglio e quali parametri sono stati davvero testati o selezionati.",
    eyebrow="RESEARCH · BACKTEST · PAPER",
)

try:
    runs = load_lab_backtest_runs()
    results = load_lab_backtest_results()
    paper = load_lab_paper_signals()
    calibration = load_lab_calibration_results()
except Exception as exc:
    st.error("Tabelle research non disponibili. Verifica le tabelle laboratorio su Supabase.")
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
    .agg(win_rate=("win_rate", "mean"), profit_factor=("profit_factor", "mean"), return_pct=("return_pct", "mean"), trades=("trades", "sum"))
    .reset_index()
)
summary["health"] = summary.apply(lambda r: strategy_health(r.get("profit_factor"), r.get("trades"), r.get("return_pct"))[0], axis=1)
summary["label"] = summary["strategy"].map(lambda x: STRATEGY_INFO.get(x, {}).get("label", x))

avg_return = numeric["return_pct"].mean() if "return_pct" in numeric else None
best_row = numeric.loc[numeric["return_pct"].idxmax()] if "return_pct" in numeric and numeric["return_pct"].notna().any() else None
best_pf = numeric["profit_factor"].max() if "profit_factor" in numeric and numeric["profit_factor"].notna().any() else None
robust_count = int((summary["health"] == "Robusta").sum())

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Backtest run", len(runs), help="Sessioni di ricerca salvate nel database.")
c2.metric("Strategie testate", summary["strategy"].nunique())
c3.metric("Strategie robuste", robust_count, help="Etichetta euristica: campione + Profit Factor + rendimento. Non equivale a promozione al Core.")
c4.metric("Return medio", f"{avg_return:.2f}%" if avg_return is not None else "N/D")
c5.metric("PF massimo", f"{best_pf:.2f}" if best_pf is not None else "N/D", help="Profit Factor = profitti lordi / perdite lorde.")

if best_row is not None:
    st.info(
        f"**Miglior combinazione del campione:** {best_row.get('symbol', 'N/D')} · "
        f"{STRATEGY_INFO.get(best_row.get('strategy'), {}).get('label', best_row.get('strategy', 'N/D'))} · "
        f"return {best_row.get('return_pct', 0):.2f}% · PF {best_row.get('profit_factor', 0):.2f}. "
        "È una combinazione ticker/strategia, non una prova che sia la strategia migliore in assoluto."
    )

st.markdown("### Classifiche rapide")
left_rank, right_rank = st.columns(2)
with left_rank:
    st.markdown("#### Strategie che stanno dando più soddisfazioni")
    strategy_view = summary[["label", "health", "trades", "win_rate", "profit_factor", "return_pct"]].sort_values(["return_pct", "profit_factor"], ascending=False)
    st.dataframe(strategy_view, use_container_width=True, hide_index=True)
with right_rank:
    st.markdown("#### Titoli che hanno risposto meglio nel campione")
    ticker_summary = (
        numeric.groupby("symbol", dropna=False)
        .agg(strategies=("strategy", "nunique"), trades=("trades", "sum"), avg_return=("return_pct", "mean"), median_return=("return_pct", "median"), avg_pf=("profit_factor", "mean"))
        .reset_index()
        .sort_values(["avg_return", "avg_pf"], ascending=False)
    )
    st.dataframe(ticker_summary.head(10), use_container_width=True, hide_index=True)

if not ticker_summary.empty:
    fig_tickers = px.bar(ticker_summary.head(10), x="symbol", y="avg_return", text_auto=".2f", hover_data=["avg_pf", "trades", "strategies"], title="Return medio per ticker nel campione research")
    fig_tickers.add_hline(y=0, line_dash="dot")
    fig_tickers.update_layout(height=380, margin=dict(l=10, r=10, t=50, b=10), xaxis_title=None, yaxis_title="Return medio %")
    st.plotly_chart(fig_tickers, use_container_width=True)

st.markdown("### Le strategie, in parole umane")
strategy_rows = {row["strategy"]: row for _, row in summary.iterrows()}
ordered = ["trend_continuation", "cross_sectional_momentum", "short_term_reversal", "defensive_low_vol_quality", "pead", "event_driven_mean_reversion", "quality_value_rerating", "macro_intermarket"]
for i in range(0, len(ordered), 2):
    cols = st.columns(2)
    for col, strategy in zip(cols, ordered[i:i+2]):
        with col:
            render_strategy_card(strategy, strategy_rows.get(strategy))

st.markdown("### Parametri testati e cosa abbiamo realmente cambiato")
st.caption("Questa sezione separa il grid search dalla promozione. Un parametro testato non diventa automaticamente un parametro del Core.")
with st.container(border=True):
    p1, p2, p3, p4 = st.columns(4)
    p1.metric("Entry score testati", "70 · 75 · 80", help="Soglie esplorate dal walk-forward grid.")
    p2.metric("Stop ATR testati", "1.5 · 2.0 · 2.5×")
    p3.metric("Target R testati", "2.0 · 2.5 · 3.0R")
    p4.metric("Split", "70% / 30%", help="Selezione sul train, verifica sul segmento successivo OOS.")

if calibration.empty:
    st.warning("Nessun risultato di calibrazione salvato nel database: quindi al momento **nessun parametro è stato promosso come miglioramento validato**. Il motore di calibrazione esiste, ma non confondiamo codice disponibile con evidenza statistica.")
else:
    cal = calibration.copy()
    for col in ["entry_score", "atr_stop_mult", "target_r_multiple", "train_return_pct", "test_return_pct", "test_trades"]:
        if col in cal:
            cal[col] = pd.to_numeric(cal[col], errors="coerce")
    cols = [c for c in ["created_at", "symbol", "strategy", "entry_score", "atr_stop_mult", "target_r_multiple", "train_return_pct", "test_return_pct", "test_trades"] if c in cal.columns]
    st.dataframe(cal[cols].head(30), use_container_width=True, hide_index=True)
    if {"train_return_pct", "test_return_pct"}.issubset(cal.columns):
        plot_cal = cal.dropna(subset=["train_return_pct", "test_return_pct"]).head(30).copy()
        if not plot_cal.empty:
            plot_cal["case"] = plot_cal.get("symbol", "N/D").astype(str) + " · " + plot_cal.get("strategy", "N/D").astype(str)
            melted = plot_cal.melt(id_vars="case", value_vars=["train_return_pct", "test_return_pct"], var_name="segmento", value_name="return_pct")
            fig_cal = px.bar(melted, x="case", y="return_pct", color="segmento", barmode="group", title="Train vs OOS: il controllo anti-overfit")
            fig_cal.update_layout(height=430, margin=dict(l=10, r=10, t=50, b=10), xaxis_title=None, yaxis_title="Return %")
            st.plotly_chart(fig_cal, use_container_width=True)

st.markdown("### Come stanno andando")
left, right = st.columns(2)
with left:
    fig_return = px.bar(summary.sort_values("return_pct", ascending=False), x="label", y="return_pct", text_auto=".2f", title="Return medio per strategia", labels={"return_pct": "Return medio %", "label": "Strategia"})
    fig_return.add_hline(y=0, line_dash="dot")
    fig_return.update_layout(height=420, margin=dict(l=10, r=10, t=50, b=10), xaxis_title=None)
    st.plotly_chart(fig_return, use_container_width=True)
with right:
    fig_pf = px.bar(summary.sort_values("profit_factor", ascending=False), x="label", y="profit_factor", text_auto=".2f", title="Profit Factor medio", labels={"profit_factor": "Profit Factor", "label": "Strategia"})
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
        st.caption("Una strategia sana dovrebbe funzionare su più titoli e periodi, non vivere di una singola combinazione fortunata.")

st.markdown("### Robustezza del campione")
if {"win_rate", "profit_factor", "return_pct", "trades", "symbol", "strategy"}.issubset(numeric.columns):
    scatter = numeric.dropna(subset=["win_rate", "profit_factor", "return_pct"]).copy()
    if not scatter.empty:
        fig_scatter = px.scatter(scatter, x="win_rate", y="profit_factor", size="trades", color="return_pct", hover_name="symbol", hover_data=["strategy", "return_pct", "trades"], title="Win rate vs Profit Factor · dimensione bolla = numero trade", labels={"win_rate": "Win rate %", "profit_factor": "Profit Factor", "return_pct": "Return %"})
        fig_scatter.add_hline(y=1, line_dash="dot")
        fig_scatter.update_layout(height=500, margin=dict(l=10, r=10, t=50, b=10))
        st.plotly_chart(fig_scatter, use_container_width=True)

with st.expander("Tutti i risultati"):
    display = [c for c in ["created_at", "symbol", "strategy", "trades", "win_rate", "profit_factor", "return_pct", "data_status"] if c in numeric]
    st.dataframe(numeric[display], use_container_width=True, hide_index=True)

st.markdown("### Paper signals")
if paper.empty:
    st.info("Nessun paper signal attivo. Il Daily Lab li popolerà quando il punteggio supera la soglia configurata.")
else:
    pcols = [c for c in ["created_at", "signal_date", "symbol", "strategy", "score", "price", "proposed_entry", "proposed_stop", "proposed_target", "status"] if c in paper]
    st.dataframe(paper[pcols], use_container_width=True, hide_index=True)

st.caption("Research-only · nessuna strategia o calibrazione viene promossa automaticamente al Core · OOS / walk-forward restano obbligatori.")
