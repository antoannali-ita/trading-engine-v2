from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from typing import Any

import pandas as pd
import streamlit as st

from common_utility.lab_cost_model import CURRENT_COMMISSION_PER_SIDE, SLIPPAGE_BPS
from common_utility.lab_dashboard_metrics import open_net_pnl

try:
    from dashboard import data_access
except ModuleNotFoundError:
    import dashboard.data_access as data_access

st.set_page_config(page_title="Laboratory Control", page_icon="🔬", layout="wide")


def j(v: Any) -> dict:
    if isinstance(v, dict):
        return v
    try:
        return json.loads(str(v)) if v else {}
    except Exception:
        return {}


def n(v: Any) -> float | None:
    try:
        return float(v) if v is not None else None
    except Exception:
        return None


def session_of(row: dict[str, Any]) -> str | None:
    value = row.get("signal_date") or row.get("source_signal_date") or row.get("created_at") or row.get("opened_at")
    return str(value)[:10] if value else None


def tier_of(row: dict[str, Any]) -> str:
    d = j(row.get("details"))
    policy = j(d.get("paper_policy"))
    return str(d.get("paper_tier") or policy.get("tier") or "N/D")


def gate_rows(signal: dict[str, Any]) -> list[dict[str, str]]:
    d = j(signal.get("details"))
    policy = j(d.get("paper_policy"))
    out: list[dict[str, str]] = []
    for gate in policy.get("data_gate_failures", []) or []:
        out.append({"Family": "DATA", "Policy": "PAPER_POLICY", "Tier": "ALL", "Gate": str(gate)})
    for gate in policy.get("policy_hard_failures", []) or []:
        out.append({"Family": "POLICY", "Policy": "PAPER_POLICY", "Tier": "ALL", "Gate": str(gate)})
    checks = policy.get("tier_checks") or {}
    if isinstance(checks, dict):
        for tier, check in checks.items():
            if isinstance(check, dict):
                for gate in check.get("failed", []) or []:
                    out.append({"Family": "DATA" if str(gate).startswith("DATA_") else "POLICY", "Policy": "PAPER_POLICY", "Tier": str(tier), "Gate": str(gate)})
    strict = j(d.get("strict_trade_eligibility") or d.get("trade_eligibility"))
    for gate in strict.get("failed", []) or []:
        out.append({"Family": "DATA" if "DATA" in str(gate) else "POLICY", "Policy": "LEGACY_STRICT", "Tier": "LEGACY", "Gate": str(gate)})
    return out


def style_signed(frame: pd.DataFrame, cols: list[str]):
    styler = frame.style
    def color(v: Any) -> str:
        value = n(v)
        if value is None or value == 0:
            return ""
        return "color:#15803d;font-weight:700;" if value > 0 else "color:#dc2626;font-weight:700;"
    for col in cols:
        if col in frame.columns:
            styler = styler.map(color, subset=[col])
    return styler


@st.cache_data(ttl=60, show_spinner=False)
def load_data():
    return {
        "signals": data_access.lab_paper_signals(10000),
        "positions": data_access.lab_paper_positions(10000),
    }


st.title("🔬 Laboratory Control")
st.caption("Technical control room: signal flow, tier conversion, blocking gates and session-to-session changes. PAPER only.")

with st.sidebar:
    st.markdown("## Guida · Laboratory Control")
    with st.expander("A cosa serve", expanded=True):
        st.markdown("Questa pagina spiega **perché il motore sta producendo certi segnali e certi paper trade**. Non sostituisce la Overview: qui guardiamo soprattutto diagnostica, Tier, conversione e blocchi.")
    with st.expander("Tier A / B / C"):
        st.markdown("**Tier A** = candidato quasi Production, ma ancora paper.  \n**Tier B** = esperimento controllato.  \n**Tier C** = ricerca soltanto, mai operativo.")
    with st.expander("Come leggere i Gates"):
        st.markdown("**DATA** = problema o mancanza nei dati.  \n**POLICY** = regola non superata, per esempio score, trigger, R/R, Max Buy o earnings.  \nLa tabella **Top Blocking Gates** mostra quali blocchi stanno fermando più spesso i segnali.")
    with st.expander("Last Session vs Previous"):
        st.markdown("Confronta l'ultimo run con quello precedente. Serve per capire se aumentano segnali, Tier o rifiuti. Il segno +/− non è sempre buono o cattivo: per esempio meno Data Rejects è positivo.")
    with st.expander("Open P&L Health"):
        st.markdown("È solo un **controllo tecnico rapido**. Verde = P&L aperto positivo, rosso = negativo. Il dettaglio economico vero resta in Laboratory Overview / Paper Portfolio.")

try:
    data = load_data()
except Exception as exc:
    st.error(f"Unable to read Laboratory data: {type(exc).__name__}: {exc}")
    st.stop()

signals = data["signals"]
positions = data["positions"]
sessions = sorted({x for x in (session_of(r) for r in signals) if x})
latest = sessions[-1] if sessions else None
previous = sessions[-2] if len(sessions) > 1 else None
cur = [r for r in signals if session_of(r) == latest] if latest else []
prev = [r for r in signals if session_of(r) == previous] if previous else []
cur_pos = [p for p in positions if session_of(p) == latest] if latest else []
open_pos = [p for p in positions if str(p.get("status") or "").upper() in {"OPEN", "TP1_HIT"}]
cur_tier = Counter(tier_of(r) for r in cur)
cur_status = Counter(str(r.get("status") or "N/D").upper() for r in cur)
prev_tier = Counter(tier_of(r) for r in prev)
prev_status = Counter(str(r.get("status") or "N/D").upper() for r in prev)

open_pnl_health = 0.0
for p in open_pos:
    value = open_net_pnl(
        p.get("entry_price"),
        p.get("last_price") or p.get("entry_price"),
        p.get("qty"),
        CURRENT_COMMISSION_PER_SIDE,
        SLIPPAGE_BPS,
    )
    open_pnl_health += value or 0.0

if latest:
    st.success(f"LAB ACTIVE · Last session {latest} · {len(cur)} signals · {len(cur_pos)} new paper trades")
else:
    st.warning("No Laboratory session available.")

k = st.columns(6)
k[0].metric("Signals Last Run", len(cur))
k[1].metric("New Paper Trades", len(cur_pos))
k[2].metric("Tier A", cur_tier.get("A", 0))
k[3].metric("Tier B", cur_tier.get("B", 0))
k[4].metric("Tier C", cur_tier.get("C", 0))
k[5].metric("Data Rejects", cur_status.get("BLOCKED_DATA", 0))

if open_pnl_health > 0:
    st.success(f"Engineering Health · Open P&L: +${open_pnl_health:,.2f}")
elif open_pnl_health < 0:
    st.error(f"Engineering Health · Open P&L: -${abs(open_pnl_health):,.2f}")
else:
    st.info("Engineering Health · Open P&L: $0.00")

st.subheader("Last Session vs Previous")
if previous:
    delta_rows = [
        {"Metric": "Signals", "Current": len(cur), "Previous": len(prev), "Delta": len(cur) - len(prev)},
        {"Metric": "Tier A", "Current": cur_tier.get("A", 0), "Previous": prev_tier.get("A", 0), "Delta": cur_tier.get("A", 0) - prev_tier.get("A", 0)},
        {"Metric": "Tier B", "Current": cur_tier.get("B", 0), "Previous": prev_tier.get("B", 0), "Delta": cur_tier.get("B", 0) - prev_tier.get("B", 0)},
        {"Metric": "Tier C", "Current": cur_tier.get("C", 0), "Previous": prev_tier.get("C", 0), "Delta": cur_tier.get("C", 0) - prev_tier.get("C", 0)},
        {"Metric": "Data Rejects", "Current": cur_status.get("BLOCKED_DATA", 0), "Previous": prev_status.get("BLOCKED_DATA", 0), "Delta": cur_status.get("BLOCKED_DATA", 0) - prev_status.get("BLOCKED_DATA", 0)},
    ]
    st.dataframe(pd.DataFrame(delta_rows), width="stretch", hide_index=True)
else:
    st.info("A previous session is not available yet.")

st.subheader("Strategy Diagnostics")
strategies = sorted({str(r.get("strategy")) for r in signals if r.get("strategy")} | {str(p.get("strategy")) for p in positions if p.get("strategy")})
summary = []
for strategy in strategies:
    current_signals = [r for r in cur if str(r.get("strategy")) == strategy]
    all_positions = [p for p in positions if str(p.get("strategy")) == strategy]
    open_s = [p for p in all_positions if str(p.get("status") or "").upper() in {"OPEN", "TP1_HIT"}]
    closed_s = [p for p in all_positions if str(p.get("status") or "").upper() == "CLOSED"]
    opened_current = [p for p in cur_pos if str(p.get("strategy")) == strategy]
    conversion = 100.0 * len(opened_current) / len(current_signals) if current_signals else None
    closed_pnls = [n(p.get("net_pnl")) for p in closed_s]
    valid = [x for x in closed_pnls if x is not None]
    win_rate = 100.0 * sum(1 for x in valid if x > 0) / len(valid) if valid else None
    summary.append({"Strategy": strategy,"Signals": len(current_signals),"Paper Trades": len(opened_current),"Conversion %": conversion,"Open": len(open_s),"Closed": len(closed_s),"Win Rate %": win_rate})
if summary:
    sdf = pd.DataFrame(summary)
    st.dataframe(sdf.style.format({"Conversion %": "{:.2f}%", "Win Rate %": "{:.2f}%"}, na_rep="-"), width="stretch", hide_index=True)

st.subheader("Top Blocking Gates")
gates: list[dict[str, str]] = []
for signal in cur:
    gates.extend(gate_rows(signal))
if gates:
    gdf = pd.DataFrame(gates)
    top = gdf.groupby(["Family", "Policy", "Gate"], as_index=False).size().rename(columns={"size": "Count"}).sort_values("Count", ascending=False)
    st.dataframe(top.head(30), width="stretch", hide_index=True)
    with st.expander("Gate Detail by Tier"):
        st.dataframe(gdf, width="stretch", hide_index=True)
else:
    st.info("No blocking gates were recorded in the latest session.")

st.subheader("Current Signal Mix")
if cur:
    mix = pd.DataFrame([{"Strategy": r.get("strategy"),"Ticker": r.get("symbol") or r.get("ticker"),"Tier": tier_of(r),"Status": r.get("status")} for r in cur])
    st.dataframe(mix, width="stretch", hide_index=True)

st.caption("Question answered by this page: Why is the Laboratory doing this?")
st.caption(f"Updated: {datetime.now().astimezone().strftime('%d/%m/%Y %H:%M:%S %Z')}")
