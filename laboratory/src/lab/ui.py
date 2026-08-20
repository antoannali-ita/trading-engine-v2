from __future__ import annotations

import html
from typing import Any

import pandas as pd
import streamlit as st

UI_BUILD = "2026.08.20-2358"
COPYRIGHT_TEXT = "Questo sito è stato prodotto da Antonio Larocca · Tutti i diritti riservati."

COMPANY_NAMES = {
    "AAPL": "Apple Inc.", "ADBE": "Adobe Inc.", "AMZN": "Amazon.com Inc.", "AMD": "Advanced Micro Devices Inc.",
    "ASML": "ASML Holding N.V.", "AVGO": "Broadcom Inc.", "AXP": "American Express Co.", "BKNG": "Booking Holdings Inc.",
    "BUD": "Anheuser-Busch InBev", "CAT": "Caterpillar Inc.", "COST": "Costco Wholesale Corp.", "CRM": "Salesforce Inc.",
    "CSCO": "Cisco Systems Inc.", "CVS": "CVS Health Corp.", "CVX": "Chevron Corp.", "FTNT": "Fortinet Inc.",
    "GE": "GE Aerospace", "GOOG": "Alphabet Inc.", "GOOGL": "Alphabet Inc.", "GS": "Goldman Sachs Group Inc.",
    "HD": "Home Depot Inc.", "JPM": "JPMorgan Chase & Co.", "LIN": "Linde plc", "LLY": "Eli Lilly and Co.",
    "MA": "Mastercard Inc.", "META": "Meta Platforms Inc.", "MSFT": "Microsoft Corp.", "MUFG": "Mitsubishi UFJ Financial Group",
    "NFLX": "Netflix Inc.", "NVDA": "NVIDIA Corp.", "NVO": "Novo Nordisk A/S", "ORCL": "Oracle Corp.",
    "PANW": "Palo Alto Networks Inc.", "PGR": "Progressive Corp.", "QQQ": "Invesco QQQ Trust", "RTX": "RTX Corp.",
    "SPY": "SPDR S&P 500 ETF Trust", "TJX": "TJX Companies Inc.", "TSM": "Taiwan Semiconductor Manufacturing Co.",
    "UBER": "Uber Technologies Inc.", "UNH": "UnitedHealth Group Inc.", "V": "Visa Inc.", "WMT": "Walmart Inc.", "XOM": "Exxon Mobil Corp.",
}

STRATEGY_INFO = {
    "trend_continuation": {"label": "Trend Continuation", "summary": "Cerca titoli già in trend positivo e prova a entrare su continuazione o pullback ordinati, evitando prezzi troppo estesi.", "signals": ["Price vs SMA50/SMA200", "Pullback to SMA50", "ATR", "60d Momentum", "Relative Volume", "20d Breakout"], "best_for": "Trend direzionali puliti e leadership persistente.", "weak_when": "Mercato laterale, falsi breakout, inversioni rapide."},
    "cross_sectional_momentum": {"label": "Cross-Sectional Momentum", "summary": "Premia i titoli più forti rispetto all'universo. La versione v2 dovrà usare una vera classifica cross-sectional sullo stesso giorno.", "signals": ["20d Return", "60d Return", "120d Return", "Cross-Sectional Rank"], "best_for": "Regimi risk-on con leadership stabile.", "weak_when": "Rotazioni violente e mean reversion improvvisa."},
    "short_term_reversal": {"label": "Short-Term Reversal", "summary": "Cerca eccessi ribassisti di breve periodo dentro una struttura di fondo ancora accettabile, puntando a un rimbalzo controllato.", "signals": ["RSI14", "Distance from SMA20", "ATR", "Long-Term Trend", "Daily Stabilization"], "best_for": "Sell-off tecnici non accompagnati da rottura strutturale.", "weak_when": "Crolli fondamentali, gap negativi, downtrend persistenti."},
    "defensive_low_vol_quality": {"label": "Defensive Low Vol", "summary": "Favorisce titoli meno volatili, sopra la media lunga e con momentum ancora positivo.", "signals": ["20d Volatility", "SMA200", "ATR%", "60d Momentum"], "best_for": "Fasi difensive o mercati incerti con preferenza per stabilità.", "weak_when": "Bull market molto aggressivi dominati da beta elevato."},
    "pead": {"label": "PEAD", "summary": "Post-Earnings Announcement Drift con dati point-in-time.", "signals": ["EPS Surprise", "Revenue Surprise", "Analyst Revisions", "Event Age"], "best_for": "Earnings con sorpresa credibile e revisioni coerenti.", "weak_when": "Dati evento incompleti."},
    "event_driven_mean_reversion": {"label": "Event Mean Reversion", "summary": "Cerca eccessi di prezzo dopo eventi non binari.", "signals": ["Event Return", "Volume Z-Score", "Day-1 Reaction"], "best_for": "Shock temporanei.", "weak_when": "Eventi binari o strutturali."},
    "quality_value_rerating": {"label": "Quality Value Rerating", "summary": "Combina qualità, crescita, leva e valutazione.", "signals": ["FCF Yield", "ROIC", "Revenue Growth", "EPS Growth", "Net Debt/EBITDA"], "best_for": "Rerating di società solide.", "weak_when": "Value trap."},
    "macro_intermarket": {"label": "Macro Intermarket", "summary": "Integra trend e impulsi macro.", "signals": ["Trend Score", "Rates Impulse", "Credit Impulse", "Commodity Impulse", "USD Impulse"], "best_for": "Regimi macro persistenti.", "weak_when": "Transizioni rapide."},
}

STATUS_LABELS = {
    "PAPER_OPEN": "PAPER OPEN", "OPEN": "OPEN", "TP1_HIT": "TP1 HIT", "PRE_BUY": "PRE-BUY", "PRE_BUY_HIGH": "PRE-BUY HIGH",
    "NEAR_SETUP": "NEAR SETUP", "WATCH": "WATCH", "CONFIRMED": "CONFIRMED", "WAITING": "WAITING", "BLOCKED": "BLOCKED",
    "BLOCKED_DATA": "BLOCKED DATA", "REJECTED": "REJECTED", "PROMOTABLE": "PROMOTABLE", "CANDIDATE": "CANDIDATE",
    "BENCHMARK": "BENCHMARK", "SHADOW_BUY": "SHADOW BUY", "BUY NOW": "BUY NOW", "BUY LIMIT": "BUY LIMIT", "AVOID": "AVOID",
}
REGIME_LABELS = {"BULL_QUIET": "BULL QUIET", "BULL_VOLATILE": "BULL VOLATILE", "RANGE_NEUTRAL": "RANGE / NEUTRAL", "NEUTRAL": "NEUTRAL", "BEAR_HIGH_VOL": "BEAR / HIGH VOL", "BEAR": "BEAR"}
QUALITY_LABELS = {"GREEN": "GREEN", "YELLOW": "YELLOW", "RED": "RED"}
COLUMN_LABELS = {
    "created_at": "Created At", "last_seen_at": "Last Seen", "last_checked_date": "Last Checked", "signal_date": "Signal Date", "source_signal_date": "Source Signal Date", "opened_at": "Opened At",
    "symbol": "Ticker", "ticker": "Ticker", "azienda": "Company", "company_name_display": "Company", "market": "Market", "horizon": "Horizon", "strategy": "Strategy", "parent_strategy": "Parent Strategy",
    "status": "Status", "source_signal_status": "Signal Status", "trade_status": "Trade Status", "decision": "Decision", "score": "Score", "score_total": "Total Score", "strategy_score": "Strategy Score", "trade_score": "Trade Score",
    "portfolio_fit": "Portfolio Fit", "portfolio_fit_score": "Portfolio Fit", "trigger": "Trigger", "setup": "Setup", "price": "Price", "entry": "Entry", "entry_price": "Entry Price", "proposed_entry": "Proposed Entry",
    "buy_range_low": "Buy Range Low", "buy_range_high": "Buy Range High", "max_buy": "Max Buy", "stop": "Stop", "stop_initial": "Initial Stop", "stop_current": "Current Stop", "proposed_stop": "Proposed Stop",
    "tp1": "TP1", "tp2": "TP2", "proposed_target": "Proposed Target", "last_price": "Last Price", "exit_price": "Exit Price", "qty": "Qty", "capital": "Capital", "gross_pnl": "Gross P&L", "net_pnl": "Net P&L",
    "return_pct": "Return %", "win_rate": "Win Rate", "profit_factor": "Profit Factor", "trades": "Trades", "rr_net_tp1": "Net R/R TP1", "rr_net_tp2": "Net R/R TP2", "distance_to_entry_pct": "Distance to Entry",
    "alert_type": "Alert Type", "alert_price": "Alert Price", "reason": "Reason", "data_quality": "Data Quality", "regime": "Regime", "regime_state": "Regime", "gate_result": "Gate Result",
    "ret_d1": "Return D+1", "ret_d3": "Return D+3", "ret_d5": "Return D+5", "ret_d10": "Return D+10", "ret_d20": "Return D+20", "ret_d60": "Return D+60", "excess_ret_d20": "Excess Return D+20 vs SPY",
    "mfe_pct": "MFE %", "mae_pct": "MAE %", "mfe_r": "MFE (R)", "mae_r": "MAE (R)", "bars_to_mfe": "Bars to MFE", "bars_to_mae": "Bars to MAE", "block_reasons": "Block Reasons",
    "position_id": "Position ID", "event_type": "Event Type", "old_stop": "Old Stop", "new_stop": "New Stop", "note": "Note", "run_timestamp": "Run Timestamp", "run_id": "Run ID", "engine_version": "Engine Version", "candidates_count": "Candidates",
    "variant_id": "Variant ID", "generation": "Generation", "promoted_to_core": "Promoted to Core", "mutation_reason": "Mutation Reason", "parameters": "Parameters", "notes": "Notes", "entry_score": "Entry Score", "atr_stop_mult": "ATR Stop Multiplier",
    "target_r_multiple": "Target R Multiple", "train_return_pct": "Train Return %", "test_return_pct": "Test Return %", "test_trades": "Test Trades",
}


def _sidebar_navigation() -> None:
    st.sidebar.markdown("## 📈 TRADING 2.0")
    st.sidebar.caption("DECISION · RISK · RESEARCH")
    st.sidebar.page_link("app.py", label="🏠  CONTROL ROOM")
    st.sidebar.markdown("---")
    st.sidebar.caption("CORE")
    st.sidebar.page_link("pages/7_Core_Opportunities.py", label="🎯  BUY / PRE-BUY HIGH")
    st.sidebar.page_link("pages/1_Signals.py", label="📋  CORE SIGNALS")
    st.sidebar.markdown("---")
    st.sidebar.caption("LABORATORY")
    st.sidebar.page_link("pages/5_Action_Center.py", label="⚡  ACTION CENTER")
    st.sidebar.page_link("pages/2_Portfolio.py", label="💼  PAPER PORTFOLIO")
    st.sidebar.page_link("pages/6_Backtest_Research.py", label="🧪  STRATEGY LAB")
    st.sidebar.page_link("pages/3_Laboratory.py", label="📊  SIGNAL OUTCOMES")
    st.sidebar.page_link("pages/4_Engine_Health.py", label="🩺  ENGINE HEALTH")
    st.sidebar.markdown("---")
    st.sidebar.caption(f"UI BUILD {UI_BUILD}")
    st.sidebar.caption("© 2026 Antonio Larocca · Tutti i diritti riservati.")


def apply_theme() -> None:
    st.markdown("""
    <style>
    [data-testid="stSidebarNav"] {display:none;}
    [data-testid="stSidebar"] {border-right:1px solid rgba(128,128,128,.14);}
    [data-testid="stSidebar"] .stPageLink {margin-bottom:.12rem;}
    [data-testid="stSidebar"] .stPageLink a {border-radius:9px;padding:.44rem .58rem;font-weight:700;letter-spacing:.02em;}
    [data-testid="stSidebar"] .stPageLink a:hover {background:rgba(99,102,241,.09);}
    .block-container {padding-top:1.35rem;padding-bottom:5.2rem;max-width:1500px;}
    h1,h2,h3 {letter-spacing:-0.02em;}
    [data-testid="stMetric"] {border:1px solid rgba(128,128,128,.18);border-radius:12px;padding:7px 9px;background:rgba(128,128,128,.035);min-height:66px;}
    [data-testid="stMetricLabel"] {font-weight:600;opacity:.76;font-size:.68rem;}
    [data-testid="stMetricValue"] {font-weight:750;font-size:1.22rem;line-height:1.05;overflow:visible;white-space:normal;}
    .lab-hero {border:1px solid rgba(128,128,128,.18);border-radius:20px;padding:18px 21px;margin-bottom:15px;background:linear-gradient(135deg,rgba(99,102,241,.12),rgba(14,165,233,.05));}
    .lab-eyebrow {font-size:.70rem;letter-spacing:.12em;text-transform:uppercase;opacity:.62;font-weight:700;}.lab-title {font-size:1.75rem;font-weight:800;margin-top:3px;}.lab-subtitle {font-size:.91rem;opacity:.74;margin-top:4px;max-width:900px;}
    .strategy-card {border:1px solid rgba(128,128,128,.18);border-radius:16px;padding:15px;min-height:190px;background:rgba(128,128,128,.035);}.strategy-name {font-size:1rem;font-weight:760;margin-bottom:4px;}.strategy-meta {font-size:.76rem;opacity:.68;margin-bottom:9px;}
    .pill {display:inline-block;padding:3px 8px;border-radius:999px;font-size:.69rem;font-weight:700;margin-right:4px;margin-bottom:4px;background:rgba(99,102,241,.12);}.status-good {background:rgba(34,197,94,.14);}.status-mid {background:rgba(234,179,8,.16);}.status-bad {background:rgba(239,68,68,.13);}.status-na {background:rgba(148,163,184,.16);}
    div[data-testid="stDataFrame"] {border:1px solid rgba(128,128,128,.13);border-radius:12px;overflow:hidden;}.candidate-title {font-size:1.02rem;font-weight:780;margin:0 0 .15rem 0;line-height:1.18;}.company-name {font-size:.76rem;opacity:.66;font-weight:500;margin-left:.2rem;}.candidate-state {font-size:.70rem;opacity:.62;margin:.05rem 0 .45rem 0;text-transform:uppercase;}.candidate-detail {font-size:.74rem;opacity:.80;line-height:1.42;margin-top:.20rem;}
    .trigger-badge {display:inline-block;padding:3px 7px;border-radius:8px;font-size:.70rem;font-weight:800;}.trigger-confirmed {background:rgba(34,197,94,.13);}.trigger-wait {background:rgba(234,179,8,.15);}.trigger-buy {background:rgba(59,130,246,.12);}
    .site-footer {position:fixed;left:0;right:0;bottom:0;z-index:999;padding:.50rem 1rem;text-align:center;font-size:.72rem;opacity:.78;backdrop-filter:blur(10px);background:rgba(250,250,250,.88);border-top:1px solid rgba(128,128,128,.14);}@media (prefers-color-scheme:dark){.site-footer{background:rgba(14,17,23,.88);}}
    </style>
    """, unsafe_allow_html=True)
    st.markdown(f'<div class="site-footer">{html.escape(COPYRIGHT_TEXT)} · © 2026</div>', unsafe_allow_html=True)
    _sidebar_navigation()


def page_header(title: str, subtitle: str, eyebrow: str = "TRADING LAB 2.0") -> None:
    st.markdown(f'<div class="lab-hero"><div class="lab-eyebrow">{html.escape(str(eyebrow))}</div><div class="lab-title">{html.escape(str(title))}</div><div class="lab-subtitle">{html.escape(str(subtitle))}</div></div>', unsafe_allow_html=True)


def _scalar(value: Any) -> Any:
    if value is None: return None
    if isinstance(value, pd.DataFrame): return None if value.empty else _scalar(value.iloc[0, 0])
    if isinstance(value, pd.Series):
        if value.empty: return None
        for item in value.tolist():
            item = _scalar(item)
            if item is None: continue
            try:
                if pd.isna(item): continue
            except Exception: pass
            return item
        return None
    if isinstance(value, (list, tuple)): return _scalar(value[0]) if len(value) else None
    return value


def _number(value: Any) -> float | None:
    scalar = _scalar(value)
    if scalar is None: return None
    try: number = float(scalar)
    except (TypeError, ValueError): return None
    try:
        if pd.isna(number): return None
    except Exception: pass
    return number


def fmt_money(value: Any, symbol: str = "$", decimals: int = 2) -> str:
    number = _number(value); return "N/D" if number is None else f"{symbol}{number:,.{decimals}f}"
def fmt_pct(value: Any, decimals: int = 2) -> str:
    number = _number(value); return "N/D" if number is None else f"{number:.{decimals}f}%"
def fmt_num(value: Any, decimals: int = 2) -> str:
    number = _number(value); return "N/D" if number is None else f"{number:,.{decimals}f}"
def fmt_score(value: Any) -> str: return fmt_num(value, 1)
def fmt_rr(value: Any) -> str:
    number = _number(value); return "N/D" if number is None else f"{number:.2f}"
def fmt_qty(value: Any) -> str:
    number = _number(value); return "N/D" if number is None else f"{int(number)}"
def fmt_status(value: Any) -> str:
    text = "N/D" if value is None else str(value).strip().upper(); return STATUS_LABELS.get(text, text.replace("_", " "))
def fmt_strategy(value: Any) -> str:
    key = "" if value is None else str(value).strip(); return STRATEGY_INFO.get(key, {}).get("label", key.replace("_", " ").strip().title() or "N/D")
def fmt_regime(value: Any) -> str:
    text = "N/D" if value is None else str(value).strip().upper(); return REGIME_LABELS.get(text, text.replace("_", " "))
def fmt_quality(value: Any) -> str:
    text = "N/D" if value is None else str(value).strip().upper(); return QUALITY_LABELS.get(text, text)
def fmt_trigger(value: Any) -> str:
    text = "N/D" if value is None else str(value).strip().upper().replace("_", " "); return {"CONFIRMED":"CONFIRMED","WAITING":"WAITING","WAIT":"WAIT","BUY ZONE":"BUY ZONE","ENTRY REACHED":"ENTRY REACHED","INVALID":"INVALID"}.get(text, text)
def trigger_class(trigger: str) -> str:
    t = str(trigger).upper()
    if "CONFIRMED" in t: return "trigger-confirmed"
    if "BUY" in t or "ENTRY" in t: return "trigger-buy"
    return "trigger-wait"
def company_name(ticker: Any, supplied: Any = None) -> str:
    if supplied is not None:
        text = str(supplied).strip()
        if text and text.lower() not in {"nan", "none", "n/d"}: return text
    key = "" if ticker is None else str(ticker).strip().upper(); return COMPANY_NAMES.get(key, "Company N/D")
def candidate_title(ticker: Any, supplied_company: Any = None) -> str:
    t = "N/D" if ticker is None else str(ticker).strip().upper(); company = company_name(t, supplied_company); return f'{html.escape(t)} <span class="company-name">{html.escape(company)}</span>'
def localize_table(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in ["strategy", "parent_strategy"]:
        if col in out: out[col] = out[col].map(fmt_strategy)
    for col in ["status", "source_signal_status", "trade_status", "decision"]:
        if col in out: out[col] = out[col].map(fmt_status)
    if "trigger" in out: out["trigger"] = out["trigger"].map(fmt_trigger)
    for col in ["regime", "regime_state"]:
        if col in out: out[col] = out[col].map(fmt_regime)
    if "data_quality" in out: out["data_quality"] = out["data_quality"].map(fmt_quality)
    return out.rename(columns={c: COLUMN_LABELS[c] for c in out.columns if c in COLUMN_LABELS})
def strategy_health(row_or_pf: Any, trades: Any = None, ret: Any = None) -> tuple[str, str]:
    if isinstance(row_or_pf, pd.Series):
        trades_n = _number(row_or_pf.get("trades")) or 0; pf = _number(row_or_pf.get("profit_factor")); ret_n = _number(row_or_pf.get("total_return_pct", row_or_pf.get("return_pct")))
    else: pf = _number(row_or_pf); trades_n = _number(trades) or 0; ret_n = _number(ret)
    if trades_n < 5: return "LIMITED DATA", "status-na"
    if pf is not None and pf >= 1.5 and ret_n is not None and ret_n > 0: return "ROBUST V1", "status-good"
    if pf is not None and pf >= 1.0 and ret_n is not None and ret_n >= 0: return "TO VALIDATE", "status-mid"
    return "WEAK", "status-bad"
def render_strategy_card(name: str, results: Any, paper: pd.DataFrame | None = None) -> None:
    info = STRATEGY_INFO.get(name, {"label": fmt_strategy(name), "summary": "N/D", "signals": [], "best_for": "N/D", "weak_when": "N/D"})
    if isinstance(results, dict):
        trades = int(_number(results.get("trades")) or 0); avg_pf = _number(results.get("profit_factor")); avg_ret = _number(results.get("return_pct")); status, cls = strategy_health(avg_pf, trades, avg_ret); paper_count = 0; latest_state = "N/D"
    else:
        r = results[results["strategy"] == name].copy() if isinstance(results, pd.DataFrame) and not results.empty and "strategy" in results else pd.DataFrame(); p = paper[paper["strategy"] == name].copy() if isinstance(paper, pd.DataFrame) and not paper.empty and "strategy" in paper else pd.DataFrame()
        if r.empty: status, cls = "WAITING", "status-na"; avg_pf, avg_ret, trades = None, None, 0
        else:
            trades = int(pd.to_numeric(r.get("trades"), errors="coerce").fillna(0).sum()); avg_pf = pd.to_numeric(r.get("profit_factor"), errors="coerce").replace([float("inf"), float("-inf")], pd.NA).dropna().mean(); avg_ret = pd.to_numeric(r.get("total_return_pct", r.get("return_pct")), errors="coerce").dropna().mean(); status, cls = strategy_health(avg_pf, trades, avg_ret)
        paper_count = len(p); latest_state = fmt_status(p.iloc[0].get("status")) if not p.empty else "N/D"
    signal_text = " · ".join(info.get("signals", [])[:4])
    st.markdown(f'<div class="strategy-card"><div class="strategy-name">{html.escape(info["label"])}</div><div class="strategy-meta"><span class="pill {cls}">{status}</span><span class="pill">Paper {paper_count}</span><span class="pill">{html.escape(str(latest_state))}</span></div><div style="font-size:.84rem;line-height:1.44;opacity:.88">{html.escape(info["summary"])}</div><div style="font-size:.72rem;line-height:1.4;opacity:.64;margin-top:8px">{html.escape(signal_text)}</div><div style="display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin-top:10px;font-size:.72rem"><div><b>Trades</b><br>{trades}</div><div><b>Avg PF</b><br>{fmt_num(avg_pf,2)}</div><div><b>Avg Return</b><br>{fmt_pct(avg_ret)}</div></div><div style="font-size:.71rem;line-height:1.36;opacity:.66;margin-top:9px"><b>Best for:</b> {html.escape(info["best_for"])}<br><b>Weak when:</b> {html.escape(info["weak_when"])}</div></div>', unsafe_allow_html=True)
