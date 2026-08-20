import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

LAB_ROOT = Path(__file__).resolve().parents[2]
SRC = LAB_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from lab.auth import require_dashboard_auth
from lab.data import load_signals
from lab.ui import apply_theme, page_header

st.set_page_config(page_title="Trading Lab | Signals", layout="wide", page_icon="🎯")
require_dashboard_auth()
apply_theme()
page_header(
    "Signals",
    "Screener operativo dei segnali Core. Filtra, confronta score e R/R e concentra l'attenzione sui setup realmente azionabili.",
    eyebrow="CORE SIGNALS · DECISION SUPPORT",
)

try:
    signals = load_signals()
except Exception as exc:
    st.error(str(exc))
    st.stop()

if signals.empty:
    st.info("Nessun segnale Core nel database. Il Research Lab può comunque avere risultati propri nella pagina Strategy Lab.")
    st.stop()

for col in ["score_total", "price", "entry", "max_buy", "stop", "tp1", "tp2", "rr_net_tp1", "rr_net_tp2"]:
    if col in signals:
        signals[col] = pd.to_numeric(signals[col], errors="coerce")

markets = sorted(signals["market"].dropna().unique().tolist()) if "market" in signals else []
statuses = sorted(signals["status"].dropna().unique().tolist()) if "status" in signals else []
horizons = sorted(signals["horizon"].dropna().unique().tolist()) if "horizon" in signals else []

with st.container(border=True):
    c1, c2, c3, c4 = st.columns(4)
    market = c1.multiselect("Mercato", markets, default=markets)
    status = c2.multiselect("Stato", statuses, default=statuses)
    horizon = c3.multiselect("Horizon", horizons, default=horizons)
    min_score = c4.slider("Score minimo", 0, 100, 0, help="Filtro visuale: non modifica lo score del motore.")

view = signals.copy()
if market:
    view = view[view["market"].isin(market)]
if status:
    view = view[view["status"].isin(status)]
if horizon:
    view = view[view["horizon"].isin(horizon)]
if "score_total" in view:
    view = view[view["score_total"].fillna(0) >= min_score]
    view = view.sort_values("score_total", ascending=False)

operational = {"BUY NOW", "BUY LIMIT", "PRE-BUY", "PRE_BUY", "PRE_BUY_HIGH", "SHADOW_BUY"}
state = view.get("decision", pd.Series(index=view.index, dtype=object)).fillna("").astype(str).str.upper()
status_state = view.get("status", pd.Series(index=view.index, dtype=object)).fillna("").astype(str).str.upper()
active_mask = state.isin(operational) | status_state.isin(operational)

k1, k2, k3, k4 = st.columns(4)
k1.metric("Segnali filtrati", len(view))
k2.metric("Operativi", int(active_mask.sum()), help="BUY / BUY LIMIT / PRE-BUY / SHADOW_BUY")
k3.metric("Score medio", f"{view['score_total'].mean():.1f}" if "score_total" in view and view["score_total"].notna().any() else "N/D")
k4.metric("R/R medio TP2", f"{view['rr_net_tp2'].mean():.2f}" if "rr_net_tp2" in view and view["rr_net_tp2"].notna().any() else "N/D", help="Rapporto rendimento/rischio netto stimato sul target principale.")

st.markdown("### Candidati in evidenza")
active = view[active_mask].head(6)
if active.empty:
    st.info("Nessun candidato operativo con i filtri attuali.")
else:
    cols = st.columns(3)
    for idx, (_, row) in enumerate(active.iterrows()):
        with cols[idx % 3]:
            with st.container(border=True):
                st.markdown(f"### {row.get('ticker', 'N/D')}")
                st.caption(f"{row.get('status', '')} · {row.get('setup', 'N/D')}")
                a, b, c = st.columns(3)
                a.metric("Score", f"{row.get('score_total'):.1f}" if pd.notna(row.get('score_total')) else "N/D")
                b.metric("R/R", f"{row.get('rr_net_tp2'):.2f}" if pd.notna(row.get('rr_net_tp2')) else "N/D")
                c.metric("Trigger", str(row.get('trigger', 'N/D')))
                st.write(f"**Entry:** {row.get('entry', 'N/D')}  ·  **Max Buy:** {row.get('max_buy', 'N/D')}")
                st.write(f"**Stop:** {row.get('stop', 'N/D')}  ·  **TP2:** {row.get('tp2', 'N/D')}")
                st.caption(f"Data quality: {row.get('data_quality', 'N/D')} · Earnings: {row.get('earnings_date', 'N/D')}")

left, right = st.columns(2)
with left:
    if "score_total" in view and view["score_total"].notna().any():
        fig = px.histogram(view, x="score_total", nbins=15, title="Distribuzione score")
        fig.update_layout(height=350, margin=dict(l=10, r=10, t=45, b=10))
        st.plotly_chart(fig, use_container_width=True)
with right:
    if "status" in view:
        counts = view["status"].fillna("N/D").value_counts().rename_axis("status").reset_index(name="count")
        fig = px.bar(counts, x="status", y="count", text="count", title="Segnali per stato")
        fig.update_layout(height=350, margin=dict(l=10, r=10, t=45, b=10), xaxis_title=None, yaxis_title=None)
        st.plotly_chart(fig, use_container_width=True)

if "ticker" in view:
    view["TradingView"] = view.apply(lambda r: f"https://www.tradingview.com/chart/?symbol={'NASDAQ' if r.get('market') == 'USA' else 'MIL'}:{r.get('ticker')}", axis=1)
preferred = ["created_at", "market", "ticker", "horizon", "status", "decision", "price", "score_total", "setup", "trigger", "entry", "buy_range_low", "buy_range_high", "max_buy", "stop", "tp1", "tp2", "rr_net_tp1", "rr_net_tp2", "earnings_date", "data_quality", "TradingView"]
cols = [c for c in preferred if c in view.columns]
with st.expander("Tabella completa", expanded=False):
    st.dataframe(view[cols], use_container_width=True, hide_index=True, column_config={"TradingView": st.column_config.LinkColumn("Chart", display_text="Apri")})

st.caption("Score e stati sono output del motore. Questa pagina li organizza, non li ricalcola.")
