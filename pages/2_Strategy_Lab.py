from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import pandas as pd
import streamlit as st

try:
    from dashboard import data_access
except ModuleNotFoundError:
    import dashboard.data_access as data_access

st.set_page_config(page_title="Strategy Lab", page_icon="🧪", layout="wide")

VERDICT_ICON = {"WORKING": "🟢", "EARLY": "🟡", "WATCH": "🟠", "WEAK": "🔴", "DATA_ISSUE": "🔴"}


def j(v: Any) -> dict:
    if isinstance(v, dict):
        return v
    try:
        parsed = json.loads(str(v)) if v else {}
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def n(v: Any) -> float | None:
    try:
        return float(v) if v is not None else None
    except Exception:
        return None


def signed_style(frame: pd.DataFrame, columns: list[str]):
    styler = frame.style
    def color(v: Any) -> str:
        value = n(v)
        if value is None or value == 0:
            return ""
        return "color:#15803d;font-weight:700;" if value > 0 else "color:#dc2626;font-weight:700;"
    for col in columns:
        if col in frame.columns:
            styler = styler.map(color, subset=[col])
    return styler


@st.cache_data(ttl=60, show_spinner=False)
def load_summary():
    return data_access.lab_strategy_summaries(500), data_access.lab_strategy_ticker_snapshots(1000), data_access.lab_latest_completed_aggregation()


@st.cache_data(ttl=120, show_spinner=False)
def strategy_signals(strategy: str):
    return [r for r in data_access.lab_paper_signals(10000) if str(r.get("strategy") or "") == strategy]


@st.cache_data(ttl=300, show_spinner=False)
def strategy_outcomes(strategy: str):
    return [r for r in data_access.lab_signal_outcomes(10000) if str(r.get("strategy") or "") == strategy]


@st.cache_data(ttl=300, show_spinner=False)
def strategy_backtests(strategy: str):
    return [r for r in data_access.lab_backtest_results(5000) if str(r.get("strategy") or r.get("strategy_name") or "") == strategy]


@st.cache_data(ttl=300, show_spinner=False)
def strategy_variants(strategy: str):
    return [r for r in data_access.lab_strategy_variants(2000) if str(r.get("parent_strategy") or "") == strategy]


st.title("🧪 Strategy Lab")
st.caption("Which strategies are actually working? Normalized R evidence first, nominal dollars second. PAPER research only.")

with st.sidebar:
    st.markdown("## Guida · Strategy Lab")
    with st.expander("A cosa serve", expanded=True):
        st.markdown("Qui confrontiamo le strategie. Il centro non è il P&L in dollari ma **Expectancy R, Profit Factor, MTM R, Drawdown e maturità del campione**.")
    with st.expander("Verdict"):
        st.markdown("**EARLY** <30 closed. **WORKING** richiede campione sufficiente, PF ≥1.20, Expectancy R positiva, rendimento medio positivo e Live Stress PASS. **WATCH/WEAK/DATA ISSUE** seguono la policy versionata del backend.")
    with st.expander("Perché R"):
        st.markdown("R normalizza ogni trade per il rischio iniziale. Una strategia non sembra migliore solo perché usa una size maggiore.")
    with st.expander("Drill-down"):
        st.markdown("Seleziona una strategia e poi una vista. I dati pesanti vengono letti solo per la vista scelta, invece di caricare tutto a ogni render.")

summaries, tickers, aggregation_run = load_summary()
if not summaries:
    st.warning("Strategy snapshots are not available yet. Apply the Laboratory 2.2 schema and complete the snapshot pipeline before using Strategy Lab verdicts.")
    st.stop()

active_by_strategy: dict[str, list[str]] = {}
for row in tickers:
    active_by_strategy.setdefault(str(row.get("strategy") or "N/D"), []).append(str(row.get("symbol") or "N/D"))

score_rows = []
for s in summaries:
    verdict = str(s.get("verdict") or "N/D").upper()
    score_rows.append({
        "Strategy": s.get("strategy"),
        "Verdict": f"{VERDICT_ICON.get(verdict, '⚪')} {verdict}",
        "Maturity": s.get("maturity") or "N/D",
        "Closed": int(s.get("closed") or 0),
        "Exp R": n(s.get("expectancy_r")),
        "PF": n(s.get("net_pf")),
        "Avg %": n(s.get("avg_return_pct")),
        "MTM R": n(s.get("mtm_r")),
        "Max DD R": n(s.get("max_drawdown_r")),
        "Open": int(s.get("open") or 0),
        "Active Tickers": ", ".join(sorted(set(active_by_strategy.get(str(s.get("strategy")), [])))) or "-",
    })

st.subheader("Strategy Scoreboard")
sdf = pd.DataFrame(score_rows)
styled = signed_style(sdf, ["Exp R", "Avg %", "MTM R", "Max DD R"]).format({
    "Exp R": "{:+.2f}", "PF": "{:.2f}", "Avg %": "{:+.2f}%", "MTM R": "{:+.2f}", "Max DD R": "{:+.2f}"
}, na_rep="-")
st.dataframe(styled, width="stretch", hide_index=True)

chart = sdf[["Strategy", "Exp R"]].dropna()
if not chart.empty:
    st.caption("Expectancy R by Strategy")
    st.bar_chart(chart.set_index("Strategy")["Exp R"], horizontal=True)

strategy_names = [str(x) for x in sdf["Strategy"].dropna().tolist()]
selected = st.selectbox("Strategy", strategy_names)
summary = next((s for s in summaries if str(s.get("strategy")) == selected), None)
selected_tickers = [x for x in tickers if str(x.get("strategy")) == selected]

view = st.radio("Strategy Detail", ["Overview", "Live Trades", "Signals", "Evidence", "Backtest", "Parameters", "Policy"], horizontal=True)

if view == "Overview" and summary:
    verdict = str(summary.get("verdict") or "N/D").upper()
    st.subheader(f"{selected} · {VERDICT_ICON.get(verdict, '⚪')} {verdict}")
    cols = st.columns(8)
    cols[0].metric("Maturity", str(summary.get("maturity") or "N/D"))
    cols[1].metric("Closed", int(summary.get("closed") or 0))
    cols[2].metric("Expectancy R", f"{n(summary.get('expectancy_r')):+.2f}R" if n(summary.get("expectancy_r")) is not None else "N/D")
    cols[3].metric("PF", f"{n(summary.get('net_pf')):.2f}" if n(summary.get("net_pf")) is not None else "N/D")
    cols[4].metric("Win Rate", f"{n(summary.get('win_rate')):.1f}%" if n(summary.get("win_rate")) is not None else "N/D")
    cols[5].metric("MTM R", f"{n(summary.get('mtm_r')):+.2f}R" if n(summary.get("mtm_r")) is not None else "N/D")
    cols[6].metric("Open Risk", f"{n(summary.get('open_risk_r')):.2f}R" if n(summary.get("open_risk_r")) is not None else "N/D")
    cols[7].metric("Max DD", f"{n(summary.get('max_drawdown_r')):+.2f}R" if n(summary.get("max_drawdown_r")) is not None else "N/D")
    reasons = summary.get("verdict_reason_codes") or []
    stress = summary.get("stress_reason_codes") or []
    if reasons:
        st.caption("Verdict reasons: " + ", ".join(str(x) for x in reasons))
    if stress:
        st.caption("Live stress reasons: " + ", ".join(str(x) for x in stress))
    st.info(f"Active tickers: {', '.join(sorted(set(active_by_strategy.get(selected, [])))) or 'none'}")

elif view == "Live Trades":
    st.subheader(f"{selected} · Live Trades")
    if not selected_tickers:
        st.info("No open paper positions for this strategy.")
    else:
        frame = pd.DataFrame([{
            "Ticker": x.get("symbol"), "Tier": x.get("tier") or "N/D", "State": x.get("state") or "N/D",
            "Days": x.get("trading_days"), "Fill $": n(x.get("fill_price")), "Current $": n(x.get("current_price")),
            "Net %": n(x.get("net_return_pct")), "MTM R": n(x.get("mtm_r")), "Risk R": n(x.get("open_risk_r")),
            "SL $": n(x.get("stop_current")), "TP1 $": n(x.get("tp1")), "TP2 $": n(x.get("tp2")),
        } for x in selected_tickers])
        style = signed_style(frame, ["Net %", "MTM R"]).format({
            "Fill $":"{:.2f}", "Current $":"{:.2f}", "Net %":"{:+.2f}%", "MTM R":"{:+.2f}", "Risk R":"{:.2f}",
            "SL $":"{:.2f}", "TP1 $":"{:.2f}", "TP2 $":"{:.2f}"
        }, na_rep="-")
        st.dataframe(style, width="stretch", hide_index=True)

elif view == "Signals":
    st.subheader(f"{selected} · Signals")
    rows = strategy_signals(selected)
    if not rows:
        st.info("No signals available.")
    else:
        frame_rows = []
        for r in rows[:500]:
            d = j(r.get("details")); policy = j(d.get("paper_policy")); dq = j(d.get("data_quality"))
            frame_rows.append({
                "Date": str(r.get("signal_date") or r.get("created_at") or "")[:10],
                "Ticker": r.get("symbol"), "Status": r.get("status"), "Tier": policy.get("tier") or "-",
                "Strategy Score": n(d.get("strategy_score")) or n(r.get("score")), "Trade Score": n(d.get("trade_score")),
                "Trigger": d.get("trigger") or "N/D", "Data Quality": dq.get("status") or "N/D",
                "R/R Net TP2": n(d.get("rr_net_tp2")),
            })
        st.dataframe(pd.DataFrame(frame_rows), width="stretch", hide_index=True)

elif view == "Evidence":
    st.subheader(f"{selected} · Evidence")
    rows = strategy_outcomes(selected)
    if not rows:
        st.info("No signal outcomes available yet.")
    else:
        vals = pd.DataFrame([{
            "Date": str(r.get("signal_date") or "")[:10], "Ticker": r.get("symbol"), "Source Status": r.get("source_signal_status"),
            "MFE R": n(r.get("mfe_r")), "MAE R": n(r.get("mae_r")), "D1 %": n(r.get("ret_d1")), "D5 %": n(r.get("ret_d5")),
            "D10 %": n(r.get("ret_d10")), "D20 %": n(r.get("ret_d20")), "D60 %": n(r.get("ret_d60")),
        } for r in rows[:1000]])
        st.dataframe(signed_style(vals, ["MFE R","MAE R","D1 %","D5 %","D10 %","D20 %","D60 %"]), width="stretch", hide_index=True)

elif view == "Backtest":
    st.subheader(f"{selected} · Backtest vs Paper Forward")
    rows = strategy_backtests(selected)
    if not rows:
        st.info("No matching backtest result is available for this strategy. Paper Forward metrics remain visible in the scoreboard; backtest comparison is N/D rather than inferred.")
    else:
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

elif view == "Parameters":
    st.subheader(f"{selected} · Parameters")
    rows = strategy_variants(selected)
    if not rows:
        st.info("No lab_strategy_variants row is available for this strategy yet.")
    else:
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

elif view == "Policy":
    st.subheader(f"{selected} · PAPER_POLICY vs LEGACY_STRICT")
    rows = strategy_signals(selected)
    if not rows:
        st.info("No policy evidence available.")
    else:
        paper_eligible = legacy_eligible = 0
        for r in rows:
            d = j(r.get("details"))
            paper_eligible += int(bool(j(d.get("paper_policy")).get("eligible")))
            legacy_eligible += int(bool(j(d.get("strict_trade_eligibility") or d.get("trade_eligibility")).get("eligible")))
        st.dataframe(pd.DataFrame([
            {"Policy": "PAPER_POLICY", "Signals": len(rows), "Eligible": paper_eligible, "Eligible %": 100.0*paper_eligible/len(rows)},
            {"Policy": "LEGACY_STRICT", "Signals": len(rows), "Eligible": legacy_eligible, "Eligible %": 100.0*legacy_eligible/len(rows)},
        ]).style.format({"Eligible %":"{:.1f}%"}), width="stretch", hide_index=True)

st.caption(f"Snapshot run: {aggregation_run.get('id') if aggregation_run else 'N/D'} · Updated {datetime.now().astimezone().strftime('%d/%m/%Y %H:%M:%S %Z')}")
