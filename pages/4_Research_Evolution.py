from __future__ import annotations

import json
from datetime import datetime
from itertools import combinations
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
    return


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


def holding_business_days(opened_at: Any, closed_at: Any) -> int | None:
    try:
        start = pd.Timestamp(opened_at).normalize()
        end = pd.Timestamp(closed_at).normalize()
        if end < start:
            return None
        return max(len(pd.bdate_range(start, end)) - 1, 1)
    except Exception:
        return None


def regime_name(details: dict) -> str:
    raw = details.get("market_regime")
    if isinstance(raw, dict):
        return str(raw.get("state") or "UNKNOWN")
    return str(raw or "UNKNOWN")


@st.cache_data(ttl=60, show_spinner=False)
def load_data():
    return {
        "positions": data_access.lab_paper_positions(10000),
        "outcomes": data_access.lab_signal_outcomes(20000),
        "backtests": data_access.lab_backtest_results(20000),
        "signals": data_access.lab_paper_signals(20000),
    }


require_access()
st.title("🧬 Research / Evolution")
st.caption("Evidenza empirica per Strategy × Tier. Questa pagina non promuove automaticamente nulla in Production.")

with st.sidebar:
    st.markdown("### Guida della pagina")
    st.markdown("""
**Domanda:** cosa stiamo imparando?

La maturità è calcolata per **Strategy × Tier**:
- `<10` UNDERTESTED
- `10-29` EARLY
- `30-49` DEVELOPING
- `≥50` EVALUABLE

Le strategie hanno holding diversi. Per questo, oltre al Profit Factor, mostriamo anche **ritorno netto normalizzato a 20 sessioni**, holding medio e **cost drag**.

La **Overlap Matrix** va letta anche per regime: due strategie possono essere quasi duplicate in RISK_ON e molto meno sovrapposte in altri mercati.

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
signals = data["signals"]

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
    entry = f(p.get("entry_price")); qty = f(p.get("qty"))
    capital = (entry * qty) if entry and qty else None
    net_return = (net990 / capital * 100.0) if net990 is not None and capital else None
    hold = holding_business_days(p.get("opened_at") or p.get("created_at"), p.get("closed_at"))
    return20 = (net_return * 20.0 / hold) if net_return is not None and hold else None
    cost_drag = (gross - net990) if gross is not None and net990 is not None else None
    closed.append({
        "strategy": p.get("strategy"),
        "tier": tier,
        "gross_pnl": gross,
        "net12": net12,
        "net990": net990,
        "net_return_pct": net_return,
        "return_20_sessions_pct": return20,
        "holding_sessions": hold,
        "cost_drag_usd": cost_drag,
        "closed_at": p.get("closed_at"),
    })

st.subheader("📈 Strategy × Tier · risultati chiusi")
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
        avg_ret = grp["net_return_pct"].dropna().mean()
        avg_ret20 = grp["return_20_sessions_pct"].dropna().mean()
        avg_hold = grp["holding_sessions"].dropna().mean()
        avg_cost = grp["cost_drag_usd"].dropna().mean()
        indication = "CANDIDATE_REVIEW" if mat == "EVALUABLE" and pf990 is not None and pf990 > 1.20 and (avg_net or 0) > 0 else "NO_VERDICT"
        rows.append({
            "strategy": strategy,
            "tier": tier,
            "N_closed": n,
            "maturity": mat,
            "win_rate_net_9_90_pct": round(100 * wins / len(net990_vals), 2) if net990_vals else None,
            "gross_PF": round(gross_pf, 2) if gross_pf not in (None, float("inf")) else gross_pf,
            "net_PF_12": round(pf12, 2) if pf12 not in (None, float("inf")) else pf12,
            "net_PF_9_90": round(pf990, 2) if pf990 not in (None, float("inf")) else pf990,
            "avg_net_return_pct": round(avg_ret, 2) if pd.notna(avg_ret) else None,
            "avg_return_20_sessions_pct": round(avg_ret20, 2) if pd.notna(avg_ret20) else None,
            "avg_holding_sessions": round(avg_hold, 2) if pd.notna(avg_hold) else None,
            "avg_cost_drag_usd": round(avg_cost, 2) if pd.notna(avg_cost) else None,
            "max_drawdown_usd_9_90": round(dd, 2) if dd is not None else None,
            "evidence_label": indication,
        })
    rdf = pd.DataFrame(rows).sort_values(["maturity", "net_PF_9_90"], ascending=[True, False])
    st.dataframe(rdf, width="stretch", hide_index=True)
    st.caption("Return/20 sessioni serve solo a rendere più leggibili strategie con holding diversi; non sostituisce drawdown, PF, numero di trade e capitale impegnato.")

st.subheader("🔗 Overlap strategie · globale e per regime")
sig_rows = []
for s in signals:
    strategy = str(s.get("strategy") or "")
    symbol = str(s.get("symbol") or "")
    session = str(s.get("signal_date") or "")[:10]
    if not strategy or not symbol or not session:
        continue
    d = j(s.get("details"))
    sig_rows.append({"strategy": strategy, "symbol": symbol, "session": session, "regime": regime_name(d)})

if sig_rows:
    sdf = pd.DataFrame(sig_rows).drop_duplicates()
    overlap_rows = []
    strategies = sorted(sdf["strategy"].unique())
    regimes = ["ALL"] + sorted(sdf["regime"].dropna().unique().tolist())
    for regime in regimes:
        part = sdf if regime == "ALL" else sdf[sdf["regime"] == regime]
        sets = {
            stg: set(zip(part.loc[part["strategy"] == stg, "session"], part.loc[part["strategy"] == stg, "symbol"]))
            for stg in strategies
        }
        for a, b in combinations(strategies, 2):
            sa, sb = sets[a], sets[b]
            if not sa and not sb:
                continue
            inter = sa & sb
            union = sa | sb
            overlap_rows.append({
                "regime": regime,
                "strategy_A": a,
                "strategy_B": b,
                "signals_A": len(sa),
                "signals_B": len(sb),
                "overlap_N": len(inter),
                "overlap_union_pct": round(100.0 * len(inter) / len(union), 2) if union else 0.0,
                "overlap_min_pct": round(100.0 * len(inter) / min(len(sa), len(sb)), 2) if sa and sb else 0.0,
            })
    if overlap_rows:
        odf = pd.DataFrame(overlap_rows).sort_values(["regime", "overlap_min_pct"], ascending=[True, False])
        st.dataframe(odf, width="stretch", hide_index=True)
        st.caption("Overlap alto non significa automaticamente ridondanza: va letto insieme al regime e, quando avremo abbastanza chiuse, alla correlazione dei P&L.")
else:
    st.info("Nessun segnale sufficiente per calcolare l'overlap tra strategie.")

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
    ssdf = pd.DataFrame(shadow_rows)
    agg = ssdf.groupby(["strategy", "group"], as_index=False).agg(
        N=("strategy", "size"),
        avg_d1=("ret_d1", "mean"),
        avg_d5=("ret_d5", "mean"),
        avg_d20=("ret_d20", "mean"),
        avg_mfe_r=("mfe_r", "mean"),
        avg_mae_r=("mae_r", "mean"),
    ).round(2)
    st.dataframe(agg, width="stretch", hide_index=True)
else:
    st.info("Gli shadow outcome compariranno dopo i run del feed/outcome worker.")

st.subheader("Backtest storico: contesto, non verdetto")
if backtests:
    bdf = pd.DataFrame(backtests)
    cols = [c for c in ["strategy", "symbol", "trades", "win_rate", "avg_return_pct", "profit_factor", "max_drawdown_pct", "created_at"] if c in bdf.columns]
    st.dataframe(bdf[cols].head(500), width="stretch", hide_index=True)

st.caption(f"Aggiornato: {datetime.now().astimezone().strftime('%d/%m/%Y %H:%M:%S %Z')}")
