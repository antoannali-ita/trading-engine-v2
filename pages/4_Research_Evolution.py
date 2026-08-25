from __future__ import annotations

import json
from datetime import datetime
from itertools import combinations
from typing import Any

import pandas as pd
import streamlit as st

from common_utility.lab_cost_model import (
    CURRENT_COMMISSION_PER_SIDE,
    DISCOUNT_COMMISSION_PER_SIDE,
    SLIPPAGE_BPS,
    closed_net_pnl,
)

try:
    from dashboard import data_access
except ModuleNotFoundError:
    import dashboard.data_access as data_access

st.set_page_config(page_title="Research Evolution", page_icon="🧬", layout="wide")


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


def profit_factor(values: list[float]) -> float | None:
    gains = sum(v for v in values if v > 0)
    losses = abs(sum(v for v in values if v < 0))
    if losses == 0:
        return None if gains == 0 else float("inf")
    return gains / losses


def max_drawdown(pnls: list[float]) -> float | None:
    if not pnls:
        return None
    equity = peak = 0.0
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


def tier_of(row: dict[str, Any]) -> str:
    d = j(row.get("details"))
    policy = j(d.get("paper_policy"))
    return str(d.get("paper_tier") or policy.get("tier") or "N/D")


def version_of(row: dict[str, Any]) -> str:
    d = j(row.get("details"))
    return str(d.get("strategy_version") or d.get("version") or "N/D")


def regime_name(details: dict) -> str:
    raw = details.get("market_regime")
    if isinstance(raw, dict):
        return str(raw.get("state") or "UNKNOWN")
    return str(raw or "UNKNOWN")


def style_signed(frame: pd.DataFrame, cols: list[str]):
    styler = frame.style
    def color(v: Any) -> str:
        value = f(v)
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
        "positions": data_access.lab_paper_positions(10000),
        "outcomes": data_access.lab_signal_outcomes(20000),
        "backtests": data_access.lab_backtest_results(20000),
        "signals": data_access.lab_paper_signals(20000),
    }


st.title("🧬 Research Evolution")
st.caption("Evidence layer: what we are learning, which strategy/tier/version combinations are maturing, and whether experimental policy changes add value.")

with st.sidebar:
    st.markdown("## Guida · Research Evolution")
    with st.expander("A cosa serve", expanded=True):
        st.markdown("Questa pagina risponde alla domanda: **cosa stiamo imparando dagli esperimenti?** Qui non si aprono trade e non si promuove automaticamente nulla in Production.")
    with st.expander("Maturity"):
        st.markdown("La maturità è misurata per **Strategy × Tier × Version**.  \n**UNDERTESTED** < 10 trade chiusi  \n**EARLY** 10-29  \n**DEVELOPING** 30-49  \n**EVALUABLE** >= 50.  \nUn campione piccolo non va trattato come una conclusione.")
    with st.expander("PF, Return e Drawdown"):
        st.markdown("**PF (Profit Factor)** > 1 significa che i guadagni lordi superano le perdite lorde.  \n**Avg Net Return** misura il ritorno medio netto.  \n**Max Drawdown** mostra la peggiore discesa cumulata del campione.  \nVerde = valore positivo; rosso = valore negativo dove il segno ha significato economico.")
    with st.expander("PAPER_POLICY vs LEGACY_STRICT"):
        st.markdown("È un esperimento centrale: confronta i trade ammessi dalla nuova **PAPER_POLICY** con quelli che la vecchia **LEGACY_STRICT** avrebbe accettato o rifiutato. Serve a capire se la nuova policy aggiunge opportunità utili o solo rumore.")
    with st.expander("Shadow Outcomes"):
        st.markdown("Osserviamo anche cosa succede ai segnali non aperti o rifiutati ma con dati validi. **MFE** misura quanto il trade sarebbe andato a favore; **MAE** quanto sarebbe andato contro.")
    with st.expander("Overlap e Backtest"):
        st.markdown("**Strategy Overlap** mostra quanto due strategie selezionano gli stessi ticker/sessioni. Un overlap alto non significa automaticamente duplicazione. I backtest sono solo contesto storico, non un verdetto operativo.")
    with st.expander("CANDIDATE_REVIEW"):
        st.markdown("Significa soltanto che c'è abbastanza evidenza per una **revisione umana**. Non equivale mai a promozione automatica in Production.")

try:
    data = load_data()
except Exception as exc:
    st.error(f"Unable to read Laboratory research data: {type(exc).__name__}: {exc}")
    st.stop()

positions = data["positions"]
outcomes = data["outcomes"]
backtests = data["backtests"]
signals = data["signals"]

closed_rows = []
for p in positions:
    if str(p.get("status") or "").upper() != "CLOSED":
        continue
    exit_price = f(p.get("exit_price")) or f(p.get("last_price"))
    entry = f(p.get("entry_price"))
    qty = f(p.get("qty"))
    gross = ((exit_price - entry) * qty) if None not in (entry, exit_price, qty) else None
    net12 = closed_net_pnl(entry, exit_price, qty, CURRENT_COMMISSION_PER_SIDE, SLIPPAGE_BPS)
    net990 = closed_net_pnl(entry, exit_price, qty, DISCOUNT_COMMISSION_PER_SIDE, SLIPPAGE_BPS)
    capital = entry * qty if entry and qty else None
    net_return = net12 / capital * 100.0 if net12 is not None and capital else None
    hold = holding_business_days(p.get("opened_at") or p.get("created_at"), p.get("closed_at") or p.get("exit_at"))
    return20 = net_return * 20.0 / hold if net_return is not None and hold else None
    cost_drag = gross - net12 if gross is not None and net12 is not None else None
    closed_rows.append({
        "Strategy": p.get("strategy"),
        "Tier": tier_of(p),
        "Version": version_of(p),
        "Gross P&L": gross,
        "Net 12": net12,
        "Net 9.90": net990,
        "Net Return %": net_return,
        "Return 20 Sessions %": return20,
        "Holding Sessions": hold,
        "Cost Drag $": cost_drag,
    })

st.subheader("Strategy × Tier × Version · Closed Evidence")
if not closed_rows:
    st.warning("There are not enough closed paper trades yet for mature statistics. This is normal early in the Laboratory lifecycle.")
else:
    cdf = pd.DataFrame(closed_rows)
    rows = []
    for (strategy, tier, version), grp in cdf.groupby(["Strategy", "Tier", "Version"], dropna=False):
        net = [float(x) for x in grp["Net 12"].dropna()]
        net990 = [float(x) for x in grp["Net 9.90"].dropna()]
        gross = [float(x) for x in grp["Gross P&L"].dropna()]
        count = len(grp)
        mat = maturity(count)
        pf = profit_factor(net)
        pf990 = profit_factor(net990)
        avg_net = sum(net) / len(net) if net else None
        indication = "CANDIDATE_REVIEW" if mat == "EVALUABLE" and pf is not None and pf > 1.20 and (avg_net or 0) > 0 else "NO_VERDICT"
        rows.append({
            "Strategy": strategy,
            "Tier": tier,
            "Version": version,
            "N Closed": count,
            "Maturity": mat,
            "Win Rate %": 100.0 * sum(1 for x in net if x > 0) / len(net) if net else None,
            "Gross PF": profit_factor(gross),
            "Net PF 12": pf,
            "Net PF 9.90": pf990,
            "Avg Net Return %": grp["Net Return %"].dropna().mean(),
            "Avg Return / 20 Sessions %": grp["Return 20 Sessions %"].dropna().mean(),
            "Avg Holding Sessions": grp["Holding Sessions"].dropna().mean(),
            "Avg Cost Drag $": grp["Cost Drag $"].dropna().mean(),
            "Max Drawdown $": max_drawdown(net),
            "Evidence": indication,
        })
    rdf = pd.DataFrame(rows)
    st.dataframe(style_signed(rdf, ["Avg Net Return %", "Avg Return / 20 Sessions %", "Max Drawdown $"]), width="stretch", hide_index=True)

st.subheader("Policy Experiment · PAPER_POLICY vs LEGACY_STRICT")
policy_rows = []
for s in signals:
    d = j(s.get("details"))
    paper = j(d.get("paper_policy"))
    strict = j(d.get("strict_trade_eligibility") or d.get("trade_eligibility"))
    paper_eligible = bool(paper.get("eligible") or paper.get("accepted") or tier_of(s) in {"A", "B", "C"})
    legacy_eligible = bool(strict.get("eligible") or strict.get("accepted"))
    policy_rows.append({
        "Session": str(s.get("signal_date") or s.get("created_at") or "")[:10],
        "Ticker": s.get("symbol") or s.get("ticker"),
        "Strategy": s.get("strategy"),
        "Tier": tier_of(s),
        "Version": version_of(s),
        "PAPER_POLICY": "ACCEPT" if paper_eligible else "REJECT",
        "LEGACY_STRICT": "ACCEPT" if legacy_eligible else "REJECT",
        "Paper Only": paper_eligible and not legacy_eligible,
    })
if policy_rows:
    pdf = pd.DataFrame(policy_rows)
    summary = pdf.groupby(["Strategy", "Tier"], dropna=False).agg(
        Signals=("Ticker", "count"),
        Paper_Accepted=("PAPER_POLICY", lambda x: int((x == "ACCEPT").sum())),
        Legacy_Accepted=("LEGACY_STRICT", lambda x: int((x == "ACCEPT").sum())),
        Paper_Only=("Paper Only", "sum"),
    ).reset_index()
    st.dataframe(summary, width="stretch", hide_index=True)
    with st.expander("Policy Comparison · Signal Detail"):
        st.dataframe(pdf, width="stretch", hide_index=True)
    st.caption("Outcome quality for PAPER-only trades is evaluated below through shadow outcomes when enough observations exist.")
else:
    st.info("No policy-comparison signals are available yet.")

st.subheader("Shadow Outcomes · Accepted vs Rejected-C Valid Data")
shadow_rows = []
for o in outcomes:
    d = j(o.get("details"))
    if d.get("exclude_from_performance"):
        continue
    group = d.get("observation_group")
    if group not in {"REJECTED_C_VALID_DATA", "ACCEPTED_PAPER", "PAPER_ELIGIBLE_NOT_OPENED"}:
        continue
    shadow_rows.append({
        "Strategy": o.get("strategy"),
        "Group": group,
        "Tier": d.get("paper_tier"),
        "D1": f(o.get("ret_d1")),
        "D5": f(o.get("ret_d5")),
        "D20": f(o.get("ret_d20")),
        "MFE R": f(o.get("mfe_r")),
        "MAE R": f(o.get("mae_r")),
    })
if shadow_rows:
    ssdf = pd.DataFrame(shadow_rows)
    agg = ssdf.groupby(["Strategy", "Group"], as_index=False).agg(
        N=("Strategy", "size"),
        Avg_D1=("D1", "mean"),
        Avg_D5=("D5", "mean"),
        Avg_D20=("D20", "mean"),
        Avg_MFE_R=("MFE R", "mean"),
        Avg_MAE_R=("MAE R", "mean"),
    ).round(2)
    st.dataframe(style_signed(agg, ["Avg_D1", "Avg_D5", "Avg_D20", "Avg_MFE_R", "Avg_MAE_R"]), width="stretch", hide_index=True)
else:
    st.info("Shadow outcomes will appear after the outcome worker has accumulated observations.")

st.subheader("Strategy Overlap · Global and by Regime")
sig_rows = []
for s in signals:
    strategy = str(s.get("strategy") or "")
    symbol = str(s.get("symbol") or "")
    session = str(s.get("signal_date") or "")[:10]
    if not strategy or not symbol or not session:
        continue
    d = j(s.get("details"))
    sig_rows.append({"Strategy": strategy, "Symbol": symbol, "Session": session, "Regime": regime_name(d)})
if sig_rows:
    sdf = pd.DataFrame(sig_rows).drop_duplicates()
    overlap_rows = []
    strategies = sorted(sdf["Strategy"].unique())
    regimes = ["ALL"] + sorted(sdf["Regime"].dropna().unique().tolist())
    for regime in regimes:
        part = sdf if regime == "ALL" else sdf[sdf["Regime"] == regime]
        sets = {stg: set(zip(part.loc[part["Strategy"] == stg, "Session"], part.loc[part["Strategy"] == stg, "Symbol"])) for stg in strategies}
        for a, b in combinations(strategies, 2):
            sa, sb = sets[a], sets[b]
            if not sa and not sb:
                continue
            inter = sa & sb
            union = sa | sb
            overlap_rows.append({
                "Regime": regime,
                "Strategy A": a,
                "Strategy B": b,
                "Signals A": len(sa),
                "Signals B": len(sb),
                "Overlap N": len(inter),
                "Overlap Union %": 100.0 * len(inter) / len(union) if union else 0.0,
                "Overlap Min %": 100.0 * len(inter) / min(len(sa), len(sb)) if sa and sb else 0.0,
            })
    if overlap_rows:
        st.dataframe(pd.DataFrame(overlap_rows).sort_values(["Regime", "Overlap Min %"], ascending=[True, False]), width="stretch", hide_index=True)
else:
    st.info("Not enough signals to calculate strategy overlap.")

st.subheader("Historical Backtests · Context, Not Verdict")
if backtests:
    bdf = pd.DataFrame(backtests)
    cols = [c for c in ["strategy", "symbol", "trades", "win_rate", "avg_return_pct", "profit_factor", "max_drawdown_pct", "created_at"] if c in bdf.columns]
    shown = bdf[cols].head(500)
    st.dataframe(style_signed(shown, ["avg_return_pct", "max_drawdown_pct"]), width="stretch", hide_index=True)
else:
    st.info("No backtest records available.")

st.caption("Question answered by this page: What have we learned?")
st.caption(f"Updated: {datetime.now().astimezone().strftime('%d/%m/%Y %H:%M:%S %Z')}")
