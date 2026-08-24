from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import pandas as pd
import streamlit as st
import yfinance as yf

try:
    from dashboard import data_access
except ModuleNotFoundError:
    import dashboard.data_access as data_access

st.set_page_config(page_title="Paper Portfolio", page_icon="📒", layout="wide")

CURRENT_COMMISSION = 12.0
DISCOUNT_COMMISSION = 9.90
SLIPPAGE_BPS = 5.0


def require_access() -> None:
    return


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
        data = yf.download(
            list(tickers), period="1d", interval="1m", auto_adjust=False,
            progress=False, group_by="ticker", threads=True,
        )
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
    except Exception:
        return {}


def net_pnl(entry, exit_price, qty, commission):
    entry, exit_price, qty = n(entry), n(exit_price), n(qty)
    if not entry or exit_price is None or not qty:
        return None
    slip = SLIPPAGE_BPS / 10000.0
    entry_exec = entry * (1 + slip)
    exit_exec = exit_price * (1 - slip)
    return (exit_exec - entry_exec) * qty - 2 * commission


def gross_rr(entry, stop, tp2):
    entry, stop, tp2 = n(entry), n(stop), n(tp2)
    if entry is None or stop is None or tp2 is None or entry <= stop:
        return None
    return (tp2 - entry) / (entry - stop)


def fmt_table(frame: pd.DataFrame) -> pd.io.formats.style.Styler:
    money_cols = {"entry","ideal_entry","last_exit","notional","stop","tp1","tp2","pnl_net_12_now","pnl_net_9_90_now"}
    pct_cols = {"return_pct_db","move_pct_live"}
    ratio_cols = {"gross_rr_tp2","net_rr_12","net_rr_9_90"}
    fmt: dict[str, str] = {}
    for col in frame.columns:
        if col in money_cols:
            fmt[col] = "{:.2f}"
        elif col in pct_cols:
            fmt[col] = "{:.2f}%"
        elif col in ratio_cols:
            fmt[col] = "{:.2f}"
        elif pd.api.types.is_float_dtype(frame[col]):
            fmt[col] = "{:.2f}"
    return frame.style.format(fmt, na_rep="-")


@st.cache_data(ttl=60, show_spinner=False)
def load_positions():
    return data_access.lab_paper_positions(10000)


require_access()
st.title("📒 Paper Portfolio")
st.caption("Posizioni virtuali del Laboratory. Non sono ordini reali e non modificano Production.")

with st.sidebar:
    st.markdown("### Guida della pagina")
    st.markdown("""
**Domanda:** cosa stiamo realmente sperimentando e come sta andando?

- **A:** quasi-production, ma sempre paper.
- **B:** esperimento con regole più permissive.
- **C:** 🔬 **RESEARCH ONLY · NON OPERATIVO**.

Per le posizioni aperte il **prezzo corrente viene letto dal mercato** con cache di circa 60 secondi. Se il feed non risponde, compare `DB FALLBACK`.

I costi mostrano due scenari Fineco:
- storico/conservativo: **$12 per eseguito**;
- scenario scontato: **$9,90 per eseguito**.
""")

try:
    positions = load_positions()
except Exception as exc:
    st.error(f"Impossibile leggere Supabase: {type(exc).__name__}: {exc}")
    st.stop()

if not positions:
    st.info("Nessuna paper position disponibile.")
    st.stop()

open_symbols = tuple(sorted({
    str(p.get("symbol") or "").upper()
    for p in positions
    if str(p.get("status") or "").upper() in {"OPEN", "TP1_HIT"} and p.get("symbol")
}))
market_prices = live_prices(open_symbols)

rows = []
for p in positions:
    d = j(p.get("details"))
    cost = j(d.get("cost_model"))
    tier = d.get("paper_tier") or "N/D"
    status = str(p.get("status") or "N/D").upper()
    ticker = str(p.get("symbol") or "").upper()
    entry = n(p.get("entry_price"))

    if status in {"OPEN", "TP1_HIT"}:
        live = market_prices.get(ticker)
        last = live if live is not None else (n(p.get("last_price")) or entry)
        source = "LIVE 1M" if live is not None else "DB FALLBACK"
    else:
        last = n(p.get("exit_price")) or n(p.get("last_price")) or entry
        source = "CLOSED"

    current_pnl = net_pnl(entry, last, p.get("qty"), CURRENT_COMMISSION)
    discount_pnl = net_pnl(entry, last, p.get("qty"), DISCOUNT_COMMISSION)
    capital = n(p.get("capital")) or ((entry or 0) * (n(p.get("qty")) or 0))
    safety = d.get("safety_label") or ("RESEARCH_ONLY_NON_OPERATIONAL" if tier == "C" else "PAPER")
    move_pct = ((last / entry) - 1) * 100 if last is not None and entry else None

    rows.append({
        "apertura": p.get("opened_at") or p.get("created_at"),
        "ticker": ticker,
        "strategy": p.get("strategy"),
        "tier": tier,
        "safety": safety,
        "risk_key": d.get("risk_key") or f"EQUITY:{ticker}",
        "experiment_key": d.get("experiment_key"),
        "stato": status,
        "entry": entry,
        "ideal_entry": n(d.get("ideal_entry")),
        "last_exit": last,
        "price_source": source,
        "move_pct_live": move_pct,
        "qty": p.get("qty"),
        "notional": capital,
        "stop": n(p.get("stop_current")) or n(p.get("stop_initial")),
        "tp1": n(p.get("tp1")),
        "tp2": n(p.get("tp2")),
        "gross_rr_tp2": n(cost.get("gross_rr")) or gross_rr(entry, p.get("stop_initial"), p.get("tp2")),
        "net_rr_12": n(cost.get("net_rr_fineco_current_12")),
        "net_rr_9_90": n(cost.get("net_rr_fineco_discount_9_90")),
        "pnl_net_12_now": current_pnl,
        "pnl_net_9_90_now": discount_pnl,
        "return_pct_db": n(p.get("return_pct")),
        "exit_reason": p.get("exit_reason"),
    })

df = pd.DataFrame(rows)
open_mask = df["stato"].astype(str).str.upper().isin(["OPEN", "TP1_HIT"])
closed_mask = df["stato"].astype(str).str.upper().eq("CLOSED")

m = st.columns(5)
m[0].metric("Posizioni totali", len(df))
m[1].metric("Aperte", int(open_mask.sum()))
m[2].metric("Chiuse", int(closed_mask.sum()))
m[3].metric("Tier C 🔬", int((df["tier"] == "C").sum()))
m[4].metric("Strategie", df["strategy"].nunique())

if (df["tier"] == "C").any():
    st.warning("🔬 Le righe Tier C sono esperimenti controfattuali RESEARCH ONLY. Non vanno interpretate come BUY o indicazioni operative.")

status_filter = st.multiselect("Stato", sorted(df["stato"].dropna().astype(str).unique()), default=sorted(df["stato"].dropna().astype(str).unique()))
tier_filter = st.multiselect("Tier", sorted(df["tier"].dropna().astype(str).unique()), default=sorted(df["tier"].dropna().astype(str).unique()))
shown = df[df["stato"].astype(str).isin(status_filter) & df["tier"].astype(str).isin(tier_filter)]
st.dataframe(fmt_table(shown), width="stretch", hide_index=True)

st.subheader("Concentrazione virtuale per RiskKey")
risk = df.groupby("risk_key", as_index=False).agg(posizioni=("ticker", "count"), notional=("notional", "sum"))
st.dataframe(fmt_table(risk.sort_values("notional", ascending=False)), width="stretch", hide_index=True)
st.caption("Questa concentrazione è informativa. Il Portfolio Risk Engine futuro userà RiskKey per aggregare strategie diverse sullo stesso sottostante.")

st.caption(f"Aggiornato: {datetime.now().astimezone().strftime('%d/%m/%Y %H:%M:%S %Z')}")
