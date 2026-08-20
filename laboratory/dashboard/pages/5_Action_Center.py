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
from lab.ui import apply_theme, fmt_money, fmt_qty, fmt_rr, fmt_score, fmt_trigger, page_header

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
k2.metric("Score migliore", fmt_score(view["score_total"].max()) if "score_total" in view else "N/D")
k3.metric("R/R migliore", fmt_rr(view["rr_net_tp2"].max()) if "rr_net_tp2" in view else "N/D")
k4.metric("Trigger confirmed", int(view.get("trigger", pd.Series(index=view.index, dtype=object)).fillna("").astype(str).str.upper().eq("CONFIRMED").sum()))

st.markdown("### Migliore operazione")
best = view.iloc[0]
with st.container(border=True):
    c0, c1, c2, c3, c4 = st.columns([1.25, 1, 1, 1, 1])
    c0.markdown(f"## {best.get('ticker', 'N/D')}")
    c0.caption(str(best.get("decision") or best.get("status") or "N/D"))
    c1.metric("Score", fmt_score(best.get("score_total")))
    c2.metric("Entry", fmt_money(best.get("entry")))
    c3.metric("Stop", fmt_money(best.get("stop")))
    c4.metric("R/R TP2", fmt_rr(best.get("rr_net_tp2")))

    a, b, c, d = st.columns(4)
    a.write(f"**Trigger:** {fmt_trigger(best.get('trigger'))}")
    b.write(f"**Max Buy:** {fmt_money(best.get('max_buy'))}")
    c.write(f"**TP1:** {fmt_money(best.get('tp1'))}")
    d.write(f"**TP2:** {fmt_money(best.get('tp2'))}")
    st.caption(f"Setup: {best.get('setup', 'N/D')} · Earnings: {best.get('earnings_date', 'N/D')} · Data quality: {best.get('data_quality', 'N/D')}")

    market = best.get("market", "")
    exchange = "NASDAQ" if market == "USA" else "MIL"
    st.link_button("Apri TradingView", f"https://www.tradingview.com/chart/?symbol={exchange}:{best.get('ticker', '')}")
    st.code(
        f"{best.get('ticker', 'N/D')} | LIMIT {fmt_money(best.get('entry'))} | QTY {fmt_qty(best.get('qty'))} | STOP {fmt_money(best.get('stop'))} | TP1 {fmt_money(best.get('tp1'))} | TP2 {fmt_money(best.get('tp2'))}",
        language=None,
    )

if len(view) > 1:
    st.markdown("### Altri candidati")
    cols = st.columns(2)
    for i, (_, row) in enumerate(view.iloc[1:7].iterrows()):
        with cols[i % 2]:
            with st.container(border=True):
                state = row.get("status") if pd.notna(row.get("status")) else row.get("decision", "")
                st.markdown(f"#### {row.get('ticker', 'N/D')} · {state}")
                x1, x2, x3 = st.columns(3)
                x1.metric("Score", fmt_score(row.get("score_total")))
                x2.metric("R/R", fmt_rr(row.get("rr_net_tp2")))
                x3.metric("Trigger", fmt_trigger(row.get("trigger")))
                st.markdown(
                    f'<div class="candidate-detail"><b>Entry</b> {fmt_money(row.get("entry"))} · '
                    f'<b>Stop</b> {fmt_money(row.get("stop"))} · '
                    f'<b>TP2</b> {fmt_money(row.get("tp2"))}</div>',
                    unsafe_allow_html=True,
                )

with st.expander("Tutti i candidati · dettaglio"):
    display = view.copy()
    for col in ["price", "entry", "max_buy", "stop", "tp1", "tp2", "capital", "loss_max"]:
        if col in display:
            display[col] = display[col].map(fmt_money)
    for col in ["rr_net_tp2"]:
        if col in display:
            display[col] = display[col].map(fmt_rr)
    if "score_total" in display:
        display["score_total"] = display["score_total"].map(fmt_score)
    if "trigger" in display:
        display["trigger"] = display["trigger"].map(fmt_trigger)
    cols = [c for c in ["ticker", "market", "status", "decision", "score_total", "setup", "trigger", "price", "entry", "max_buy", "stop", "tp1", "tp2", "rr_net_tp2", "qty", "capital", "loss_max", "earnings_date", "data_quality"] if c in display.columns]
    st.dataframe(display[cols], use_container_width=True, hide_index=True)

st.caption("Supporto decisionale soltanto. Nessun ordine automatico viene inviato a Fineco.")
