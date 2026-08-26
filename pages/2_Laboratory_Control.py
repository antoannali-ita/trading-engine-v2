from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from typing import Any

import pandas as pd
import streamlit as st

try:
    from dashboard import data_access
except ModuleNotFoundError:
    import dashboard.data_access as data_access

st.set_page_config(page_title="Laboratory Control", page_icon="🔬", layout="wide")

VERDICT_ICON = {
    "WORKING": "🟢",
    "EARLY": "🟡",
    "WATCH": "🟠",
    "WEAK": "🔴",
    "DATA_ISSUE": "🔴",
}

GATE_LABELS = {
    "STRATEGY_SCORE_LT_75": "Score below Tier A",
    "STRATEGY_SCORE_LT_65": "Score below Tier B",
    "STRATEGY_SCORE_LT_55": "Score below Tier C",
    "TRADE_SCORE_LT_70": "Trade score too low",
    "TRADE_SCORE_LT_55": "Trade score too low",
    "TRADE_SCORE_LT_40": "Trade score too low",
    "TRIGGER_NOT_CONFIRMED": "Trigger not confirmed",
    "PRICE_ABOVE_MAX_BUY": "Price above buy zone",
    "EXTENSION_GT_0_5_ATR": "Too extended",
    "EXTENSION_GT_1_ATR": "Too extended",
    "RR_LT_1_75": "Risk/reward below Tier A",
    "RR_LT_1_15": "Risk/reward below Tier B",
    "RR_LT_0_75": "Risk/reward below Tier C",
    "EARNINGS_LT_3D": "Earnings too close",
    "EARNINGS_LT_5D": "Earnings too close",
    "EARNINGS_LT_7D": "Earnings too close",
    "DATA_QUALITY_RED": "Data quality issue",
    "DATA_NOT_GREEN_FOR_TIER_A": "Data not green for Tier A",
}


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


def gate_label(code: Any) -> str:
    value = str(code or "N/D").upper()
    return GATE_LABELS.get(value, value.replace("_", " ").title())


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
def load_snapshots():
    return {
        "run": data_access.lab_latest_completed_aggregation(),
        "control": data_access.lab_control_snapshot(),
        "strategies": data_access.lab_strategy_summaries(500),
        "tickers": data_access.lab_strategy_ticker_snapshots(1000),
    }


@st.cache_data(ttl=60, show_spinner=False)
def load_raw_signals():
    return data_access.lab_paper_signals(10000)


@st.cache_data(ttl=60, show_spinner=False)
def load_raw_positions():
    return data_access.lab_paper_positions(10000)


def raw_session(row: dict[str, Any]) -> str | None:
    value = row.get("signal_date") or row.get("created_at")
    return str(value)[:10] if value else None


def raw_tier(row: dict[str, Any]) -> str:
    d = j(row.get("details"))
    policy = j(d.get("paper_policy"))
    return str(d.get("paper_tier") or policy.get("tier") or "N/D")


def raw_fallback() -> tuple[dict[str, Any] | None, list[dict[str, Any]], list[dict[str, Any]]]:
    signals = load_raw_signals()
    positions = load_raw_positions()
    sessions = sorted({x for x in (raw_session(r) for r in signals) if x})
    if not sessions:
        return None, [], []
    latest = sessions[-1]
    cur = [r for r in signals if raw_session(r) == latest]
    tiers = Counter(raw_tier(r) for r in cur)
    open_pos = [p for p in positions if str(p.get("status") or "").upper() in {"OPEN", "TP1_HIT"}]
    control = {
        "session": latest,
        "run_status": "TRANSITION",
        "data_status": "N/D",
        "raw_freshness_status": "N/D",
        "lifecycle_freshness_status": "N/D",
        "snapshot_freshness_status": "MISSING",
        "signals": len(cur),
        "data_valid": len([r for r in cur if str(j(j(r.get("details")).get("data_quality")).get("status") or "").upper() != "RED"]),
        "valid_setups": len([r for r in cur if (n(j(r.get("details")).get("strategy_score")) or n(r.get("score")) or 0) >= 55]),
        "triggered": len([r for r in cur if str(j(r.get("details")).get("trigger") or "").upper() == "CONFIRMED"]),
        "tier_a": tiers.get("A", 0),
        "tier_b": tiers.get("B", 0),
        "tier_c": tiers.get("C", 0),
        "paper_opened": len([r for r in cur if str(r.get("status") or "").upper() == "PAPER_OPEN"]),
        "open_positions": len(open_pos),
        "closed_positions": len([p for p in positions if str(p.get("status") or "").upper() == "CLOSED"]),
        "data_rejects": len([r for r in cur if str(r.get("status") or "").upper() == "BLOCKED_DATA"]),
        "mtm_r": None,
        "open_risk_r": None,
        "locked_profit_r": None,
        "paper_net_pnl": None,
    }
    ticker_rows = []
    for p in open_pos:
        d = j(p.get("details"))
        ticker_rows.append({
            "strategy": p.get("strategy"),
            "symbol": p.get("symbol"),
            "tier": d.get("paper_tier") or j(d.get("paper_policy")).get("tier"),
            "state": p.get("status"),
            "fill_price": p.get("entry_price"),
            "current_price": p.get("last_price") or p.get("entry_price"),
            "net_return_pct": p.get("return_pct"),
            "mtm_r": None,
            "open_risk_r": None,
        })
    return control, [], ticker_rows


def technical_gate_rows(signal: dict[str, Any], selector: str) -> list[str]:
    details = j(signal.get("details"))
    policy = j(details.get("paper_policy"))
    if selector == "Legacy Strict":
        strict = j(details.get("strict_trade_eligibility") or details.get("trade_eligibility"))
        return [str(x) for x in strict.get("failed", []) or []]
    checks = j(policy.get("tier_checks"))
    tier = selector.replace("Tier ", "")
    check = j(checks.get(tier))
    return [str(x) for x in check.get("failed", []) or []]


st.title("🔬 Laboratory Control")
st.caption("5-second control room: system health, signal flow, strategy state, active tickers and blockers. PAPER research only.")

with st.sidebar:
    st.markdown("## Guida · Laboratory Control")
    with st.expander("A cosa serve", expanded=True):
        st.markdown("La Control deve rispondere subito a tre domande: **il Laboratory è sano? dove si fermano i segnali? quali strategie/titoli richiedono attenzione?**")
    with st.expander("Come leggere System Health"):
        st.markdown("**HEALTHY** significa che l'ultimo run completato e la pipeline fino allo snapshot sono coerenti; non significa che un job sia in esecuzione in questo momento. Raw Data, Lifecycle e Snapshot hanno freshness separata. Se manca lo snapshot 2.2 viene mostrato un fallback transitorio, chiaramente segnalato.")
    with st.expander("Come leggere Strategy Health"):
        st.markdown("**WORKING / EARLY / WATCH / WEAK / DATA ISSUE** arrivano dal backend e sono versionati. **EARLY** significa campione insufficiente: un PF alto non basta.")
    with st.expander("Tier e Blockers"):
        st.markdown("A/B/C sono **policy parallele**. La classifica principale dei blocker usa **Tier A** e almeno 20 segnali rifiutati; sotto il minimo mostra N/D.")
    with st.expander("Metriche R"):
        st.markdown("**MTM R** = risultato aperto normalizzato. **Open Risk R** = capitale ancora a rischio. **Locked R** = profitto già protetto dallo stop. Il P&L in dollari è secondario.")

snap = load_snapshots()
control = snap["control"]
strategies = snap["strategies"]
tickers = snap["tickers"]
run = snap["run"]
using_snapshot = control is not None and run is not None

if not using_snapshot:
    control, strategies, tickers = raw_fallback()
    if control is None:
        st.warning("No Laboratory data available yet.")
        st.stop()
    st.warning("Laboratory 2.2 snapshot not available yet. Transitional raw fallback is active; normalized R/verdict metrics remain N/D until the snapshot pipeline is online.")

session = str(control.get("session") or "N/D")
run_status = str(control.get("run_status") or "N/D").upper()
raw_fresh = str(control.get("raw_freshness_status") or "N/D").upper()
life_fresh = str(control.get("lifecycle_freshness_status") or "N/D").upper()
snap_fresh = str(control.get("snapshot_freshness_status") or "N/D").upper()
last_completed = data_access.utc_label(run.get("completed_at")) if run and run.get("completed_at") else "N/D"

health_ok = using_snapshot and run_status == "OK" and raw_fresh == "FRESH" and life_fresh in {"FRESH", "N/D"} and snap_fresh == "FRESH"
health_text = f"{'🟢 LAB HEALTHY' if health_ok else '🟠 LAB ATTENTION'} · Last Completed Run {last_completed} · Session {session} · Raw {raw_fresh} · Lifecycle {life_fresh} · Snapshot {snap_fresh}"
if health_ok:
    st.success(health_text)
else:
    st.warning(health_text)
st.caption("Daily Laboratory session is expected after the US market close; HEALTHY describes the latest completed pipeline, not a job currently executing.")

st.subheader("Run Snapshot")
k = st.columns(6)
k[0].metric("Signals", int(control.get("signals") or 0))
k[1].metric("Paper Opened", int(control.get("paper_opened") or 0))
k[2].metric("Tier A", int(control.get("tier_a") or 0))
k[3].metric("Tier B", int(control.get("tier_b") or 0))
k[4].metric("Tier C", int(control.get("tier_c") or 0))
k[5].metric("Data Rejects", int(control.get("data_rejects") or 0))

r = st.columns(4)
r[0].metric("Open MTM R", f"{n(control.get('mtm_r')):+.2f}R" if n(control.get("mtm_r")) is not None else "N/D")
r[1].metric("Open Risk R", f"{n(control.get('open_risk_r')):.2f}R" if n(control.get("open_risk_r")) is not None else "N/D")
r[2].metric("Locked Profit R", f"{n(control.get('locked_profit_r')):+.2f}R" if n(control.get("locked_profit_r")) is not None else "N/D")
r[3].metric("Paper P&L $", f"${n(control.get('paper_net_pnl')):,.2f}" if n(control.get("paper_net_pnl")) is not None else "N/D")

st.subheader("Signal Flow")
funnel_cols = st.columns(5)
flow = [
    ("Signals", int(control.get("signals") or 0)),
    ("Data Valid", int(control.get("data_valid") or 0)),
    ("Valid Setups", int(control.get("valid_setups") or 0)),
    ("Triggered", int(control.get("triggered") or 0)),
    ("Paper Opened", int(control.get("paper_opened") or 0)),
]
for col, (label, value) in zip(funnel_cols, flow):
    col.metric(label, value)
st.caption(f"Parallel policy branches from Research Candidates: Tier A {int(control.get('tier_a') or 0)} · Tier B {int(control.get('tier_b') or 0)} · Tier C {int(control.get('tier_c') or 0)}. A/B/C are not sequential gates.")

st.subheader("Strategy Health")
if strategies:
    active_by_strategy: dict[str, list[str]] = {}
    for row in tickers:
        strategy = str(row.get("strategy") or "N/D")
        symbol = str(row.get("symbol") or "N/D")
        active_by_strategy.setdefault(strategy, []).append(symbol)
    rows = []
    for s in strategies:
        verdict = str(s.get("verdict") or "N/D").upper()
        rows.append({
            "Strategy": s.get("strategy"),
            "Verdict": f"{VERDICT_ICON.get(verdict, '⚪')} {verdict}",
            "Maturity": s.get("maturity") or "N/D",
            "Closed": s.get("closed"),
            "Exp R": n(s.get("expectancy_r")),
            "PF": n(s.get("net_pf")),
            "MTM R": n(s.get("mtm_r")),
            "DD R": n(s.get("max_drawdown_r")),
            "Open": s.get("open"),
            "Active Tickers": ", ".join(sorted(set(active_by_strategy.get(str(s.get("strategy")), [])))) or "-",
        })
    sdf = pd.DataFrame(rows)
    formats = {"Exp R": "{:+.2f}", "PF": "{:.2f}", "MTM R": "{:+.2f}", "DD R": "{:+.2f}"}
    styled = signed_style(sdf, ["Exp R", "MTM R", "DD R"]).format(formats, na_rep="-")
    st.dataframe(styled, width="stretch", hide_index=True)
else:
    st.info("Strategy verdicts are waiting for the 2.2 snapshot layer.")

st.subheader("Active Tickers")
if tickers:
    tdf = pd.DataFrame([{
        "Ticker": x.get("symbol"),
        "Strategy": x.get("strategy"),
        "Tier": x.get("tier") or "N/D",
        "State": x.get("state") or "N/D",
        "Days": x.get("trading_days"),
        "Fill $": n(x.get("fill_price")),
        "Current $": n(x.get("current_price")),
        "Net %": n(x.get("net_return_pct")),
        "MTM R": n(x.get("mtm_r")),
        "Risk R": n(x.get("open_risk_r")),
    } for x in tickers])
    styler = signed_style(tdf, ["Net %", "MTM R"]).format({"Fill $": "{:.2f}", "Current $": "{:.2f}", "Net %": "{:+.2f}%", "MTM R": "{:+.2f}", "Risk R": "{:.2f}"}, na_rep="-")
    st.dataframe(styler, width="stretch", hide_index=True)
else:
    st.info("No active paper positions.")

st.subheader("Why Signals Are Blocked · Tier A")
if strategies:
    blocker_rows = []
    for s in strategies:
        code = s.get("main_blocker")
        sample = int(s.get("blocker_sample") or 0)
        pct = n(s.get("main_blocker_pct"))
        if code and sample >= 20 and pct is not None:
            estimated_count = int(round(sample * pct / 100.0))
            blocker_rows.append({"Blocker": gate_label(code), "Count": estimated_count})
    if blocker_rows:
        bdf = pd.DataFrame(blocker_rows).groupby("Blocker", as_index=False)["Count"].sum().sort_values("Count", ascending=False).head(5)
        st.bar_chart(bdf.set_index("Blocker")["Count"], horizontal=True)
        st.dataframe(bdf, width="stretch", hide_index=True)
    else:
        st.info("N/D: fewer than 20 rejected valid signals per strategy in the 20-session blocker window, or no Tier A blocker is available.")
else:
    st.info("Blocker summary is waiting for snapshots.")

load_policy_detail = st.toggle("Load Tier B / Tier C / Legacy blocker detail", value=False)
if load_policy_detail:
    selector = st.selectbox("Policy", ["Tier B", "Tier C", "Legacy Strict"])
    raw = load_raw_signals()
    sessions = sorted({x for x in (raw_session(r) for r in raw) if x})
    recent = set(sessions[-20:])
    counts: Counter[str] = Counter()
    for signal in raw:
        if raw_session(signal) not in recent:
            continue
        for gate in technical_gate_rows(signal, selector):
            counts[gate] += 1
    if counts:
        detail = pd.DataFrame([{"Blocker": gate_label(code), "Count": count, "Technical Code": code} for code, count in counts.most_common(20)])
        st.dataframe(detail, width="stretch", hide_index=True)
    else:
        st.info("No blockers recorded for this policy in the last 20 sessions.")

st.subheader("Risk & Concentration")
if tickers:
    symbols = [str(x.get("symbol") or "") for x in tickers if x.get("symbol")]
    overlap = Counter(symbols)
    multi = [f"{symbol} ×{count}" for symbol, count in overlap.items() if count > 1]
    long_count = sum(1 for x in tickers if str(x.get("side") or "LONG").upper() == "LONG")
    net_long = 100.0 * long_count / len(tickers) if tickers else None
    rc = st.columns(4)
    rc[0].metric("Net Long", f"{net_long:.0f}%" if net_long is not None else "N/D")
    rc[1].metric("Open Risk", f"{n(control.get('open_risk_r')):.2f}R" if n(control.get("open_risk_r")) is not None else "N/D")
    rc[2].metric("Locked Profit", f"{n(control.get('locked_profit_r')):+.2f}R" if n(control.get("locked_profit_r")) is not None else "N/D")
    rc[3].metric("Ticker Overlap", ", ".join(multi) if multi else "None")
    st.caption("Sector and correlation-cluster concentration require the 2.2 enrichment/snapshot fields; until verified they remain N/D rather than being estimated in the UI.")
else:
    st.info("No open exposure to evaluate.")

show_previous = st.toggle("Show Today vs Previous Run", value=False)
if show_previous:
    raw = load_raw_signals()
    sessions = sorted({x for x in (raw_session(r) for r in raw) if x})
    if len(sessions) >= 2:
        current_session, previous_session = sessions[-1], sessions[-2]
        current_rows = [r for r in raw if raw_session(r) == current_session]
        previous_rows = [r for r in raw if raw_session(r) == previous_session]
        current_tiers, previous_tiers = Counter(raw_tier(r) for r in current_rows), Counter(raw_tier(r) for r in previous_rows)
        compare = pd.DataFrame([
            {"Metric": "Signals", "Current": len(current_rows), "Previous": len(previous_rows), "Delta": len(current_rows)-len(previous_rows)},
            {"Metric": "Tier A", "Current": current_tiers.get("A",0), "Previous": previous_tiers.get("A",0), "Delta": current_tiers.get("A",0)-previous_tiers.get("A",0)},
            {"Metric": "Tier B", "Current": current_tiers.get("B",0), "Previous": previous_tiers.get("B",0), "Delta": current_tiers.get("B",0)-previous_tiers.get("B",0)},
            {"Metric": "Tier C", "Current": current_tiers.get("C",0), "Previous": previous_tiers.get("C",0), "Delta": current_tiers.get("C",0)-previous_tiers.get("C",0)},
        ])
        st.dataframe(compare, width="stretch", hide_index=True)
    else:
        st.info("A previous session is not available yet.")

st.caption("Question answered by this page: Is the Laboratory healthy, where is signal flow blocked, and what needs attention now?")
st.caption(f"Updated: {datetime.now().astimezone().strftime('%d/%m/%Y %H:%M:%S %Z')}")