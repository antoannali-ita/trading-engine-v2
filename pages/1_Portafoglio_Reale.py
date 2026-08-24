from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "production_portfolio.json"

st.set_page_config(page_title="Portafoglio Reale", page_icon="💰", layout="wide")


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
def _usd_eur_rate() -> float | None:
    try:
        data = yf.download("EURUSD=X", period="5d", interval="1d", auto_adjust=False, progress=False)
        close = data["Close"].dropna()
        if close.empty:
            return None
        eurusd = float(close.iloc[-1])
        return 1.0 / eurusd if eurusd > 0 else None
    except Exception:
        return None


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
        return "🟢 GUADAGNO"
    if x < 0:
        return "🔴 PERDITA"
    return "⚪ PARI"


def _production_style(frame: pd.DataFrame):
    """Forza la resa visuale a 2 decimali: round() da solo non basta con Styler/Arrow."""
    fmt: dict[str, str] = {}
    money_cols = {"PMC $", "Prezzo $", "Valore $", "Valore €", "P&L $", "P&L €", "Target $"}
    pct_cols = {"P&L %", "Dist. Target %", "Peso %"}
    fx_cols = {"PMC EUR/USD", "Cambio EUR/USD", "Target EUR/USD"}
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

tickers = tuple(str(r["ticker"]).upper() for r in equities)
prices = _live_prices(tickers)
usd_eur = _usd_eur_rate()

rows = []
for r in equities:
    ticker = str(r["ticker"]).upper()
    live = prices.get(ticker)
    source = "LIVE" if live is not None else "SNAPSHOT"
    px = live if live is not None else float(r["snapshot_price_usd"])
    qty = float(r["quantity"])
    avg = float(r["avg_price_usd"])
    target = float(r["target_usd"])
    value_usd = qty * px
    pnl_usd = qty * (px - avg)
    pnl_pct = ((px / avg) - 1.0) * 100 if avg else None
    value_eur = value_usd * usd_eur if usd_eur else None
    pnl_eur = pnl_usd * usd_eur if usd_eur else None
    dist_target = ((target / px) - 1.0) * 100 if px else None
    rows.append({
        "Ticker": ticker,
        "Nome": r.get("name", ""),
        "Mercato": r.get("market", ""),
        "Qty": qty,
        "PMC $": avg,
        "Prezzo $": px,
        "Fonte": source,
        "Valore $": value_usd,
        "Valore €": value_eur,
        "P&L $": pnl_usd,
        "P&L €": pnl_eur,
        "P&L %": pnl_pct,
        "Esito": _status_label(pnl_usd),
        "Target $": target,
        "Dist. Target %": dist_target,
        "Stato": "OPEN" if qty > 0 else "CLOSED",
    })

df = pd.DataFrame(rows)

st.title("💰 Portafoglio Reale · Production")
st.caption("Capitale reale. Separato dal Laboratory paper/research. Prezzi aggiornati automaticamente quando disponibili; in fallback usa l'ultima fotografia salvata.")

if not df.empty:
    total_usd = float(df["Valore $"].sum())
    total_pnl_usd = float(df["P&L $"].sum())
    total_eur = float(df["Valore €"].dropna().sum()) if df["Valore €"].notna().any() else None
    winners = int((df["P&L $"] > 0).sum())
    losers = int((df["P&L $"] < 0).sum())
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Posizioni", len(df))
    c2.metric("Valore azioni $", f"${total_usd:,.2f}")
    c3.metric("Valore azioni €", f"€{total_eur:,.2f}" if total_eur is not None else "N/D")
    c4.metric("P&L aperto $", f"${total_pnl_usd:,.2f}", delta=f"{total_pnl_usd:+,.2f} $")
    c5.metric("In profitto / perdita", f"{winners} / {losers}")

    st.subheader("Posizioni aperte")
    show = df.copy()
    show["Qty"] = pd.to_numeric(show["Qty"], errors="coerce").astype("Int64")
    st.dataframe(_production_style(show), width="stretch", hide_index=True)

    st.subheader("Concentrazione per titolo")
    concentration = df[["Ticker", "Valore $"]].copy()
    concentration["Peso %"] = concentration["Valore $"] / total_usd * 100 if total_usd else 0
    concentration = concentration.sort_values("Peso %", ascending=False)
    st.dataframe(_production_style(concentration), width="stretch", hide_index=True)

if fx_positions:
    st.subheader("Valuta / esposizione USD")
    fx_rows = []
    for r in fx_positions:
        qty_usd = float(r["quantity_usd"])
        rate = usd_eur if usd_eur is not None else float(r["snapshot_rate_eur_per_usd"])
        avg = float(r["avg_rate_eur_per_usd"])
        target = float(r["target_rate_eur_per_usd"])
        value_eur = qty_usd * rate
        pnl_eur = qty_usd * (rate - avg)
        pnl_pct = ((rate / avg) - 1.0) * 100 if avg else None
        fx_rows.append({
            "Coppia": r["pair"],
            "USD": qty_usd,
            "PMC EUR/USD": avg,
            "Cambio EUR/USD": rate,
            "Fonte": "LIVE" if usd_eur is not None else "SNAPSHOT",
            "Valore €": value_eur,
            "P&L €": pnl_eur,
            "P&L %": pnl_pct,
            "Esito": _status_label(pnl_eur),
            "Target EUR/USD": target,
        })
    fx_df = pd.DataFrame(fx_rows)
    fx_df["USD"] = pd.to_numeric(fx_df["USD"], errors="coerce").round(2)
    st.dataframe(_production_style(fx_df), width="stretch", hide_index=True)

with st.sidebar:
    st.header("Guida · Portafoglio Reale")
    st.markdown(
        """
        **Questa pagina mostra capitale reale.**\n\n
        - 🟢 verde = posizione in guadagno.\n
        - 🔴 rosso = posizione in perdita.\n
        - Tutti i valori monetari, percentuali e di cambio sono mostrati con massimo **2 decimali**.\n
        - `Qty` è la quantità residua effettivamente ancora in portafoglio.\n
        - Vendite parziali riducono `Qty`; la posizione resta OPEN finché Qty > 0.\n
        - `LIVE` indica prezzo recuperato dal mercato; `SNAPSHOT` è solo fallback.\n
        - Laboratory Control / Paper Portfolio / Research sono simulazioni separate e non modificano questa pagina.\n
        - Target e PMC derivano dalla fotografia fornita; stop non viene inventato se non disponibile.
        """
    )

st.info("Per aggiornare quantità residue, PMC, target o aggiungere/rimuovere posizioni si modifica config/production_portfolio.json. In una fase successiva questa configurazione potrà essere spostata su Supabase con storico delle vendite parziali.")
