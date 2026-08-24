from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from datetime import datetime
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


def j(value: Any) -> dict:
    if isinstance(value, dict):
        return value
    try:
        return json.loads(str(value)) if value else {}
    except Exception:
        return {}


def session_of(row: dict[str, Any]) -> str | None:
    value = row.get("signal_date") or row.get("source_signal_date") or row.get("created_at") or row.get("opened_at")
    return str(value)[:10] if value else None


def tier_of(row: dict[str, Any]) -> str | None:
    d = j(row.get("details"))
    policy = j(d.get("paper_policy"))
    value = d.get("paper_tier") or policy.get("tier")
    return str(value) if value else None


def gate_rows(signal: dict[str, Any]) -> list[dict[str, str]]:
    d = j(signal.get("details"))
    policy = j(d.get("paper_policy"))
    out: list[dict[str, str]] = []

    for gate in policy.get("data_gate_failures", []) or []:
        out.append({"family": "DATA", "policy": "PAPER_POLICY", "tier": "ALL", "gate": str(gate)})
    for gate in policy.get("policy_hard_failures", []) or []:
        out.append({"family": "POLICY", "policy": "PAPER_POLICY", "tier": "ALL", "gate": str(gate)})

    checks = policy.get("tier_checks") or {}
    if isinstance(checks, dict):
        for tier, check in checks.items():
            if not isinstance(check, dict):
                continue
            for gate in check.get("failed", []) or []:
                family = "DATA" if str(gate).startswith("DATA_") else "POLICY"
                out.append({"family": family, "policy": "PAPER_POLICY", "tier": str(tier), "gate": str(gate)})

    strict = j(d.get("strict_trade_eligibility") or d.get("trade_eligibility"))
    for gate in strict.get("failed", []) or []:
        family = "DATA" if "DATA" in str(gate) else "POLICY"
        out.append({"family": family, "policy": "LEGACY_STRICT", "tier": "LEGACY", "gate": str(gate)})
    return out


@st.cache_data(ttl=60, show_spinner=False)
def load_data():
    return {
        "signals": data_access.lab_paper_signals(10000),
        "positions": data_access.lab_paper_positions(10000),
        "outcomes": data_access.lab_signal_outcomes(20000),
    }


require_access()
st.title("🧪 Laboratory Control")
st.caption("Controllo del throughput sperimentale. Production resta separata e nessun elemento di questa pagina genera ordini reali.")

with st.sidebar:
    st.markdown("### Guida della pagina")
    st.markdown("""
**Domanda:** il Laboratory sta lavorando e dove si blocca?

**Funnel:** universo → segnali → Tier A/B/C → paper open.

- **A:** baseline quasi-production.
- **B:** esperimento con gate rilassati.
- **C:** 🔬 **RESEARCH ONLY · NON OPERATIVO**.
- **RED data quality:** veto.
- **YELLOW:** può entrare solo B/C, mai A.

I gate **DATA** indicano problemi/limiti dei dati. I gate **POLICY** sono scelte strategiche. Non vanno confusi.

`LEGACY_STRICT` è solo un confronto diagnostico: non rappresenta "alpha perso" e non osserva l'intero universo senza filtri.
""")

try:
    data = load_data()
except Exception as exc:
    st.error(f"Impossibile leggere Supabase: {type(exc).__name__}: {exc}")
    st.stop()

signals = data["signals"]
positions = data["positions"]
outcomes = data["outcomes"]

sessions = sorted({x for x in (session_of(r) for r in signals) if x})
latest = sessions[-1] if sessions else None
previous = sessions[-2] if len(sessions) > 1 else None
cur = [r for r in signals if session_of(r) == latest] if latest else []
prev = [r for r in signals if session_of(r) == previous] if previous else []
cur_pos = [p for p in positions if session_of(p) == latest] if latest else []
prev_pos = [p for p in positions if session_of(p) == previous] if previous else []

cur_status = Counter(str(r.get("status") or "N/D").upper() for r in cur)
cur_tier = Counter(tier_of(r) for r in cur if tier_of(r))
prev_tier = Counter(tier_of(r) for r in prev if tier_of(r))
conversion = 100 * len(cur_pos) / len(cur) if cur else 0.0
prev_conversion = 100 * len(prev_pos) / len(prev) if prev else 0.0

st.info(f"Ultima sessione: **{latest or 'N/D'}** · precedente: **{previous or 'N/D'}**")
cols = st.columns(7)
cols[0].metric("Segnali", len(cur), len(cur) - len(prev))
cols[1].metric("Tier A", cur_tier.get("A", 0), cur_tier.get("A", 0) - prev_tier.get("A", 0))
cols[2].metric("Tier B", cur_tier.get("B", 0), cur_tier.get("B", 0) - prev_tier.get("B", 0))
cols[3].metric("Tier C 🔬", cur_tier.get("C", 0), cur_tier.get("C", 0) - prev_tier.get("C", 0))
cols[4].metric("Paper Open", len(cur_pos), len(cur_pos) - len(prev_pos))
cols[5].metric("Conversione", f"{conversion:.1f}%", f"{conversion-prev_conversion:+.1f} pp")
cols[6].metric("BLOCKED_DATA", cur_status.get("BLOCKED_DATA", 0))

if cur_tier.get("C", 0):
    st.warning("🔬 I Tier C sono controfattuali di ricerca. NON sono segnali operativi né candidati diretti a ordini reali.")

st.subheader("Funnel per strategia")
strategies = sorted({str(r.get("strategy")) for r in signals if r.get("strategy")})
summary = []
for strategy in strategies:
    rs = [r for r in cur if str(r.get("strategy")) == strategy]
    ps = [p for p in cur_pos if str(p.get("strategy")) == strategy]
    tiers = Counter(tier_of(r) for r in rs if tier_of(r))
    stats = Counter(str(r.get("status") or "N/D").upper() for r in rs)
    summary.append({
        "strategy": strategy,
        "signals": len(rs),
        "tier_A": tiers.get("A", 0),
        "tier_B": tiers.get("B", 0),
        "tier_C_research_only": tiers.get("C", 0),
        "paper_open": len(ps),
        "conversion_pct": round(100 * len(ps) / len(rs), 2) if rs else 0.0,
        "blocked_data": stats.get("BLOCKED_DATA", 0),
    })
st.dataframe(pd.DataFrame(summary), width="stretch", hide_index=True)

st.subheader("Gate Analysis: DATA vs POLICY, A/B/C vs LEGACY")
counter: Counter[tuple[str, str, str, str]] = Counter()
for row in cur:
    strategy = str(row.get("strategy") or "N/D")
    for item in gate_rows(row):
        counter[(strategy, item["family"], item["policy"], item["tier"], item["gate"])] += 1

gates = [
    {"strategy": k[0], "family": k[1], "policy": k[2], "tier": k[3], "gate": k[4], "count": n}
    for k, n in counter.most_common()
]
if gates:
    gate_df = pd.DataFrame(gates)
    family_filter = st.segmented_control("Famiglia", ["TUTTI", "DATA", "POLICY"], default="TUTTI")
    shown = gate_df if family_filter == "TUTTI" else gate_df[gate_df["family"] == family_filter]
    st.dataframe(shown, width="stretch", hide_index=True)
else:
    st.info("Nessun gate dettagliato disponibile per l'ultima sessione. I nuovi campi compariranno dopo il primo run V2.1.")

st.subheader("Shadow outcomes")
obs = Counter()
for row in outcomes:
    d = j(row.get("details"))
    group = d.get("observation_group")
    if group:
        obs[str(group)] += 1
if obs:
    st.dataframe(pd.DataFrame([{"gruppo": k, "osservazioni": v} for k, v in obs.items()]), width="stretch", hide_index=True)
    st.caption("REJECTED_C_VALID_DATA viene seguito come shadow outcome. DATA_REJECT resta fuori dalle statistiche di performance.")
else:
    st.info("La classificazione shadow sarà popolata dal prossimo run degli outcome V2.1.")

st.subheader("Confronto sessione")
st.dataframe(pd.DataFrame([
    {"metrica": "Segnali", "ultima": len(cur), "precedente": len(prev)},
    {"metrica": "Tier A", "ultima": cur_tier.get("A",0), "precedente": prev_tier.get("A",0)},
    {"metrica": "Tier B", "ultima": cur_tier.get("B",0), "precedente": prev_tier.get("B",0)},
    {"metrica": "Tier C", "ultima": cur_tier.get("C",0), "precedente": prev_tier.get("C",0)},
    {"metrica": "Paper Open", "ultima": len(cur_pos), "precedente": len(prev_pos)},
    {"metrica": "Conversione %", "ultima": round(conversion,2), "precedente": round(prev_conversion,2)},
]), width="stretch", hide_index=True)

st.caption(f"Aggiornato: {datetime.now().astimezone().strftime('%d/%m/%Y %H:%M:%S %Z')}")
