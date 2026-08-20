import sys
from pathlib import Path

import pandas as pd
import streamlit as st

LAB_ROOT = Path(__file__).resolve().parents[1]
SRC = LAB_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from lab.auth import require_dashboard_auth
from lab.db import get_supabase_client


st.set_page_config(page_title="Trading Lab", layout="wide")
require_dashboard_auth()
st.title("Trading Lab | Control Room")

try:
    supabase = get_supabase_client()
except Exception as exc:
    st.error(str(exc))
    st.stop()

runs_response = (
    supabase.table("engine_runs")
    .select("*")
    .order("run_timestamp", desc=True)
    .limit(100)
    .execute()
)

signals_response = (
    supabase.table("signals")
    .select("*")
    .order("created_at", desc=True)
    .limit(250)
    .execute()
)

runs = pd.DataFrame(runs_response.data or [])
signals = pd.DataFrame(signals_response.data or [])

c1, c2, c3, c4 = st.columns(4)
c1.metric("Runs caricati", len(runs))
c2.metric("Segnali caricati", len(signals))

if not signals.empty:
    c3.metric("Ticker unici", signals["ticker"].nunique() if "ticker" in signals else 0)
    c4.metric("Ultimo score", signals.iloc[0].get("score_total", "N/D"))
else:
    c3.metric("Ticker unici", 0)
    c4.metric("Ultimo score", "N/D")

st.subheader("Segnali recenti")
if signals.empty:
    st.info("Nessun segnale ancora presente nel database.")
else:
    preferred = [
        "created_at", "market", "ticker", "horizon", "status", "decision",
        "price", "score_total", "setup", "trigger", "entry", "max_buy",
        "stop", "tp1", "tp2", "rr_net_tp2", "earnings_date"
    ]
    cols = [col for col in preferred if col in signals.columns]
    st.dataframe(signals[cols], use_container_width=True, hide_index=True)

st.subheader("Ultimi run")
if runs.empty:
    st.info("Nessun run presente nel database.")
else:
    st.dataframe(runs, use_container_width=True, hide_index=True)
