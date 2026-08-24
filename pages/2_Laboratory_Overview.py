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

st.set_page_config(page_title="Laboratory Overview", page_icon="🔬", layout="wide")
COMMISSION = 9.90
SLIPPAGE_BPS = 5.0


def require_access() -> None:
    return


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


def fmt_dt(v: Any) -> str:
    if not v:
        return "-"
    try:
        ts = pd.Timestamp(v)
        return ts.strftime("%d/%m/%Y %H:%M:%S")
    except Exception:
        return str(v).split(".")[0]


@st.cache_data(ttl=60, show_spinner=False)
def live_prices(tickers: tuple[str, ...]) -> dict[str, float]:
    """Prezzi correnti/ultimi disponibili per le posizioni OPEN.

    Non usa last_price del DB come fonte primaria perché il lifecycle worker è
    giornaliero e quindi quel campo può coincidere con l'entry per molte ore.
    """
    if not tickers:
        return {}
    try:
        data = yf.download(
            list(tickers),
            period="1d",
            interval="1m",
            auto_adjust=False,
            progress=False,
            group_by="ticker",
            threads=True,
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


def pnl_components(entry: Any, last: Any, qty: Any) -> tuple[float | None, float | None, float | None]:
    entry, last, qty = n(entry), n(last), n(qty)
    if entry is None or last is None or qty is None:
        return None, None, None
    gross = (last - entry) * qty
    slip = SLIPPAGE_BPS / 10000
    costs = 2 * COMMISSION + (entry * slip + last * slip) * qty
    net = gross - costs
    return gross, costs, net


def realized_pnl(row: dict[str, Any]) -> float | None:
    stored = n(row.get("net_pnl"))
    if stored is not None:
        return stored
    entry = n(row.get("entry_price"))
    exit_price = n(row.get("exit_price")) or n(row.get("last_price"))
    qty = n(row.get("qty"))
    _, _, net = pnl_components(entry, exit_price, qty)
    return net


def fmt_table(frame: pd.DataFrame) -> pd.io.formats.style.Styler:
    money_cols = {
        "Entry", "Prezzo attuale", "Prezzo uscita", "Stop", "TP1", "TP2",
        "P&L lordo $", "Costi stimati $", "P&L netto $", "P&L realizzato netto $",
        "PnL_netto",
    }
    pct_cols = {"Variazione titolo %", "Performance netta %", "Performance_media", "Win rate %"}
    formats: dict[str, str] = {}
    for col in frame.columns:
        if col in money_cols:
            formats[col] = "{:.2f}"
        elif col in pct_cols:
            formats[col] = "{:.2f}%"
        elif pd.api.types.is_float_dtype(frame[col]):
            formats[col] = "{:.2f}"
    styler = frame.style.format(formats, na_rep="-")

    pnl_col = "P&L netto $" if "P&L netto $" in frame.columns else (
        "P&L realizzato netto $" if "P&L realizzato netto $" in frame.columns else None
    )
    if pnl_col:
        def row_color(row):
            value = n(row.get(pnl_col))
            if value is None or abs(value) < 1e-12:
                return [""] * len(row)
            css = (
                "background-color: rgba(46,160,67,.16); color:#137333; font-weight:600;"
                if value > 0 else
                "background-color: rgba(248,81,73,.16); color:#b42318; font-weight:600;"
            )
            return [css] * len(row)
        styler = styler.apply(row_color, axis=1)
    return styler


@st.cache_data(ttl=60, show_spinner=False)
def load_positions():
    return data_access.lab_paper_positions(10000)


require_access()
st.title("🔬 Laboratory · Situazione semplice")
st.caption("Cosa sta girando adesso, con quale strategia e se sta guadagnando o perdendo. Tutto è PAPER, non Production.")

with st.sidebar:
    st.markdown("### Come leggere questa pagina")
    st.markdown(
        "**Prezzo attuale** viene letto direttamente dal mercato con cache di circa 60 secondi. Se il feed non risponde, viene usato il prezzo salvato nel database e la colonna Fonte lo segnala.\n\n"
        "**P&L lordo** misura solo il movimento del titolo.\n\n"
        "**Costi stimati** = commissioni Fineco-like $9,90 per lato + slippage 5 bps.\n\n"
        "**P&L netto** = P&L lordo meno costi. Quindi Entry e Prezzo uguali possono dare netto negativo, ma ora lo vedi separatamente.\n\n"
        "**Tier C** = 🔬 RESEARCH ONLY, mai operativo."
    )

try:
    positions = load_positions()
except Exception as exc:
    st.error(f"Errore lettura Laboratory: {type(exc).__name__}: {exc}")
    st.stop()
if not positions:
    st.info("Il Laboratory non ha ancora posizioni paper.")
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
    tier = d.get("paper_tier") or "N/D"
    status = str(p.get("status") or "N/D").upper()
    ticker = str(p.get("symbol") or "").upper()
    entry = n(p.get("entry_price"))
    qty = n(p.get("qty"))
    db_last = n(p.get("last_price"))
    exit_price = n(p.get("exit_price"))

    if status == "CLOSED":
        current = None
        source = "CLOSED"
        gross = (exit_price - entry) * qty if exit_price is not None and entry is not None and qty is not None else None
        costs = (gross - realized_pnl(p)) if gross is not None and realized_pnl(p) is not None else None
        net = realized_pnl(p)
        gross_pct = ((exit_price / entry) - 1) * 100 if exit_price is not None and entry else None
    else:
        current = market_prices.get(ticker)
        source = "LIVE 1M" if current is not None else "DB FALLBACK"
        if current is None:
            current = db_last or entry
        gross, costs, net = pnl_components(entry, current, qty)
        gross_pct = ((current / entry) - 1) * 100 if current is not None and entry else None

    net_pct = (net / (entry * qty) * 100) if net is not None and entry and qty else n(p.get("return_pct"))

    rows.append({
        "Ticker": ticker,
        "Strategia": p.get("strategy"),
        "Tier": tier,
        "Stato": status,
        "Apertura": fmt_dt(p.get("opened_at") or p.get("created_at")),
        "Entry": entry,
        "Prezzo attuale": current if status != "CLOSED" else None,
        "Fonte": source,
        "Prezzo uscita": exit_price if status == "CLOSED" else None,
        "Qty": qty,
        "Variazione titolo %": gross_pct,
        "P&L lordo $": gross,
        "Costi stimati $": costs,
        "P&L netto $": net if status != "CLOSED" else None,
        "P&L realizzato netto $": net if status == "CLOSED" else None,
        "Performance netta %": net_pct,
        "Stop": n(p.get("stop_current")) or n(p.get("stop_initial")),
        "TP1": n(p.get("tp1")),
        "TP2": n(p.get("tp2")),
        "Esito": "🟢 GUADAGNO" if net is not None and net > 0 else ("🔴 PERDITA" if net is not None and net < 0 else "⚪ PARI/N.D."),
        "Motivo chiusura": p.get("exit_reason"),
    })

df = pd.DataFrame(rows)
open_df = df[df["Stato"].isin(["OPEN", "TP1_HIT"])].copy()
closed_df = df[df["Stato"].eq("CLOSED")].copy()
open_pnl = open_df["P&L netto $"].fillna(0).sum()
closed_pnl = closed_df["P&L realizzato netto $"].fillna(0).sum()
closed_wins = int((closed_df["P&L realizzato netto $"] > 0).sum()) if len(closed_df) else 0
closed_losses = int((closed_df["P&L realizzato netto $"] < 0).sum()) if len(closed_df) else 0
win_rate = closed_wins / len(closed_df) * 100 if len(closed_df) else None

c = st.columns(6)
c[0].metric("Aperte adesso", len(open_df))
c[1].metric("P&L aperto netto", f"${open_pnl:,.2f}")
c[2].metric("Chiuse", len(closed_df))
c[3].metric("P&L chiuso netto", f"${closed_pnl:,.2f}")
c[4].metric("Vinte / Perse", f"{closed_wins} / {closed_losses}")
c[5].metric("Win rate", f"{win_rate:.2f}%" if win_rate is not None else "N/D")

st.subheader("🟢 Cosa sta girando adesso")
if open_df.empty:
    st.info("Nessuna posizione paper aperta.")
else:
    shown_open = open_df[[
        "Ticker", "Strategia", "Tier", "Entry", "Prezzo attuale", "Fonte",
        "Variazione titolo %", "P&L lordo $", "Costi stimati $", "P&L netto $",
        "Performance netta %", "Stop", "TP1", "TP2", "Esito", "Apertura",
    ]]
    st.dataframe(fmt_table(shown_open), width="stretch", hide_index=True)

    s = open_df.groupby("Strategia", dropna=False).agg(
        Posizioni=("Ticker", "count"),
        PnL_netto=("P&L netto $", "sum"),
        Performance_media=("Performance netta %", "mean"),
    ).reset_index()
    st.markdown("#### Come stanno andando le strategie aperte")
    st.dataframe(fmt_table(s.sort_values("PnL_netto", ascending=False)), width="stretch", hide_index=True)

st.subheader("🏁 Operazioni chiuse · risultati realizzati")
if closed_df.empty:
    st.info(
        "Nessuna operazione paper chiusa per ora. Il lifecycle worker chiude una posizione quando un run successivo osserva Stop o TP. "
        "Le posizioni aperte oggi possono quindi restare OPEN fino al prossimo aggiornamento del lifecycle."
    )
else:
    shown_closed = closed_df[[
        "Ticker", "Strategia", "Tier", "Entry", "Prezzo uscita",
        "Variazione titolo %", "P&L lordo $", "Costi stimati $", "P&L realizzato netto $",
        "Performance netta %", "Esito", "Motivo chiusura", "Apertura",
    ]]
    st.dataframe(fmt_table(shown_closed), width="stretch", hide_index=True)

    cs = closed_df.groupby("Strategia", dropna=False).agg(
        Trade=("Ticker", "count"),
        Vinte=("P&L realizzato netto $", lambda x: int((x > 0).sum())),
        Perse=("P&L realizzato netto $", lambda x: int((x < 0).sum())),
        PnL_netto=("P&L realizzato netto $", "sum"),
        Performance_media=("Performance netta %", "mean"),
    ).reset_index()
    cs["Win rate %"] = cs["Vinte"] / cs["Trade"] * 100
    st.markdown("#### Performance storica per strategia")
    st.dataframe(fmt_table(cs.sort_values("PnL_netto", ascending=False)), width="stretch", hide_index=True)

st.caption("Prezzi OPEN: feed mercato 1 minuto con cache 60s; fallback al DB se indisponibile. P&L netto = movimento titolo - commissioni - slippage.")
st.caption(f"Aggiornato: {datetime.now().astimezone().strftime('%d/%m/%Y %H:%M:%S %Z')}")
