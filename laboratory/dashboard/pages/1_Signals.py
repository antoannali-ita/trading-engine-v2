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
from lab.data import load_signals
from lab.ui import apply_theme, candidate_title, company_name, fmt_money, fmt_rr, fmt_score, fmt_status, fmt_trigger, localize_table, page_header, trigger_class

st.set_page_config(page_title="Trading Lab | Core Opportunities", layout="wide", page_icon="🎯")
require_dashboard_auth()
apply_theme()
page_header(
    "Core Opportunities",
    "Vista operativa dei segnali Core. Filtra e confronta score, R/R e setup senza ricalcolare la logica del motore.",
    eyebrow="CORE · SIGNALS · DECISION SUPPORT",
)

try:
    signals = load_signals()
except Exception as exc:
    st.error(str(exc))
    st.stop()

if signals.empty:
    st.info("No Core signals in the database. The Laboratory can still have its own research results.")
    st.stop()

for col in ["score_total", "price", "entry", "max_buy", "stop", "tp1", "tp2", "rr_net_tp1", "rr_net_tp2"]:
    if col in signals:
        signals[col] = pd.to_numeric(signals[col], errors="coerce")

markets = sorted(signals["market"].dropna().unique().tolist()) if "market" in signals else []
statuses = sorted(signals["status"].dropna().unique().tolist()) if "status" in signals else []
horizons = sorted(signals["horizon"].dropna().unique().tolist()) if "horizon" in signals else []

with st.container(border=True):
    c1, c2, c3, c4 = st.columns(4)
    market = c1.multiselect("Market", markets, default=markets)
    status = c2.multiselect("Status", statuses, default=statuses, format_func=fmt_status)
    horizon = c3.multiselect("Horizon", horizons, default=horizons)
    min_score = c4.slider("Minimum Score", 0, 100, 0, help="Display filter only; it does not modify the engine score.")

view = signals.copy()
if market:
    view = view[view["market"].isin(market)]
if status:
    view = view[view["status"].isin(status)]
if horizon:
    view = view[view["horizon"].isin(horizon)]
if "score_total" in view:
    view = view[view["score_total"].fillna(0) >= min_score]
    view = view.sort_values("score_total", ascending=False)

operational = {"BUY NOW", "BUY LIMIT", "PRE-BUY", "PRE_BUY", "PRE_BUY_HIGH", "SHADOW_BUY"}
state = view.get("decision", pd.Series(index=view.index, dtype=object)).fillna("").astype(str).str.upper()
status_state = view.get("status", pd.Series(index=view.index, dtype=object)).fillna("").astype(str).str.upper()
active_mask = state.isin(operational) | status_state.isin(operational)

k1, k2, k3, k4 = st.columns(4)
k1.metric("Filtered Signals", len(view))
k2.metric("Operational", int(active_mask.sum()), help="BUY NOW / BUY LIMIT / PRE-BUY / PRE-BUY HIGH / SHADOW BUY")
k3.metric("Average Score", fmt_score(view["score_total"].mean()) if "score_total" in view and view["score_total"].notna().any() else "N/D")
k4.metric("Average Net R/R TP2", fmt_rr(view["rr_net_tp2"].mean()) if "rr_net_tp2" in view and view["rr_net_tp2"].notna().any() else "N/D")

st.markdown("### Highlighted Candidates")
active = view[active_mask].head(6)
if active.empty:
    st.info("No operational candidate with the current filters.")
else:
    cols = st.columns(3, gap="small")
    for idx, (_, row) in enumerate(active.iterrows()):
        with cols[idx % 3]:
            with st.container(border=True):
                row_company = row.get("company_name") if "company_name" in row.index else None
                st.markdown(f'<div class="candidate-title">{candidate_title(row.get("ticker"), row_company)}</div>', unsafe_allow_html=True)
                status_text = fmt_status(row.get("status", ""))
                setup_text = str(row.get("setup", "N/D")).replace("_", " ")
                st.markdown(f'<div class="candidate-state">{status_text} · {setup_text}</div>', unsafe_allow_html=True)
                a, b, c = st.columns([1, 1, 1.15], gap="small")
                a.metric("Score", fmt_score(row.get("score_total")))
                b.metric("Net R/R", fmt_rr(row.get("rr_net_tp2")))
                trigger = fmt_trigger(row.get("trigger"))
                with c:
                    st.caption("Trigger")
                    st.markdown(f'<span class="trigger-badge {trigger_class(trigger)}">{trigger}</span>', unsafe_allow_html=True)
                st.markdown(
                    f'<div class="candidate-detail"><b>Entry / Max Buy:</b> {fmt_money(row.get("entry"))} / {fmt_money(row.get("max_buy"))}<br>'
                    f'<b>Stop:</b> {fmt_money(row.get("stop"))} · <b>TP2:</b> {fmt_money(row.get("tp2"))}<br>'
                    f'<span style="opacity:.76">Data Quality: {row.get("data_quality", "N/D")} · Earnings: {row.get("earnings_date", "N/D")}</span></div>',
                    unsafe_allow_html=True,
                )

left, right = st.columns(2)
with left:
    if "score_total" in view and view["score_total"].notna().any():
        fig = px.histogram(view, x="score_total", nbins=15, title="Score Distribution")
        fig.update_layout(height=330, margin=dict(l=10, r=10, t=42, b=10), xaxis_title="Score")
        st.plotly_chart(fig, use_container_width=True)
with right:
    if "status" in view:
        counts = view["status"].fillna("N/D").map(fmt_status).value_counts().rename_axis("Status").reset_index(name="Count")
        fig = px.bar(counts, x="Status", y="Count", text="Count", title="Signals by Status")
        fig.update_layout(height=330, margin=dict(l=10, r=10, t=42, b=10), xaxis_title=None, yaxis_title=None)
        st.plotly_chart(fig, use_container_width=True)

if "ticker" in view:
    view["company_name_display"] = view.apply(lambda r: company_name(r.get("ticker"), r.get("company_name") if "company_name" in view.columns else None), axis=1)
    view["TradingView"] = view["ticker"].map(lambda t: f"https://www.tradingview.com/chart/?symbol={t}")

formatted = view.copy()
for col in ["price", "entry", "buy_range_low", "buy_range_high", "max_buy", "stop", "tp1", "tp2"]:
    if col in formatted:
        formatted[col] = formatted[col].map(fmt_money)
for col in ["rr_net_tp1", "rr_net_tp2"]:
    if col in formatted:
        formatted[col] = formatted[col].map(fmt_rr)
if "score_total" in formatted:
    formatted["score_total"] = formatted["score_total"].map(fmt_score)

preferred = ["created_at", "market", "ticker", "company_name_display", "horizon", "status", "decision", "price", "score_total", "setup", "trigger", "entry", "buy_range_low", "buy_range_high", "max_buy", "stop", "tp1", "tp2", "rr_net_tp1", "rr_net_tp2", "earnings_date", "data_quality", "TradingView"]
cols = [c for c in preferred if c in formatted.columns]
with st.expander("Full Table", expanded=False):
    localized = localize_table(formatted[cols])
    st.dataframe(localized, use_container_width=True, hide_index=True, column_config={"Company": st.column_config.TextColumn("Company"), "TradingView": st.column_config.LinkColumn("Chart", display_text="Open")})

st.caption("Scores and statuses are engine outputs. This page organizes them; it does not recalculate them.")
