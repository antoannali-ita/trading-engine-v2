import sys
from pathlib import Path

import pandas as pd
import streamlit as st

LAB_ROOT = Path(__file__).resolve().parents[2]
SRC = LAB_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from lab.data import load_lab_backtest_results, load_lab_backtest_runs, load_lab_paper_signals

st.set_page_config(page_title="Backtest Research", layout="wide")
st.title("Backtest Research")
st.caption("Research-only. Nessun ordine reale viene inviato.")

try:
    runs = load_lab_backtest_runs()
    results = load_lab_backtest_results()
    paper = load_lab_paper_signals()
except Exception as exc:
    st.error("Tabelle research non disponibili. Eseguire laboratory/sql/02_lab_research_tables.sql su Supabase.")
    st.code(str(exc))
    st.stop()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Backtest run", len(runs))
c2.metric("Risultati", len(results))
c3.metric("Paper signal", len(paper))
if not results.empty and "return_pct" in results:
    c4.metric("Return medio", f"{pd.to_numeric(results.return_pct, errors='coerce').mean():.2f}%")
else:
    c4.metric("Return medio", "N/D")

st.subheader("Ultimi risultati")
if results.empty:
    st.info("Nessun backtest salvato ancora.")
else:
    display = [c for c in ["created_at", "symbol", "strategy", "trades", "win_rate", "profit_factor", "return_pct", "data_status"] if c in results]
    st.dataframe(results[display], use_container_width=True, hide_index=True)

    st.subheader("Performance media per strategia")
    numeric = results.copy()
    for col in ["win_rate", "profit_factor", "return_pct", "trades"]:
        if col in numeric:
            numeric[col] = pd.to_numeric(numeric[col], errors="coerce")
    agg_cols = {c: "mean" for c in ["win_rate", "profit_factor", "return_pct", "trades"] if c in numeric}
    if agg_cols:
        summary = numeric.groupby("strategy", dropna=False).agg(agg_cols).reset_index()
        st.dataframe(summary, use_container_width=True, hide_index=True)

st.subheader("Paper signals")
if paper.empty:
    st.info("Nessun paper signal attivo.")
else:
    cols = [c for c in ["created_at", "signal_date", "symbol", "strategy", "score", "price", "proposed_entry", "proposed_stop", "proposed_target", "status"] if c in paper]
    st.dataframe(paper[cols], use_container_width=True, hide_index=True)
