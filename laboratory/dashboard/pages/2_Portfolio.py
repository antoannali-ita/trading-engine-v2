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
from lab.settings import CAPITAL_TOTAL_BASE, MAX_POSITION_USD, USA_COMMISSION_USD
from lab.ui import apply_theme, company_name, fmt_money, fmt_pct, page_header

st.set_page_config(page_title="Trading Lab | Portfolio", layout="wide", page_icon="💼")
require_dashboard_auth()
apply_theme()
page_header(
    "Portfolio & Watchlist",
    "Posizioni reali sincronizzate, capitale, alert e livelli da sorvegliare. Nessun segnale viene spacciato per posizione aperta.",
    eyebrow="RISK · POSITIONS · ALERTS",
)

try:
    trades = load_trades()
    watchlist = load_watchlist()
except Exception as exc:
    st.error(str(exc))
    st.stop()

open_trades = trades.copy()
if not trades.empty and "trade_status" in trades:
    open_trades = trades[trades["trade_status"].fillna("").astype(str).str.upper().isin(["OPEN", "ACTIVE", "PARTIAL"])]

# The trades table stores qty and entry_price, not a redundant capital column.
def position_value(frame: pd.DataFrame) -> pd.Series:
    if frame.empty or "qty" not in frame or "entry_price" not in frame:
        return pd.Series(dtype=float)
    qty = pd.to_numeric(frame["qty"], errors="coerce")
    entry = pd.to_numeric(frame["entry_price"], errors="coerce")
    return qty * entry

open_values = position_value(open_trades)
capital_open = float(open_values.fillna(0).sum()) if len(open_values) else None
net_pnl = pd.to_numeric(trades.get("net_pnl"), errors="coerce").fillna(0).sum() if not trades.empty and "net_pnl" in trades else None
active_alerts = len(watchlist) if not watchlist.empty else 0

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Capitale base", f"{CAPITAL_TOTAL_BASE:,.0f}", help="Capitale di riferimento del progetto. EUR/USD non vengono convertiti automaticamente.")
c2.metric("Max posizione USA", fmt_money(MAX_POSITION_USD))
c3.metric("Posizioni reali", len(open_trades))
c4.metric("Capitale investito", fmt_money(capital_open) if capital_open is not None else "N/D")
c5.metric("P&L registrato", fmt_money(net_pnl) if net_pnl is not None else "N/D")
c6.metric("Alert attivi", active_alerts)

st.caption(f"Commissione USA configurata: {fmt_money(USA_COMMISSION_USD)} per operazione. La liquidità Fineco reale resta N/D finché non viene sincronizzato anche il cash ledger.")

st.markdown("### Posizioni reali")
if trades.empty:
    st.warning(
        "Nessuna posizione reale sincronizzata. Il Master Scan ora può importarle dal secret "
        "`PORTFOLIO_POSITIONS_JSON`; se quel secret è vuoto o non contiene posizioni valide, questa sezione resta correttamente a zero."
    )
    st.caption("I BUY/PRE-BUY non vengono trasformati automaticamente in posizioni reali. Le simulazioni sono gestite separatamente dal Paper Portfolio.")
else:
    display = trades.copy()
    if "ticker" in display:
        display.insert(display.columns.get_loc("ticker") + 1, "azienda", display["ticker"].map(company_name))
    if {"qty", "entry_price"}.issubset(display.columns):
        display["capitale"] = position_value(display).map(fmt_money)
    for col in ["entry_price", "stop_initial", "stop_current", "tp1", "tp2", "exit_price", "gross_pnl", "net_pnl", "commission_entry", "commission_exit"]:
        if col in display:
            display[col] = display[col].map(fmt_money)
    if "return_pct" in display:
        display["return_pct"] = display["return_pct"].map(fmt_pct)
    preferred = ["ticker", "azienda", "market", "trade_status", "qty", "capitale", "entry_price", "stop_current", "tp1", "tp2", "exit_price", "gross_pnl", "net_pnl", "return_pct", "entry_date", "exit_date", "exit_reason"]
    cols = [c for c in preferred if c in display.columns]
    st.dataframe(display[cols], use_container_width=True, hide_index=True)

    if len(open_values):
        breaches = open_trades[open_values > MAX_POSITION_USD]
        if not breaches.empty:
            names = ", ".join(breaches["ticker"].astype(str).tolist()) if "ticker" in breaches else str(len(breaches))
            st.error(f"Posizioni sopra il limite {fmt_money(MAX_POSITION_USD)}: {names}")

st.markdown("### Watchlist / Alert")
if watchlist.empty:
    st.warning(
        "Nessun alert attivo ricevuto. Dal prossimo Master Scan la persistenza Core crea automaticamente la watchlist "
        "per WATCH / WAIT / PRE-BUY / BUY LIMIT / BUY NOW e monitora il relativo livello di entry/trigger."
    )
else:
    display = watchlist.copy()
    if "ticker" in display:
        display.insert(display.columns.get_loc("ticker") + 1, "azienda", display["ticker"].map(company_name))
    if "alert_price" in display:
        display["alert_price"] = display["alert_price"].map(fmt_money)
    preferred = ["ticker", "azienda", "market", "status", "alert_type", "alert_price", "reason", "created_at", "expires_at"]
    cols = [c for c in preferred if c in display.columns]
    st.dataframe(display[cols], use_container_width=True, hide_index=True)

st.caption("Fonte posizioni: snapshot esplicito del portafoglio. Fonte watchlist: Master Scan Core. Nessun ordine automatico viene inviato a Fineco.")
