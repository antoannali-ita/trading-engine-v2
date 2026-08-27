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

st.set_page_config(page_title="Live Paper Trades", page_icon="📒", layout="wide")


def j(value: Any) -> dict:
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(str(value)) if value else {}
        return parsed if isinstance(parsed, dict) else {}
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
    formats: dict[str, str] = {}
    for col in frame.columns:
        if col in {"Fill", "Ideal Entry", "Current / Exit", "Notional", "Stop", "TP1", "TP2 Initial", "TP2 Current", "Projected Net P&L 12", "Projected Net P&L 9.90", "Old TP2", "New TP2"}:
            formats[col] = "{:.2f}"
        elif col in {"MTM R", "Risk R", "Locked R", "Realized R"}:
            formats[col] = "{:+.2f}"
        elif "%" in col:
            formats[col] = "{:.2f}%"
        elif col == "Qty":
            formats[col] = "{:.0f}"
        elif pd.api.types.is_float_dtype(frame[col]):
            formats[col] = "{:.2f}"
    styler = frame.style.format(formats, na_rep="-")

    def color(v: Any) -> str:
        value = n(v)
        if value is None or value == 0:
            return ""
        return "color:#15803d;font-weight:700;" if value > 0 else "color:#dc2626;font-weight:700;"

    for col in ["Move %", "MTM R", "Realized R", "Locked R", "Projected Net P&L 12", "Projected Net P&L 9.90"]:
        if col in frame.columns:
            styler = styler.map(color, subset=[col])
    return styler


@st.cache_data(ttl=60, show_spinner=False)
def load_positions():
    return data_access.lab_paper_positions(10000)


@st.cache_data(ttl=60, show_spinner=False)
def load_ticker_snapshot():
    return data_access.lab_strategy_ticker_snapshots(2000)


@st.cache_data(ttl=120, show_spinner=False)
def load_events():
    return data_access.lab_paper_events(10000)


st.title("📒 Live Paper Trades")
st.caption("Operational Laboratory ledger: open/closed paper trades, normalized risk and lifecycle. PAPER only; no broker orders are sent.")

with st.sidebar:
    st.markdown("## Guida · Live Paper Trades")
    with st.expander("A cosa serve", expanded=True):
        st.markdown("Qui vedi **quali titoli stanno realmente girando nel paper test**, con strategia, Tier, fill, prezzo corrente, stop/target, P&L e metriche R quando lo snapshot 2.2 è disponibile.")
    with st.expander("Fill vs Ideal Entry"):
        st.markdown("**Fill** è il prezzo paper effettivo e la base per performance/R. **Ideal Entry** resta diagnostico: serve a misurare la qualità del setup, non sostituisce l'eseguito.")
    with st.expander("MTM / Risk / Locked R"):
        st.markdown("**MTM R** = risultato aperto normalizzato. **Risk R** = capitale ancora esposto fino allo stop corrente. **Locked R** = profitto già protetto dallo stop.")
    with st.expander("Dynamic Exit V1"):
        st.markdown("**DYNAMIC_EXIT_V1** è una variante Laboratory. Lo stop può solo salire; TP1 resta fisso; TP2 può essere alzato dopo conferme codificate. `TP2 Initial` conserva il target originale, `TP2 Current` è quello operativo corrente.")
    with st.expander("Lifecycle"):
        st.markdown("Il dettaglio eventi viene caricato solo quando richiesto: OPEN, TP1, EXIT_POLICY_INITIALIZED, TARGET_MODE_CHANGED, STOP_MOVED, TP2_RAISED, TP2/STOP e CLOSED.")
    with st.expander("Costi"):
        st.markdown(f"Scenario corrente: **${CURRENT_COMMISSION_PER_SIDE:.2f} per lato**. Scenario futuro: **${DISCOUNT_COMMISSION_PER_SIDE:.2f} per lato**. Slippage: **{SLIPPAGE_BPS:.0f} bps**.")

positions = load_positions()
if not positions:
    st.info("No paper positions available.")
    st.stop()

snapshots = load_ticker_snapshot()
snapshot_map = {
    (str(x.get("symbol") or "").upper(), str(x.get("strategy") or "")): x
    for x in snapshots
}

open_symbols = tuple(sorted({str(p.get("symbol") or "").upper() for p in positions if str(p.get("status") or "").upper() in {"OPEN", "TP1_HIT"} and p.get("symbol")}))
market_prices = live_prices(open_symbols)

rows = []
for p in positions:
    d = j(p.get("details"))
    dyn = j(d.get("dynamic_exit"))
    cost = j(d.get("cost_model"))
    status = str(p.get("status") or "N/D").upper()
    ticker = str(p.get("symbol") or "").upper()
    strategy = str(p.get("strategy") or "")
    fill = n(p.get("fill_price")) or n(p.get("entry_price"))
    qty = n(p.get("qty"))
    snap = snapshot_map.get((ticker, strategy), {})
    if status in {"OPEN", "TP1_HIT"}:
        current = market_prices.get(ticker)
        last = current if current is not None else (n(p.get("last_price")) or fill)
        source = "LIVE 1M" if current is not None else "DB FALLBACK"
    else:
        last = n(p.get("exit_price")) or n(p.get("last_price")) or fill
        source = "CLOSED"
    capital = n(p.get("capital")) or ((fill or 0) * (qty or 0))
    move_pct = ((last / fill) - 1) * 100 if last is not None and fill else None
    if status == "CLOSED":
        pnl12 = closed_net_pnl(fill, last, qty, CURRENT_COMMISSION_PER_SIDE, SLIPPAGE_BPS)
        pnl990 = closed_net_pnl(fill, last, qty, DISCOUNT_COMMISSION_PER_SIDE, SLIPPAGE_BPS)
    else:
        pnl12 = projected_round_trip_pnl(fill, last, qty, CURRENT_COMMISSION_PER_SIDE, SLIPPAGE_BPS)
        pnl990 = projected_round_trip_pnl(fill, last, qty, DISCOUNT_COMMISSION_PER_SIDE, SLIPPAGE_BPS)

    tp2_current = n(dyn.get("tp2_current")) or n(p.get("tp2"))
    tp2_initial = n(dyn.get("tp2_initial")) or n(p.get("tp2"))
    exit_variant = d.get("exit_variant") or (dyn.get("policy_version") if dyn else None) or "FIXED_LEGACY"

    rows.append({
        "Opened": data_access.utc_label(p.get("opened_at") or p.get("created_at")),
        "Ticker": ticker,
        "Strategy": strategy,
        "Exit Variant": exit_variant,
        "Target Mode": dyn.get("target_mode") or "FIXED",
        "Recalibration": dyn.get("recalibration_reason"),
        "Tier": d.get("paper_tier") or j(d.get("paper_policy")).get("tier") or "N/D",
        "Status": status,
        "Fill": fill,
        "Ideal Entry": n(p.get("ideal_entry")) or n(d.get("ideal_entry")),
        "Current / Exit": last,
        "Price Source": source,
        "Move %": move_pct,
        "MTM R": n(snap.get("mtm_r")) if status in {"OPEN", "TP1_HIT"} else None,
        "Risk R": n(snap.get("open_risk_r")) if status in {"OPEN", "TP1_HIT"} else None,
        "Locked R": n(snap.get("locked_profit_r")) if status in {"OPEN", "TP1_HIT"} else None,
        "Realized R": n(p.get("realized_r")) if status == "CLOSED" else None,
        "Qty": qty,
        "Notional": capital,
        "Stop": n(p.get("stop_current")) or n(p.get("stop_initial")),
        "TP1": n(p.get("tp1")),
        "TP2 Initial": tp2_initial,
        "TP2 Current": tp2_current,
        "Gross R/R TP2": n(cost.get("gross_rr")) or gross_rr(fill, p.get("stop_initial"), tp2_current),
        "Projected Net P&L 12": pnl12,
        "Projected Net P&L 9.90": pnl990,
        "Exit Reason": p.get("exit_reason"),
        "Position ID": p.get("id"),
    })

df = pd.DataFrame(rows)
open_mask = df["Status"].isin(["OPEN", "TP1_HIT"])
closed_mask = df["Status"].eq("CLOSED")

m = st.columns(7)
m[0].metric("Total Positions", len(df))
m[1].metric("Open", int(open_mask.sum()))
m[2].metric("Closed", int(closed_mask.sum()))
m[3].metric("Dynamic Exit", int(df["Exit Variant"].eq("DYNAMIC_EXIT_V1").sum()))
m[4].metric("Open MTM R", f"{df.loc[open_mask, 'MTM R'].dropna().sum():+.2f}R" if df.loc[open_mask, "MTM R"].notna().any() else "N/D")
m[5].metric("Open Risk R", f"{df.loc[open_mask, 'Risk R'].dropna().sum():.2f}R" if df.loc[open_mask, "Risk R"].notna().any() else "N/D")
m[6].metric("Strategies", df["Strategy"].nunique())

status_filter = st.multiselect("Status", sorted(df["Status"].dropna().astype(str).unique()), default=sorted(df["Status"].dropna().astype(str).unique()))
tier_filter = st.multiselect("Tier", sorted(df["Tier"].dropna().astype(str).unique()), default=sorted(df["Tier"].dropna().astype(str).unique()))
variant_filter = st.multiselect("Exit Variant", sorted(df["Exit Variant"].dropna().astype(str).unique()), default=sorted(df["Exit Variant"].dropna().astype(str).unique()))
shown = df[
    df["Status"].astype(str).isin(status_filter)
    & df["Tier"].astype(str).isin(tier_filter)
    & df["Exit Variant"].astype(str).isin(variant_filter)
]
st.dataframe(fmt_table(shown.drop(columns=["Position ID"])), width="stretch", hide_index=True)

st.subheader("Virtual Concentration by Risk Key")
risk_rows = []
for p in positions:
    d = j(p.get("details"))
    ticker = str(p.get("symbol") or "").upper()
    entry = n(p.get("fill_price")) or n(p.get("entry_price")) or 0.0
    qty = n(p.get("qty")) or 0.0
    risk_rows.append({"Risk Key": d.get("risk_key") or f"EQUITY:{ticker}", "Notional": n(p.get("capital")) or entry * qty})
risk = pd.DataFrame(risk_rows).groupby("Risk Key", as_index=False).agg(Positions=("Risk Key", "count"), Notional=("Notional", "sum"))
st.dataframe(fmt_table(risk.sort_values("Notional", ascending=False)), width="stretch", hide_index=True)

show_lifecycle = st.toggle("Load Trade Lifecycle", value=False)
if show_lifecycle:
    selected_position = st.selectbox(
        "Position",
        [int(x) for x in df["Position ID"].dropna().tolist()],
        format_func=lambda pid: f"#{pid} · {df.loc[df['Position ID'] == pid, 'Ticker'].iloc[0]} · {df.loc[df['Position ID'] == pid, 'Strategy'].iloc[0]}",
    )
    events = [e for e in load_events() if int(e.get("position_id") or -1) == int(selected_position)]
    if events:
        event_rows = []
        for e in sorted(events, key=lambda x: str(x.get("created_at") or "")):
            ed = j(e.get("details"))
            event_rows.append({
                "Time": data_access.utc_label(e.get("created_at")),
                "Event": e.get("event_type"),
                "Price": n(e.get("price")),
                "Old Stop": n(e.get("old_stop")),
                "New Stop": n(e.get("new_stop")),
                "Old TP2": n(ed.get("old_tp2")),
                "New TP2": n(ed.get("new_tp2")),
                "Reason": ed.get("reason"),
                "Target Mode": ed.get("target_mode"),
                "Note": e.get("note"),
            })
        event_df = pd.DataFrame(event_rows)
        st.dataframe(fmt_table(event_df), width="stretch", hide_index=True)
    else:
        st.info("No lifecycle events recorded for this position.")

st.caption("Question answered by this page: What paper trades are open/closed, how are they performing, and what happened during their lifecycle?")
st.caption(f"Updated: {datetime.now().astimezone().strftime('%d/%m/%Y %H:%M:%S %Z')}")
