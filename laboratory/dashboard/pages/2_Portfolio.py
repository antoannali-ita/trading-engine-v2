import sys
from pathlib import Path

import streamlit as st

LAB_ROOT = Path(__file__).resolve().parents[2]
SRC = LAB_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from lab.auth import require_dashboard_auth
from lab.data import load_trades, load_watchlist

st.set_page_config(page_title="Trading Lab | Portfolio", layout="wide")
require_dashboard_auth()
st.title("Portfolio & Watchlist")

try:
    trades = load_trades()
    watchlist = load_watchlist()
except Exception as exc:
    st.error(str(exc))
    st.stop()

open_trades = trades
if not trades.empty and "trade_status" in trades:
    open_trades = trades[trades["trade_status"].fillna("").str.upper().isin(["OPEN", "ACTIVE", "PARTIAL"])]

c1, c2, c3 = st.columns(3)
c1.metric("Posizioni aperte", len(open_trades))
c2.metric("Watchlist attiva", len(watchlist))
if not open_trades.empty and "capital" in open_trades:
    c3.metric("Capitale aperto", f"{open_trades['capital'].fillna(0).sum():,.0f}")
else:
    c3.metric("Capitale aperto", "N/D")

st.subheader("Posizioni")
if trades.empty:
    st.info("Nessuna operazione reale registrata.")
else:
    preferred = [
        "ticker", "market", "trade_status", "qty", "entry_price", "stop_current",
        "tp1", "tp2", "exit_price", "gross_pnl", "net_pnl", "return_pct",
        "entry_date", "exit_date", "exit_reason"
    ]
    cols = [c for c in preferred if c in trades.columns]
    st.dataframe(trades[cols], use_container_width=True, hide_index=True)

st.subheader("Watchlist / Alert")
if watchlist.empty:
    st.info("Nessun alert attivo nel database.")
else:
    preferred = ["ticker", "market", "status", "alert_type", "alert_price", "reason", "created_at", "expires_at"]
    cols = [c for c in preferred if c in watchlist.columns]
    st.dataframe(watchlist[cols], use_container_width=True, hide_index=True)
