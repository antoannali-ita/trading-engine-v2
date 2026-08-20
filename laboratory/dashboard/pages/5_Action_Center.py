import sys
from pathlib import Path

import pandas as pd
import streamlit as st

LAB_ROOT = Path(__file__).resolve().parents[2]
SRC = LAB_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from lab.auth import require_dashboard_auth
from lab.data import load_lab_paper_positions, load_lab_watchlist
from lab.settings import USA_COMMISSION_USD
from lab.ui import (
    apply_theme,
    candidate_title,
    company_name,
    fmt_money,
    fmt_pct,
    fmt_qty,
    fmt_rr,
    fmt_score,
    fmt_trigger,
    page_header,
    trigger_class,
)

st.set_page_config(page_title="Trading Lab | Action Center", layout="wide", page_icon="⚡")
require_dashboard_auth()
apply_theme()
page_header(
    "Action Center",
    "Priorità operative del Laboratory: PAPER OPEN, PRE-BUY e NEAR SETUP. Il Core resta separato e nessun ordine reale viene creato qui.",
    eyebrow="LAB · TODAY · ENTRY · RISK",
)


def _num(value):
    try:
        number = float(value)
        return None if pd.isna(number) else number
    except Exception:
        return None


def _details(row) -> dict:
    value = row.get("details")
    return value if isinstance(value, dict) else {}


def _net_rr(row) -> float | None:
    entry = _num(row.get("entry"))
    stop = _num(row.get("stop"))
    tp2 = _num(row.get("tp2"))
    details = _details(row)
    qty = _num(details.get("qty"))
    commission = _num(details.get("commission")) or USA_COMMISSION_USD
    if None in (entry, stop, tp2, qty) or qty <= 0 or entry <= stop:
        return None
    risk = (entry - stop) * qty + commission
    reward = (tp2 - entry) * qty - 2.0 * commission
    return reward / risk if risk > 0 else None


try:
    watch = load_lab_watchlist(2000)
    positions = load_lab_paper_positions(1000)
except Exception as exc:
    st.error("Le tabelle operative del Laboratory non sono leggibili.")
    st.code(str(exc))
    st.stop()

if watch.empty:
    st.info("Nessun candidato operativo nel Lab. Esegui il job Strategy Lab Daily Opportunity Feed per aggiornare la ladder.")
    st.stop()

for col in ["score", "price", "entry", "max_buy", "stop", "tp1", "tp2", "alert_price", "distance_to_entry_pct"]:
    if col in watch:
        watch[col] = pd.to_numeric(watch[col], errors="coerce")

watch["rr_net_tp2"] = watch.apply(_net_rr, axis=1)
rank = {"PAPER_OPEN": 0, "PRE_BUY": 1, "NEAR_SETUP": 2, "WATCH": 3}
watch["_rank"] = watch.get("status", pd.Series(index=watch.index, dtype=object)).fillna("").astype(str).str.upper().map(rank).fillna(9)
watch = watch.sort_values(["_rank", "score"], ascending=[True, False]).drop(columns="_rank")

active = watch[watch["status"].fillna("").astype(str).str.upper().isin(["PAPER_OPEN", "PRE_BUY", "NEAR_SETUP"])].copy()
view = active if not active.empty else watch.head(10).copy()

open_paper = positions.copy()
if not positions.empty and "status" in positions:
    open_paper = positions[positions["status"].fillna("").astype(str).str.upper().isin(["OPEN", "TP1_HIT"])]

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Candidati", len(view))
k2.metric("PAPER OPEN", int((watch["status"].astype(str).str.upper() == "PAPER_OPEN").sum()))
k3.metric("PRE-BUY", int((watch["status"].astype(str).str.upper() == "PRE_BUY").sum()))
k4.metric("Trigger confermati", int((watch["trigger"].fillna("").astype(str).str.upper() == "CONFIRMED").sum()) if "trigger" in watch else 0)
k5.metric("Paper aperte", len(open_paper))

st.markdown("### Migliore opportunità Lab")
best = view.iloc[0]
with st.container(border=True):
    st.markdown(f'<div class="candidate-title" style="font-size:1.22rem">{candidate_title(best.get("symbol"))}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="candidate-state">{best.get("status", "N/D")} · {best.get("strategy", "N/D")}</div>', unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4, gap="small")
    c1.metric("Score", fmt_score(best.get("score")))
    c2.metric("Entry", fmt_money(best.get("entry")))
    c3.metric("Stop", fmt_money(best.get("stop")))
    c4.metric("R/R netto TP2", fmt_rr(best.get("rr_net_tp2")))

    a, b, c, d = st.columns(4, gap="small")
    trigger = fmt_trigger(best.get("trigger"))
    with a:
        st.caption("Trigger")
        st.markdown(f'<span class="trigger-badge {trigger_class(trigger)}">{trigger}</span>', unsafe_allow_html=True)
    b.write(f"**Max Buy:** {fmt_money(best.get('max_buy'))}")
    c.write(f"**TP1:** {fmt_money(best.get('tp1'))}")
    d.write(f"**TP2:** {fmt_money(best.get('tp2'))}")

    details = _details(best)
    st.caption(
        f"Alert: {best.get('alert_type', 'N/D')} @ {fmt_money(best.get('alert_price'))} · "
        f"Distanza entry: {fmt_pct(best.get('distance_to_entry_pct'))} · "
        f"Earnings: {details.get('earnings_date', 'N/D')}"
    )
    qty = details.get("qty")
    st.code(
        f"{best.get('symbol', 'N/D')} | PAPER LIMIT {fmt_money(best.get('entry'))} | QTY {fmt_qty(qty)} | STOP {fmt_money(best.get('stop'))} | TP1 {fmt_money(best.get('tp1'))} | TP2 {fmt_money(best.get('tp2'))}",
        language=None,
    )

if len(view) > 1:
    st.markdown("### Altri candidati")
    cols = st.columns(2, gap="small")
    for i, (_, row) in enumerate(view.iloc[1:9].iterrows()):
        with cols[i % 2]:
            with st.container(border=True):
                st.markdown(f'<div class="candidate-title">{candidate_title(row.get("symbol"))}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="candidate-state">{row.get("status", "N/D")} · {row.get("strategy", "N/D")}</div>', unsafe_allow_html=True)
                x1, x2, x3 = st.columns([1, 1, 1.15], gap="small")
                x1.metric("Score", fmt_score(row.get("score")))
                x2.metric("R/R", fmt_rr(row.get("rr_net_tp2")))
                trigger = fmt_trigger(row.get("trigger"))
                with x3:
                    st.caption("Trigger")
                    st.markdown(f'<span class="trigger-badge {trigger_class(trigger)}">{trigger}</span>', unsafe_allow_html=True)
                st.markdown(
                    f'<div class="candidate-detail"><b>Entry / Max Buy:</b> {fmt_money(row.get("entry"))} / {fmt_money(row.get("max_buy"))}<br>'
                    f'<b>Stop:</b> {fmt_money(row.get("stop"))} · <b>TP2:</b> {fmt_money(row.get("tp2"))}</div>',
                    unsafe_allow_html=True,
                )

with st.expander("Tutta la ladder operativa", expanded=False):
    display = watch.copy()
    if "symbol" in display:
        display.insert(display.columns.get_loc("symbol") + 1, "azienda", display["symbol"].map(company_name))
    for col in ["price", "entry", "max_buy", "stop", "tp1", "tp2", "alert_price"]:
        if col in display:
            display[col] = display[col].map(fmt_money)
    if "distance_to_entry_pct" in display:
        display["distance_to_entry_pct"] = display["distance_to_entry_pct"].map(fmt_pct)
    if "score" in display:
        display["score"] = display["score"].map(fmt_score)
    if "rr_net_tp2" in display:
        display["rr_net_tp2"] = display["rr_net_tp2"].map(fmt_rr)
    if "trigger" in display:
        display["trigger"] = display["trigger"].map(fmt_trigger)
    preferred = ["symbol", "azienda", "strategy", "status", "score", "trigger", "price", "entry", "max_buy", "stop", "tp1", "tp2", "rr_net_tp2", "alert_type", "alert_price", "distance_to_entry_pct", "signal_date", "last_seen_at"]
    cols = [c for c in preferred if c in display.columns]
    st.dataframe(display[cols], use_container_width=True, hide_index=True)

st.caption("Action Center alimentato dal Laboratory. PAPER_OPEN è una simulazione research-only e non equivale a BUY reale.")
