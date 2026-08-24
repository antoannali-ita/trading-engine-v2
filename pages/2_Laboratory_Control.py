from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
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


def parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def parse_json(value: Any, default: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if value in (None, ""):
        return default
    try:
        return json.loads(str(value))
    except Exception:
        return default


def failed_gates(row: dict[str, Any]) -> list[str]:
    details = parse_json(row.get("details"), {})
    failed: list[str] = []
    if isinstance(details, dict):
        trade = details.get("trade_eligibility") or {}
        if isinstance(trade, dict):
            failed.extend(str(x) for x in (trade.get("failed") or []))
        quality = details.get("data_quality") or {}
        if isinstance(quality, dict) and quality.get("blocked"):
            failed.append("DATA_QUALITY_RED")
    if str(row.get("status") or "").upper() == "BLOCKED_DATA" and not any("DATA" in x for x in failed):
        failed.append("BLOCKED_DATA")
    return sorted(set(failed))


def within(rows: list[dict[str, Any]], field: str, start: datetime, end: datetime) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        dt = parse_dt(row.get(field))
        if dt and start <= dt < end:
            out.append(row)
    return out


def ratio(num: int, den: int) -> float:
    return num / den * 100.0 if den else 0.0


def fmt_delta(current: float, previous: float, suffix: str = "") -> str:
    if previous == 0:
        return "n/a" if current == 0 else f"+{current:.2f}{suffix}"
    change = (current - previous) / abs(previous) * 100.0
    return f"{change:+.1f}%"


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
st.caption("Diagnostica del Laboratory: attività, conversione in paper trade, colli di bottiglia e confronto tra strategie. Nessun ordine reale viene generato da questa pagina.")

with st.sidebar:
    st.markdown("### Come leggere questa pagina")
    st.markdown("""
**Obiettivo:** capire se il Laboratory sta realmente testando le strategie, non solo producendo segnali.

**Controlla nell'ordine:**
1. Segnali 48h
2. Paper Open 48h
3. Conversione segnale → paper
4. Gate che bloccano di più
5. Strategie UNDERTESTED / REVIEW
6. Backtest e forward outcome

**Interpretazione:** un basso numero di paper trade con molti PRE_BUY/NEAR_SETUP indica un collo di bottiglia nei gate, non necessariamente una strategia scadente.
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

now = datetime.now(timezone.utc)
cur_start = now - timedelta(hours=48)
prev_start = cur_start - timedelta(hours=48)
cur = within(signals, "created_at", cur_start, now)
prev = within(signals, "created_at", prev_start, cur_start)
cur_pos = within(positions, "opened_at", cur_start, now)
prev_pos = within(positions, "opened_at", prev_start, cur_start)

cur_status = Counter(str(x.get("status") or "N/D").upper() for x in cur)
prev_status = Counter(str(x.get("status") or "N/D").upper() for x in prev)
cur_conv = ratio(len(cur_pos), len(cur))
prev_conv = ratio(len(prev_pos), len(prev))

m1, m2, m3, m4, m5, m6 = st.columns(6)
m1.metric("Segnali 48h", len(cur), fmt_delta(len(cur), len(prev)))
m2.metric("PRE_BUY", cur_status.get("PRE_BUY", 0), fmt_delta(cur_status.get("PRE_BUY", 0), prev_status.get("PRE_BUY", 0)))
m3.metric("NEAR_SETUP", cur_status.get("NEAR_SETUP", 0), fmt_delta(cur_status.get("NEAR_SETUP", 0), prev_status.get("NEAR_SETUP", 0)))
m4.metric("Paper Open 48h", len(cur_pos), fmt_delta(len(cur_pos), len(prev_pos)))
m5.metric("Conversione", f"{cur_conv:.2f}%", f"{cur_conv-prev_conv:+.2f} pp")
m6.metric("BLOCKED_DATA", cur_status.get("BLOCKED_DATA", 0), fmt_delta(cur_status.get("BLOCKED_DATA", 0), prev_status.get("BLOCKED_DATA", 0)))

if len(cur) >= 10 and cur_conv < 3:
    st.error("🔴 Collo di bottiglia: molti segnali ma conversione in paper trade sotto il 3% nelle ultime 48h.")
elif not cur:
    st.warning("🟠 Nessun nuovo segnale nelle ultime 48h.")
else:
    st.success("🟢 Attività Laboratory presente. Verifica sotto distribuzione e gate per strategia.")

strategies = sorted({str(r.get("strategy") or "") for r in signals if r.get("strategy")})
backtest_map: dict[str, list[dict[str, Any]]] = defaultdict(list)
for row in backtests:
    backtest_map[str(row.get("strategy") or "")].append(row)
outcome_map: dict[str, list[dict[str, Any]]] = defaultdict(list)
for row in outcomes:
    outcome_map[str(row.get("strategy") or "")].append(row)

summary = []
gates: Counter[tuple[str, str]] = Counter()
for strategy in strategies:
    r48 = [r for r in cur if str(r.get("strategy") or "") == strategy]
    all_r = [r for r in signals if str(r.get("strategy") or "") == strategy]
    p48 = [r for r in cur_pos if str(r.get("strategy") or "") == strategy]
    stats = Counter(str(r.get("status") or "N/D").upper() for r in r48)
    for row in r48:
        for gate in failed_gates(row):
            gates[(strategy, gate)] += 1

    bt = backtest_map.get(strategy, [])
    pf = [float(r["profit_factor"]) for r in bt if r.get("profit_factor") not in (None, "")]
    avgr = [float(r["avg_return_pct"]) for r in bt if r.get("avg_return_pct") not in (None, "")]
    avg_pf = sum(pf) / len(pf) if pf else None
    avg_ret = sum(avgr) / len(avgr) if avgr else None

    outs = outcome_map.get(strategy, [])
    d1 = [float(r["ret_d1"]) for r in outs if r.get("ret_d1") not in (None, "")]
    avg_d1 = sum(d1) / len(d1) if d1 else None

    conv = ratio(len(p48), len(r48))
    blocked_ratio = stats.get("BLOCKED_DATA", 0) / len(r48) if r48 else 0.0
    if len(all_r) < 10 or len(r48) < 3:
        lab_status = "UNDERTESTED"
    elif blocked_ratio >= 0.30:
        lab_status = "REVIEW"
    elif len(r48) >= 10 and conv < 3:
        lab_status = "REVIEW"
    elif avg_pf is not None and avg_pf >= 1.40 and (avg_ret or 0) > 0:
        lab_status = "PROMISING"
    else:
        lab_status = "ACTIVE"

    summary.append({
        "strategy": strategy,
        "signals_48h": len(r48),
        "PRE_BUY": stats.get("PRE_BUY", 0),
        "NEAR_SETUP": stats.get("NEAR_SETUP", 0),
        "CONFIRMED": stats.get("CONFIRMED", 0),
        "BLOCKED_DATA": stats.get("BLOCKED_DATA", 0),
        "paper_open_48h": len(p48),
        "conversion_pct": round(conv, 2),
        "backtest_avg_pf": round(avg_pf, 3) if avg_pf is not None else None,
        "backtest_avg_return_pct": round(avg_ret, 3) if avg_ret is not None else None,
        "forward_d1_n": len(d1),
        "forward_avg_d1_pct": round(avg_d1, 3) if avg_d1 is not None else None,
        "lab_status": lab_status,
    })

st.subheader("Strategie")
st.dataframe(pd.DataFrame(summary), width="stretch", hide_index=True)

st.subheader("Perché non stiamo comprando in paper?")
gate_rows = [{"strategy": s, "gate": g, "blocked_48h": n} for (s, g), n in gates.most_common()]
if gate_rows:
    gate_df = pd.DataFrame(gate_rows)
    st.dataframe(gate_df, width="stretch", hide_index=True)
    total_gates = gate_df.groupby("gate", as_index=False)["blocked_48h"].sum().sort_values("blocked_48h", ascending=False)
    st.bar_chart(total_gates.set_index("gate"))
else:
    st.info("Nessun hard/soft gate registrato nei dettagli dei segnali delle ultime 48h.")

st.subheader("Confronto 48h vs 48h precedenti")
comparison = pd.DataFrame([
    {"metrica": "Segnali", "ultime_48h": len(cur), "precedenti_48h": len(prev)},
    {"metrica": "PRE_BUY", "ultime_48h": cur_status.get("PRE_BUY", 0), "precedenti_48h": prev_status.get("PRE_BUY", 0)},
    {"metrica": "NEAR_SETUP", "ultime_48h": cur_status.get("NEAR_SETUP", 0), "precedenti_48h": prev_status.get("NEAR_SETUP", 0)},
    {"metrica": "CONFIRMED", "ultime_48h": cur_status.get("CONFIRMED", 0), "precedenti_48h": prev_status.get("CONFIRMED", 0)},
    {"metrica": "BLOCKED_DATA", "ultime_48h": cur_status.get("BLOCKED_DATA", 0), "precedenti_48h": prev_status.get("BLOCKED_DATA", 0)},
    {"metrica": "Paper Open", "ultime_48h": len(cur_pos), "precedenti_48h": len(prev_pos)},
    {"metrica": "Conversione %", "ultime_48h": round(cur_conv, 2), "precedenti_48h": round(prev_conv, 2)},
])
st.dataframe(comparison, width="stretch", hide_index=True)

st.subheader("Ultimi paper trade")
if positions:
    p = pd.DataFrame(positions)
    cols = [c for c in ["opened_at", "symbol", "strategy", "status", "entry_price", "last_price", "stop_current", "tp1", "tp2", "return_pct", "exit_reason"] if c in p.columns]
    st.dataframe(p[cols].head(100), width="stretch", hide_index=True)
else:
    st.info("Nessuna paper position registrata.")

st.caption(f"Aggiornato: {datetime.now().astimezone().strftime('%d/%m/%Y %H:%M:%S %Z')}")
