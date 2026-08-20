import sys
from pathlib import Path

import pandas as pd
import streamlit as st

LAB_ROOT = Path(__file__).resolve().parents[1]
SRC = LAB_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from lab.auth import require_dashboard_auth
from lab.data import load_engine_runs, load_lab_paper_positions, load_lab_watchlist, load_signals
from lab.settings import CAPITAL_TOTAL_BASE, MAX_NEW_BUYS, MAX_POSITION_USD, PREFERRED_ORDER_TYPE, USA_COMMISSION_USD
from lab.ui import apply_theme, company_name, fmt_money, fmt_pct, fmt_rr, fmt_score, fmt_status, fmt_strategy, fmt_trigger, localize_table, page_header

st.set_page_config(page_title="Trading Lab | Control Room", layout="wide", page_icon="📈")
require_dashboard_auth()
apply_theme()
page_header(
    "Control Room",
    "Vista operativa del Laboratory: Lab opportunities, Core high-conviction signals, paper positions e engine status. Core e Lab restano separati.",
)

try:
    lab_watch = load_lab_watchlist(2000)
    paper_positions = load_lab_paper_positions(1000)
except Exception as exc:
    st.error("Le tabelle operative del Laboratory non sono leggibili.")
    st.code(str(exc))
    st.stop()

try:
    runs = load_engine_runs(100)
    signals = load_signals(2000)
except Exception:
    runs = pd.DataFrame()
    signals = pd.DataFrame()

open_paper = paper_positions.copy()
if not paper_positions.empty and "status" in paper_positions:
    open_paper = paper_positions[paper_positions["status"].fillna("").astype(str).str.upper().isin(["OPEN", "TP1_HIT"])]

counts = lab_watch["status"].fillna("N/D").astype(str).str.upper().value_counts() if not lab_watch.empty and "status" in lab_watch else pd.Series(dtype=int)

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Lab Capital", f"{CAPITAL_TOTAL_BASE:,.0f}")
c2.metric("Max Position", fmt_money(MAX_POSITION_USD))
c3.metric("PAPER OPEN", int(counts.get("PAPER_OPEN", 0)))
c4.metric("PRE-BUY", int(counts.get("PRE_BUY", 0)))
c5.metric("NEAR SETUP", int(counts.get("NEAR_SETUP", 0)))
c6.metric("Open Paper Positions", len(open_paper))
st.caption(f"Lab policy: max {MAX_NEW_BUYS} new setups · preferred order {PREFERRED_ORDER_TYPE} · simulated USA commission {fmt_money(USA_COMMISSION_USD)} per side. Nessun ordine automatico.")

st.markdown("### Lab Opportunity Ladder")
if lab_watch.empty:
    st.info("Lab watchlist vuota. Esegui Strategy Lab Daily Opportunity Feed per creare il primo stato operativo.")
else:
    ladder = lab_watch.copy()
    for col in ["score", "price", "entry", "max_buy", "stop", "tp1", "tp2", "distance_to_entry_pct"]:
        if col in ladder:
            ladder[col] = pd.to_numeric(ladder[col], errors="coerce")
    order = {"PAPER_OPEN": 0, "PRE_BUY": 1, "NEAR_SETUP": 2, "WATCH": 3}
    ladder["_rank"] = ladder["status"].fillna("").astype(str).str.upper().map(order).fillna(9)
    ladder = ladder.sort_values(["_rank", "score"], ascending=[True, False]).drop(columns="_rank")

    show = ladder.copy()
    show.insert(show.columns.get_loc("symbol") + 1, "azienda", show["symbol"].map(company_name))
    for col in ["price", "entry", "max_buy", "stop", "tp1", "tp2"]:
        if col in show:
            show[col] = show[col].map(fmt_money)
    if "score" in show:
        show["score"] = show["score"].map(fmt_score)
    if "distance_to_entry_pct" in show:
        show["distance_to_entry_pct"] = show["distance_to_entry_pct"].map(fmt_pct)
    if "alert_price" in show:
        show["alert_price"] = show["alert_price"].map(fmt_money)
    cols = [c for c in ["symbol", "azienda", "strategy", "status", "score", "trigger", "price", "entry", "max_buy", "distance_to_entry_pct", "alert_type", "alert_price", "signal_date"] if c in show.columns]
    st.dataframe(localize_table(show[cols]).head(30), use_container_width=True, hide_index=True)

    near = ladder[ladder["status"].fillna("").astype(str).str.upper().isin(["PAPER_OPEN", "PRE_BUY", "NEAR_SETUP"])].head(4)
    if not near.empty:
        st.markdown("### Closest to Action")
        cols_ui = st.columns(len(near))
        for col, (_, row) in zip(cols_ui, near.iterrows()):
            with col:
                st.markdown(f"#### {row.get('symbol', 'N/D')} · {company_name(row.get('symbol'))}")
                st.caption(f"{fmt_status(row.get('status'))} · {fmt_strategy(row.get('strategy'))}")
                st.metric("Score", fmt_score(row.get("score")))
                st.write(f"**Entry / Max Buy:** {fmt_money(row.get('entry'))} / {fmt_money(row.get('max_buy'))}")
                st.write(f"**Distance to Entry:** {fmt_pct(row.get('distance_to_entry_pct'))}")
                st.write(f"**Trigger:** {fmt_trigger(row.get('trigger'))}")

st.markdown("### Core High-Conviction Opportunities")
CORE_HIGH = {"BUY NOW", "BUY LIMIT", "PRE-BUY HIGH", "PRE_BUY_HIGH", "SHADOW BUY", "SHADOW_BUY"}

if signals.empty:
    st.caption("No Core signals available in Supabase.")
else:
    core = signals.copy()
    if "created_at" in core:
        core["_created"] = pd.to_datetime(core["created_at"], errors="coerce", utc=True)
        core = core.sort_values("_created", ascending=False)

    decision_state = core.get("decision", pd.Series(index=core.index, dtype=object)).fillna("").astype(str).str.upper().str.replace("_", " ", regex=False)
    status_state = core.get("status", pd.Series(index=core.index, dtype=object)).fillna("").astype(str).str.upper().str.replace("_", " ", regex=False)
    core["_core_state"] = decision_state.where(decision_state.isin(CORE_HIGH), status_state)
    core = core[core["_core_state"].isin(CORE_HIGH)].copy()

    if "ticker" in core:
        dedup_cols = [c for c in ["market", "ticker"] if c in core.columns]
        if dedup_cols:
            core = core.drop_duplicates(subset=dedup_cols, keep="first")

    if core.empty:
        st.info("No Core BUY / PRE-BUY HIGH signals currently available for USA or Italy.")
    else:
        core["Company"] = core["ticker"].map(company_name) if "ticker" in core else "N/D"
        core["Status"] = core["_core_state"].map(lambda x: x.replace("_", " "))
        core["Current Price"] = core.get("price", pd.Series(index=core.index)).map(fmt_money)
        low = core.get("buy_range_low", core.get("entry", pd.Series(index=core.index)))
        high = core.get("buy_range_high", core.get("max_buy", pd.Series(index=core.index)))
        core["Buy Range"] = [f"{fmt_money(a)} – {fmt_money(b)}" for a, b in zip(low, high)]
        core["Entry"] = core.get("entry", pd.Series(index=core.index)).map(fmt_money)
        core["Stop"] = core.get("stop", pd.Series(index=core.index)).map(fmt_money)
        core["TP1"] = core.get("tp1", pd.Series(index=core.index)).map(fmt_money)
        core["TP2"] = core.get("tp2", pd.Series(index=core.index)).map(fmt_money)
        core["Net R/R"] = core.get("rr_net_tp2", pd.Series(index=core.index)).map(fmt_rr)
        core["Trigger"] = core.get("trigger", pd.Series(index=core.index)).map(fmt_trigger)
        core["TradingView"] = core.get("ticker", pd.Series(index=core.index)).map(lambda t: f"https://www.tradingview.com/chart/?symbol={t}")

        market_values = core.get("market", pd.Series(index=core.index, dtype=object)).fillna("N/D").astype(str).str.upper()
        for market_label, mask in [("USA", market_values.str.contains("USA|US")), ("ITALY", market_values.str.contains("ITALY|ITA|MIL"))]:
            block = core[mask].copy()
            if block.empty:
                continue
            st.markdown(f"#### {market_label}")
            table_cols = [c for c in ["ticker", "Company", "Status", "Current Price", "Buy Range", "Entry", "Stop", "TP1", "TP2", "Net R/R", "Trigger", "TradingView"] if c in block.columns]
            compact = block[table_cols].rename(columns={"ticker": "Ticker"})
            st.dataframe(
                compact,
                use_container_width=True,
                hide_index=True,
                column_config={"TradingView": st.column_config.LinkColumn("Chart", display_text="Open")},
            )

            info_cols = st.columns(min(len(block), 4))
            for idx, (_, row) in enumerate(block.head(4).iterrows()):
                with info_cols[idx % len(info_cols)]:
                    ticker = row.get("ticker", "N/D")
                    with st.popover(f"ℹ️ {ticker}", use_container_width=True):
                        st.markdown(f"**{ticker} · {company_name(ticker)}**")
                        st.write(f"Core status: **{row.get('_core_state', 'N/D')}**")
                        if pd.notna(row.get("setup")):
                            st.write(f"Setup: **{str(row.get('setup')).replace('_', ' ')}**")
                        if pd.notna(row.get("trigger")):
                            st.write(f"Trigger: **{fmt_trigger(row.get('trigger'))}**")
                        if pd.notna(row.get("score_total")):
                            st.write(f"Score: **{fmt_score(row.get('score_total'))}**")
                        if pd.notna(row.get("rr_net_tp2")):
                            st.write(f"Net R/R TP2: **{fmt_rr(row.get('rr_net_tp2'))}**")
                        if pd.notna(row.get("data_quality")):
                            st.write(f"Data Quality: **{row.get('data_quality')}**")
                        if pd.notna(row.get("earnings_date")):
                            st.write(f"Earnings: **{row.get('earnings_date')}**")
                        if pd.notna(row.get("reason")):
                            st.write(f"Core reason: {row.get('reason')}")
                        st.caption("The panel reports Core output only; it does not recalculate or upgrade the signal.")

st.markdown("### Paper Portfolio")
if open_paper.empty:
    st.info("Nessuna paper position aperta. Il Lab apre solo quando tutti i gate sono superati e il trigger è valido.")
else:
    paper = open_paper.copy()
    paper.insert(paper.columns.get_loc("symbol") + 1, "azienda", paper["symbol"].map(company_name))
    for col in ["entry_price", "capital", "stop_current", "tp1", "tp2", "last_price"]:
        if col in paper:
            paper[col] = paper[col].map(fmt_money)
    cols = [c for c in ["symbol", "azienda", "strategy", "status", "qty", "capital", "entry_price", "last_price", "stop_current", "tp1", "tp2", "last_checked_date"] if c in paper.columns]
    st.dataframe(localize_table(paper[cols]).head(20), use_container_width=True, hide_index=True)

st.markdown("### Engine Snapshot")
if runs.empty:
    st.caption("No Core run registered.")
else:
    latest = runs.iloc[0]
    a, b, c, d = st.columns(4)
    a.metric("Latest Core Run", str(latest.get("run_id", "N/D")))
    b.metric("Market", str(latest.get("market", "N/D")))
    c.metric("Engine", str(latest.get("engine_version", "N/D")))
    d.metric("Timestamp", str(latest.get("run_timestamp", "N/D")))
if not lab_watch.empty and "last_seen_at" in lab_watch:
    latest_lab = pd.to_datetime(lab_watch["last_seen_at"], errors="coerce", utc=True).max()
    st.caption(f"Latest Lab Feed: {latest_lab if pd.notna(latest_lab) else 'N/D'}")

st.caption("Trading Lab 2.0 · operational Laboratory tables first · Core read-only · no automatic broker orders.")
