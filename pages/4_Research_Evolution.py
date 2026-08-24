from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any

import pandas as pd
import streamlit as st

try:
    from dashboard import data_access
except ModuleNotFoundError:
    import dashboard.data_access as data_access

st.set_page_config(page_title="Research / Evolution", page_icon="🧬", layout="wide")

CURRENT_COMMISSION = 12.0
DISCOUNT_COMMISSION = 9.90
SLIPPAGE_BPS = 5.0


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


def f(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except Exception:
        return None


def maturity(n: int) -> str:
    if n < 10:
        return "UNDERTESTED"
    if n < 30:
        return "EARLY"
    if n < 50:
        return "DEVELOPING"
    return "EVALUABLE"


def realized_net(entry, exit_price, qty, commission):
    entry, exit_price, qty = f(entry), f(exit_price), f(qty)
    if not entry or exit_price is None or not qty:
        return None
    slip = SLIPPAGE_BPS / 10000.0
    entry_exec = entry * (1 + slip)
    exit_exec = exit_price * (1 - slip)
    return (exit_exec - entry_exec) * qty - 2 * commission


def profit_factor(values: list[float]) -> float | None:
    gains = sum(v for v in values if v > 0)
    losses = abs(sum(v for v in values if v < 0))
    if losses == 0:
        return None if gains == 0 else float("inf")
    return gains / losses


def max_drawdown(pnls: list[float]) -> float | None:
    if not pnls:
        return None
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    for pnl in pnls:
        equity += pnl
        peak = max(peak, equity)
        max_dd = min(max_dd, equity - peak)
    return max_dd


@st.cache_data(ttl=60, show_spinner=False)
def load_data():
    return {
        "positions": data_access.lab_paper_positions(10000),
        "outcomes": data_access.lab_signal_outcomes(20000),
        "backtests": data_access.lab_backtest_results(20000),
    }


require_access()
st.title("🧬 Research / Evolution")
st.caption("Evidenza empirica per Strategy × Tier. Questa pagina non promuove automaticamente nulla in Production.")

with st.sidebar:
    st.markdown("### Guida della pagina")
    st.markdown("""
**Domanda:** cosa stiamo imparando?

La maturità è calcolata per **Strategy × Tier**, non mescolando A/B/C:
- `<10` UNDERTESTED
- `10-29` EARLY
- `30-49` DEVELOPING
- `≥50` EVALUABLE

Con l'attuale frequenza di esperimenti possono servire **diverse settimane** prima che una singola combinazione diventi EVALUABLE.

Il numero principale è il **Net Profit Factor**, dopo commissioni e slippage stimato. Mostriamo sia $12 sia $9,90 per eseguito. Il secondo è lo scenario scontato comunicato dall'utente e va verificato quando diventerà effettivo.

`CANDIDATE_REVIEW` significa solo "merita revisione umana". Non equivale a promozione in Production.
""")

try:
    data = load_data()
except Exception as exc:
    st.error(f"Impossibile leggere Supabase: {type(exc).__name__}: {exc}")
    st.stop()

positions = data["positions"]
outcomes = data["outcomes"]
backtests = data["backtests"]

closed = []
for p in positions:
    if str(p.get("status") or "").upper() != "CLOSED":
        continue
    d = j(p.get("details"))
    tier = d.get("paper_tier") or "N/D"
    exit_price = p.get("exit_price") or p.get("last_price")
    gross = f(p.get("gross_pnl"))
    if gross is None:
        e, x, q = f(p.get("entry_price")), f(exit_price), f(p.get("qty"))
        gross = ((x - e) * q) if None not in (e, x, q) else None
    net12 = realized_net(p.get("entry_price"), exit_price, p.get("qty"), CURRENT_COMMISSION)
    net990 = realized_net(p.get("entry_price"), exit_price, p.get("qty"), DISCOUNT_COMMISSION)
    closed.append({
        "strategy": p.get("strategy"),
        "tier": tier,
        "gross_pnl": gross,
        "net12": net12,
        "net990": net990,
        "return_pct_db": f(p.get("return_pct")),
        "closed_at": p.get("closed_at"),
    })

if not closed:
    st.warning("Non ci sono ancora trade paper chiusi sufficienti per statistiche Strategy × Tier. È normale nelle prime sessioni V2.")
else:
    cdf = pd.DataFrame(closed)
    rows = []
    for (strategy, tier), grp in cdf.groupby(["strategy", "tier"], dropna=False):
        gross_vals = [float(x) for x in grp["gross_pnl"].dropna()]
        net12_vals = [float(x) for x in grp["net12"].dropna()]
        net990_vals = [float(x) for x in grp["net990"].dropna()]
        n = len(grp)
        wins = sum(1 for x in net990_vals if x > 0)
        mat = maturity(n)
        pf12 = profit_factor(net12_vals)
        pf990 = profit_factor(net990_vals)
        gross_pf = profit_factor(gross_vals)
        avg_net = sum(net990_vals) / len(net990_vals) if net990_vals else None
        dd = max_drawdown(net990_vals)
        indication = "CANDIDATE_REVIEW" if mat == "EVALUABLE" and pf990 is not None and pf990 > 1.20 and (avg_net or 0) > 0 else "NO_VERDICT"
        rows.append({
            "strategy": strategy,
            "tier": tier,
            "N_closed": n,
            "maturity": mat,
            "win_rate_net_9_90_pct": round(100 * wins / len(net990_vals), 2) if net990_vals else None,
            "gross_PF": round(gross_pf, 3) if gross_pf not in (None, float("inf")) else gross_pf,
            "net_PF_12": round(pf12, 3) if pf12 not in (None, float("inf")) else pf12,
            "net_PF_9_90": round(pf990, 3) if pf990 not in (None, float("inf")) else pf990,
            "avg_net_pnl_9_90": round(avg_net, 2) if avg_net is not None else None,
            "max_drawdown_usd_9_90": round(dd, 2) if dd is not None else None,
            "evidence_label": indication,
        })
    rdf = pd.DataFrame(rows).sort_values(["maturity", "net_PF_9_90"], ascending=[True, False])
    st.dataframe(rdf, width="stretch", hide_index=True)
    st.caption("Le soglie dell'etichetta CANDIDATE_REVIEW sono un filtro di attenzione, non una decisione automatica. I numeri e il campione restano la fonte primaria.")

st.subheader("Shadow outcome: cosa succede ai rejected-C validi")
shadow_rows = []
for o in outcomes:
    d = j(o.get("details"))
    if d.get("exclude_from_performance"):
        continue
    group = d.get("observation_group")
    if group not in {"REJECTED_C_VALID_DATA", "ACCEPTED_PAPER", "PAPER_ELIGIBLE_NOT_OPENED"}:
        continue
    shadow_rows.append({
        "strategy": o.get("strategy"),
        "group": group,
        "tier": d.get("paper_tier"),
        "ret_d1": f(o.get("ret_d1")),
        "ret_d3": f(o.get("ret_d3")),
        "ret_d5": f(o.get("ret_d5")),
        "ret_d10": f(o.get("ret_d10")),
        "ret_d20": f(o.get("ret_d20")),
        "mfe_r": f(o.get("mfe_r")),
        "mae_r": f(o.get("mae_r")),
    })
if shadow_rows:
    sdf = pd.DataFrame(shadow_rows)
    agg = sdf.groupby(["strategy", "group"], as_index=False).agg(
        N=("strategy", "size"),
        avg_d1=("ret_d1", "mean"),
        avg_d5=("ret_d5", "mean"),
        avg_d20=("ret_d20", "mean"),
        avg_mfe_r=("mfe_r", "mean"),
        avg_mae_r=("mae_r", "mean"),
    )
    st.dataframe(agg, width="stretch", hide_index=True)
    st.caption("Questo confronto è più corretto di LEGACY_STRICT vs paper soltanto: i rejected-C validi vengono osservati senza aprire una posizione virtuale. I DATA_REJECT sono esclusi dalla performance.")
else:
    st.info("Gli shadow outcome V2.1 compariranno dopo il prossimo run del feed/outcome worker.")

st.subheader("Backtest storico: contesto, non verdetto")
if backtests:
    bdf = pd.DataFrame(backtests)
    cols = [c for c in ["strategy", "symbol", "trades", "win_rate", "avg_return_pct", "profit_factor", "max_drawdown_pct", "created_at"] if c in bdf.columns]
    st.dataframe(bdf[cols].head(500), width="stretch", hide_index=True)
    st.caption("Il backtest serve come contesto. La promozione richiede anche forward paper, costi realistici, campione sufficiente e review umana.")

st.caption(f"Aggiornato: {datetime.now().astimezone().strftime('%d/%m/%Y %H:%M:%S %Z')}")
