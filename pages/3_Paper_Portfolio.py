from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import pandas as pd
import streamlit as st
import yfinance as yf

from common_utility.lab_cost_model import (
    CURRENT_COMMISSION_PER_SIDE,
    DISCOUNT_COMMISSION_PER_SIDE,
    SLIPPAGE_BPS,
    closed_net_pnl,
    projected_round_trip_pnl,
)

try:
    from dashboard import data_access
except ModuleNotFoundError:
    import dashboard.data_access as data_access

st.set_page_config(page_title="Paper Portfolio", page_icon="📒", layout="wide")


def j(value: Any) -> dict:
    if isinstance(value, dict):
        return value
    try:
        return json.loads(str(value)) if value else {}
    except Exception:
        return {}


def n(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except Exception:
        return None


@st.cache_data(ttl=60, show_spinner=False)
def live_prices(tickers: tuple[str, ...]) -> dict[str, float]:
    if not tickers:
        return {}
    try:
        data = yf.download(list(tickers), period="1d", interval="1m", auto_adjust=False, progress=False, group_by="ticker", threads=True)
        out: dict[str, float] = {}
        for ticker in tickers:
            try:
                series = data["Close"].dropna() if len(tickers) == 1 else data[(ticker, "Close")].dropna()
                if not series.empty:
                    out[ticker] = float(series.iloc[-1])
            except Exception:
                pass
        return out
    except Exception:
        return {}


def gross_rr(entry, stop, tp2):
    entry, stop, tp2 = n(entry), n(stop), n(tp2)
    if entry is None or stop is None or tp2 is None or entry <= stop:
        return None
    return (tp2 - entry) / (entry - stop)


def fmt_table(frame: pd.DataFrame):
    fmt: dict[str, str] = {}
    for col in frame.columns:
        if col in {"Entry", "Ideal Entry", "Current / Exit", "Notional", "Stop", "TP1", "TP2", "Projected Net P&L 12", "Projected Net P&L 9.90"}:
            fmt[col] = "{:.2f}"
        elif "%" in col:
            fmt[col] = "{:.2f}%"
        elif pd.api.types.is_float_dtype(frame[col]):
            fmt[col] = "{:.2f}"
    return frame.style.format(fmt, na_rep="-")


@st.cache_data(ttl=60, show_spinner=False)
def load_positions():
    return data_access.lab_paper_positions(10000)


st.title("📒 Paper Portfolio")
st.caption("Detailed paper-trade ledger. PAPER only; this page does not modify Production or send broker orders.")

with st.sidebar:
    st.markdown("### Page Guide")
    st.markdown(
        f"**Current modeled cost:** ${CURRENT_COMMISSION_PER_SIDE:.2f} per executed side.\n\n"
        f"**Future discount scenario:** ${DISCOUNT_COMMISSION_PER_SIDE:.2f} per side.\n\n"
        f"**Research slippage:** {SLIPPAGE_BPS:.0f} bps.\n\n"
        "Projected P&L assumes a hypothetical exit now and therefore includes both sides. The Live Overview uses only entry costs for open-trade status."
    )

try:
    positions = load_positions()
except Exception as exc:
    st.error(f"Unable to read paper portfolio: {type(exc).__name__}: {exc}")
    st.stop()

if not positions:
    st.info("No paper positions available.")
    st.stop()

open_symbols = tuple(sorted({str(p.get("symbol") or "").upper() for p in positions if str(p.get("status") or "").upper() in {"OPEN", "TP1_HIT"} and p.get("symbol")}))
market_prices = live_prices(open_symbols)

rows = []
for p in positions:
    d = j(p.get("details"))
    cost = j(d.get("cost_model"))
    status = str(p.get("status") or "N/D").upper()
    ticker = str(p.get("symbol") or "").upper()
    entry = n(p.get("entry_price"))
    qty = n(p.get("qty"))
    if status in {"OPEN", "TP1_HIT"}:
        current = market_prices.get(ticker)
        last = current if current is not None else (n(p.get("last_price")) or entry)
        source = "LIVE 1M" if current is not None else "DB FALLBACK"
    else:
        last = n(p.get("exit_price")) or n(p.get("last_price")) or entry
        source = "CLOSED"
    capital = n(p.get("capital")) or ((entry or 0) * (qty or 0))
    move_pct = ((last / entry) - 1) * 100 if last is not None and entry else None
    if status == "CLOSED":
        pnl12 = closed_net_pnl(entry, last, qty, CURRENT_COMMISSION_PER_SIDE, SLIPPAGE_BPS)
        pnl990 = closed_net_pnl(entry, last, qty, DISCOUNT_COMMISSION_PER_SIDE, SLIPPAGE_BPS)
    else:
        pnl12 = projected_round_trip_pnl(entry, last, qty, CURRENT_COMMISSION_PER_SIDE, SLIPPAGE_BPS)
        pnl990 = projected_round_trip_pnl(entry, last, qty, DISCOUNT_COMMISSION_PER_SIDE, SLIPPAGE_BPS)
    rows.append({
        "Opened": p.get("opened_at") or p.get("created_at"),
        "Ticker": ticker,
        "Strategy": p.get("strategy"),
        "Tier": d.get("paper_tier") or "N/D",
        "Status": status,
        "Entry": entry,
        "Ideal Entry": n(d.get("ideal_entry")),
        "Current / Exit": last,
        "Price Source": source,
        "Move %": move_pct,
        "Qty": qty,
        "Notional": capital,
        "Stop": n(p.get("stop_current")) or n(p.get("stop_initial")),
        "TP1": n(p.get("tp1")),
        "TP2": n(p.get("tp2")),
        "Gross R/R TP2": n(cost.get("gross_rr")) or gross_rr(entry, p.get("stop_initial"), p.get("tp2")),
        "Projected Net P&L 12": pnl12,
        "Projected Net P&L 9.90": pnl990,
        "Exit Reason": p.get("exit_reason"),
    })

df = pd.DataFrame(rows)
open_mask = df["Status"].isin(["OPEN", "TP1_HIT"])
closed_mask = df["Status"].eq("CLOSED")

m = st.columns(5)
m[0].metric("Total Positions", len(df))
m[1].metric("Open", int(open_mask.sum()))
m[2].metric("Closed", int(closed_mask.sum()))
m[3].metric("Tier C", int((df["Tier"] == "C").sum()))
m[4].metric("Strategies", df["Strategy"].nunique())

status_filter = st.multiselect("Status", sorted(df["Status"].dropna().astype(str).unique()), default=sorted(df["Status"].dropna().astype(str).unique()))
tier_filter = st.multiselect("Tier", sorted(df["Tier"].dropna().astype(str).unique()), default=sorted(df["Tier"].dropna().astype(str).unique()))
shown = df[df["Status"].astype(str).isin(status_filter) & df["Tier"].astype(str).isin(tier_filter)]
st.dataframe(fmt_table(shown), width="stretch", hide_index=True)

st.subheader("Virtual Concentration by Risk Key")
risk_rows = []
for p in positions:
    d = j(p.get("details"))
    ticker = str(p.get("symbol") or "").upper()
    entry = n(p.get("entry_price")) or 0.0
    qty = n(p.get("qty")) or 0.0
    risk_rows.append({"Risk Key": d.get("risk_key") or f"EQUITY:{ticker}", "Notional": n(p.get("capital")) or entry * qty})
risk = pd.DataFrame(risk_rows).groupby("Risk Key", as_index=False).agg(Positions=("Risk Key", "count"), Notional=("Notional", "sum"))
st.dataframe(fmt_table(risk.sort_values("Notional", ascending=False)), width="stretch", hide_index=True)

st.caption("Question answered by this page: What paper trades are actually open or closed?")
st.caption(f"Updated: {datetime.now().astimezone().strftime('%d/%m/%Y %H:%M:%S %Z')}")
