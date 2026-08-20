import sys
from pathlib import Path

import pandas as pd
import streamlit as st

LAB_ROOT = Path(__file__).resolve().parents[2]
SRC = LAB_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from lab.data import load_signals

st.set_page_config(page_title="Trading Lab | Signals", layout="wide")
st.title("Signals")

try:
    signals = load_signals()
except Exception as exc:
    st.error(str(exc))
    st.stop()

if signals.empty:
    st.info("Nessun segnale nel database.")
    st.stop()

c1, c2, c3 = st.columns(3)
markets = sorted(signals["market"].dropna().unique().tolist()) if "market" in signals else []
statuses = sorted(signals["status"].dropna().unique().tolist()) if "status" in signals else []
horizons = sorted(signals["horizon"].dropna().unique().tolist()) if "horizon" in signals else []
market = c1.multiselect("Mercato", markets, default=markets)
status = c2.multiselect("Stato", statuses, default=statuses)
horizon = c3.multiselect("Horizon", horizons, default=horizons)

view = signals.copy()
if market:
    view = view[view["market"].isin(market)]
if status:
    view = view[view["status"].isin(status)]
if horizon:
    view = view[view["horizon"].isin(horizon)]

if "ticker" in view:
    view["TradingView"] = view.apply(
        lambda r: f"https://www.tradingview.com/chart/?symbol={'NASDAQ' if r.get('market') == 'USA' else 'MIL'}:{r.get('ticker')}",
        axis=1,
    )

preferred = [
    "created_at", "market", "ticker", "horizon", "status", "decision", "price",
    "score_total", "setup", "trigger", "entry", "buy_range_low", "buy_range_high",
    "max_buy", "stop", "tp1", "tp2", "rr_net_tp1", "rr_net_tp2", "earnings_date",
    "data_quality", "TradingView"
]
cols = [c for c in preferred if c in view.columns]

st.caption(f"{len(view)} segnali")
st.dataframe(
    view[cols],
    use_container_width=True,
    hide_index=True,
    column_config={"TradingView": st.column_config.LinkColumn("Chart", display_text="Apri")},
)

st.subheader("Dettaglio ticker")
tickers = sorted(view["ticker"].dropna().unique().tolist()) if "ticker" in view else []
if tickers:
    ticker = st.selectbox("Ticker", tickers)
    detail = view[view["ticker"] == ticker].head(1)
    st.dataframe(detail.T, use_container_width=True)
