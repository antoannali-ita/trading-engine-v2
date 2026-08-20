import html
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
import yfinance as yf

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

st.markdown(
    """
    <style>
    .core-kpi-row {display:grid; grid-template-columns:.72fr .72fr 1.56fr; gap:8px; margin:.42rem 0 .55rem 0;}
    .core-kpi {border:1px solid rgba(128,128,128,.20); border-radius:10px; padding:7px 9px; min-height:58px; background:rgba(128,128,128,.025);}
    .core-kpi-label {font-size:.65rem; opacity:.65; margin-bottom:3px;}
    .core-kpi-value {font-size:1rem; font-weight:760; line-height:1.18;}
    .core-trigger-box {transition:background .15s ease,border-color .15s ease;}
    .core-trigger-box.trigger-confirmed {background:rgba(34,197,94,.16);border-color:rgba(34,197,94,.36);}
    .core-trigger-box.trigger-buy {background:rgba(59,130,246,.16);border-color:rgba(59,130,246,.34);}
    .core-trigger-box.trigger-wait {background:rgba(245,158,11,.18);border-color:rgba(245,158,11,.38);}
    .core-trigger-box.trigger-invalid {background:rgba(239,68,68,.17);border-color:rgba(239,68,68,.38);}
    .core-trigger-box.trigger-na {background:rgba(148,163,184,.13);border-color:rgba(148,163,184,.28);}
    .core-trigger {font-size:.70rem; font-weight:780; line-height:1.28; overflow-wrap:anywhere; background:transparent !important;}
    .core-market-strip {margin:.12rem 0 .48rem 0; padding:6px 8px; border-radius:8px; background:rgba(59,130,246,.06); font-size:.76rem; line-height:1.35;}
    .core-day-pos {font-weight:800; color:inherit;}
    .core-day-neg {font-weight:800; color:#dc2626;}
    .core-day-flat {font-weight:800; opacity:.72;}
    .core-levels {display:grid; grid-template-columns:1fr 1fr; gap:5px 12px; font-size:.80rem; line-height:1.38; margin-top:.18rem;}
    .core-levels b {font-weight:730;}
    .core-meta {grid-column:1 / -1; padding-top:3px; margin-top:2px; border-top:1px solid rgba(128,128,128,.12); font-size:.76rem; opacity:.82;}
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(ttl=300, show_spinner=False)
def intraday_snapshot(ticker: str, market: str):
    t = str(ticker or "").strip().upper()
    m = str(market or "").strip().upper()
    symbol = t
    if m in {"ITALY", "ITA", "MIL", "MI"} and "." not in t:
        symbol = f"{t}.MI"
    try:
        hist = yf.Ticker(symbol).history(period="1d", interval="5m", auto_adjust=True)
        if hist.empty or hist["Close"].dropna().empty:
            return None, None, None, None
        current = float(hist["Close"].dropna().iloc[-1])
        day_low = float(hist["Low"].dropna().min()) if "Low" in hist and not hist["Low"].dropna().empty else None
        day_high = float(hist["High"].dropna().max()) if "High" in hist and not hist["High"].dropna().empty else None
        session_open = float(hist["Open"].dropna().iloc[0]) if "Open" in hist and not hist["Open"].dropna().empty else None
        day_pct = ((current / session_open) - 1.0) * 100.0 if session_open not in (None, 0) else None
        return current, day_low, day_high, day_pct
    except Exception:
        return None, None, None, None


def _money(value, market):
    symbol = "€" if str(market or "").upper() in {"ITALY", "ITA", "MIL", "MI"} else "$"
    return fmt_money(value, symbol=symbol)


def _day_pct_html(value) -> str:
    if value is None or pd.isna(value):
        return '<span class="core-day-flat">N/D</span>'
    cls = "core-day-neg" if float(value) < 0 else "core-day-pos" if float(value) > 0 else "core-day-flat"
    return f'<span class="{cls}">{float(value):+.2f}%</span>'


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
                ticker = row.get("ticker")
                market_value = row.get("market", "USA")
                current, day_low, day_high, day_pct = intraday_snapshot(str(ticker), str(market_value))

                st.markdown(f'<div class="candidate-title">{candidate_title(ticker, row_company)}</div>', unsafe_allow_html=True)
                status_text = fmt_status(row.get("status", ""))
                setup_text = str(row.get("setup", "N/D")).replace("_", " ")
                st.markdown(f'<div class="candidate-state">{html.escape(status_text)} · {html.escape(setup_text)}</div>', unsafe_allow_html=True)

                trigger = fmt_trigger(row.get("trigger"))
                trigger_css = trigger_class(trigger)
                st.markdown(
                    f'<div class="core-kpi-row">'
                    f'<div class="core-kpi"><div class="core-kpi-label">Score</div><div class="core-kpi-value">{fmt_score(row.get("score_total"))}</div></div>'
                    f'<div class="core-kpi"><div class="core-kpi-label">Net R/R</div><div class="core-kpi-value">{fmt_rr(row.get("rr_net_tp2"))}</div></div>'
                    f'<div class="core-kpi core-trigger-box {trigger_css}"><div class="core-kpi-label">Trigger</div><div class="core-trigger">{html.escape(trigger)}</div></div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                st.markdown(
                    f'<div class="core-market-strip"><b>Current:</b> {_money(current, market_value)} &nbsp;·&nbsp; '
                    f'<b>Min:</b> {_money(day_low, market_value)} &nbsp;·&nbsp; '
                    f'<b>Max:</b> {_money(day_high, market_value)} &nbsp;·&nbsp; '
                    f'<b>Oggi:</b> {_day_pct_html(day_pct)}</div>',
                    unsafe_allow_html=True,
                )

                st.markdown(
                    f'<div class="core-levels">'
                    f'<div><b>Entry:</b> {_money(row.get("entry"), market_value)}</div>'
                    f'<div><b>Max Buy:</b> {_money(row.get("max_buy"), market_value)}</div>'
                    f'<div><b>Stop:</b> {_money(row.get("stop"), market_value)}</div>'
                    f'<div><b>TP2:</b> {_money(row.get("tp2"), market_value)}</div>'
                    f'<div class="core-meta"><b>Data Quality:</b> {html.escape(str(row.get("data_quality", "N/D")))} &nbsp;·&nbsp; '
                    f'<b>Earnings:</b> {html.escape(str(row.get("earnings_date", "N/D")))}</div>'
                    f'</div>',
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

st.caption("Scores and statuses are engine outputs. Intraday Current/Min/Max/% Oggi are cached market-data context and do not change the Core decision.")
