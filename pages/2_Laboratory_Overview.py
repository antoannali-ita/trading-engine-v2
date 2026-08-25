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
    entry_cost,
    estimated_exit_cost,
    open_net_pnl,
    open_price_pnl,
)

try:
    from dashboard import data_access
except ModuleNotFoundError:
    import dashboard.data_access as data_access

st.set_page_config(page_title="Laboratory Overview", page_icon="🔬", layout="wide")


def j(v: Any) -> dict:
    if isinstance(v, dict):
        return v
    try:
        return json.loads(str(v)) if v else {}
    except Exception:
        return {}


def n(v: Any) -> float | None:
    try:
        return float(v) if v is not None else None
    except Exception:
        return None


def _extract_close(data: pd.DataFrame, ticker: str, count: int) -> float | None:
    try:
        if data is None or data.empty:
            return None
        series = data["Close"].dropna() if count == 1 else data[(ticker, "Close")].dropna()
        return float(series.iloc[-1]) if not series.empty else None
    except Exception:
        return None


@st.cache_data(ttl=60, show_spinner=False)
def market_prices(tickers: tuple[str, ...]) -> dict[str, tuple[float, str]]:
    if not tickers:
        return {}
    out: dict[str, tuple[float, str]] = {}
    try:
        intraday = yf.download(list(tickers), period="1d", interval="1m", auto_adjust=False, progress=False, group_by="ticker", threads=True)
        for ticker in tickers:
            px = _extract_close(intraday, ticker, len(tickers))
            if px is not None:
                out[ticker] = (px, "YAHOO 1M")
    except Exception:
        pass
    missing = tuple(t for t in tickers if t not in out)
    if missing:
        try:
            daily = yf.download(list(missing), period="5d", interval="1d", auto_adjust=False, progress=False, group_by="ticker", threads=True)
            for ticker in missing:
                px = _extract_close(daily, ticker, len(missing))
                if px is not None:
                    out[ticker] = (px, "YAHOO CLOSE")
        except Exception:
            pass
    return out


def effective_price(row: dict[str, Any], live: dict[str, tuple[float, str]]) -> tuple[float | None, str]:
    status = str(row.get("status") or "").upper()
    if status == "CLOSED":
        return n(row.get("exit_price")) or n(row.get("last_price")), "CLOSED"
    ticker = str(row.get("symbol") or "").upper()
    if ticker in live:
        return live[ticker]
    db = n(row.get("last_price"))
    if db is not None:
        return db, "DB FALLBACK"
    return n(row.get("entry_price")), "ENTRY FALLBACK"


def tier_of(row: dict[str, Any]) -> str:
    d = j(row.get("details"))
    policy = j(d.get("paper_policy"))
    return str(d.get("paper_tier") or policy.get("tier") or "N/D")


def open_status(current: float | None, stop: float | None, tp1: float | None, tp2: float | None, raw_status: str) -> str:
    if raw_status == "TP1_HIT":
        return "TP1 HIT"
    if current is None:
        return "OPEN"
    if stop is not None and current > stop and (current - stop) / current <= 0.02:
        return "NEAR STOP"
    if tp1 is not None and current < tp1 and (tp1 - current) / current <= 0.02:
        return "NEAR TP1"
    if tp2 is not None and current < tp2 and (tp2 - current) / current <= 0.02:
        return "NEAR TP2"
    return "OPEN"


def fmt(frame: pd.DataFrame):
    formats = {}
    for c in frame.columns:
        if c in {"Current $", "Net P&L $", "Capital $", "Open Risk $", "Stop $"}:
            formats[c] = "{:.2f}"
        elif "%" in c:
            formats[c] = "{:.2f}%"
        elif pd.api.types.is_float_dtype(frame[c]):
            formats[c] = "{:.2f}"
    return frame.style.format(formats, na_rep="-")


@st.cache_data(ttl=60, show_spinner=False)
def load_positions():
    return data_access.lab_paper_positions(10000)


st.title("🔬 Laboratory · Live Overview")
st.caption("Executive paper-trading view: how the Laboratory is doing right now. PAPER only; no real broker orders are generated here.")

with st.sidebar:
    st.markdown("## How to read this page")
    st.markdown(
        f"**Open Net P&L** subtracts only costs already incurred at entry. Estimated exit costs are not used to label an open trade as profit/loss.\n\n"
        f"**Current cost model:** ${CURRENT_COMMISSION_PER_SIDE:.2f} per side + {SLIPPAGE_BPS:.0f} bps slippage.\n\n"
        f"**Future discount scenario:** ${DISCOUNT_COMMISSION_PER_SIDE:.2f} per side.\n\n"
        "**Open Risk** is the remaining downside from current price to the stored stop.\n\n"
        "Status values are derived only from implemented states and stored Stop/TP levels."
    )

try:
    positions = load_positions()
except Exception as exc:
    st.error(f"Unable to read Laboratory positions: {type(exc).__name__}: {exc}")
    st.stop()

if not positions:
    st.info("No paper positions are available yet.")
    st.stop()

open_pos = [p for p in positions if str(p.get("status") or "").upper() in {"OPEN", "TP1_HIT"}]
closed_pos = [p for p in positions if str(p.get("status") or "").upper() == "CLOSED"]
open_symbols = tuple(sorted({str(p.get("symbol") or "").upper() for p in open_pos if p.get("symbol")}))
live = market_prices(open_symbols)

rows: list[dict[str, Any]] = []
capital_deployed = 0.0
open_risk_total = 0.0
open_net_total = 0.0
for p in open_pos:
    ticker = str(p.get("symbol") or "").upper()
    entry = n(p.get("entry_price"))
    qty = n(p.get("qty"))
    current, source = effective_price(p, live)
    stop = n(p.get("stop_current")) or n(p.get("stop_initial"))
    tp1 = n(p.get("tp1"))
    tp2 = n(p.get("tp2"))
    capital = (entry * qty) if entry is not None and qty is not None else None
    price_pnl = open_price_pnl(entry, current, qty)
    net = open_net_pnl(entry, current, qty)
    net_pct = (net / capital * 100.0) if net is not None and capital else None
    risk = max((current - stop) * qty, 0.0) if None not in (current, stop, qty) else None
    risk_pct = ((current - stop) / current * 100.0) if current and stop is not None else None
    if capital is not None:
        capital_deployed += capital
    if risk is not None:
        open_risk_total += risk
    if net is not None:
        open_net_total += net
    rows.append({
        "Ticker": ticker,
        "Strategy": p.get("strategy"),
        "Tier": tier_of(p),
        "Current $": current,
        "Net P&L $": net,
        "Net %": net_pct,
        "Capital $": capital,
        "Stop $": stop,
        "Risk to Stop %": risk_pct,
        "Open Risk $": risk,
        "Status": open_status(current, stop, tp1, tp2, str(p.get("status") or "").upper()),
        "Source": source,
        "Price P&L $": price_pnl,
        "Entry Cost $": entry_cost(entry, qty),
        "Est. Exit Cost $": estimated_exit_cost(current, qty),
    })

closed_net_values = []
wins = 0
for p in closed_pos:
    entry = n(p.get("entry_price"))
    exit_price = n(p.get("exit_price")) or n(p.get("last_price"))
    qty = n(p.get("qty"))
    value = closed_net_pnl(entry, exit_price, qty)
    if value is not None:
        closed_net_values.append(value)
        wins += int(value > 0)
realized_total = sum(closed_net_values)
win_rate = 100.0 * wins / len(closed_net_values) if closed_net_values else None

k = st.columns(6)
k[0].metric("Open Positions", len(open_pos))
k[1].metric("Capital Deployed", f"${capital_deployed:,.2f}")
k[2].metric("Open Net P&L", f"${open_net_total:,.2f}")
k[3].metric("Open Risk", f"${open_risk_total:,.2f}")
k[4].metric("Realized Net P&L", f"${realized_total:,.2f}")
k[5].metric("Win Rate", f"{win_rate:.2f}%" if win_rate is not None else "N/D")

st.subheader("Open Paper Positions")
open_df = pd.DataFrame(rows)
if open_df.empty:
    st.info("No open paper positions.")
else:
    shown = open_df[["Ticker", "Strategy", "Tier", "Current $", "Net P&L $", "Net %", "Risk to Stop %", "Open Risk $", "Status"]]
    st.dataframe(fmt(shown), width="stretch", hide_index=True)
    with st.expander("Cost audit · entry costs vs estimated exit costs"):
        audit = open_df[["Ticker", "Source", "Price P&L $", "Entry Cost $", "Est. Exit Cost $", "Net P&L $"]]
        st.dataframe(fmt(audit), width="stretch", hide_index=True)
        st.caption("Open Net P&L uses only entry costs already incurred. Estimated exit costs are shown separately and are not used for the open status badge.")

st.subheader("Strategy Snapshot")
if not open_df.empty:
    s = open_df.groupby("Strategy", dropna=False).agg(
        Open=("Ticker", "count"),
        Capital=("Capital $", "sum"),
        Net_PnL=("Net P&L $", "sum"),
        Avg_Return=("Net %", "mean"),
        Open_Risk=("Open Risk $", "sum"),
    ).reset_index().rename(columns={"Capital": "Capital $", "Net_PnL": "Net P&L $", "Avg_Return": "Avg Return %", "Open_Risk": "Open Risk $"})
    st.dataframe(fmt(s.sort_values("Net P&L $", ascending=False)), width="stretch", hide_index=True)

st.caption("Question answered by this page: How is the Laboratory doing right now?")
st.caption(f"Updated: {datetime.now().astimezone().strftime('%d/%m/%Y %H:%M:%S %Z')}")
