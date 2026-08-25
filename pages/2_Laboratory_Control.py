from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from typing import Any

import pandas as pd
import streamlit as st
import yfinance as yf

from common_utility.lab_dashboard_metrics import (
    closed_net_pnl,
    estimated_round_trip_cost,
    gross_price_pnl,
    gross_price_return_pct,
    open_net_pnl,
    open_trade_state,
)

try:
    from dashboard import data_access
except ModuleNotFoundError:
    import dashboard.data_access as data_access

st.set_page_config(page_title="Laboratory Dashboard", page_icon="🔬", layout="wide")
COMMISSION = 9.90
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


def n(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except Exception:
        return None


def session_of(row: dict[str, Any]) -> str | None:
    value = row.get("signal_date") or row.get("source_signal_date") or row.get("created_at") or row.get("opened_at")
    return str(value)[:10] if value else None


def tier_of(row: dict[str, Any]) -> str | None:
    d = j(row.get("details"))
    policy = j(d.get("paper_policy"))
    value = d.get("paper_tier") or policy.get("tier")
    return str(value) if value else None


def strategy_label(value: Any) -> str:
    raw = str(value or "N/D")
    labels = {
        "cross_sectional_momentum": "Cross-Sectional Momentum",
        "defensive_low_vol": "Defensive Low Vol",
        "defensive_low_vol_quality": "Defensive Low Vol · Quality",
        "short_term_reversal": "Short-Term Reversal",
        "short_term_reversal_rsi35": "Short-Term Reversal · RSI 35",
        "short_term_reversal_rsi45": "Short-Term Reversal · RSI 45",
        "trend_continuation": "Trend Continuation",
    }
    return labels.get(raw, raw.replace("_", " ").title())


def _extract_close(data: pd.DataFrame, ticker: str, count: int) -> float | None:
    try:
        if data is None or data.empty:
            return None
        series = data["Close"].dropna() if count == 1 else data[(ticker, "Close")].dropna()
        return float(series.iloc[-1]) if not series.empty else None
    except Exception:
        return None


@st.cache_data(ttl=60, show_spinner=False)
def market_prices(tickers: tuple[str, ...]) -> dict[str, tuple[float, str]]:
    if not tickers:
        return {}
    out: dict[str, tuple[float, str]] = {}
    try:
        intraday = yf.download(list(tickers), period="1d", interval="1m", auto_adjust=False, progress=False, group_by="ticker", threads=True)
        for ticker in tickers:
            px = _extract_close(intraday, ticker, len(tickers))
            if px is not None:
                out[ticker] = (px, "YAHOO 1M")
    except Exception:
        pass
    missing = tuple(t for t in tickers if t not in out)
    if missing:
        try:
            daily = yf.download(list(missing), period="5d", interval="1d", auto_adjust=False, progress=False, group_by="ticker", threads=True)
            for ticker in missing:
                px = _extract_close(daily, ticker, len(missing))
                if px is not None:
                    out[ticker] = (px, "YAHOO CLOSE")
        except Exception:
            pass
    return out


def effective_price(row: dict[str, Any], live: dict[str, tuple[float, str]]) -> tuple[float | None, str]:
    status = str(row.get("status") or "").upper()
    if status == "CLOSED":
        px = n(row.get("exit_price")) or n(row.get("last_price"))
        return px, "CLOSED"
    ticker = str(row.get("symbol") or "").upper()
    quote = live.get(ticker)
    if quote is not None:
        return quote
    db = n(row.get("last_price"))
    if db is not None:
        return db, "DB FALLBACK"
    return n(row.get("entry_price")), "ENTRY FALLBACK"


def closed_pnl(row: dict[str, Any]) -> float | None:
    return closed_net_pnl(
        row.get("entry_price"),
        n(row.get("exit_price")) or n(row.get("last_price")),
        row.get("qty"),
        COMMISSION,
        SLIPPAGE_BPS,
    )


def closed_return(row: dict[str, Any], pnl: float | None) -> float | None:
    entry = n(row.get("entry_price"))
    qty = n(row.get("qty"))
    if pnl is None or not entry or not qty:
        return n(row.get("return_pct"))
    return pnl / (entry * qty) * 100.0


def fmt(frame: pd.DataFrame):
    formats: dict[str, str] = {}
    money = {
        "Entry $", "Current $", "Stop $", "TP1 $", "TP2 $", "Open Net P&L $",
        "Open Price P&L $", "Closed Net P&L $", "Est. Round-Trip Cost $",
    }
    for c in frame.columns:
        if c in money:
            formats[c] = "{:.2f}"
        elif "%" in c or c == "Conversion":
            formats[c] = "{:.2f}%"
        elif pd.api.types.is_float_dtype(frame[c]):
            formats[c] = "{:.2f}"
    styler = frame.style.format(formats, na_rep="-")
    pnl_cols = [c for c in ["Price Move %", "Open Net P&L $", "Closed Net P&L $"] if c in frame.columns]
    if pnl_cols:
        def color_value(v: Any) -> str:
            value = n(v)
            if value is None:
                return ""
            if value > 0:
                return "color:#15803d;font-weight:700;"
            if value < 0:
                return "color:#dc2626;font-weight:700;"
            return ""
        styler = styler.map(color_value, subset=pnl_cols)
    return styler


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
            if isinstance(check, dict):
                for gate in check.get("failed", []) or []:
                    out.append({"family": "DATA" if str(gate).startswith("DATA_") else "POLICY", "policy": "PAPER_POLICY", "tier": str(tier), "gate": str(gate)})
    strict = j(d.get("strict_trade_eligibility") or d.get("trade_eligibility"))
    for gate in strict.get("failed", []) or []:
        out.append({"family": "DATA" if "DATA" in str(gate) else "POLICY", "policy": "LEGACY_STRICT", "tier": "LEGACY", "gate": str(gate)})
    return out


@st.cache_data(ttl=60, show_spinner=False)
def load_data():
    return {
        "signals": data_access.lab_paper_signals(10000),
        "positions": data_access.lab_paper_positions(10000),
        "outcomes": data_access.lab_signal_outcomes(20000),
    }


require_access()
st.title("🔬 Laboratory Dashboard")
st.caption("Research control room: strategy activity, paper positions and evidence. PAPER only; no real broker orders are generated here.")

with st.sidebar:
    st.markdown("## Guide · Laboratory")
    with st.expander("What this page shows", expanded=True):
        st.markdown("Il Laboratory è il campo di prova del Trading Engine. Testa strategie e regole con capitale virtuale; non decide il portafoglio reale.")
    with st.expander("Tier A / B / C"):
        st.markdown("**A** · quasi Production  \
**B** · experimental  \
**C** · RESEARCH ONLY · non operativo")
    with st.expander("Costs & open P&L"):
        st.markdown("Open Net P&L sottrae solo i costi di entrata già sostenuti. Il costo round-trip completo resta una stima separata. Closed Net P&L include entrata + uscita.")
    with st.expander("Data Quality & Gates"):
        st.markdown("**RED** = veto. **YELLOW** = ammesso solo B/C, mai A. DATA GATES riguardano i dati; POLICY GATES riguardano score, trigger, R/R, Max Buy, earnings e altre regole.")

try:
    data = load_data()
except Exception as exc:
    st.error(f"Impossibile leggere i dati Laboratory: {type(exc).__name__}: {exc}")
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
open_pos = [p for p in positions if str(p.get("status") or "").upper() in {"OPEN", "TP1_HIT"}]
closed_pos = [p for p in positions if str(p.get("status") or "").upper() == "CLOSED"]
open_symbols = tuple(sorted({str(p.get("symbol") or "").upper() for p in open_pos if p.get("symbol")}))
live = market_prices(open_symbols)
cur_tier = Counter(tier_of(r) for r in cur if tier_of(r))
cur_status = Counter(str(r.get("status") or "N/D").upper() for r in cur)

open_net_values: list[float] = []
for p in open_pos:
    px, _ = effective_price(p, live)
    value = open_net_pnl(p.get("entry_price"), px, p.get("qty"), COMMISSION, SLIPPAGE_BPS)
    if value is not None:
        open_net_values.append(value)
open_total = sum(open_net_values)

closed_pnls = [closed_pnl(p) for p in closed_pos]
closed_total = sum(x for x in closed_pnls if x is not None)
wins = sum(1 for x in closed_pnls if x is not None and x > 0)
losses = sum(1 for x in closed_pnls if x is not None and x < 0)
winrate = 100 * wins / len(closed_pos) if closed_pos else None

if latest:
    st.success(f"LAB ACTIVE · Last session {latest} · {len(cur)} signals · {len(cur_pos)} new paper trades")
else:
    st.warning("No Laboratory session available.")

c = st.columns(6)
c[0].metric("Signals Last Run", len(cur))
c[1].metric("New Paper Trades", len(cur_pos))
c[2].metric("Open Positions", len(open_pos))
c[3].metric("Open Net P&L", f"${open_total:,.2f}")
c[4].metric("Closed Trades", len(closed_pos))
c[5].metric("Win Rate", f"{winrate:.2f}%" if winrate is not None else "N/D")

t = st.columns(4)
t[0].metric("Tier A · Production Candidate", cur_tier.get("A", 0))
t[1].metric("Tier B · Experimental", cur_tier.get("B", 0))
t[2].metric("Tier C · Research Only", cur_tier.get("C", 0))
t[3].metric("Data Reject", cur_status.get("BLOCKED_DATA", 0))

st.subheader("Strategy Performance")
strategies = sorted({str(r.get("strategy")) for r in signals if r.get("strategy")} | {str(p.get("strategy")) for p in positions if p.get("strategy")})
summary: list[dict[str, Any]] = []
for strategy in strategies:
    sig = [r for r in cur if str(r.get("strategy")) == strategy]
    pp = [p for p in positions if str(p.get("strategy")) == strategy]
    op = [p for p in pp if str(p.get("status") or "").upper() in {"OPEN", "TP1_HIT"}]
    cp = [p for p in pp if str(p.get("status") or "").upper() == "CLOSED"]
    opnl = 0.0
    for p in op:
        px, _ = effective_price(p, live)
        value = open_net_pnl(p.get("entry_price"), px, p.get("qty"), COMMISSION, SLIPPAGE_BPS)
        opnl += value or 0.0
    cpnl = [closed_pnl(p) for p in cp]
    ctotal = sum(x for x in cpnl if x is not None)
    cw = sum(1 for x in cpnl if x is not None and x > 0)
    cl = sum(1 for x in cpnl if x is not None and x < 0)
    strategy_wr = 100.0 * cw / len(cp) if cp else None
    summary.append({
        "Strategy": strategy_label(strategy),
        "Signals": len(sig),
        "Open": len(op),
        "Closed": len(cp),
        "Wins": cw,
        "Losses": cl,
        "Win Rate %": strategy_wr,
        "Open Net P&L $": opnl,
        "Closed Net P&L $": ctotal,
        "Status": "● ACTIVE" if sig or op else "○ INACTIVE",
    })
summary_df = pd.DataFrame(summary)
st.dataframe(fmt(summary_df), width="stretch", hide_index=True)

st.subheader("Active Paper Positions")
open_rows: list[dict[str, Any]] = []
cost_rows: list[dict[str, Any]] = []
for p in open_pos:
    px, source = effective_price(p, live)
    entry = n(p.get("entry_price"))
    qty = n(p.get("qty"))
    price_pnl = gross_price_pnl(entry, px, qty)
    move = gross_price_return_pct(entry, px)
    net_open = open_net_pnl(entry, px, qty, COMMISSION, SLIPPAGE_BPS)
    est_cost = estimated_round_trip_cost(entry, px, qty, COMMISSION, SLIPPAGE_BPS)
    tier = tier_of(p) or j(p.get("details")).get("paper_tier") or "N/D"
    state = open_trade_state(entry, px, qty, p.get("opened_at") or p.get("created_at"))
    open_rows.append({
        "Ticker": p.get("symbol"),
        "Strategy": strategy_label(p.get("strategy")),
        "Tier": f"C 🔬" if str(tier) == "C" else tier,
        "Entry $": entry,
        "Current $": px,
        "Price Move %": move,
        "Open Net P&L $": net_open,
        "Stop $": n(p.get("stop_current")) or n(p.get("stop_initial")),
        "TP1 $": n(p.get("tp1")),
        "TP2 $": n(p.get("tp2")),
        "Status": state,
    })
    cost_rows.append({
        "Ticker": p.get("symbol"),
        "Strategy": strategy_label(p.get("strategy")),
        "Source": source,
        "Open Price P&L $": price_pnl,
        "Open Net P&L $": net_open,
        "Est. Round-Trip Cost $": est_cost,
        "Opened At": p.get("opened_at") or p.get("created_at"),
    })

if open_rows:
    open_df = pd.DataFrame(open_rows)
    st.dataframe(fmt(open_df), width="stretch", hide_index=True)
    st.caption("Status is based on the underlying price move. Trades inside the estimated cost band during the first 2 days are shown as OPEN · TOO EARLY, not as an immediate loss verdict.")
    with st.expander("ℹ️ Cost & price-source details", expanded=False):
        st.dataframe(fmt(pd.DataFrame(cost_rows)), width="stretch", hide_index=True)
        st.caption("Estimated Round-Trip Cost is shown for context only. It is not pre-booked as a future exit loss in Open Net P&L.")
else:
    st.info("No open paper positions.")

st.subheader("Closed Trades · Realized Evidence")
cc = st.columns(5)
cc[0].metric("Closed", len(closed_pos))
cc[1].metric("Wins", wins)
cc[2].metric("Losses", losses)
cc[3].metric("Closed Net P&L", f"${closed_total:,.2f}")
cc[4].metric("Win Rate", f"{winrate:.2f}%" if winrate is not None else "N/D")
closed_rows: list[dict[str, Any]] = []
for p in closed_pos:
    pnlv = closed_pnl(p)
    ret = closed_return(p, pnlv)
    tier = tier_of(p) or j(p.get("details")).get("paper_tier") or "N/D"
    closed_rows.append({
        "Ticker": p.get("symbol"),
        "Strategy": strategy_label(p.get("strategy")),
        "Tier": f"C 🔬" if str(tier) == "C" else tier,
        "Entry $": n(p.get("entry_price")),
        "Current $": n(p.get("exit_price")) or n(p.get("last_price")),
        "Closed Net P&L $": pnlv,
        "Performance %": ret,
        "Status": "🟢 PROFIT" if pnlv is not None and pnlv > 0 else ("🔴 LOSS" if pnlv is not None and pnlv < 0 else "⚪ N/D"),
        "Exit Reason": p.get("exit_reason"),
    })
if closed_rows:
    st.dataframe(fmt(pd.DataFrame(closed_rows)), width="stretch", hide_index=True)
else:
    st.info("No closed paper trades yet. Open P&L alone is not enough evidence to judge a strategy.")

with st.expander("Diagnostics · Gate Analysis", expanded=False):
    st.markdown("Use this section when the Laboratory opens too few/many trades or behaves unexpectedly.")
    counter = Counter()
    for row in cur:
        strategy = str(row.get("strategy") or "N/D")
        for item in gate_rows(row):
            counter[(strategy, item["family"], item["policy"], item["tier"], item["gate"])] += 1
    gates = [
        {
            "Strategy": strategy_label(k[0]),
            "Family": k[1],
            "Policy": k[2],
            "Tier": k[3],
            "Blocking Gate": k[4],
            "Count": v,
        }
        for k, v in counter.most_common()
    ]
    if gates:
        st.dataframe(pd.DataFrame(gates), width="stretch", hide_index=True)
    else:
        st.info("No gate details available.")

    st.markdown("#### Shadow Outcomes")
    obs = Counter()
    for row in outcomes:
        group = j(row.get("details")).get("observation_group")
        if group:
            obs[str(group)] += 1
    if obs:
        st.dataframe(pd.DataFrame([{"Group": k, "Observations": v} for k, v in obs.items()]), width="stretch", hide_index=True)
    else:
        st.info("No shadow outcomes available.")

    st.markdown("#### Latest Session vs Previous")
    prev_pos = [p for p in positions if session_of(p) == previous] if previous else []
    prev_tier = Counter(tier_of(r) for r in prev if tier_of(r))
    st.dataframe(pd.DataFrame([
        {"Metric": "Signals", "Latest": len(cur), "Previous": len(prev)},
        {"Metric": "Paper Open", "Latest": len(cur_pos), "Previous": len(prev_pos)},
        {"Metric": "Tier A", "Latest": cur_tier.get("A", 0), "Previous": prev_tier.get("A", 0)},
        {"Metric": "Tier B", "Latest": cur_tier.get("B", 0), "Previous": prev_tier.get("B", 0)},
        {"Metric": "Tier C", "Latest": cur_tier.get("C", 0), "Previous": prev_tier.get("C", 0)},
    ]), width="stretch", hide_index=True)

st.caption(
    f"OPEN prices: Yahoo 1m → Yahoo close → DB → Entry · Entry cost: $9.90 + {SLIPPAGE_BPS:.0f} bps · "
    f"Closed round-trip cost: $9.90/side + {SLIPPAGE_BPS:.0f} bps/side · Updated {datetime.now().astimezone().strftime('%d/%m/%Y %H:%M:%S %Z')}"
)
