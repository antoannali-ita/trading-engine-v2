from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import streamlit as st

try:
    from dashboard import data_access
except ModuleNotFoundError:
    import dashboard.data_access as data_access

st.set_page_config(page_title="Laboratory Control", page_icon="🧪", layout="wide")


def require_access() -> None:
    expected = (os.getenv("DASHBOARD_PASSWORD") or "").strip()
    if not expected or st.session_state.get("dashboard_auth"):
        return
    st.title("🔐 Trading Engine Control Center")
    pwd = st.text_input("Password", type="password")
    if st.button("Accedi", type="primary"):
        if pwd == expected:
            st.session_state["dashboard_auth"] = True
            st.rerun()
        st.error("Password non valida")
    st.stop()


def parse_json(value: Any, default: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if value in (None, ""):
        return default
    try:
        return json.loads(str(value))
    except Exception:
        return default


def signal_session(row: dict[str, Any]) -> str | None:
    value = row.get("signal_date") or row.get("created_at")
    return str(value)[:10] if value else None


def position_session(row: dict[str, Any]) -> str | None:
    value = row.get("source_signal_date") or row.get("opened_at") or row.get("created_at")
    return str(value)[:10] if value else None


def paper_failed_gates(row: dict[str, Any]) -> list[str]:
    details = parse_json(row.get("details"), {})
    failed: list[str] = []
    if isinstance(details, dict):
        policy = details.get("paper_policy") or {}
        if isinstance(policy, dict):
            failed.extend(str(x) for x in (policy.get("hard_failed") or []))
    if str(row.get("status") or "").upper() == "BLOCKED_DATA" and not failed:
        failed.append("BLOCKED_DATA")
    return sorted(set(failed))


def strict_failed_gates(row: dict[str, Any]) -> list[str]:
    details = parse_json(row.get("details"), {})
    failed: list[str] = []
    if isinstance(details, dict):
        trade = details.get("strict_trade_eligibility") or details.get("trade_eligibility") or {}
        if isinstance(trade, dict):
            failed.extend(str(x) for x in (trade.get("failed") or []))
        quality = details.get("data_quality") or {}
        if isinstance(quality, dict) and quality.get("blocked"):
            failed.append("DATA_QUALITY_RED")
    return sorted(set(failed))


def ratio(num: int, den: int) -> float:
    return num / den * 100.0 if den else 0.0


def fmt_delta(current: float, previous: float) -> str:
    if previous == 0:
        return "n/a" if current == 0 else f"+{current:.2f}"
    change = (current - previous) / abs(previous) * 100.0
    return f"{change:+.1f}%"


def paper_tier(row: dict[str, Any]) -> str:
    details = parse_json(row.get("details"), {})
    if isinstance(details, dict) and details.get("paper_tier"):
        return str(details.get("paper_tier"))
    return "-"


@st.cache_data(ttl=60, show_spinner=False)
def load_data():
    return {
        "signals": data_access.lab_paper_signals(5000),
        "positions": data_access.lab_paper_positions(5000),
        "outcomes": data_access.lab_signal_outcomes(10000),
        "backtests": data_access.lab_backtest_results(10000),
    }


require_access()
st.title("🧪 Laboratory Control")
st.caption("Diagnostica del Laboratory per sessione di mercato: segnali, paper trade, tier A/B/C, colli di bottiglia e confronto tra strategie. Nessun ordine reale viene generato da questa pagina.")

with st.sidebar:
    st.markdown("### Come leggere questa pagina")
    st.markdown("""
**Obiettivo:** capire se il Laboratory sta realmente facendo esperimenti, non solo producendo segnali.

**Controlla nell'ordine:**
1. Ultima sessione analizzata
2. Segnali e Paper Open
3. Conversione segnale → paper
4. Tier A/B/C
5. Gate PAPER_POLICY che bloccano davvero
6. Gate LEGACY_STRICT che in produzione sarebbero più severi
7. Strategie UNDERTESTED / BOTTLENECK / REVIEW

Il confronto è tra **sessioni completate**, non tra 48 ore di calendario. Weekend e festività quindi non fanno sembrare fermo un sistema che correttamente non aveva mercato da analizzare.
""")

try:
    data = load_data()
except Exception as exc:
    st.error(f"Impossibile leggere Supabase: {type(exc).__name__}: {exc}")
    st.stop()

signals = data["signals"]
positions = data["positions"]
outcomes = data["outcomes"]
backtests = data["backtests"]

sessions = sorted({d for d in (signal_session(r) for r in signals) if d})
latest_session = sessions[-1] if sessions else None
previous_session = sessions[-2] if len(sessions) >= 2 else None
cur = [r for r in signals if signal_session(r) == latest_session] if latest_session else []
prev = [r for r in signals if signal_session(r) == previous_session] if previous_session else []
cur_pos = [r for r in positions if position_session(r) == latest_session] if latest_session else []
prev_pos = [r for r in positions if position_session(r) == previous_session] if previous_session else []

cur_status = Counter(str(x.get("status") or "N/D").upper() for x in cur)
prev_status = Counter(str(x.get("status") or "N/D").upper() for x in prev)
cur_tiers = Counter(paper_tier(x) for x in cur if paper_tier(x) != "-")
prev_tiers = Counter(paper_tier(x) for x in prev if paper_tier(x) != "-")
cur_conv = ratio(len(cur_pos), len(cur))
prev_conv = ratio(len(prev_pos), len(prev))

st.info(f"Ultima sessione disponibile: **{latest_session or 'N/D'}** · precedente: **{previous_session or 'N/D'}**")
m1, m2, m3, m4, m5, m6 = st.columns(6)
m1.metric("Segnali sessione", len(cur), fmt_delta(len(cur), len(prev)))
m2.metric("CONFIRMED", cur_status.get("CONFIRMED", 0), fmt_delta(cur_status.get("CONFIRMED", 0), prev_status.get("CONFIRMED", 0)))
m3.metric("Paper Open", len(cur_pos), fmt_delta(len(cur_pos), len(prev_pos)))
m4.metric("Conversione", f"{cur_conv:.2f}%", f"{cur_conv-prev_conv:+.2f} pp")
m5.metric("Tier A/B/C", f"{cur_tiers.get('A',0)}/{cur_tiers.get('B',0)}/{cur_tiers.get('C',0)}")
m6.metric("BLOCKED_DATA", cur_status.get("BLOCKED_DATA", 0), fmt_delta(cur_status.get("BLOCKED_DATA", 0), prev_status.get("BLOCKED_DATA", 0)))

if len(cur) >= 10 and cur_conv < 5:
    st.error("🔴 Collo di bottiglia: conversione in paper trade sotto il 5% nell'ultima sessione.")
elif not cur:
    st.warning("🟠 Nessuna sessione Laboratory disponibile.")
else:
    st.success("🟢 Attività Laboratory presente. Il dettaglio sotto mostra dove si perde conversione.")

strategies = sorted({str(r.get("strategy") or "") for r in signals if r.get("strategy")})
backtest_map: dict[str, list[dict[str, Any]]] = defaultdict(list)
for row in backtests:
    backtest_map[str(row.get("strategy") or "")].append(row)
outcome_map: dict[str, list[dict[str, Any]]] = defaultdict(list)
for row in outcomes:
    outcome_map[str(row.get("strategy") or "")].append(row)

summary = []
gates: Counter[tuple[str, str, str]] = Counter()
for strategy in strategies:
    rs = [r for r in cur if str(r.get("strategy") or "") == strategy]
    all_r = [r for r in signals if str(r.get("strategy") or "") == strategy]
    ps = [r for r in cur_pos if str(r.get("strategy") or "") == strategy]
    all_p = [r for r in positions if str(r.get("strategy") or "") == strategy]
    stats = Counter(str(r.get("status") or "N/D").upper() for r in rs)
    tiers = Counter(paper_tier(r) for r in rs if paper_tier(r) != "-")
    for row in rs:
        for gate in paper_failed_gates(row):
            gates[(strategy, "PAPER_POLICY", gate)] += 1
        for gate in strict_failed_gates(row):
            gates[(strategy, "LEGACY_STRICT", gate)] += 1

    bt = backtest_map.get(strategy, [])
    pf = [float(r["profit_factor"]) for r in bt if r.get("profit_factor") not in (None, "")]
    avgr = [float(r["avg_return_pct"]) for r in bt if r.get("avg_return_pct") not in (None, "")]
    avg_pf = sum(pf) / len(pf) if pf else None
    avg_ret = sum(avgr) / len(avgr) if avgr else None

    outs = outcome_map.get(strategy, [])
    d1 = [float(r["ret_d1"]) for r in outs if r.get("ret_d1") not in (None, "")]
    avg_d1 = sum(d1) / len(d1) if d1 else None

    session_conv = ratio(len(ps), len(rs))
    lifetime_conv = ratio(len(all_p), len(all_r))
    blocked_ratio = stats.get("BLOCKED_DATA", 0) / len(rs) if rs else 0.0
    if len(all_p) < 10:
        lab_status = "UNDERTESTED"
    elif blocked_ratio >= 0.30:
        lab_status = "REVIEW"
    elif len(all_r) >= 20 and lifetime_conv < 5:
        lab_status = "BOTTLENECK"
    elif avg_pf is not None and avg_pf >= 1.40 and (avg_ret or 0) > 0:
        lab_status = "PROMISING"
    else:
        lab_status = "ACTIVE"

    summary.append({
        "strategy": strategy,
        "signals_session": len(rs),
        "PRE_BUY": stats.get("PRE_BUY", 0),
        "NEAR_SETUP": stats.get("NEAR_SETUP", 0),
        "CONFIRMED": stats.get("CONFIRMED", 0),
        "BLOCKED_DATA": stats.get("BLOCKED_DATA", 0),
        "tier_A": tiers.get("A", 0),
        "tier_B": tiers.get("B", 0),
        "tier_C": tiers.get("C", 0),
        "paper_open_session": len(ps),
        "conversion_session_pct": round(session_conv, 2),
        "paper_open_lifetime": len(all_p),
        "conversion_lifetime_pct": round(lifetime_conv, 2),
        "backtest_avg_pf": round(avg_pf, 3) if avg_pf is not None else None,
        "backtest_avg_return_pct": round(avg_ret, 3) if avg_ret is not None else None,
        "forward_d1_n": len(d1),
        "forward_avg_d1_pct": round(avg_d1, 3) if avg_d1 is not None else None,
        "lab_status": lab_status,
    })

st.subheader("Strategie")
st.dataframe(pd.DataFrame(summary), width="stretch", hide_index=True)

st.subheader("Perché non stiamo comprando in paper?")
gate_rows = [
    {"strategy": s, "policy_type": p, "gate": g, "blocked_session": n}
    for (s, p, g), n in gates.most_common()
]
if gate_rows:
    gate_df = pd.DataFrame(gate_rows)
    st.dataframe(gate_df, width="stretch", hide_index=True)
    paper_only = gate_df[gate_df["policy_type"] == "PAPER_POLICY"]
    if not paper_only.empty:
        total_gates = paper_only.groupby("gate", as_index=False)["blocked_session"].sum().sort_values("blocked_session", ascending=False)
        st.markdown("#### Gate che bloccano davvero il paper V2")
        st.bar_chart(total_gates.set_index("gate"))
    st.caption("LEGACY_STRICT mostra cosa avrebbe bloccato la vecchia logica severa; PAPER_POLICY indica invece i veto effettivi del nuovo Laboratory.")
else:
    st.info("Nessun gate registrato nei dettagli dei segnali dell'ultima sessione.")

st.subheader("Confronto ultima sessione vs precedente")
comparison = pd.DataFrame([
    {"metrica": "Segnali", "ultima": len(cur), "precedente": len(prev)},
    {"metrica": "PRE_BUY", "ultima": cur_status.get("PRE_BUY", 0), "precedente": prev_status.get("PRE_BUY", 0)},
    {"metrica": "NEAR_SETUP", "ultima": cur_status.get("NEAR_SETUP", 0), "precedente": prev_status.get("NEAR_SETUP", 0)},
    {"metrica": "CONFIRMED", "ultima": cur_status.get("CONFIRMED", 0), "precedente": prev_status.get("CONFIRMED", 0)},
    {"metrica": "BLOCKED_DATA", "ultima": cur_status.get("BLOCKED_DATA", 0), "precedente": prev_status.get("BLOCKED_DATA", 0)},
    {"metrica": "Tier A", "ultima": cur_tiers.get("A", 0), "precedente": prev_tiers.get("A", 0)},
    {"metrica": "Tier B", "ultima": cur_tiers.get("B", 0), "precedente": prev_tiers.get("B", 0)},
    {"metrica": "Tier C", "ultima": cur_tiers.get("C", 0), "precedente": prev_tiers.get("C", 0)},
    {"metrica": "Paper Open", "ultima": len(cur_pos), "precedente": len(prev_pos)},
    {"metrica": "Conversione %", "ultima": round(cur_conv, 2), "precedente": round(prev_conv, 2)},
])
st.dataframe(comparison, width="stretch", hide_index=True)

st.subheader("Ultimi paper trade")
if positions:
    enriched = []
    for row in positions:
        item = dict(row)
        item["paper_tier"] = paper_tier(row)
        enriched.append(item)
    p = pd.DataFrame(enriched)
    cols = [c for c in ["opened_at", "symbol", "strategy", "paper_tier", "status", "entry_price", "last_price", "stop_current", "tp1", "tp2", "return_pct", "exit_reason"] if c in p.columns]
    st.dataframe(p[cols].head(100), width="stretch", hide_index=True)
else:
    st.info("Nessuna paper position registrata.")

st.caption(f"Aggiornato: {datetime.now().astimezone().strftime('%d/%m/%Y %H:%M:%S %Z')}")
