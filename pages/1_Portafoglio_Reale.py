from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
import yfinance as yf

from common_utility.production_portfolio_metrics import (
    as_float,
    distance_pct,
    distance_to_stop_pct,
    invested_pct,
    pnl_pct,
    risk_to_stop_usd,
    usd_to_eur,
    weight_pct,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "production_portfolio.json"

st.set_page_config(page_title="Production Portfolio", page_icon="💰", layout="wide")


def _load_config() -> dict[str, Any]:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


@st.cache_data(ttl=300, show_spinner=False)
def _live_prices(tickers: tuple[str, ...]) -> dict[str, float]:
    if not tickers:
        return {}
    data = yf.download(list(tickers), period="5d", interval="1d", auto_adjust=False, progress=False, group_by="ticker")
    out: dict[str, float] = {}
    for ticker in tickers:
        try:
            if len(tickers) == 1:
                series = data["Close"].dropna()
            else:
                series = data[(ticker, "Close")].dropna()
            if not series.empty:
                out[ticker] = float(series.iloc[-1])
        except Exception:
            pass
    return out


@st.cache_data(ttl=300, show_spinner=False)
def _usd_eur_rate() -> tuple[float | None, str]:
    """Return EUR received for USD 1, plus the market-data source label."""
    try:
        data = yf.download("EURUSD=X", period="1d", interval="5m", auto_adjust=False, progress=False)
        close = data["Close"].dropna()
        if not close.empty:
            eurusd = float(close.iloc[-1])
            if eurusd > 0:
                return 1.0 / eurusd, "LIVE 5M"
    except Exception:
        pass
    try:
        data = yf.download("EURUSD=X", period="5d", interval="1d", auto_adjust=False, progress=False)
        close = data["Close"].dropna()
        if not close.empty:
            eurusd = float(close.iloc[-1])
            if eurusd > 0:
                return 1.0 / eurusd, "EOD"
    except Exception:
        pass
    return None, "SNAPSHOT"


def _pnl_color(v: Any) -> str:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return ""
    if x > 0:
        return "color: #21c55d; font-weight: 700;"
    if x < 0:
        return "color: #ef4444; font-weight: 700;"
    return ""


def _status_label(v: Any) -> str:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return "⚪ N/D"
    if x > 0:
        return "🟢 PROFIT"
    if x < 0:
        return "🔴 LOSS"
    return "⚪ FLAT"


def _production_style(frame: pd.DataFrame):
    fmt: dict[str, str] = {}
    money_cols = {
        "Average Price $", "Current Price $", "Value $", "Value €", "P&L $", "P&L €",
        "Stop $", "Risk to Stop $", "Target $",
    }
    pct_cols = {"P&L %", "Distance to Stop %", "Distance to Target %", "Weight %"}
    fx_cols = {"Average USD/EUR", "Current USD/EUR", "Target USD/EUR"}
    for col in frame.columns:
        if col in money_cols or col in fx_cols:
            fmt[col] = "{:.2f}"
        elif col in pct_cols:
            fmt[col] = "{:.2f}"
    styler = frame.style.format(fmt, na_rep="-")
    pnl_subset = [c for c in ["P&L $", "P&L €", "P&L %"] if c in frame.columns]
    if pnl_subset:
        styler = styler.map(_pnl_color, subset=pnl_subset)
    return styler


cfg = _load_config()
equities = cfg.get("equities", [])
fx_positions = cfg.get("fx_positions", [])
capital_total_usd = as_float(cfg.get("capital_total_usd"))
cash_usd = as_float(cfg.get("cash_usd"))

tickers = tuple(str(r["ticker"]).upper() for r in equities)
prices = _live_prices(tickers)
usd_eur_live, fx_source = _usd_eur_rate()
refresh_time = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")

# If live FX is unavailable, use the configured snapshot only as a clearly labelled fallback.
fx_snapshot = None
if fx_positions:
    fx_snapshot = as_float(fx_positions[0].get("snapshot_rate_eur_per_usd"))
usd_eur = usd_eur_live if usd_eur_live is not None else fx_snapshot
if usd_eur_live is None and usd_eur is not None:
    fx_source = "SNAPSHOT"

rows = []
for r in equities:
    ticker = str(r["ticker"]).upper()
    live = prices.get(ticker)
    source = "LIVE" if live is not None else "SNAPSHOT"
    px = live if live is not None else float(r["snapshot_price_usd"])
    qty = float(r["quantity"])
    avg = float(r["avg_price_usd"])
    target = float(r["target_usd"])
    stop = as_float(r.get("stop_usd"))
    value_usd = qty * px
    cost_usd = qty * avg
    pnl_usd = value_usd - cost_usd
    position_pnl_pct = pnl_pct(value_usd, cost_usd)
    value_eur = usd_to_eur(value_usd, usd_eur)
    pnl_eur = usd_to_eur(pnl_usd, usd_eur)
    dist_target = distance_pct(target, px)
    dist_stop = distance_to_stop_pct(px, stop)
    risk_stop = risk_to_stop_usd(qty, px, stop)
    rows.append({
        "Ticker": ticker,
        "Company": r.get("name", ""),
        "Market": r.get("market", ""),
        "Qty": qty,
        "Average Price $": avg,
        "Current Price $": px,
        "Source": source,
        "Value $": value_usd,
        "Value €": value_eur,
        "P&L $": pnl_usd,
        "P&L €": pnl_eur,
        "P&L %": position_pnl_pct,
        "Status": _status_label(pnl_usd),
        "Stop $": stop,
        "Distance to Stop %": dist_stop,
        "Risk to Stop $": risk_stop,
        "Target $": target,
        "Distance to Target %": dist_target,
        "Position State": "OPEN" if qty > 0 else "CLOSED",
    })

df = pd.DataFrame(rows)

st.title("💰 Production Portfolio")
st.caption(
    "Capitale reale, separato dal Laboratory paper/research. Prezzi e cambio sono aggiornati quando disponibili; "
    "gli snapshot configurati sono solo fallback."
)

if not df.empty:
    total_usd = float(df["Value $"].sum())
    total_cost_usd = float((df["Average Price $"] * df["Qty"]).sum())
    total_pnl_usd = float(df["P&L $"].sum())
    total_pnl_pct = pnl_pct(total_usd, total_cost_usd)
    total_eur = usd_to_eur(total_usd, usd_eur)
    total_pnl_eur = usd_to_eur(total_pnl_usd, usd_eur)
    winners = int((df["P&L $"] > 0).sum())
    losers = int((df["P&L $"] < 0).sum())

    df["Weight %"] = df["Value $"].map(lambda v: weight_pct(v, total_usd))

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Positions", len(df))
    c2.metric("Equity Value $", f"${total_usd:,.2f}")
    c3.metric("Equity Value €", f"€{total_eur:,.2f}" if total_eur is not None else "N/D")
    c3.caption(f"USD/EUR {usd_eur:.4f} · {fx_source}" if usd_eur is not None else "USD/EUR N/D")
    c4.metric("Open P&L $", f"${total_pnl_usd:,.2f}", delta=f"{total_pnl_usd:+,.2f} $")
    c5.metric("Open P&L %", f"{total_pnl_pct:+.2f}%" if total_pnl_pct is not None else "N/D")
    c6.metric("Winners / Losers", f"{winners} / {losers}")

    if capital_total_usd is not None or cash_usd is not None or df["Risk to Stop $"].notna().any():
        m1, m2, m3, m4 = st.columns(4)
        invested = invested_pct(total_usd, capital_total_usd)
        m1.metric("Total Capital $", f"${capital_total_usd:,.2f}" if capital_total_usd is not None else "N/D")
        m2.metric("Invested %", f"{invested:.1f}%" if invested is not None else "N/D")
        m3.metric("Cash $", f"${cash_usd:,.2f}" if cash_usd is not None else "N/D")
        if df["Risk to Stop $"].notna().any():
            heat = float(df["Risk to Stop $"].dropna().sum())
            heat_pct = heat / capital_total_usd * 100.0 if capital_total_usd else None
            m4.metric("Portfolio Heat", f"${heat:,.2f}", delta=f"{heat_pct:.2f}% of capital" if heat_pct is not None else "stops available")
        else:
            m4.metric("Portfolio Heat", "N/D")

    st.caption(
        f"Market Data Refresh: {refresh_time} · FX: USD/EUR {usd_eur:.4f} ({fx_source})"
        if usd_eur is not None else f"Market Data Refresh: {refresh_time} · FX: N/D"
    )

    st.subheader("Open Positions")
    show = df.copy()
    show["Qty"] = pd.to_numeric(show["Qty"], errors="coerce").astype("Int64")
    st.dataframe(_production_style(show), width="stretch", hide_index=True)

    st.subheader("Position Concentration")
    concentration = df[["Ticker", "Value $", "Value €", "Weight %"]].copy()
    concentration = concentration.sort_values("Weight %", ascending=False)
    st.dataframe(_production_style(concentration), width="stretch", hide_index=True)

if fx_positions:
    st.subheader("FX / USD Exposure")
    fx_rows = []
    for r in fx_positions:
        qty_usd = float(r["quantity_usd"])
        rate = usd_eur if usd_eur is not None else float(r["snapshot_rate_eur_per_usd"])
        avg = float(r["avg_rate_eur_per_usd"])
        target = float(r["target_rate_eur_per_usd"])
        value_eur = qty_usd * rate
        pnl_eur = qty_usd * (rate - avg)
        fx_pnl_pct = pnl_pct(rate, avg)
        fx_rows.append({
            "Pair": "USD/EUR",
            "USD": qty_usd,
            "Average USD/EUR": avg,
            "Current USD/EUR": rate,
            "Source": fx_source,
            "Value €": value_eur,
            "P&L €": pnl_eur,
            "P&L %": fx_pnl_pct,
            "Status": _status_label(pnl_eur),
            "Target USD/EUR": target,
        })
    fx_df = pd.DataFrame(fx_rows)
    fx_df["USD"] = pd.to_numeric(fx_df["USD"], errors="coerce").round(2)
    st.dataframe(_production_style(fx_df), width="stretch", hide_index=True)

with st.sidebar:
    st.header("Guide · Production Portfolio")
    with st.expander("What this page shows", expanded=True):
        st.markdown(
            """
            Questa pagina mostra **capitale reale** e resta separata da Laboratory e paper trading.

            - 🟢 `PROFIT` = posizione in guadagno.
            - 🔴 `LOSS` = posizione in perdita.
            - `FLAT` = posizione sostanzialmente invariata.
            - `LIVE` / `LIVE 5M` = dato recuperato dal mercato.
            - `EOD` = ultimo dato giornaliero.
            - `SNAPSHOT` = fallback configurato.
            """
        )
    with st.expander("FX & concentration", expanded=False):
        st.markdown(
            """
            - `USD/EUR` indica quanti euro vale 1 dollaro e viene usato per il controvalore in euro.
            - `Weight %` misura la concentrazione della singola posizione sul valore totale delle azioni.
            """
        )
    with st.expander("Risk fields", expanded=False):
        st.markdown(
            """
            - `Stop`, `Distance to Stop %` e `Portfolio Heat` vengono calcolati solo se gli stop sono presenti in configurazione.
            - Nessuno stop viene inventato quando il dato manca.
            - `Qty` è la quantità residua effettivamente ancora in portafoglio.
            """
        )
    with st.expander("Portfolio maintenance", expanded=False):
        st.markdown(
            """
            Vendite parziali riducono `Qty`; la posizione resta `OPEN` finché Qty > 0.
            Target e Average Price derivano dalla configurazione/fotografia fornita.
            Laboratory Control, Paper Portfolio e Research non modificano questa pagina.
            """
        )

st.info(
    "Per aggiornare quantità residue, Average Price, Target, Stop o aggiungere/rimuovere posizioni si modifica "
    "config/production_portfolio.json. `capital_total_usd` e `cash_usd` sono opzionali: se assenti non vengono stimati."
)
