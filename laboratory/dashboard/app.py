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
    "Vista operativa: Core, opportunity ladder, paper monitoring e catalyst. Il punto non è riempire lo schermo, è capire cosa si sta avvicinando a un trade valido.",
)

try:
    supabase = get_supabase_client()
    runs = pd.DataFrame((supabase.table("engine_runs").select("*").order("run_timestamp", desc=True).limit(100).execute().data or []))
    signals = pd.DataFrame((supabase.table("signals").select("*").order("created_at", desc=True).limit(500).execute().data or []))
    paper = pd.DataFrame((supabase.table("lab_paper_signals").select("*").order("created_at", desc=True).limit(500).execute().data or []))
except Exception as exc:
    st.error(str(exc))
    st.stop()

# Keep only the most recent row for each paper strategy/symbol pair.
if not paper.empty:
    paper = paper.sort_values("created_at", ascending=False).drop_duplicates(["symbol", "strategy"], keep="first")

states = {"PAPER_OPEN", "PRE_BUY", "NEAR_SETUP", "WATCH"}
if not paper.empty and "status" in paper:
    counts = paper["status"].fillna("N/D").value_counts()
else:
    counts = pd.Series(dtype=int)

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Capitale base", f"{CAPITAL_TOTAL_BASE:,.0f}")
c2.metric("Max posizione", f"${MAX_POSITION_USD:,.0f}")
c3.metric("PAPER OPEN", int(counts.get("PAPER_OPEN", 0)), help="Setup research con score elevato e trigger confermato. Non è un ordine reale.")
c4.metric("PRE-BUY", int(counts.get("PRE_BUY", 0)))
c5.metric("NEAR SETUP", int(counts.get("NEAR_SETUP", 0)))
c6.metric("WATCH", int(counts.get("WATCH", 0)))
st.caption(f"Policy: max {MAX_NEW_BUYS} nuovi BUY · preferenza {PREFERRED_ORDER_TYPE} · commissione USA ${USA_COMMISSION_USD:.0f}. Nessun ordine automatico.")

st.markdown("### Opportunity Ladder")
if paper.empty:
    st.info("Il feed operativo non è ancora stato popolato. Il job giornaliero deve completare almeno un run.")
else:
    rows = []
    for _, r in paper.iterrows():
        details = r.get("details") if isinstance(r.get("details"), dict) else {}
        rows.append({
            "Ticker": r.get("symbol"),
            "Strategia": r.get("strategy"),
            "Stato": r.get("status"),
            "Score": r.get("score"),
            "Prezzo": r.get("price"),
            "Entry": r.get("proposed_entry"),
            "Distanza %": details.get("distance_to_entry_pct"),
            "Max Buy": details.get("max_buy"),
            "Trigger": details.get("trigger"),
            "Qty": details.get("qty"),
            "Capitale $": details.get("capital"),
            "Stop": r.get("proposed_stop"),
            "Target": r.get("proposed_target"),
            "Earnings": details.get("earnings_date"),
        })
    ladder = pd.DataFrame(rows)
    order = {"PAPER_OPEN": 0, "PRE_BUY": 1, "NEAR_SETUP": 2, "WATCH": 3}
    ladder["_rank"] = ladder["Stato"].map(order).fillna(9)
    ladder["Score"] = pd.to_numeric(ladder["Score"], errors="coerce")
    ladder = ladder.sort_values(["_rank", "Score"], ascending=[True, False]).drop(columns="_rank")
    st.dataframe(ladder.head(30), use_container_width=True, hide_index=True)

    near = ladder[ladder["Stato"].isin(["PAPER_OPEN", "PRE_BUY", "NEAR_SETUP"])].copy()
    if not near.empty:
        st.markdown("### Più vicini all'azione")
        cols = st.columns(min(4, len(near.head(4))))
        for col, (_, r) in zip(cols, near.head(4).iterrows()):
            with col:
                st.markdown(f"#### {r['Ticker']}")
                st.caption(f"{r['Stato']} · {r['Strategia']}")
                st.metric("Score", f"{r['Score']:.1f}" if pd.notna(r['Score']) else "N/D")
                dist = r.get("Distanza %")
                st.write(f"**Distanza entry:** {dist:.2f}%" if pd.notna(dist) else "**Distanza entry:** N/D")
                st.write(f"**Trigger:** {r.get('Trigger', 'N/D')}")
                st.write(f"**Entry / Max Buy:** {r.get('Entry', 'N/D')} / {r.get('Max Buy', 'N/D')}")

st.markdown("### Catalyst / News monitor")
news_rows = []
if not paper.empty:
    for _, r in paper.iterrows():
        details = r.get("details") if isinstance(r.get("details"), dict) else {}
        for item in details.get("news", [])[:2]:
            if not isinstance(item, dict) or not item.get("title"):
                continue
            news_rows.append({
                "Ticker": r.get("symbol"),
                "Titolo": item.get("title"),
                "Fonte": item.get("publisher") or "N/D",
                "Classificazione": item.get("classification") or "NEWS_AGGREGATOR_UNVERIFIED",
                "URL": item.get("url"),
            })
if news_rows:
    st.warning("Le news qui sono enrichment da aggregatore e NON sono ancora conferma primaria. Prima di un trade reale vanno verificate su SEC/IR o fonte affidabile.")
    st.dataframe(pd.DataFrame(news_rows).head(20), use_container_width=True, hide_index=True, column_config={"URL": st.column_config.LinkColumn("Apri")})
else:
    st.info("Nessuna news/catalyst ancora disponibile nel feed. I rumor non vengono inventati né trattati come catalyst verificati.")

left, right = st.columns([1.25, 1])
with left:
    st.markdown("### Core signals")
    if signals.empty:
        st.info("Il Core non ha ancora scritto segnali su Supabase. La persistenza automatica è stata collegata e si popolerà al prossimo scan completato.")
    else:
        show = [c for c in ["created_at", "market", "ticker", "status", "decision", "score_total", "entry", "max_buy", "stop", "tp2", "rr_net_tp2"] if c in signals.columns]
        st.dataframe(signals[show].head(20), use_container_width=True, hide_index=True)

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
        st.write(f"**Timestamp:** {latest.get('run_timestamp', 'N/D')}")

st.caption("Trading Lab 2.0 · Core observation + opportunity ladder + paper monitoring · nessun ordine viene inviato automaticamente al broker.")
