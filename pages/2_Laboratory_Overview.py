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

NEAR_THRESHOLD_PCT = 2.0


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


def _series(data: pd.DataFrame, ticker: str, field: str, count: int) -> pd.Series:
    if data is None or data.empty:
        return pd.Series(dtype=float)
    try:
        if count == 1:
            return data[field].dropna()
        return data[(ticker, field)].dropna()
    except Exception:
        return pd.Series(dtype=float)


@st.cache_data(ttl=60, show_spinner=False)
def market_snapshot(tickers: tuple[str, ...]) -> dict[str, dict[str, Any]]:
    if not tickers:
        return {}

    out: dict[str, dict[str, Any]] = {}
    try:
        intraday = yf.download(
            list(tickers),
            period="1d",
            interval="1m",
            auto_adjust=False,
            progress=False,
            group_by="ticker",
            threads=True,
        )
        for ticker in tickers:
            close = _series(intraday, ticker, "Close", len(tickers))
            high = _series(intraday, ticker, "High", len(tickers))
            low = _series(intraday, ticker, "Low", len(tickers))
            if not close.empty:
                out[ticker] = {
                    "current": float(close.iloc[-1]),
                    "day_low": float(low.min()) if not low.empty else None,
                    "day_high": float(high.max()) if not high.empty else None,
                    "source": "YAHOO 1M",
                }
    except Exception:
        pass

    missing = tuple(t for t in tickers if t not in out)
    if missing:
        try:
            daily = yf.download(
                list(missing),
                period="5d",
                interval="1d",
                auto_adjust=False,
                progress=False,
                group_by="ticker",
                threads=True,
            )
            for ticker in missing:
                close = _series(daily, ticker, "Close", len(missing))
                high = _series(daily, ticker, "High", len(missing))
                low = _series(daily, ticker, "Low", len(missing))
                if not close.empty:
                    out[ticker] = {
                        "current": float(close.iloc[-1]),
                        "day_low": float(low.iloc[-1]) if not low.empty else None,
                        "day_high": float(high.iloc[-1]) if not high.empty else None,
                        "source": "YAHOO DAILY",
                    }
        except Exception:
            pass
    return out


def _stored_company_name(row: dict[str, Any]) -> str | None:
    candidates = [row, j(row.get("details"))]
    keys = ("company_name", "company", "name", "shortName", "longName", "short_name", "long_name")
    for source in candidates:
        for key in keys:
            value = source.get(key) if isinstance(source, dict) else None
            if value and str(value).strip():
                return str(value).strip()
    return None


@st.cache_data(ttl=21600, show_spinner=False)
def yahoo_company_names(tickers: tuple[str, ...]) -> dict[str, str]:
    out: dict[str, str] = {}
    for ticker in tickers:
        try:
            info = yf.Ticker(ticker).get_info() or {}
            name = info.get("shortName") or info.get("longName")
            if name:
                out[ticker] = str(name)
        except Exception:
            pass
    return out


def effective_market(row: dict[str, Any], live: dict[str, dict[str, Any]]) -> dict[str, Any]:
    status = str(row.get("status") or "").upper()
    ticker = str(row.get("symbol") or "").upper()
    if status == "CLOSED":
        return {
            "current": n(row.get("exit_price")) or n(row.get("last_price")),
            "day_low": None,
            "day_high": None,
            "source": "CLOSED",
        }
    if ticker in live:
        return live[ticker]
    db = n(row.get("last_price"))
    if db is not None:
        return {"current": db, "day_low": None, "day_high": None, "source": "DB FALLBACK"}
    return {"current": n(row.get("entry_price")), "day_low": None, "day_high": None, "source": "ENTRY FALLBACK"}


def tier_of(row: dict[str, Any]) -> str:
    d = j(row.get("details"))
    policy = j(d.get("paper_policy"))
    return str(d.get("paper_tier") or policy.get("tier") or "N/D")


def open_status(current: float | None, stop: float | None, tp1: float | None, tp2: float | None, raw_status: str) -> str:
    if raw_status == "TP1_HIT":
        return "TP1 HIT"
    if current is None:
        return "OPEN"
    threshold = NEAR_THRESHOLD_PCT / 100.0
    if stop is not None and current > stop and (current - stop) / current <= threshold:
        return f"NEAR STOP · ≤{NEAR_THRESHOLD_PCT:.1f}%"
    if tp1 is not None and current < tp1 and (tp1 - current) / current <= threshold:
        return f"NEAR TP1 · ≤{NEAR_THRESHOLD_PCT:.1f}%"
    if tp2 is not None and current < tp2 and (tp2 - current) / current <= threshold:
        return f"NEAR TP2 · ≤{NEAR_THRESHOLD_PCT:.1f}%"
    return "OPEN"


def fmt(frame: pd.DataFrame):
    formats: dict[str, str] = {}
    money_cols = {
        "Entry $", "Avg Cost $", "Current $", "Day Low $", "Day High $", "Market Value $",
        "Net P&L $", "Capital $", "Open Risk $", "SL $", "TP1 $", "TP2 $",
        "Price P&L $", "Entry Cost $", "Est. Exit Cost $",
    }
    for c in frame.columns:
        if c in money_cols:
            formats[c] = "{:.2f}"
        elif "%" in c:
            formats[c] = "{:.2f}%"
        elif pd.api.types.is_float_dtype(frame[c]):
            formats[c] = "{:.2f}"
    styler = frame.style.format(formats, na_rep="-")

    def pnl_color(v: Any) -> str:
        value = n(v)
        if value is None or value == 0:
            return ""
        return "color:#15803d;font-weight:700;" if value > 0 else "color:#dc2626;font-weight:700;"

    for col in ["Net P&L $", "Net %", "Price P&L $", "Avg Return %"]:
        if col in frame.columns:
            styler = styler.map(pnl_color, subset=[col])
    return styler


@st.cache_data(ttl=60, show_spinner=False)
def load_positions():
    return data_access.lab_paper_positions(10000)


st.title("🔬 Laboratory · Live Overview")
st.caption("Executive paper-trading view: current positions, protection levels and market value. PAPER only; no real broker orders are generated here.")

with st.sidebar:
    st.markdown("## Guida · Laboratory Overview")
    with st.expander("A cosa serve", expanded=True):
        st.markdown("Questa pagina funziona come una vista portafoglio semplificata: per ogni posizione vedi **prezzo di carico, prezzo attuale, valore di mercato, minimo/massimo del giorno, stop e target**, oltre al P&L.")
    with st.expander("Come leggere la tabella principale"):
        st.markdown("**Entry $** = prezzo di ingresso paper.  \n**Avg Cost $** = prezzo medio di carico; oggi coincide con Entry perché ogni paper position nasce con un solo ingresso.  \n**Current $** = ultimo prezzo disponibile.  \n**Day Low / Day High** = minimo e massimo della seduta disponibili da Yahoo.  \n**Market Value $** = Current × Qty.  \n**SL / TP1 / TP2** = livelli di protezione e obiettivi correnti.")
    with st.expander("Come leggere utile/perdita e rischio"):
        st.markdown("**Verde** = valore positivo. **Rosso** = valore negativo.  \n**Open Net P&L** sottrae solo i costi già sostenuti all'ingresso.  \n**Risk to Stop %** indica quanto dista il prezzo dallo stop.  \n**Open Risk $** è la perdita teorica dal prezzo attuale allo stop memorizzato.")
    with st.expander("Come leggere Status"):
        st.markdown(f"**NEAR STOP / NEAR TP1 / NEAR TP2** = distanza prezzo **≤ {NEAR_THRESHOLD_PCT:.1f}%** dal relativo livello.  \n**TP1 HIT** = primo target già raggiunto.  \nNon viene mostrato TRAILING finché il motore non implementa davvero una logica trailing.")
    with st.expander("Costi e prezzi"):
        st.markdown(f"Costo corrente USA: **${CURRENT_COMMISSION_PER_SIDE:.2f} per lato** + **{SLIPPAGE_BPS:.0f} bps** di slippage. Scenario futuro: **${DISCOUNT_COMMISSION_PER_SIDE:.2f} per lato**. I prezzi OPEN seguono la gerarchia Yahoo live → DB → Entry fallback.")

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
live = market_snapshot(open_symbols)

stored_names = {
    str(p.get("symbol") or "").upper(): _stored_company_name(p)
    for p in open_pos
    if p.get("symbol") and _stored_company_name(p)
}
missing_name_symbols = tuple(t for t in open_symbols if t not in stored_names)
yahoo_names = yahoo_company_names(missing_name_symbols)
company_names = {**yahoo_names, **stored_names}

rows: list[dict[str, Any]] = []
capital_deployed = 0.0
market_value_total = 0.0
open_risk_total = 0.0
open_net_total = 0.0
for p in open_pos:
    ticker = str(p.get("symbol") or "").upper()
    entry = n(p.get("entry_price"))
    avg_cost = n(p.get("avg_cost")) or n(p.get("average_cost")) or entry
    qty = n(p.get("qty"))
    snap = effective_market(p, live)
    current = n(snap.get("current"))
    day_low = n(snap.get("day_low"))
    day_high = n(snap.get("day_high"))
    source = str(snap.get("source") or "N/D")
    stop = n(p.get("stop_current")) or n(p.get("stop_initial"))
    tp1 = n(p.get("tp1"))
    tp2 = n(p.get("tp2"))
    capital = (avg_cost * qty) if avg_cost is not None and qty is not None else None
    market_value = (current * qty) if current is not None and qty is not None else None
    price_pnl = open_price_pnl(avg_cost, current, qty)
    net = open_net_pnl(avg_cost, current, qty)
    net_pct = (net / capital * 100.0) if net is not None and capital else None
    risk = max((current - stop) * qty, 0.0) if None not in (current, stop, qty) else None
    risk_pct = ((current - stop) / current * 100.0) if current and stop is not None else None
    if capital is not None:
        capital_deployed += capital
    if market_value is not None:
        market_value_total += market_value
    if risk is not None:
        open_risk_total += risk
    if net is not None:
        open_net_total += net
    rows.append({
        "Ticker": ticker,
        "Company": company_names.get(ticker, "N/D"),
        "Strategy": p.get("strategy"),
        "Tier": tier_of(p),
        "Qty": qty,
        "Entry $": entry,
        "Avg Cost $": avg_cost,
        "Current $": current,
        "Day Low $": day_low,
        "Day High $": day_high,
        "Market Value $": market_value,
        "Net P&L $": net,
        "Net %": net_pct,
        "SL $": stop,
        "TP1 $": tp1,
        "TP2 $": tp2,
        "Risk to Stop %": risk_pct,
        "Open Risk $": risk,
        "Status": open_status(current, stop, tp1, tp2, str(p.get("status") or "").upper()),
        "Source": source,
        "Price P&L $": price_pnl,
        "Entry Cost $": entry_cost(avg_cost, qty),
        "Est. Exit Cost $": estimated_exit_cost(current, qty),
        "Capital $": capital,
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

k = st.columns(7)
k[0].metric("Open Positions", len(open_pos))
k[1].metric("Capital Deployed", f"${capital_deployed:,.2f}")
k[2].metric("Market Value", f"${market_value_total:,.2f}")
k[3].metric("Open Net P&L", f"${open_net_total:,.2f}")
k[4].metric("Open Risk", f"${open_risk_total:,.2f}")
k[5].metric("Realized Net P&L", f"${realized_total:,.2f}")
k[6].metric("Win Rate", f"{win_rate:.2f}%" if win_rate is not None else "N/D")

if open_net_total > 0:
    st.success(f"Open P&L is positive: +${open_net_total:,.2f}")
elif open_net_total < 0:
    st.error(f"Open P&L is negative: -${abs(open_net_total):,.2f}")

st.subheader("Open Paper Positions")
open_df = pd.DataFrame(rows)
if open_df.empty:
    st.info("No open paper positions.")
else:
    shown = open_df[[
        "Ticker", "Company", "Strategy", "Tier", "Qty",
        "Entry $", "Avg Cost $", "Current $", "Day Low $", "Day High $",
        "Market Value $", "Net P&L $", "Net %",
        "SL $", "TP1 $", "TP2 $", "Risk to Stop %", "Status",
    ]]
    st.dataframe(fmt(shown), width="stretch", hide_index=True)
    st.caption("Fineco-style summary without Bid/Ask/Volume. Day Low/High use the available Yahoo session snapshot; '-' means the daily range could not be verified from the current feed.")
    with st.expander("Risk & Cost Audit"):
        audit = open_df[[
            "Ticker", "Source", "Capital $", "Open Risk $", "Price P&L $",
            "Entry Cost $", "Est. Exit Cost $", "Net P&L $",
        ]]
        st.dataframe(fmt(audit), width="stretch", hide_index=True)
        st.caption("Open Net P&L uses only entry costs already incurred. Estimated exit costs are shown separately and are not used for the open status badge.")

st.subheader("Strategy Snapshot")
if not open_df.empty:
    s = open_df.groupby("Strategy", dropna=False).agg(
        Open=("Ticker", "count"),
        Capital=("Capital $", "sum"),
        Market_Value=("Market Value $", "sum"),
        Net_PnL=("Net P&L $", "sum"),
        Avg_Return=("Net %", "mean"),
        Open_Risk=("Open Risk $", "sum"),
    ).reset_index().rename(columns={
        "Capital": "Capital $",
        "Market_Value": "Market Value $",
        "Net_PnL": "Net P&L $",
        "Avg_Return": "Avg Return %",
        "Open_Risk": "Open Risk $",
    })
    st.dataframe(fmt(s.sort_values("Net P&L $", ascending=False)), width="stretch", hide_index=True)

st.caption("Question answered by this page: How is the Laboratory doing right now?")
st.caption(f"Updated: {datetime.now().astimezone().strftime('%d/%m/%Y %H:%M:%S %Z')}")
