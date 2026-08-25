from __future__ import annotations

import pandas as pd
import streamlit as st

from common_utility.lab_cost_model import CURRENT_COMMISSION_PER_SIDE, DISCOUNT_COMMISSION_PER_SIDE, SLIPPAGE_BPS

try:
    from dashboard import data_access
except ModuleNotFoundError:
    import dashboard.data_access as data_access

st.set_page_config(page_title="Strategy Parameters", page_icon="🧠", layout="wide")

ACTIVE = [
    {"Strategy":"trend_continuation","Status":"🟢 ACTIVE","Holding Days":20,"Version":"v2.0","Active From":"2026-08","What it looks for":"Structural trend + pullback + momentum + volume + breakout","Score":"Trend 35 · Pullback 25 · Momentum 20 · Volume 10 · Breakout 10","Trigger":"Primary: Price > SMA50 > SMA200","Experiment":"Shadow buffer: 0% vs +0.5% above SMA50"},
    {"Strategy":"cross_sectional_momentum","Status":"🟢 ACTIVE","Holding Days":40,"Version":"v2.0","Active From":"2026-08","What it looks for":"Relative strength versus the same-session universe","Score":"Ret20 percentile 30% · Ret60 35% · Ret120 35%","Trigger":"Price >= 20-day high","Experiment":"True cross-sectional score; not absolute returns"},
    {"Strategy":"short_term_reversal_rsi45","Status":"🟢 A/B TEST","Holding Days":10,"Version":"v2.0-r45","Active From":"2026-08","What it looks for":"Reversal after a moderate downside excess","Score":"RSI 45 · Stretch 30 · Long trend 15 · Stabilization 10","Trigger":"1d return > 0 and RSI14 < 45","Experiment":"Compared separately with RSI35 through A/B/C"},
    {"Strategy":"short_term_reversal_rsi35","Status":"🟢 A/B TEST","Holding Days":10,"Version":"v2.0-r35","Active From":"2026-08","What it looks for":"Reversal after a more extreme downside excess","Score":"RSI 45 · Stretch 30 · Long trend 15 · Stabilization 10","Trigger":"1d return > 0 and RSI14 < 35","Experiment":"RSI score normalized to its own threshold; A/B/C kept separate"},
    {"Strategy":"defensive_low_vol","Status":"🟢 ACTIVE","Holding Days":60,"Version":"v2.0","Active From":"2026-08","What it looks for":"Low volatility, stability, trend and momentum","Score":"Low vol 40 · Above SMA200 25 · ATR stability 20 · 60d momentum 15","Trigger":"Price > SMA200","Experiment":"Renamed: no fundamental quality component in the score"},
]

NOT_ACTIVE = [
    {"Strategy":"pead","Status":"🟠 IMPLEMENTED, NOT ACTIVE","Holding Days":20,"Missing":"point_in_time_earnings + analyst_revisions"},
    {"Strategy":"event_driven_mean_reversion","Status":"🟠 IMPLEMENTED, NOT ACTIVE","Holding Days":10,"Missing":"point_in_time_events"},
    {"Strategy":"quality_value_rerating","Status":"🟠 IMPLEMENTED, NOT ACTIVE","Holding Days":60,"Missing":"point_in_time_fundamentals"},
    {"Strategy":"macro_intermarket","Status":"🟠 IMPLEMENTED, NOT ACTIVE","Holding Days":40,"Missing":"rates + credit_spreads + commodities + usd"},
]

TIERS = pd.DataFrame([
    {"Tier":"A","Use":"Near-Production, always paper","Data Quality":"GREEN only","Strategy Score Min":75,"Trade Score Min":70,"Trigger":"CONFIRMED","Net R/R Min":1.75,"Max Extension":"0 ATR above MaxBuy","Earnings":">= 7 days"},
    {"Tier":"B","Use":"Experimental","Data Quality":"GREEN/YELLOW","Strategy Score Min":65,"Trade Score Min":55,"Trigger":"CONFIRMED","Net R/R Min":1.15,"Max Extension":"0.5 ATR","Earnings":">= 5 days"},
    {"Tier":"C","Use":"🔬 RESEARCH ONLY · NON-OPERATIONAL","Data Quality":"GREEN/YELLOW","Strategy Score Min":55,"Trade Score Min":40,"Trigger":"May be WAITING","Net R/R Min":0.75,"Max Extension":"1 ATR","Earnings":"Hard veto < 3 days"},
])

CHANGE_HISTORY = pd.DataFrame([
    {"Date":"2026-08","Strategy":"trend_continuation","Version":"v2.0","Change":"Primary 0% SMA50 buffer retained; +0.5% recorded as shadow experiment"},
    {"Date":"2026-08","Strategy":"short_term_reversal","Version":"v2.0-r35 / v2.0-r45","Change":"Split RSI35 and RSI45 into separately tracked variants"},
    {"Date":"2026-08","Strategy":"cross_sectional_momentum","Version":"v2.0","Change":"Operational score changed to same-session cross-sectional percentiles"},
    {"Date":"2026-08","Strategy":"defensive_low_vol","Version":"v2.0","Change":"Removed 'quality' naming because the score is technical, not fundamental"},
])

st.title("🧠 Strategy Parameters")
st.caption("Configuration source of truth: what rules are running, which versions are active and which experiments are frozen before evaluation.")

with st.sidebar:
    st.markdown("## Guida · Strategy Parameters")
    with st.expander("Cosa mostra questa pagina", expanded=True):
        st.markdown("Qui vedi **le regole con cui gira il Laboratory**: strategie attive, holding, score, trigger, versioni e test A/B. Non è una pagina di performance.")
    with st.expander("Come leggere Tier A / B / C"):
        st.markdown("**Tier A** = candidato vicino alla Production ma sempre paper.  \n**Tier B** = sperimentale.  \n**Tier C** = solo ricerca, mai operativo.")
    with st.expander("Versioni e Change History"):
        st.markdown("Ogni modifica importante deve creare una **nuova versione**. In questo modo Research Evolution può confrontare i risultati prima e dopo senza mischiare regole diverse.")
    with st.expander("Costi usati dal Laboratory"):
        st.markdown(f"Costo corrente USA: **${CURRENT_COMMISSION_PER_SIDE:.2f} per lato**. Scenario futuro: **${DISCOUNT_COMMISSION_PER_SIDE:.2f} per lato**. Slippage di ricerca: **{SLIPPAGE_BPS:.0f} bps**.")

try:
    signals = data_access.lab_paper_signals(10000)
except Exception:
    signals = []
seen = {str(r.get("strategy")) for r in signals if r.get("strategy")}
active_df = pd.DataFrame(ACTIVE)
active_df["Seen in Data"] = active_df["Strategy"].apply(lambda x: "YES" if x in seen else "NEXT RUN")

m = st.columns(3)
m[0].metric("Active Strategies / Variants", len(ACTIVE))
m[1].metric("Implemented, Not Active", len(NOT_ACTIVE))
m[2].metric("Registered Total", len(ACTIVE) + len(NOT_ACTIVE))

st.subheader("Active Strategies and Variants")
st.dataframe(active_df, width="stretch", hide_index=True)
st.info("Experimental baseline is frozen. Do not change thresholds retrospectively without creating a new version.")

st.subheader("A/B/C Admission Parameters")
st.dataframe(TIERS, width="stretch", hide_index=True)
st.caption("Common vetoes: Data Quality RED, qty <= 0, ATR <= 0, unavailable R/R, earnings < 3 days. Tier C remains non-operational.")

st.subheader("Paper Portfolio Limits and Cost Model")
st.dataframe(pd.DataFrame([
    {"Parameter":"Max new openings per run","Value":12},
    {"Parameter":"Max active Laboratory positions","Value":80},
    {"Parameter":"Max active positions per strategy","Value":24},
    {"Parameter":"Ticker + strategy cooldown","Value":"7 sessions"},
    {"Parameter":"Current commission per side","Value":f"${CURRENT_COMMISSION_PER_SIDE:.2f}"},
    {"Parameter":"Future discount scenario per side","Value":f"${DISCOUNT_COMMISSION_PER_SIDE:.2f}"},
    {"Parameter":"Research slippage","Value":f"{SLIPPAGE_BPS:.0f} bps"},
]), width="stretch", hide_index=True)

with st.expander("Change History", expanded=False):
    st.dataframe(CHANGE_HISTORY, width="stretch", hide_index=True)
    st.caption("Research Evolution should compare evidence by strategy and version whenever enough observations exist.")

st.subheader("Implemented but Not Active")
st.dataframe(pd.DataFrame(NOT_ACTIVE), width="stretch", hide_index=True)
st.info("These strategies remain disabled until their point-in-time data sources exist. They are not approximated with invented or contemporaneous substitutes.")

st.caption("Question answered by this page: What rules are running?")
