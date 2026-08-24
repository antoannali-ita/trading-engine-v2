from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import pandas as pd
import streamlit as st

try:
    from dashboard import data_access
except ModuleNotFoundError:
    import dashboard.data_access as data_access

st.set_page_config(page_title="Laboratory Overview", page_icon="🔬", layout="wide")
COMMISSION = 9.90
SLIPPAGE_BPS = 5.0


def require_access() -> None:
    # Accesso temporaneamente sospeso. Manteniamo la funzione per poterlo riattivare facilmente.
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
    """Mostra timestamp leggibili fino al secondo, senza microsecondi."""
    if not v:
        return "-"
    try:
        ts = pd.Timestamp(v)
        return ts.strftime("%d/%m/%Y %H:%M:%S")
    except Exception:
        return str(v).split(".")[0]


def pnl_if_closed_now(entry: Any, last: Any, qty: Any) -> float | None:
    """P&L teorico netto se una posizione OPEN fosse liquidata adesso.

    Include commissione di ingresso, commissione di uscita e slippage su entrambi i lati.
    Per questo, a prezzo invariato rispetto all'entry il valore e' leggermente negativo.
    """
    entry, last, qty = n(entry), n(last), n(qty)
    if entry is None or last is None or qty is None:
        return None
    slip = SLIPPAGE_BPS / 10000
    return (last * (1 - slip) - entry * (1 + slip)) * qty - 2 * COMMISSION


def realized_pnl(row: dict[str, Any]) -> float | None:
    """Per trade CLOSED preferisce il net_pnl realmente scritto dal lifecycle worker."""
    stored = n(row.get("net_pnl"))
    if stored is not None:
        return stored
    exit_price = n(row.get("exit_price")) or n(row.get("last_price"))
    return pnl_if_closed_now(row.get("entry_price"), exit_price, row.get("qty"))


def fmt_table(frame: pd.DataFrame) -> pd.io.formats.style.Styler:
    """Visualizzazione uniforme: prezzi/valuta e percentuali massimo 2 decimali."""
    money_cols = {
        "Entry", "Prezzo attuale", "Prezzo uscita", "Stop", "TP1", "TP2",
        "P&L netto se chiusa ora $", "P&L realizzato netto $", "PnL_netto",
    }
    pct_cols = {"Performance %", "Performance_media", "Win rate %"}
    fmt: dict[str, str] = {}
    for col in frame.columns:
        if col in money_cols:
            fmt[col] = "{:.2f}"
        elif col in pct_cols:
            fmt[col] = "{:.2f}%"
        elif pd.api.types.is_float_dtype(frame[col]):
            fmt[col] = "{:.2f}"
    return frame.style.format(fmt, na_rep="-")


@st.cache_data(ttl=60, show_spinner=False)
def load_positions():
    return data_access.lab_paper_positions(10000)


require_access()
st.title("🔬 Laboratory · Situazione semplice")
st.caption("Una sola pagina per capire cosa sta girando, con quale strategia e se sta guadagnando o perdendo. Tutto è PAPER, non Production.")

with st.sidebar:
    st.markdown("### Come leggere questa pagina")
    st.markdown(
        "**Aperte adesso** = esperimenti ancora in corso.\n\n"
        "**Chiuse** = esperimenti terminati.\n\n"
        "**P&L netto se chiusa ora** include commissione Fineco-like $9,90 per lato e slippage di ricerca. "
        "Quindi, se Entry e Prezzo attuale sono uguali, il risultato puo' essere leggermente negativo: sono i costi teorici di entrata+uscita, non un calo del titolo.\n\n"
        "**P&L realizzato netto** compare per le posizioni chiuse e usa il risultato salvato dal lifecycle worker.\n\n"
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

rows = []
for p in positions:
    d = j(p.get("details"))
    tier = d.get("paper_tier") or "N/D"
    status = str(p.get("status") or "N/D").upper()
    entry = n(p.get("entry_price"))
    qty = n(p.get("qty"))
    current = n(p.get("last_price")) or entry
    exit_price = n(p.get("exit_price"))

    if status == "CLOSED":
        net = realized_pnl(p)
        price_for_return = exit_price or current
    else:
        net = pnl_if_closed_now(entry, current, qty)
        price_for_return = current

    ret = (net / (entry * qty) * 100) if net is not None and entry and qty else n(p.get("return_pct"))

    rows.append({
        "Ticker": p.get("symbol"),
        "Strategia": p.get("strategy"),
        "Tier": tier,
        "Stato": status,
        "Apertura": fmt_dt(p.get("opened_at") or p.get("created_at")),
        "Entry": entry,
        "Prezzo attuale": current if status != "CLOSED" else None,
        "Prezzo uscita": exit_price if status == "CLOSED" else None,
        "Qty": qty,
        "Stop": n(p.get("stop_current")) or n(p.get("stop_initial")),
        "TP1": n(p.get("tp1")),
        "TP2": n(p.get("tp2")),
        "P&L netto se chiusa ora $": net if status != "CLOSED" else None,
        "P&L realizzato netto $": net if status == "CLOSED" else None,
        "Performance %": ret,
        "Esito": "🟢 GUADAGNO" if net is not None and net > 0 else ("🔴 PERDITA" if net is not None and net < 0 else "⚪ PARI/N.D."),
        "Motivo chiusura": p.get("exit_reason"),
    })

df = pd.DataFrame(rows)
open_mask = df["Stato"].isin(["OPEN", "TP1_HIT"])
closed_mask = df["Stato"].eq("CLOSED")
open_df = df[open_mask].copy()
closed_df = df[closed_mask].copy()
open_pnl = open_df["P&L netto se chiusa ora $"].fillna(0).sum()
closed_pnl = closed_df["P&L realizzato netto $"].fillna(0).sum()
closed_wins = int((closed_df["P&L realizzato netto $"] > 0).sum()) if len(closed_df) else 0
closed_losses = int((closed_df["P&L realizzato netto $"] < 0).sum()) if len(closed_df) else 0
win_rate = (closed_wins / len(closed_df) * 100) if len(closed_df) else None

c = st.columns(6)
c[0].metric("Aperte adesso", len(open_df))
c[1].metric("P&L aperto se chiuse ora", f"${open_pnl:,.2f}")
c[2].metric("Chiuse", len(closed_df))
c[3].metric("P&L chiuso netto", f"${closed_pnl:,.2f}")
c[4].metric("Vinte / Perse", f"{closed_wins} / {closed_losses}")
c[5].metric("Win rate", f"{win_rate:.2f}%" if win_rate is not None else "N/D")

st.subheader("🟢 Cosa sta girando adesso")
if open_df.empty:
    st.info("Nessuna posizione paper aperta.")
else:
    shown_open = open_df[[
        "Ticker", "Strategia", "Tier", "Entry", "Prezzo attuale",
        "P&L netto se chiusa ora $", "Performance %", "Stop", "TP1", "TP2", "Esito", "Apertura",
    ]]
    st.dataframe(fmt_table(shown_open), width="stretch", hide_index=True)
    s = open_df.groupby("Strategia", dropna=False).agg(
        Posizioni=("Ticker", "count"),
        PnL_netto=("P&L netto se chiusa ora $", "sum"),
        Performance_media=("Performance %", "mean"),
    ).reset_index()
    st.markdown("#### Come stanno andando le strategie aperte")
    st.dataframe(fmt_table(s.sort_values("PnL_netto", ascending=False)), width="stretch", hide_index=True)

st.subheader("🏁 Operazioni chiuse · risultati realizzati")
if closed_df.empty:
    st.info(
        "Nessuna operazione paper chiusa per ora. Il lifecycle del Laboratory viene aggiornato dal workflow giornaliero: "
        "le nuove posizioni aperte oggi non risultano chiuse finche' un run successivo non osserva Stop, TP1/TP2 o altra condizione di uscita."
    )
else:
    shown_closed = closed_df[[
        "Ticker", "Strategia", "Tier", "Entry", "Prezzo uscita",
        "P&L realizzato netto $", "Performance %", "Esito", "Motivo chiusura", "Apertura",
    ]]
    st.dataframe(fmt_table(shown_closed), width="stretch", hide_index=True)
    cs = closed_df.groupby("Strategia", dropna=False).agg(
        Trade=("Ticker", "count"),
        Vinte=("P&L realizzato netto $", lambda x: int((x > 0).sum())),
        Perse=("P&L realizzato netto $", lambda x: int((x < 0).sum())),
        PnL_netto=("P&L realizzato netto $", "sum"),
        Performance_media=("Performance %", "mean"),
    ).reset_index()
    cs["Win rate %"] = cs["Vinte"] / cs["Trade"] * 100
    st.markdown("#### Performance storica per strategia")
    st.dataframe(fmt_table(cs.sort_values("PnL_netto", ascending=False)), width="stretch", hide_index=True)

st.caption("P&L aperto = netto teorico se liquidato adesso; P&L chiuso = risultato realizzato salvato dal lifecycle worker.")
st.caption(f"Aggiornato: {datetime.now().astimezone().strftime('%d/%m/%Y %H:%M:%S %Z')}")
