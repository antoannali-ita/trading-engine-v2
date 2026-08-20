import sys
from pathlib import Path

import pandas as pd
import streamlit as st

LAB_ROOT = Path(__file__).resolve().parents[2]
SRC = LAB_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from lab.auth import require_dashboard_auth
from lab.data import load_signals
from lab.ui import apply_theme, page_header

st.set_page_config(page_title="Trading Lab | Action Center", layout="wide", page_icon="⚡")
require_dashboard_auth()
apply_theme()
page_header(
    "Action Center",
    "Solo ciò che può richiedere una decisione. Entry, trigger, rischio e target in primo piano; il resto resta dettaglio.",
    eyebrow="TODAY · DECISION · RISK",
)

try:
    signals = load_signals(1000)
except Exception as exc:
    st.error(str(exc))
    st.stop()

if signals.empty:
    st.info("Nessun segnale Core disponibile. Il Research Lab continua a funzionare separatamente.")
    st.stop()

for col in ["score_total", "price", "entry", "max_buy", "stop", "tp1", "tp2", "rr_net_tp2", "qty", "capital", "loss_max"]:
    if col in signals:
        signals[col] = pd.to_numeric(signals[col], errors="coerce")

interesting = {"BUY NOW", "BUY LIMIT", "PRE-BUY", "PRE_BUY", "PRE_BUY_HIGH", "SHADOW_BUY"}
mask = signals.apply(lambda r: str(r.get("decision", "")).upper() in interesting or str(r.get("status", "")).upper() in interesting, axis=1)
view = signals[mask].copy()
if "score_total" in view:
    view = view.sort_values("score_total", ascending=False)

if view.empty:
    st.success("Nessun candidato operativo al momento. Decisione di oggi: ASPETTA.")
    st.stop()

k1, k2, k3, k4 = st.columns(4)
k1.metric("Candidati", len(view))
k2.metric("Score migliore", f"{view['score_total'].max():.1f}" if "score_total" in view and view["score_total"].notna().any() else "N/D")
k3.metric("R/R migliore", f"{view['rr_net_tp2'].max():.2f}" if "rr_net_tp2" in view and view["rr_net_tp2"].notna().any() else "N/D")
k4.metric("Trigger confirmed", int(view.get("trigger", pd.Series(index=view.index, dtype=object)).fillna("").astype(str).str.upper().eq("CONFIRMED").sum()))

st.markdown("### Migliore operazione")
best = view.iloc[0]
with st.container(border=True):
    c0, c1, c2, c3, c4 = st.columns([1.25, 1, 1, 1, 1])
    c0.markdown(f"## {best.get('ticker', 'N/D')}")
    c0.caption(str(best.get("decision") or best.get("status") or "N/D"))
    c1.metric("Score", f"{best.get('score_total'):.1f}" if pd.notna(best.get('score_total')) else "N/D")
    c2.metric("Entry", f"{best.get('entry'):.2f}" if pd.notna(best.get('entry')) else "N/D")
    c3.metric("Stop", f"{best.get('stop'):.2f}" if pd.notna(best.get('stop')) else "N/D")
    c4.metric("R/R TP2", f"{best.get('rr_net_tp2'):.2f}" if pd.notna(best.get('rr_net_tp2')) else "N/D")

    a, b, c, d = st.columns(4)
    a.write(f"**Trigger:** {best.get('trigger', 'N/D')}")
    b.write(f"**Max Buy:** {best.get('max_buy', 'N/D')}")
    c.write(f"**TP1:** {best.get('tp1', 'N/D')}")
    d.write(f"**TP2:** {best.get('tp2', 'N/D')}")
    st.caption(f"Setup: {best.get('setup', 'N/D')} · Earnings: {best.get('earnings_date', 'N/D')} · Data quality: {best.get('data_quality', 'N/D')}")

    market = best.get("market", "")
    exchange = "NASDAQ" if market == "USA" else "MIL"
    st.link_button("Apri TradingView", f"https://www.tradingview.com/chart/?symbol={exchange}:{best.get('ticker', '')}")
    st.code(
        f"{best.get('ticker', 'N/D')} | LIMIT {best.get('entry', 'N/D')} | QTY {best.get('qty', 'N/D')} | STOP {best.get('stop', 'N/D')} | TP1 {best.get('tp1', 'N/D')} | TP2 {best.get('tp2', 'N/D')}",
        language=None,
    )

if len(view) > 1:
    st.markdown("### Altri candidati")
    cols = st.columns(2)
    for i, (_, row) in enumerate(view.iloc[1:7].iterrows()):
        with cols[i % 2]:
            with st.container(border=True):
                st.markdown(f"### {row.get('ticker', 'N/D')} · {row.get('status', row.get('decision', ''))}")
                x1, x2, x3 = st.columns(3)
                x1.metric("Score", f"{row.get('score_total'):.1f}" if pd.notna(row.get('score_total')) else "N/D")
                x2.metric("R/R", f"{row.get('rr_net_tp2'):.2f}" if pd.notna(row.get('rr_net_tp2')) else "N/D")
                x3.metric("Trigger", str(row.get('trigger', 'N/D')))
                st.write(f"Entry {row.get('entry', 'N/D')} · Stop {row.get('stop', 'N/D')} · TP2 {row.get('tp2', 'N/D')}")

with st.expander("Tutti i candidati · dettaglio"):
    cols = [c for c in ["ticker", "market", "status", "decision", "score_total", "setup", "trigger", "price", "entry", "max_buy", "stop", "tp1", "tp2", "rr_net_tp2", "qty", "capital", "loss_max", "earnings_date", "data_quality"] if c in view.columns]
    st.dataframe(view[cols], use_container_width=True, hide_index=True)

st.caption("Supporto decisionale soltanto. Nessun ordine automatico viene inviato a Fineco.")
