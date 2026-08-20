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
from lab.data import load_lab_backtest_results, load_lab_backtest_runs, load_lab_calibration_results, load_lab_paper_signals, load_strategy_evaluations, load_strategy_variants
from lab.ui import UI_BUILD, STRATEGY_INFO, apply_theme, fmt_strategy, localize_table, page_header, render_strategy_card, strategy_health

st.set_page_config(page_title="Trading Lab | Strategy Lab", layout="wide", page_icon="🧪")
require_dashboard_auth()
apply_theme()
page_header(
    "Strategy Lab",
    "Ricerca, autocritica e genealogia delle strategie: parent strategy → variant → OOS test → reject or promote to candidate.",
    eyebrow="RESEARCH · BACKTEST · EVOLUTION",
)
st.caption(f"UI BUILD {UI_BUILD}")

try:
    runs = load_lab_backtest_runs()
    results = load_lab_backtest_results()
    paper = load_lab_paper_signals()
    calibration = load_lab_calibration_results()
except Exception as exc:
    st.error("Base research tables are not available. Check Supabase.")
    st.code(str(exc))
    st.stop()

try:
    variants = load_strategy_variants()
    evaluations = load_strategy_evaluations()
    evolution_ready = True
except Exception:
    variants = pd.DataFrame()
    evaluations = pd.DataFrame()
    evolution_ready = False

if results.empty:
    c1, c2, c3 = st.columns(3)
    c1.metric("Backtest Runs", len(runs))
    c2.metric("Results", 0)
    c3.metric("Paper Signals", len(paper))
    st.info("No saved backtest yet.")
    st.stop()

numeric = results.copy()
for col in ["win_rate", "profit_factor", "return_pct", "trades", "net_pnl"]:
    if col in numeric:
        numeric[col] = pd.to_numeric(numeric[col], errors="coerce")

summary = numeric.groupby("strategy", dropna=False).agg(win_rate=("win_rate", "mean"), profit_factor=("profit_factor", "mean"), return_pct=("return_pct", "mean"), trades=("trades", "sum")).reset_index()
summary["health"] = summary.apply(lambda r: strategy_health(r.get("profit_factor"), r.get("trades"), r.get("return_pct"))[0], axis=1)
summary["label"] = summary["strategy"].map(fmt_strategy)

avg_return = numeric["return_pct"].mean() if "return_pct" in numeric else None
best_row = numeric.loc[numeric["return_pct"].idxmax()] if "return_pct" in numeric and numeric["return_pct"].notna().any() else None
best_pf = numeric["profit_factor"].max() if "profit_factor" in numeric and numeric["profit_factor"].notna().any() else None
robust_count = int((summary["health"] == "ROBUSTA").sum())
promotable_count = int((variants.get("status", pd.Series(dtype=str)).astype(str) == "PROMOTABLE").sum()) if not variants.empty else 0

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Backtest Runs", len(runs))
c2.metric("Strategies Tested", summary["strategy"].nunique())
c3.metric("Robust Strategies", robust_count)
c4.metric("Average Return", f"{avg_return:.2f}%" if avg_return is not None else "N/D")
c5.metric("Max Profit Factor", f"{best_pf:.2f}" if best_pf is not None else "N/D")
c6.metric("Promotable Variants", promotable_count, help="Research-only: no variant is automatically promoted to Core.")

if best_row is not None:
    st.info(f"**Best sample combination:** {best_row.get('symbol', 'N/D')} · {fmt_strategy(best_row.get('strategy'))} · return {best_row.get('return_pct', 0):.2f}% · PF {best_row.get('profit_factor', 0):.2f}. This is a ticker/strategy combination, not proof of general superiority.")

st.markdown("### Quick Rankings")
left_rank, right_rank = st.columns(2)
with left_rank:
    strategy_view = summary[["label", "health", "trades", "win_rate", "profit_factor", "return_pct"]].sort_values(["return_pct", "profit_factor"], ascending=False)
    strategy_view = strategy_view.rename(columns={"label": "Strategy", "health": "Robustness", "trades": "Trades", "win_rate": "Win Rate", "profit_factor": "Profit Factor", "return_pct": "Return %"})
    st.dataframe(strategy_view, use_container_width=True, hide_index=True)
with right_rank:
    ticker_summary = numeric.groupby("symbol", dropna=False).agg(strategies=("strategy", "nunique"), trades=("trades", "sum"), avg_return=("return_pct", "mean"), median_return=("return_pct", "median"), avg_pf=("profit_factor", "mean")).reset_index().sort_values(["avg_return", "avg_pf"], ascending=False)
    ticker_display = ticker_summary.head(10).rename(columns={"symbol": "Ticker", "strategies": "Strategies", "trades": "Trades", "avg_return": "Average Return", "median_return": "Median Return", "avg_pf": "Average PF"})
    st.dataframe(ticker_display, use_container_width=True, hide_index=True)

if not ticker_summary.empty:
    fig_tickers = px.bar(ticker_summary.head(10), x="symbol", y="avg_return", text_auto=".2f", hover_data=["avg_pf", "trades", "strategies"], title="Average Return by Ticker")
    fig_tickers.add_hline(y=0, line_dash="dot")
    fig_tickers.update_layout(height=360, margin=dict(l=10, r=10, t=50, b=10), xaxis_title=None, yaxis_title="Return %")
    st.plotly_chart(fig_tickers, use_container_width=True)

st.markdown("### Strategy Cards")
strategy_rows = {}
for record in summary[["strategy", "win_rate", "profit_factor", "return_pct", "trades"]].to_dict(orient="records"):
    key = str(record.get("strategy"))
    strategy_rows[key] = {"win_rate": None if pd.isna(record.get("win_rate")) else float(record.get("win_rate")), "profit_factor": None if pd.isna(record.get("profit_factor")) else float(record.get("profit_factor")), "return_pct": None if pd.isna(record.get("return_pct")) else float(record.get("return_pct")), "trades": None if pd.isna(record.get("trades")) else float(record.get("trades"))}

ordered = ["trend_continuation", "cross_sectional_momentum", "short_term_reversal", "defensive_low_vol_quality", "pead", "event_driven_mean_reversion", "quality_value_rerating", "macro_intermarket"]
for i in range(0, len(ordered), 2):
    cols = st.columns(2)
    for col, strategy in zip(cols, ordered[i:i+2]):
        with col:
            render_strategy_card(strategy, strategy_rows.get(strategy, {}))

st.markdown("### 🧬 Strategy Evolution: PARENT → VARIANT")
st.caption("Il Laboratory può generare varianti dei parametri di execution/risk. Una variante deve dimostrare robustezza OOS su più ticker. Nessuna modifica del Core è automatica.")

if not evolution_ready:
    st.warning("Strategy Evolution code is available but Supabase evolution tables are not readable.")
elif variants.empty:
    st.info("Evolution tables are active, but no generation has been executed yet.")
else:
    v = variants.copy()
    if "status" in v:
        counts = v["status"].fillna("N/D").value_counts().rename_axis("status").reset_index(name="count")
        fig_status = px.bar(counts, x="status", y="count", text="count", title="Variant Verdicts")
        fig_status.update_layout(height=320, margin=dict(l=10, r=10, t=45, b=10), xaxis_title=None, yaxis_title="Count")
        st.plotly_chart(fig_status, use_container_width=True)
    preferred = ["parent_strategy", "generation", "status", "parameters", "mutation_reason", "promoted_to_core", "notes", "created_at"]
    st.dataframe(localize_table(v[[c for c in preferred if c in v.columns]]).head(50), use_container_width=True, hide_index=True)
    if not evaluations.empty:
        e = evaluations.copy()
        for col in ["oos_return_pct", "oos_profit_factor", "oos_trades", "oos_max_drawdown_pct", "robustness_score"]:
            if col in e:
                e[col] = pd.to_numeric(e[col], errors="coerce")
        if "robustness_score" in e:
            ranked = e.groupby("variant_id", dropna=False).agg(mean_robustness=("robustness_score", "mean"), mean_oos_return=("oos_return_pct", "mean"), mean_oos_pf=("oos_profit_factor", "mean"), mean_oos_dd=("oos_max_drawdown_pct", "mean"), symbols=("symbol", "nunique")).reset_index().sort_values(["mean_robustness", "mean_oos_return"], ascending=False)
            ranked = ranked.rename(columns={"variant_id": "Variant ID", "mean_robustness": "Average Robustness", "mean_oos_return": "Average OOS Return", "mean_oos_pf": "Average OOS PF", "mean_oos_dd": "Average OOS Drawdown", "symbols": "Tickers Tested"})
            st.markdown("#### Best Variants by Robustness")
            st.dataframe(ranked.head(15), use_container_width=True, hide_index=True)

st.markdown("### Tested Parameters & Self-Critique")
with st.container(border=True):
    p1, p2, p3, p4 = st.columns(4)
    p1.metric("Entry Score", "70 · 75 · 80")
    p2.metric("ATR Stop", "1.5 · 2.0 · 2.5×")
    p3.metric("Target R", "2.0 · 2.5 · 3.0R")
    p4.metric("Walk-Forward", "70% / 30%")

if calibration.empty:
    st.warning("No saved calibration: no parameter is considered a validated improvement.")
else:
    cal = calibration.copy()
    for col in ["entry_score", "atr_stop_mult", "target_r_multiple", "train_return_pct", "test_return_pct", "test_trades"]:
        if col in cal:
            cal[col] = pd.to_numeric(cal[col], errors="coerce")
    cols = [c for c in ["created_at", "symbol", "strategy", "entry_score", "atr_stop_mult", "target_r_multiple", "train_return_pct", "test_return_pct", "test_trades"] if c in cal.columns]
    st.dataframe(localize_table(cal[cols]).head(30), use_container_width=True, hide_index=True)

st.markdown("### Strategy Performance")
left, right = st.columns(2)
with left:
    fig_return = px.bar(summary.sort_values("return_pct", ascending=False), x="label", y="return_pct", text_auto=".2f", title="Average Return by Strategy")
    fig_return.add_hline(y=0, line_dash="dot")
    fig_return.update_layout(height=410, margin=dict(l=10, r=10, t=50, b=10), xaxis_title=None, yaxis_title="Return %")
    st.plotly_chart(fig_return, use_container_width=True)
with right:
    fig_pf = px.bar(summary.sort_values("profit_factor", ascending=False), x="label", y="profit_factor", text_auto=".2f", title="Average Profit Factor")
    fig_pf.add_hline(y=1, line_dash="dot")
    fig_pf.add_hline(y=1.5, line_dash="dot")
    fig_pf.update_layout(height=410, margin=dict(l=10, r=10, t=50, b=10), xaxis_title=None, yaxis_title="Profit Factor")
    st.plotly_chart(fig_pf, use_container_width=True)

st.markdown("### Where Strategies Work")
if {"symbol", "strategy", "return_pct"}.issubset(numeric.columns):
    heat = numeric.pivot_table(index="symbol", columns="strategy", values="return_pct", aggfunc="mean")
    if not heat.empty:
        heat = heat.rename(columns={c: fmt_strategy(c) for c in heat.columns})
        fig_heat = px.imshow(heat, text_auto=".1f", aspect="auto", title="Return % · Ticker × Strategy")
        fig_heat.update_layout(height=500, margin=dict(l=10, r=10, t=50, b=10))
        st.plotly_chart(fig_heat, use_container_width=True)

st.markdown("### Paper Signals")
if paper.empty:
    st.info("No active paper signal at the moment.")
else:
    pcols = [c for c in ["created_at", "signal_date", "symbol", "strategy", "score", "price", "proposed_entry", "proposed_stop", "proposed_target", "status"] if c in paper]
    st.dataframe(localize_table(paper[pcols]), use_container_width=True, hide_index=True)

st.caption(f"Research-only · UI BUILD {UI_BUILD} · no strategy variant is automatically promoted to Core.")
