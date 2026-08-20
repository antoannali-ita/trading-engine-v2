import sys
from pathlib import Path

import pandas as pd
import streamlit as st
import yfinance as yf

LAB_ROOT = Path(__file__).resolve().parents[2]
SRC = LAB_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from lab.auth import require_dashboard_auth
from lab.data import load_core_high_conviction
from lab.ui import apply_theme, fmt_money, fmt_rr, fmt_score, page_header

st.set_page_config(page_title="Trading Lab | Core Opportunities", layout="wide", page_icon="🎯")
require_dashboard_auth()
apply_theme()
page_header(
    "Core Opportunities",
    "Solo BUY e PRE-BUY HIGH prodotti dai motori Core. USA e Italy mantengono le proprie regole; questa pagina non ricalcola né promuove segnali.",
    eyebrow="CORE · USA · ITALY · HIGH CONVICTION",
)


@st.cache_data(ttl=300, show_spinner=False)
def current_price(ticker: str, market: str):
    symbol = ticker if market.upper() == "USA" or "." in ticker else f"{ticker}.MI"
    try:
        hist = yf.Ticker(symbol).history(period="1d", interval="5m", auto_adjust=True)
        if hist.empty or hist["Close"].dropna().empty:
            return None
        return float(hist["Close"].dropna().iloc[-1])
    except Exception:
        return None


def _currency(market: str) -> str:
    return "€" if market.upper() == "ITALY" else "$"


def _money(value, market: str) -> str:
    return fmt_money(value, symbol=_currency(market))


def tv_url(row, market: str) -> str:
    ticker = str(row.get("ticker") or "").upper()
    payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
    if market.upper() == "ITALY":
        ticker = ticker.replace(".MI", "")
        return f"https://www.tradingview.com/chart/?symbol=MIL:{ticker}"
    exchange = str(payload.get("exchange") or "").upper().strip()
    if exchange:
        return f"https://www.tradingview.com/chart/?symbol={exchange}:{ticker}"
    return f"https://www.tradingview.com/chart/?symbol={ticker}"


def _reason(row) -> str:
    state = str(row.get("operational_state") or "N/D")
    signal_class = str(row.get("signal_class") or "N/D")
    missing = row.get("missing_gates")
    missing_txt = ", ".join(str(x) for x in missing) if isinstance(missing, list) and missing else "none"
    if signal_class == "BUY NOW":
        return "Core decision is BUY NOW: tutti i gate richiesti dal motore risultano superati."
    if signal_class == "BUY LIMIT":
        return "Core decision is BUY LIMIT: setup operativo valido al prezzo limite definito dal motore."
    if state == "READY_FOR_TRIGGER":
        return "PRE-BUY HIGH: struttura, score/RR e controlli non-trigger sono validi; manca la conferma del trigger."
    if state == "SCORE_MARGINAL":
        return "PRE-BUY HIGH Italy: R/R e struttura sono validi, ma lo score è ancora marginale rispetto alla soglia BUY."
    return f"High-conviction state from Core. Missing gates: {missing_txt}."


try:
    opportunities = load_core_high_conviction(500, active_only=True)
except Exception as exc:
    st.error("Core high-conviction store non disponibile. Eseguire prima la migration SQL 06 e poi un Master Scan.")
    st.code(str(exc))
    st.stop()

if opportunities.empty:
    st.info("No active BUY / PRE-BUY HIGH opportunities. This is a valid Core outcome.")
    st.stop()

if "created_at" in opportunities:
    opportunities["_created"] = pd.to_datetime(opportunities["created_at"], errors="coerce", utc=True)
    opportunities = opportunities.sort_values("_created", ascending=False)

for market in ["USA", "ITALY"]:
    block = opportunities[opportunities["market"].fillna("").astype(str).str.upper() == market].copy()
    st.markdown(f"## {market}")
    if block.empty:
        st.caption("No active high-conviction opportunity.")
        continue

    block = block.drop_duplicates(subset=["ticker"], keep="first")
    block["Current Price"] = [current_price(str(row.get("ticker")), market) for _, row in block.iterrows()]
    block["Company"] = block.get("company_name", pd.Series(index=block.index)).fillna("N/D")
    block["Status"] = block.get("signal_class", pd.Series(index=block.index)).fillna("N/D")
    block["Buy Range"] = block.apply(lambda r: f"{_money(r.get('buy_zone_low'), market)} – {_money(r.get('buy_zone_high'), market)}", axis=1)
    block["Entry"] = block.get("entry", pd.Series(index=block.index)).map(lambda v: _money(v, market))
    block["SL"] = block.get("stop", pd.Series(index=block.index)).map(lambda v: _money(v, market))
    block["TP1"] = block.get("tp1", pd.Series(index=block.index)).map(lambda v: _money(v, market))
    block["TP2"] = block.get("tp2", pd.Series(index=block.index)).map(lambda v: _money(v, market))
    block["Net R/R"] = block.get("net_rr_tp2", pd.Series(index=block.index)).map(fmt_rr)
    block["Chart"] = block.apply(lambda r: tv_url(r, market), axis=1)

    table = block[["ticker", "Company", "Status", "Current Price", "Buy Range", "Entry", "SL", "TP1", "TP2", "Net R/R", "Chart"]].copy()
    table = table.rename(columns={"ticker": "Ticker"})
    table["Current Price"] = table["Current Price"].map(lambda v: _money(v, market))

    st.dataframe(
        table,
        use_container_width=True,
        hide_index=True,
        column_config={"Chart": st.column_config.LinkColumn("TradingView", display_text="Open")},
    )

    info_cols = st.columns(min(len(block), 4))
    for idx, (_, row) in enumerate(block.iterrows()):
        with info_cols[idx % len(info_cols)]:
            ticker = str(row.get("ticker", "N/D"))
            with st.popover(f"ℹ️ {ticker}", use_container_width=True):
                st.markdown(f"**{ticker} · {row.get('company_name') or 'N/D'}**")
                st.write(f"Status: **{row.get('signal_class', 'N/D')}**")
                if pd.notna(row.get("prebuy_score")):
                    st.write(f"PRE-BUY Score: **{int(float(row.get('prebuy_score')))}/10**")
                if pd.notna(row.get("opportunity_score")):
                    st.write(f"Opportunity Score: **{fmt_score(row.get('opportunity_score'))}**")
                if pd.notna(row.get("quality_score")):
                    st.write(f"Quality Score: **{fmt_score(row.get('quality_score'))}**")
                st.write(f"Operational: **{row.get('operational_state') or 'N/D'}**")
                st.write(f"Net R/R TP2: **{fmt_rr(row.get('net_rr_tp2'))}**")
                missing = row.get("missing_gates")
                if isinstance(missing, list):
                    st.write(f"Missing Gates: **{', '.join(str(x) for x in missing) if missing else 'none'}**")
                st.info(_reason(row))
                st.caption(f"Core snapshot: {row.get('created_at', 'N/D')} · Run {row.get('run_id', 'N/D')}")

st.caption("Source: Core high-conviction persistence. Current Price is a cached market-data refresh; Signal Price remains stored in the DB for audit.")
