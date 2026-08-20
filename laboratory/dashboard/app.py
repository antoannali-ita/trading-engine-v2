import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

LAB_ROOT = Path(__file__).resolve().parents[1]
SRC = LAB_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from lab.auth import require_dashboard_auth
from lab.db import get_supabase_client
from lab.settings import CAPITAL_TOTAL_BASE, MAX_NEW_BUYS, MAX_POSITION_USD, PREFERRED_ORDER_TYPE, USA_COMMISSION_USD
from lab.ui import apply_theme, page_header

st.set_page_config(page_title="Trading Lab", layout="wide", page_icon="📈")
require_dashboard_auth()
apply_theme()
page_header(
    "Control Room",
    "Vista rapida su segnali, capitale, stato del motore e priorità operative. In pochi secondi devi capire cosa merita attenzione e quanto puoi impegnare.",
)

try:
    supabase = get_supabase_client()
except Exception as exc:
    st.error(str(exc))
    st.stop()

runs_response = supabase.table("engine_runs").select("*").order("run_timestamp", desc=True).limit(100).execute()
signals_response = supabase.table("signals").select("*").order("created_at", desc=True).limit(250).execute()

runs = pd.DataFrame(runs_response.data or [])
signals = pd.DataFrame(signals_response.data or [])

interesting = {"BUY NOW", "BUY LIMIT", "PRE-BUY", "PRE_BUY", "PRE_BUY_HIGH", "SHADOW_BUY"}
if not signals.empty:
    decision_series = signals.get("decision", pd.Series(index=signals.index, dtype=object)).fillna("").astype(str).str.upper()
    status_series = signals.get("status", pd.Series(index=signals.index, dtype=object)).fillna("").astype(str).str.upper()
    action_mask = decision_series.isin(interesting) | status_series.isin(interesting)
    action_count = int(action_mask.sum())
    ticker_count = int(signals["ticker"].nunique()) if "ticker" in signals else 0
    dq_bad = int(signals.get("data_quality", pd.Series(index=signals.index, dtype=object)).fillna("").astype(str).str.upper().isin(["FAIL", "ERROR", "DATA REVIEW", "LOW"]).sum())
else:
    action_count = ticker_count = dq_bad = 0

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Capitale configurato", f"{CAPITAL_TOTAL_BASE:,.0f}", help="Capitale totale base del progetto. La dashboard non presume un cambio EUR/USD.")
c2.metric("Max posizione", f"${MAX_POSITION_USD:,.0f}", help="Tetto massimo per una singola nuova posizione USA.")
c3.metric("Candidati operativi", action_count, help="BUY / BUY LIMIT / PRE-BUY / SHADOW_BUY.")
c4.metric("Ticker monitorati", ticker_count)
c5.metric("Data warning", dq_bad, help="Segnali con qualità dati bassa o in revisione.")

st.caption(f"Policy: max {MAX_NEW_BUYS} nuovi BUY · preferenza {PREFERRED_ORDER_TYPE} · commissione USA ${USA_COMMISSION_USD:.0f} per operazione.")

st.markdown("### Priorità operative")
if signals.empty:
    st.info("Nessun segnale Core ancora presente. Il laboratorio research è già attivo, ma il Core non sta ancora persistendo automaticamente i suoi segnali in questa tabella.")
else:
    view = signals[action_mask].copy()
    if view.empty:
        st.success("Nessun candidato operativo ad alta priorità al momento. Anche non comprare è una decisione, per quanto il mercato faccia di tutto per renderla noiosa.")
    else:
        if "score_total" in view:
            view["score_total"] = pd.to_numeric(view["score_total"], errors="coerce")
            view = view.sort_values("score_total", ascending=False)
        top = view.head(5)
        cols = st.columns(min(5, len(top)))
        for col, (_, row) in zip(cols, top.iterrows()):
            with col:
                ticker = row.get("ticker", "N/D")
                state = row.get("decision") or row.get("status") or "N/D"
                score = row.get("score_total", "N/D")
                rr = row.get("rr_net_tp2", "N/D")
                st.markdown(f"#### {ticker}")
                st.caption(str(state))
                st.metric("Score", f"{score:.1f}" if isinstance(score, (int, float)) and pd.notna(score) else score)
                st.write(f"**R/R TP2:** {rr}")
                st.write(f"**Trigger:** {row.get('trigger', 'N/D')}")
                st.write(f"**Entry:** {row.get('entry', 'N/D')}")
                st.write(f"**Stop:** {row.get('stop', 'N/D')}")

left, right = st.columns([1.35, 1])
with left:
    st.markdown("### Distribuzione segnali")
    if not signals.empty and "status" in signals:
        counts = signals["status"].fillna("N/D").value_counts().rename_axis("status").reset_index(name="count")
        fig = px.bar(counts, x="status", y="count", text="count", title="Segnali per stato")
        fig.update_layout(height=360, margin=dict(l=10, r=10, t=45, b=10), xaxis_title=None, yaxis_title=None)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Stati segnale non ancora disponibili.")

with right:
    st.markdown("### Engine snapshot")
    if runs.empty:
        st.info("Nessun run Core registrato.")
    else:
        latest = runs.iloc[0]
        st.metric("Ultimo run", str(latest.get("run_id", "N/D")))
        st.write(f"**Market:** {latest.get('market', 'N/D')}")
        st.write(f"**Horizon:** {latest.get('horizon', 'N/D')}")
        st.write(f"**Engine:** {latest.get('engine_version', 'N/D')}")
        st.write(f"**Config:** {latest.get('config_version', 'N/D')}")
        st.write(f"**Timestamp:** {latest.get('run_timestamp', 'N/D')}")

with st.expander("Segnali recenti · dettaglio"):
    if signals.empty:
        st.info("Nessun segnale ancora presente nel database.")
    else:
        preferred = ["created_at", "market", "ticker", "horizon", "status", "decision", "price", "score_total", "setup", "trigger", "entry", "max_buy", "stop", "tp1", "tp2", "rr_net_tp2", "earnings_date"]
        cols = [col for col in preferred if col in signals.columns]
        st.dataframe(signals[cols], use_container_width=True, hide_index=True)

st.caption("Trading Lab 2.0 · PAPER / RESEARCH first · nessun ordine viene inviato automaticamente al broker.")
