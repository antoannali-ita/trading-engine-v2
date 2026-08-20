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
from lab.ui import (
    apply_theme,
    candidate_title,
    company_name,
    fmt_money,
    fmt_pct,
    fmt_qty,
    fmt_quality,
    fmt_regime,
    fmt_rr,
    fmt_score,
    fmt_status,
    fmt_strategy,
    fmt_trigger,
    localize_table,
    page_header,
    trigger_class,
)

st.set_page_config(page_title="Trading Lab | Centro operativo", layout="wide", page_icon="⚡")
require_dashboard_auth()
apply_theme()
page_header(
    "Centro operativo",
    "Imbuto decisionale del Laboratory: punteggio strategia → punteggio operazione → idoneità portafoglio → controlli → simulazione approvata. Nessun ordine reale viene creato qui.",
    eyebrow="LAB · STRATEGIA · OPERAZIONE · PORTAFOGLIO · RISCHIO",
)


def _details(row) -> dict:
    value = row.get("details")
    return value if isinstance(value, dict) else {}


def _extract(row, key, default=None):
    return _details(row).get(key, default)


def _failed_text(details: dict) -> str:
    parts = []
    dq = details.get("data_quality") if isinstance(details.get("data_quality"), dict) else {}
    tg = details.get("trade_eligibility") if isinstance(details.get("trade_eligibility"), dict) else {}
    pg = details.get("portfolio_eligibility") if isinstance(details.get("portfolio_eligibility"), dict) else {}
    parts.extend(dq.get("red", []) or [])
    parts.extend(tg.get("failed", []) or [])
    parts.extend(pg.get("failed", []) or [])
    return ", ".join(dict.fromkeys(parts)) if parts else "SUPERATI"


try:
    watch = load_lab_watchlist(2000)
    positions = load_lab_paper_positions(1000)
except Exception as exc:
    st.error("Le tabelle operative del Laboratory non sono leggibili.")
    st.code(str(exc))
    st.stop()

if watch.empty:
    st.info("Nessun candidato operativo nel Lab. Esegui il flusso giornaliero del Laboratory per aggiornare l'imbuto.")
    st.stop()

for col in ["score", "price", "entry", "max_buy", "stop", "tp1", "tp2", "alert_price", "distance_to_entry_pct"]:
    if col in watch:
        watch[col] = pd.to_numeric(watch[col], errors="coerce")

watch["strategy_score"] = watch.apply(lambda r: _extract(r, "strategy_score", r.get("score")), axis=1)
watch["trade_score"] = watch.apply(lambda r: _extract(r, "trade_score"), axis=1)
watch["portfolio_fit"] = watch.apply(lambda r: _extract(r, "portfolio_fit_score"), axis=1)
watch["rr_net_tp2"] = watch.apply(lambda r: _extract(r, "rr_net_tp2"), axis=1)
watch["data_quality"] = watch.apply(lambda r: (_extract(r, "data_quality", {}) or {}).get("status", "N/D"), axis=1)
watch["regime"] = watch.apply(lambda r: (_extract(r, "market_regime", {}) or {}).get("state", "N/D"), axis=1)
watch["gate_result"] = watch.apply(lambda r: _failed_text(_details(r)), axis=1)

rank = {"PAPER_OPEN": 0, "CONFIRMED": 1, "PRE_BUY": 2, "NEAR_SETUP": 3, "WATCH": 4, "BLOCKED_DATA": 8, "BENCHMARK": 9}
watch["_rank"] = watch.get("status", pd.Series(index=watch.index, dtype=object)).fillna("").astype(str).str.upper().map(rank).fillna(7)
watch = watch.sort_values(["_rank", "trade_score", "strategy_score"], ascending=[True, False, False]).drop(columns="_rank")

active_states = ["PAPER_OPEN", "CONFIRMED", "PRE_BUY", "NEAR_SETUP"]
active = watch[watch["status"].fillna("").astype(str).str.upper().isin(active_states)].copy()
view = active if not active.empty else watch.head(10).copy()

open_paper = positions.copy()
if not positions.empty and "status" in positions:
    open_paper = positions[positions["status"].fillna("").astype(str).str.upper().isin(["OPEN", "TP1_HIT"])]

k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("Candidati", len(view))
k2.metric("Simulazioni approvate", int((watch["status"].astype(str).str.upper() == "PAPER_OPEN").sum()))
k3.metric("Confermati", int((watch["status"].astype(str).str.upper() == "CONFIRMED").sum()))
k4.metric("Pre-acquisto", int((watch["status"].astype(str).str.upper() == "PRE_BUY").sum()))
k5.metric("Qualità dati rossa", int((watch["data_quality"].astype(str).str.upper() == "RED").sum()))
k6.metric("Posizioni simulate aperte", len(open_paper))

st.markdown("### Migliore opportunità Lab")
best = view.iloc[0]
with st.container(border=True):
    st.markdown(f'<div class="candidate-title" style="font-size:1.22rem">{candidate_title(best.get("symbol"))}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="candidate-state">{fmt_status(best.get("status"))} · {fmt_strategy(best.get("strategy"))}</div>', unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4, gap="small")
    c1.metric("Punteggio strategia", fmt_score(best.get("strategy_score")))
    c2.metric("Punteggio operazione", fmt_score(best.get("trade_score")))
    c3.metric("Idoneità portafoglio", fmt_score(best.get("portfolio_fit")))
    c4.metric("R/R netto TP2", fmt_rr(best.get("rr_net_tp2")))

    a, b, c, d = st.columns(4, gap="small")
    trigger = fmt_trigger(best.get("trigger"))
    with a:
        st.caption("Conferma")
        st.markdown(f'<span class="trigger-badge {trigger_class(trigger)}">{trigger}</span>', unsafe_allow_html=True)
    b.write(f"**Qualità dati:** {fmt_quality(best.get('data_quality', 'N/D'))}")
    c.write(f"**Regime:** {fmt_regime(best.get('regime', 'N/D'))}")
    d.write(f"**Controlli:** {best.get('gate_result', 'N/D')}")

    x1, x2, x3, x4 = st.columns(4, gap="small")
    x1.write(f"**Ingresso:** {fmt_money(best.get('entry'))}")
    x2.write(f"**Prezzo massimo:** {fmt_money(best.get('max_buy'))}")
    x3.write(f"**Stop:** {fmt_money(best.get('stop'))}")
    x4.write(f"**TP2:** {fmt_money(best.get('tp2'))}")

    details = _details(best)
    st.caption(
        f"Quantità basata sul rischio: {fmt_qty(details.get('qty'))} · Capitale: {fmt_money(details.get('capital'))} · "
        f"Perdita massima stimata: {fmt_money(details.get('loss_max'))} · Prossimi utili: {details.get('earnings_date', 'N/D')} · "
        f"Modello costi esecuzione: {details.get('execution_cost_model', 'N/D')}"
    )

if len(view) > 1:
    st.markdown("### Altri candidati")
    cols = st.columns(2, gap="small")
    for i, (_, row) in enumerate(view.iloc[1:9].iterrows()):
        with cols[i % 2]:
            with st.container(border=True):
                st.markdown(f'<div class="candidate-title">{candidate_title(row.get("symbol"))}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="candidate-state">{fmt_status(row.get("status"))} · {fmt_strategy(row.get("strategy"))}</div>', unsafe_allow_html=True)
                x1, x2, x3 = st.columns(3, gap="small")
                x1.metric("Strategia", fmt_score(row.get("strategy_score")))
                x2.metric("Operazione", fmt_score(row.get("trade_score")))
                x3.metric("Portafoglio", fmt_score(row.get("portfolio_fit")))
                st.caption(
                    f"Qualità dati {fmt_quality(row.get('data_quality', 'N/D'))} · Regime {fmt_regime(row.get('regime', 'N/D'))} · "
                    f"R/R {fmt_rr(row.get('rr_net_tp2'))} · Controlli {row.get('gate_result', 'SUPERATI')}"
                )
                st.markdown(
                    f'<div class="candidate-detail"><b>Ingresso / prezzo massimo:</b> {fmt_money(row.get("entry"))} / {fmt_money(row.get("max_buy"))}<br>'
                    f'<b>Stop:</b> {fmt_money(row.get("stop"))} · <b>TP2:</b> {fmt_money(row.get("tp2"))}</div>',
                    unsafe_allow_html=True,
                )

with st.expander("Tutto l'imbuto operativo", expanded=False):
    display = watch.copy()
    if "symbol" in display:
        display.insert(display.columns.get_loc("symbol") + 1, "azienda", display["symbol"].map(company_name))
    for col in ["price", "entry", "max_buy", "stop", "tp1", "tp2", "alert_price"]:
        if col in display:
            display[col] = display[col].map(fmt_money)
    if "distance_to_entry_pct" in display:
        display["distance_to_entry_pct"] = display["distance_to_entry_pct"].map(fmt_pct)
    for col in ["strategy_score", "trade_score", "portfolio_fit"]:
        if col in display:
            display[col] = display[col].map(fmt_score)
    if "rr_net_tp2" in display:
        display["rr_net_tp2"] = display["rr_net_tp2"].map(fmt_rr)
    preferred = ["symbol", "azienda", "strategy", "status", "strategy_score", "trade_score", "portfolio_fit", "data_quality", "regime", "gate_result", "trigger", "price", "entry", "max_buy", "stop", "tp1", "tp2", "rr_net_tp2", "alert_type", "alert_price", "distance_to_entry_pct", "signal_date", "last_seen_at"]
    cols = [c for c in preferred if c in display.columns]
    st.dataframe(localize_table(display[cols]), use_container_width=True, hide_index=True)

st.caption("La simulazione viene approvata solo dopo i controlli su dati, operazione e portafoglio. I tre punteggi restano gerarchici e non vengono sommati in un punteggio unico ottimizzato.")
