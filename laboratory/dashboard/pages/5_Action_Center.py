import sys
from pathlib import Path

import pandas as pd
import streamlit as st

LAB_ROOT = Path(__file__).resolve().parents[2]
SRC = LAB_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from lab.auth import require_dashboard_auth
from lab.data import load_lab_paper_positions, load_lab_watchlist
from lab.settings import MIN_NET_RR
from lab.ui import (
    apply_theme,
    candidate_title,
    company_name,
    fmt_money,
    fmt_pct,
    fmt_qty,
    fmt_quality,
    fmt_regime,
    fmt_rr,
    fmt_score,
    fmt_status,
    fmt_strategy,
    fmt_trigger,
    localize_table,
    page_header,
    trigger_class,
)

STRICT_STRATEGY_REFERENCE = 75.0
STRICT_TRADE_REFERENCE = 75.0

st.set_page_config(page_title="Trading Lab | Action Center", layout="wide", page_icon="⚡")
require_dashboard_auth()
apply_theme()
page_header(
    "Action Center",
    "Funnel decisionale del Laboratory: Strategy Score → Trade Score → Paper Policy A/B/C → Portfolio Gate → PAPER OPEN. Nessun ordine reale viene creato qui.",
    eyebrow="LAB · STRATEGY · TRADE · PAPER POLICY · PORTFOLIO · RISK",
)


def _details(row) -> dict:
    value = row.get("details")
    return value if isinstance(value, dict) else {}


def _extract(row, key, default=None):
    return _details(row).get(key, default)


def _gate(details: dict, key: str) -> dict:
    value = details.get(key)
    return value if isinstance(value, dict) else {}


def _failed_list(details: dict) -> list[str]:
    parts: list[str] = []
    dq = _gate(details, "data_quality")
    strict = _gate(details, "strict_trade_eligibility") or _gate(details, "trade_eligibility")
    paper = _gate(details, "paper_policy")
    portfolio = _gate(details, "portfolio_eligibility")
    parts.extend(dq.get("red", []) or [])
    parts.extend(strict.get("failed", []) or [])
    parts.extend(paper.get("hard_failed", []) or [])
    parts.extend(portfolio.get("failed", []) or [])
    return list(dict.fromkeys(str(x) for x in parts if x))


def _failed_text(details: dict) -> str:
    failed = _failed_list(details)
    return ", ".join(failed) if failed else "PASS"


def _portfolio_pass(row) -> bool:
    return bool(_gate(_details(row), "portfolio_eligibility").get("eligible"))


def _data_pass(row) -> bool:
    return str(row.get("data_quality") or "N/D").upper() != "RED"


def _trigger_pass(row) -> bool:
    return str(row.get("trigger") or "").upper() == "CONFIRMED"


def _num(value):
    try:
        if value is None or pd.isna(value):
            return None
        return float(value)
    except Exception:
        return None


def _strict_reference_readiness(row) -> tuple[int, int, list[str]]:
    """Diagnostic only. This is NOT the Laboratory A/B/C admission policy."""
    strategy = _num(row.get("strategy_score"))
    trade = _num(row.get("trade_score"))
    rr = _num(row.get("rr_net_tp2"))
    checks = [
        (strategy is not None and strategy >= STRICT_STRATEGY_REFERENCE, f"Strategy ≥ {STRICT_STRATEGY_REFERENCE:.0f}"),
        (trade is not None and trade >= STRICT_TRADE_REFERENCE, f"Trade ≥ {STRICT_TRADE_REFERENCE:.0f}"),
        (rr is not None and rr >= MIN_NET_RR, f"Net R/R ≥ {MIN_NET_RR:.2f}"),
        (_trigger_pass(row), "Trigger CONFIRMED"),
        (_data_pass(row), "Data Quality not RED"),
        (_portfolio_pass(row), "Portfolio Gate PASS"),
    ]
    passed = sum(1 for ok, _ in checks if ok)
    missing = [label for ok, label in checks if not ok]
    return passed, len(checks), missing


def _score_with_reference(value, threshold: float) -> str:
    return f"{fmt_score(value)}  (strict ref ≥ {threshold:.0f})"


def _rr_with_reference(value) -> str:
    return f"{fmt_rr(value)}  (strict ref ≥ {MIN_NET_RR:.2f})"


def _portfolio_status(row) -> str:
    gate = _gate(_details(row), "portfolio_eligibility")
    if not gate:
        return "N/D"
    return "PASS" if gate.get("eligible") else "FAIL"


def _paper_tier(row) -> str:
    details = _details(row)
    policy = _gate(details, "paper_policy")
    return str(details.get("paper_tier") or policy.get("tier") or "N/D")


def _safety_label(row) -> str:
    policy = _gate(_details(row), "paper_policy")
    return str(policy.get("safety_label") or "N/D")


try:
    watch = load_lab_watchlist(2000)
    positions = load_lab_paper_positions(1000)
except Exception as exc:
    st.error("Laboratory operational tables are not readable.")
    st.code(str(exc))
    st.stop()

if watch.empty:
    st.info("No operational Lab candidate. Run the daily Laboratory feed to refresh the funnel.")
    st.stop()

for col in ["score", "price", "entry", "max_buy", "stop", "tp1", "tp2", "alert_price", "distance_to_entry_pct"]:
    if col in watch:
        watch[col] = pd.to_numeric(watch[col], errors="coerce")

watch["strategy_score"] = watch.apply(lambda r: _extract(r, "strategy_score", r.get("score")), axis=1)
watch["trade_score"] = watch.apply(lambda r: _extract(r, "trade_score"), axis=1)
watch["rr_net_tp2"] = watch.apply(lambda r: _extract(r, "rr_net_tp2"), axis=1)
watch["data_quality"] = watch.apply(lambda r: (_extract(r, "data_quality", {}) or {}).get("status", "N/D"), axis=1)
watch["regime"] = watch.apply(lambda r: (_extract(r, "market_regime", {}) or {}).get("state", "N/D"), axis=1)
watch["paper_tier"] = watch.apply(_paper_tier, axis=1)
watch["safety_label"] = watch.apply(_safety_label, axis=1)
watch["portfolio_gate"] = watch.apply(_portfolio_status, axis=1)
watch["gate_result"] = watch.apply(lambda r: _failed_text(_details(r)), axis=1)

rank = {"PAPER_OPEN": 0, "CONFIRMED": 1, "PRE_BUY": 2, "NEAR_SETUP": 3, "WATCH": 4, "BLOCKED_DATA": 8, "BENCHMARK": 9}
watch["_rank"] = watch.get("status", pd.Series(index=watch.index, dtype=object)).fillna("").astype(str).str.upper().map(rank).fillna(7)
watch = watch.sort_values(["_rank", "trade_score", "strategy_score"], ascending=[True, False, False])

active_states = ["PAPER_OPEN", "CONFIRMED", "PRE_BUY", "NEAR_SETUP"]
active = watch[watch["status"].fillna("").astype(str).str.upper().isin(active_states)].copy()
raw_view = active if not active.empty else watch.head(10).copy()
# Decision cards are ticker-centric: keep only the best-ranked strategy row per symbol.
view = raw_view.drop_duplicates(subset=["symbol"], keep="first").copy()
watch = watch.drop(columns="_rank")

open_paper = positions.copy()
if not positions.empty and "status" in positions:
    open_paper = positions[positions["status"].fillna("").astype(str).str.upper().isin(["OPEN", "TP1_HIT"])]

k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("Candidates", len(view))
k2.metric("PAPER OPEN", int((watch["status"].astype(str).str.upper() == "PAPER_OPEN").sum()))
k3.metric("CONFIRMED", int((watch["status"].astype(str).str.upper() == "CONFIRMED").sum()))
k4.metric("PRE-BUY", int((watch["status"].astype(str).str.upper() == "PRE_BUY").sum()))
k5.metric("Data Quality RED", int((watch["data_quality"].astype(str).str.upper() == "RED").sum()))
k6.metric("Open Paper Positions", len(open_paper))

st.info(
    "PAPER OPEN follows the Laboratory research policy A/B/C. The strict 75/75, R/R 2.00 and CONFIRMED checks below are a reference diagnostic only, not the admission rule for every paper tier."
)

st.markdown("### Best Lab Opportunity")
best = view.iloc[0]
with st.container(border=True):
    st.markdown(f'<div class="candidate-title" style="font-size:1.22rem">{candidate_title(best.get("symbol"))}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="candidate-state">{fmt_status(best.get("status"))} · {fmt_strategy(best.get("strategy"))}</div>', unsafe_allow_html=True)
    st.caption(f"Paper Tier: {_paper_tier(best)} · Safety: {_safety_label(best)}")

    c1, c2, c3, c4 = st.columns(4, gap="small")
    c1.metric("Strategy Score", _score_with_reference(best.get("strategy_score"), STRICT_STRATEGY_REFERENCE))
    c2.metric("Trade Score", _score_with_reference(best.get("trade_score"), STRICT_TRADE_REFERENCE))
    c3.metric("Portfolio Gate", _portfolio_status(best))
    c4.metric("Net R/R TP2", _rr_with_reference(best.get("rr_net_tp2")))

    passed, total, missing_requirements = _strict_reference_readiness(best)
    st.progress(passed / total, text=f"Strict Reference Readiness: {passed}/{total} checks passed")
    if missing_requirements:
        st.caption("Strict reference missing: " + " · ".join(missing_requirements))
    else:
        st.caption("All strict reference checks passed. Actual paper admission still follows the persisted A/B/C policy and portfolio gate.")

    a, b, c, d = st.columns(4, gap="small")
    trigger = fmt_trigger(best.get("trigger"))
    with a:
        st.caption("Trigger (strict reference expects CONFIRMED)")
        st.markdown(f'<span class="trigger-badge {trigger_class(trigger)}">{trigger}</span>', unsafe_allow_html=True)
    b.write(f"**Data Quality:** {fmt_quality(best.get('data_quality', 'N/D'))}")
    c.write(f"**Regime:** {fmt_regime(best.get('regime', 'N/D'))}")
    d.write(f"**Diagnostics:** {best.get('gate_result', 'N/D')}")

    x1, x2, x3, x4 = st.columns(4, gap="small")
    x1.write(f"**Entry:** {fmt_money(best.get('entry'))}")
    x2.write(f"**Max Buy:** {fmt_money(best.get('max_buy'))}")
    x3.write(f"**Stop:** {fmt_money(best.get('stop'))}")
    x4.write(f"**TP2:** {fmt_money(best.get('tp2'))}")
    details = _details(best)
    st.caption(
        f"Risk-based Qty: {fmt_qty(details.get('qty'))} · Capital: {fmt_money(details.get('capital'))} · "
        f"Position Cap: {fmt_money(details.get('max_position_policy'))} · Estimated Max Loss: {fmt_money(details.get('loss_max'))} · "
        f"Earnings: {details.get('earnings_date', 'N/D')} · Execution Model: {details.get('execution_cost_model', 'N/D')}"
    )

if len(view) > 1:
    st.markdown("### Other Candidates")
    cols = st.columns(2, gap="small")
    for i, (_, row) in enumerate(view.iloc[1:9].iterrows()):
        with cols[i % 2]:
            with st.container(border=True):
                st.markdown(f'<div class="candidate-title">{candidate_title(row.get("symbol"))}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="candidate-state">{fmt_status(row.get("status"))} · {fmt_strategy(row.get("strategy"))}</div>', unsafe_allow_html=True)
                st.caption(f"Paper Tier: {_paper_tier(row)} · Safety: {_safety_label(row)}")
                x1, x2, x3 = st.columns(3, gap="small")
                x1.metric("Strategy", _score_with_reference(row.get("strategy_score"), STRICT_STRATEGY_REFERENCE))
                x2.metric("Trade", _score_with_reference(row.get("trade_score"), STRICT_TRADE_REFERENCE))
                x3.metric("Portfolio", _portfolio_status(row))
                passed, total, missing_requirements = _strict_reference_readiness(row)
                st.caption(
                    f"Strict ref {passed}/{total} · DQ {fmt_quality(row.get('data_quality', 'N/D'))} · "
                    f"R/R {fmt_rr(row.get('rr_net_tp2'))} · Diagnostics {row.get('gate_result', 'PASS')}"
                )
                if missing_requirements:
                    st.caption("Strict ref missing: " + " · ".join(missing_requirements))
                st.markdown(
                    f'<div class="candidate-detail"><b>Entry / Max Buy:</b> {fmt_money(row.get("entry"))} / {fmt_money(row.get("max_buy"))}<br>'
                    f'<b>Stop:</b> {fmt_money(row.get("stop"))} · <b>TP2:</b> {fmt_money(row.get("tp2"))}</div>',
                    unsafe_allow_html=True,
                )

with st.expander("Full Operational Funnel", expanded=False):
    display = watch.copy()
    if "symbol" in display:
        display.insert(display.columns.get_loc("symbol") + 1, "azienda", display["symbol"].map(company_name))
    for col in ["price", "entry", "max_buy", "stop", "tp1", "tp2", "alert_price"]:
        if col in display:
            display[col] = display[col].map(fmt_money)
    if "distance_to_entry_pct" in display:
        display["distance_to_entry_pct"] = display["distance_to_entry_pct"].map(fmt_pct)
    for col in ["strategy_score", "trade_score"]:
        if col in display:
            display[col] = display[col].map(fmt_score)
    if "rr_net_tp2" in display:
        display["rr_net_tp2"] = display["rr_net_tp2"].map(fmt_rr)
    preferred = [
        "symbol", "azienda", "strategy", "status", "paper_tier", "safety_label",
        "strategy_score", "trade_score", "portfolio_gate", "data_quality", "regime", "gate_result",
        "trigger", "price", "entry", "max_buy", "stop", "tp1", "tp2", "rr_net_tp2",
        "alert_type", "alert_price", "distance_to_entry_pct", "signal_date", "last_seen_at",
    ]
    cols = [c for c in preferred if c in display.columns]
    st.dataframe(localize_table(display[cols]), use_container_width=True, hide_index=True)

st.caption(
    "Laboratory research policy: Tier A/B/C determines paper eligibility; Tier C is research-only/non-operational. "
    "The strict 75/75, R/R ≥2.00 and CONFIRMED checks shown above are diagnostics and must not be confused with the A/B/C admission policy."
)
