import sys
from pathlib import Path

import pandas as pd
import streamlit as st

LAB_ROOT = Path(__file__).resolve().parents[2]
SRC = LAB_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from lab.auth import require_dashboard_auth
from lab.data import load_trades, load_watchlist
from lab.ui import apply_theme, page_header

st.set_page_config(page_title="Trading Lab | Portfolio", layout="wide", page_icon="💼")
require_dashboard_auth()
apply_theme()
page_header(
    "Portfolio & Watchlist",
    "Posizioni, alert e livelli da sorvegliare. Qui il focus è il rischio reale, non il fascino teorico del ticker.",
    eyebrow="RISK · POSITIONS · ALERTS",
)

try:
    trades = load_trades()
    watchlist = load_watchlist()
except Exception as exc:
    st.error(str(exc))
    st.stop()

open_trades = trades
if not trades.empty and "trade_status" in trades:
    open_trades = trades[trades["trade_status"].fillna("").str.upper().isin(["OPEN", "ACTIVE", "PARTIAL"])]

capital_open = pd.to_numeric(open_trades.get("capital"), errors="coerce").fillna(0).sum() if not open_trades.empty and "capital" in open_trades else None
net_pnl = pd.to_numeric(trades.get("net_pnl"), errors="coerce").fillna(0).sum() if not trades.empty and "net_pnl" in trades else None

c1, c2, c3, c4 = st.columns(4)
c1.metric("Posizioni aperte", len(open_trades))
c2.metric("Watchlist attiva", len(watchlist))
c3.metric("Capitale aperto", f"${capital_open:,.0f}" if capital_open is not None else "N/D")
c4.metric("P&L netto registrato", f"${net_pnl:,.0f}" if net_pnl is not None else "N/D")

st.markdown("### Posizioni")
if trades.empty:
    st.info("Nessuna operazione reale registrata.")
else:
    preferred = ["ticker", "market", "trade_status", "qty", "entry_price", "stop_current", "tp1", "tp2", "exit_price", "gross_pnl", "net_pnl", "return_pct", "entry_date", "exit_date", "exit_reason"]
    cols = [c for c in preferred if c in trades.columns]
    st.dataframe(trades[cols], use_container_width=True, hide_index=True)

st.markdown("### Watchlist / Alert")
if watchlist.empty:
    st.info("Nessun alert attivo nel database.")
else:
    preferred = ["ticker", "market", "status", "alert_type", "alert_price", "reason", "created_at", "expires_at"]
    cols = [c for c in preferred if c in watchlist.columns]
    st.dataframe(watchlist[cols], use_container_width=True, hide_index=True)

st.caption("La pagina riflette solo posizioni e alert già registrati nel database. Non invia ordini e non sostituisce Fineco.")
