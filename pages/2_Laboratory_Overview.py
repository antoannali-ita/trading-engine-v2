from __future__ import annotations

import json
import os
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
    if isinstance(v, dict): return v
    try: return json.loads(str(v)) if v else {}
    except Exception: return {}


def n(v: Any) -> float | None:
    try: return float(v) if v is not None else None
    except Exception: return None


def pnl(entry, last, qty):
    entry, last, qty = n(entry), n(last), n(qty)
    if entry is None or last is None or qty is None: return None
    slip = SLIPPAGE_BPS / 10000
    return (last * (1-slip) - entry * (1+slip)) * qty - 2 * COMMISSION


def fmt_table(frame: pd.DataFrame) -> pd.io.formats.style.Styler:
    """Visualizzazione uniforme: prezzi/valuta e percentuali massimo 2 decimali."""
    money_cols = {"Entry", "Prezzo/Exit", "Stop", "TP1", "TP2", "P&L netto $", "PnL_netto"}
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
    st.markdown("**Aperte adesso** = esperimenti ancora in corso.\n\n**Chiuse** = esperimenti terminati.\n\n**P&L netto** include lo scenario commissionale Fineco $9,90 per lato e slippage di ricerca.\n\n**Tier C** = 🔬 RESEARCH ONLY, mai operativo.")

try:
    positions = load_positions()
except Exception as exc:
    st.error(f"Errore lettura Laboratory: {type(exc).__name__}: {exc}")
    st.stop()
if not positions:
    st.info("Il Laboratory non ha ancora posizioni paper.")
    st.stop()

rows=[]
for p in positions:
    d=j(p.get("details")); tier=d.get("paper_tier") or "N/D"
    status=str(p.get("status") or "N/D").upper()
    last=n(p.get("last_price")) or n(p.get("exit_price")) or n(p.get("entry_price"))
    net=pnl(p.get("entry_price"), last, p.get("qty"))
    entry=n(p.get("entry_price")); qty=n(p.get("qty"))
    ret=(net/(entry*qty)*100) if net is not None and entry and qty else n(p.get("return_pct"))
    rows.append({
        "Ticker":p.get("symbol"), "Strategia":p.get("strategy"), "Tier":tier,
        "Stato":status, "Apertura":p.get("opened_at") or p.get("created_at"),
        "Entry":entry, "Prezzo/Exit":last, "Qty":qty,
        "Stop":n(p.get("stop_current")) or n(p.get("stop_initial")),
        "TP1":n(p.get("tp1")), "TP2":n(p.get("tp2")),
        "P&L netto $":net, "Performance %":ret,
        "Esito": "🟢 GUADAGNO" if net is not None and net>0 else ("🔴 PERDITA" if net is not None and net<0 else "⚪ PARI/N.D."),
        "Motivo chiusura":p.get("exit_reason"),
    })
df=pd.DataFrame(rows)
open_mask=df["Stato"].isin(["OPEN","TP1_HIT"])
closed_mask=df["Stato"].eq("CLOSED")
open_df=df[open_mask].copy(); closed_df=df[closed_mask].copy()
open_pnl=open_df["P&L netto $"].fillna(0).sum(); closed_pnl=closed_df["P&L netto $"].fillna(0).sum()
closed_wins=int((closed_df["P&L netto $"]>0).sum()) if len(closed_df) else 0
closed_losses=int((closed_df["P&L netto $"]<0).sum()) if len(closed_df) else 0
win_rate=(closed_wins/len(closed_df)*100) if len(closed_df) else None

c=st.columns(6)
c[0].metric("Aperte adesso",len(open_df)); c[1].metric("P&L aperto netto",f"${open_pnl:,.2f}")
c[2].metric("Chiuse",len(closed_df)); c[3].metric("P&L chiuso netto",f"${closed_pnl:,.2f}")
c[4].metric("Vinte / Perse",f"{closed_wins} / {closed_losses}")
c[5].metric("Win rate",f"{win_rate:.2f}%" if win_rate is not None else "N/D")

st.subheader("🟢 Cosa sta girando adesso")
if open_df.empty: st.info("Nessuna posizione paper aperta.")
else:
    shown_open=open_df[["Ticker","Strategia","Tier","Entry","Prezzo/Exit","P&L netto $","Performance %","Stop","TP1","TP2","Esito","Apertura"]]
    st.dataframe(fmt_table(shown_open),width="stretch",hide_index=True)
    s=open_df.groupby("Strategia",dropna=False).agg(Posizioni=("Ticker","count"),PnL_netto=("P&L netto $","sum"),Performance_media=("Performance %","mean")).reset_index()
    st.markdown("#### Come stanno andando le strategie aperte")
    st.dataframe(fmt_table(s.sort_values("PnL_netto",ascending=False)),width="stretch",hide_index=True)

st.subheader("🏁 Operazioni chiuse · risultati realizzati")
if closed_df.empty: st.info("Nessuna operazione paper chiusa per ora.")
else:
    shown_closed=closed_df[["Ticker","Strategia","Tier","Entry","Prezzo/Exit","P&L netto $","Performance %","Esito","Motivo chiusura","Apertura"]]
    st.dataframe(fmt_table(shown_closed),width="stretch",hide_index=True)
    cs=closed_df.groupby("Strategia",dropna=False).agg(Trade=("Ticker","count"),Vinte=("P&L netto $",lambda x:int((x>0).sum())),Perse=("P&L netto $",lambda x:int((x<0).sum())),PnL_netto=("P&L netto $","sum"),Performance_media=("Performance %","mean")).reset_index()
    cs["Win rate %"]=cs["Vinte"]/cs["Trade"]*100
    st.markdown("#### Performance storica per strategia")
    st.dataframe(fmt_table(cs.sort_values("PnL_netto",ascending=False)),width="stretch",hide_index=True)

st.caption("P&L indicativo di ricerca: commissione $9,90 per lato + slippage 5 bps. Le pagine tecniche del Laboratory restano disponibili per analisi approfondite.")
st.caption(f"Aggiornato: {datetime.now().astimezone().strftime('%d/%m/%Y %H:%M:%S %Z')}")
