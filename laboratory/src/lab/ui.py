from __future__ import annotations

import html
from typing import Any

import pandas as pd
import streamlit as st


UI_BUILD = "2026.08.20-2246"
COPYRIGHT_TEXT = "Questo sito è stato prodotto da Antonio Larocca · Tutti i diritti riservati."

COMPANY_NAMES = {
    "AAPL": "Apple Inc.",
    "ADBE": "Adobe Inc.",
    "AXP": "American Express Co.",
    "BUD": "Anheuser-Busch InBev",
    "CSCO": "Cisco Systems Inc.",
    "CVS": "CVS Health Corp.",
    "FTNT": "Fortinet Inc.",
    "GOOG": "Alphabet Inc.",
    "GOOGL": "Alphabet Inc.",
    "META": "Meta Platforms Inc.",
    "MSFT": "Microsoft Corp.",
    "MUFG": "Mitsubishi UFJ Financial Group",
    "NVDA": "NVIDIA Corp.",
    "NVO": "Novo Nordisk A/S",
    "PGR": "Progressive Corp.",
    "QQQ": "Invesco QQQ Trust",
    "SPY": "SPDR S&P 500 ETF Trust",
    "TJX": "TJX Companies Inc.",
}

STRATEGY_INFO = {
    "trend_continuation": {
        "label": "Trend Continuation",
        "summary": "Cerca titoli già in trend positivo e prova a entrare su continuazione o pullback ordinati, evitando di inseguire prezzi troppo estesi.",
        "signals": ["Prezzo vs SMA50/SMA200", "Pullback su SMA50", "ATR", "Momentum 60d", "Volume relativo", "Breakout 20d"],
        "best_for": "Trend direzionali puliti e leadership persistente.",
        "weak_when": "Mercato laterale, falsi breakout, inversioni rapide.",
    },
    "cross_sectional_momentum": {
        "label": "Momentum",
        "summary": "Premia i titoli con forza relativa recente. La versione attuale è una ricerca v1 e la vera classifica cross-sectional sull'intero universo va ancora completata.",
        "signals": ["Return 20d", "Return 60d", "Return 120d", "Ranking momentum"],
        "best_for": "Regimi risk-on con leadership stabile.",
        "weak_when": "Rotazioni violente e mean reversion improvvisa.",
    },
    "short_term_reversal": {
        "label": "Short-Term Reversal",
        "summary": "Cerca eccessi ribassisti di breve periodo dentro una struttura di fondo ancora accettabile, puntando a un rimbalzo controllato.",
        "signals": ["RSI14", "Distanza da SMA20", "ATR", "Trend lungo", "Stabilizzazione daily"],
        "best_for": "Sell-off tecnici non accompagnati da rottura strutturale.",
        "weak_when": "Crolli fondamentali, gap negativi, downtrend persistenti.",
    },
    "defensive_low_vol_quality": {
        "label": "Defensive Low Vol",
        "summary": "Favorisce titoli meno volatili, sopra la media lunga e con momentum ancora positivo. Il quality overlay fondamentale completo è previsto in una fase successiva.",
        "signals": ["Volatilità 20d", "SMA200", "ATR%", "Momentum 60d"],
        "best_for": "Fasi difensive o mercati incerti con preferenza per stabilità.",
        "weak_when": "Bull market molto aggressivi dominati da beta elevato.",
    },
    "pead": {
        "label": "PEAD",
        "summary": "Post-Earnings Announcement Drift: cerca la continuazione dopo sorprese trimestrali positive o negative, usando solo dati point-in-time.",
        "signals": ["EPS surprise", "Revenue surprise", "Revisioni analisti", "Età evento", "Reazione post-earnings"],
        "best_for": "Earnings con sorpresa credibile e revisioni coerenti.",
        "weak_when": "Dati evento incompleti o reazioni già completamente assorbite.",
    },
    "event_driven_mean_reversion": {
        "label": "Event Mean Reversion",
        "summary": "Cerca eccessi di prezzo dopo eventi non binari, quando la reazione appare sproporzionata rispetto al normale comportamento del titolo.",
        "signals": ["Event return", "Volume z-score", "Reazione giorno 1", "Filtro eventi binari"],
        "best_for": "Shock temporanei e non strutturali.",
        "weak_when": "Eventi binari o cambiamenti permanenti del business.",
    },
    "quality_value_rerating": {
        "label": "Quality Value Rerating",
        "summary": "Combina qualità economica, crescita, leva e sconto di valutazione per cercare rerating di società solide ma non care.",
        "signals": ["FCF yield", "ROIC", "Revenue growth", "EPS growth", "Net Debt/EBITDA", "Valuation discount"],
        "best_for": "Normalizzazione multipli e miglioramento degli utili.",
        "weak_when": "Value trap e deterioramento strutturale del business.",
    },
    "macro_intermarket": {
        "label": "Macro Intermarket",
        "summary": "Integra trend e impulsi macro per capire quali asset o settori sono coerenti con tassi, credito, commodity e dollaro.",
        "signals": ["Trend score", "Rates impulse", "Credit impulse", "Commodity impulse", "USD impulse", "Macro fit"],
        "best_for": "Regimi macro riconoscibili e persistenti.",
        "weak_when": "Transizioni di regime rapide o segnali macro conflittuali.",
    },
}


def _sidebar_navigation() -> None:
    st.sidebar.markdown("## 📈 TRADING LAB")
    st.sidebar.caption("DECISIONE · RISCHIO · RICERCA")
    st.sidebar.page_link("app.py", label="🏠  CONTROL ROOM")
    st.sidebar.page_link("pages/1_Signals.py", label="🎯  OPPORTUNITÀ")
    st.sidebar.page_link("pages/5_Action_Center.py", label="⚡  ACTION CENTER")
    st.sidebar.page_link("pages/2_Portfolio.py", label="💼  PORTAFOGLIO")
    st.sidebar.markdown("---")
    st.sidebar.caption("ANALISI & RICERCA")
    st.sidebar.page_link("pages/6_Backtest_Research.py", label="🧪  STRATEGY LAB")
    st.sidebar.page_link("pages/3_Laboratory.py", label="📊  SIGNAL OUTCOMES")
    st.sidebar.page_link("pages/4_Engine_Health.py", label="🩺  ENGINE HEALTH")
    st.sidebar.markdown("---")
    st.sidebar.caption(f"BUILD {UI_BUILD}")
    st.sidebar.caption("© 2026 Antonio Larocca · Tutti i diritti riservati.")


def apply_theme() -> None:
    st.markdown(
        """
        <style>
        [data-testid="stSidebarNav"] {display:none;}
        [data-testid="stSidebar"] {border-right:1px solid rgba(128,128,128,.14);}
        [data-testid="stSidebar"] .stPageLink {margin-bottom:.12rem;}
        [data-testid="stSidebar"] .stPageLink a {border-radius:9px; padding:.44rem .58rem; font-weight:700; letter-spacing:.02em;}
        [data-testid="stSidebar"] .stPageLink a:hover {background:rgba(99,102,241,.09);}
        .block-container {padding-top:1.35rem; padding-bottom:5.2rem; max-width:1500px;}
        h1, h2, h3 {letter-spacing:-0.02em;}
        [data-testid="stMetric"] {border:1px solid rgba(128,128,128,.18); border-radius:12px; padding:7px 9px; background:rgba(128,128,128,.035); min-height:66px;}
        [data-testid="stMetricLabel"] {font-weight:600; opacity:.76; font-size:.68rem;}
        [data-testid="stMetricValue"] {font-weight:750; font-size:1.22rem; line-height:1.05; overflow:visible; white-space:normal; word-break:normal;}
        .lab-hero {border:1px solid rgba(128,128,128,.18); border-radius:20px; padding:18px 21px; margin-bottom:15px; background:linear-gradient(135deg, rgba(99,102,241,.12), rgba(14,165,233,.05));}
        .lab-eyebrow {font-size:.70rem; letter-spacing:.12em; text-transform:uppercase; opacity:.62; font-weight:700;}
        .lab-title {font-size:1.75rem; font-weight:800; margin-top:3px;}
        .lab-subtitle {font-size:.91rem; opacity:.74; margin-top:4px; max-width:900px;}
        .strategy-card {border:1px solid rgba(128,128,128,.18); border-radius:16px; padding:15px; min-height:190px; background:rgba(128,128,128,.035);}
        .strategy-name {font-size:1rem; font-weight:760; margin-bottom:4px;}
        .strategy-meta {font-size:.76rem; opacity:.68; margin-bottom:9px;}
        .pill {display:inline-block; padding:3px 8px; border-radius:999px; font-size:.69rem; font-weight:700; margin-right:4px; margin-bottom:4px; background:rgba(99,102,241,.12);}
        .status-good {background:rgba(34,197,94,.14);}
        .status-mid {background:rgba(234,179,8,.16);}
        .status-bad {background:rgba(239,68,68,.13);}
        .status-na {background:rgba(148,163,184,.16);}
        div[data-testid="stDataFrame"] {border:1px solid rgba(128,128,128,.13); border-radius:12px; overflow:hidden;}
        .candidate-title {font-size:1.02rem; font-weight:780; margin:0 0 .15rem 0; line-height:1.18;}
        .company-name {font-size:.76rem; opacity:.66; font-weight:500; margin-left:.2rem;}
        .candidate-state {font-size:.70rem; opacity:.62; margin:.05rem 0 .45rem 0; text-transform:uppercase; letter-spacing:.02em;}
        .candidate-detail {font-size:.74rem; opacity:.80; line-height:1.42; margin-top:.20rem;}
        .trigger-badge {display:inline-block; padding:3px 7px; border-radius:8px; font-size:.70rem; font-weight:800; line-height:1.1; white-space:normal;}
        .trigger-confirmed {background:rgba(34,197,94,.13);}
        .trigger-wait {background:rgba(234,179,8,.15);}
        .trigger-buy {background:rgba(59,130,246,.12);}
        .site-footer {position:fixed; left:0; right:0; bottom:0; z-index:999; padding:.50rem 1rem; text-align:center; font-size:.72rem; opacity:.78; backdrop-filter:blur(10px); background:rgba(250,250,250,.88); border-top:1px solid rgba(128,128,128,.14);}
        @media (prefers-color-scheme: dark) {.site-footer {background:rgba(14,17,23,.88);}}
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(f'<div class="site-footer">{html.escape(COPYRIGHT_TEXT)} · © 2026</div>', unsafe_allow_html=True)
    _sidebar_navigation()


def page_header(title: str, subtitle: str, eyebrow: str = "TRADING LAB 2.0") -> None:
    st.markdown(f'<div class="lab-hero"><div class="lab-eyebrow">{html.escape(str(eyebrow))}</div><div class="lab-title">{html.escape(str(title))}</div><div class="lab-subtitle">{html.escape(str(subtitle))}</div></div>', unsafe_allow_html=True)


def _scalar(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, pd.DataFrame):
        if value.empty:
            return None
        return _scalar(value.iloc[0, 0])
    if isinstance(value, pd.Series):
        if value.empty:
            return None
        for item in value.tolist():
            item = _scalar(item)
            if item is None:
                continue
            try:
                if pd.isna(item):
                    continue
            except Exception:
                pass
            return item
        return None
    if isinstance(value, (list, tuple)):
        return _scalar(value[0]) if len(value) else None
    return value


def _number(value: Any) -> float | None:
    scalar = _scalar(value)
    if scalar is None:
        return None
    try:
        number = float(scalar)
    except (TypeError, ValueError):
        return None
    try:
        if pd.isna(number):
            return None
    except Exception:
        return None
    return number


def fmt_money(value: Any, symbol: str = "$", decimals: int = 2) -> str:
    number = _number(value)
    return "N/D" if number is None else f"{symbol}{number:,.{decimals}f}"


def fmt_pct(value: Any, decimals: int = 2) -> str:
    number = _number(value)
    return "N/D" if number is None else f"{number:.{decimals}f}%"


def fmt_num(value: Any, decimals: int = 2) -> str:
    number = _number(value)
    return "N/D" if number is None else f"{number:,.{decimals}f}"


def fmt_score(value: Any) -> str:
    return fmt_num(value, 1)


def fmt_rr(value: Any) -> str:
    number = _number(value)
    return "N/D" if number is None else f"{number:.2f}"


def fmt_qty(value: Any) -> str:
    number = _number(value)
    return "N/D" if number is None else f"{int(number)}"


def fmt_trigger(value: Any) -> str:
    text = "N/D" if value is None else str(value).strip().upper().replace("_", " ")
    mapping = {"CONFIRMED": "CONFERMATO", "WAITING": "ATTENDI", "BUY ZONE": "BUY ZONE", "ENTRY REACHED": "ENTRY RAGGIUNTA"}
    return mapping.get(text, text)


def trigger_class(trigger: str) -> str:
    t = str(trigger).upper()
    if "CONFERMATO" in t or "CONFIRMED" in t:
        return "trigger-confirmed"
    if "BUY" in t or "ENTRY" in t:
        return "trigger-buy"
    return "trigger-wait"


def company_name(ticker: Any, supplied: Any = None) -> str:
    if supplied is not None:
        text = str(supplied).strip()
        if text and text.lower() not in {"nan", "none", "n/d"}:
            return text
    key = "" if ticker is None else str(ticker).strip().upper()
    return COMPANY_NAMES.get(key, "Nome società N/D")


def candidate_title(ticker: Any, supplied_company: Any = None) -> str:
    t = "N/D" if ticker is None else str(ticker).strip().upper()
    company = company_name(t, supplied_company)
    return f'{html.escape(t)} <span class="company-name">{html.escape(company)}</span>'


def strategy_health(row: pd.Series) -> tuple[str, str]:
    trades = _number(row.get("trades")) or 0
    pf = _number(row.get("profit_factor"))
    ret = _number(row.get("total_return_pct"))
    if trades < 5:
        return "DATI LIMITATI", "status-na"
    if pf is not None and pf >= 1.5 and ret is not None and ret > 0:
        return "ROBUSTA V1", "status-good"
    if pf is not None and pf >= 1.0 and ret is not None and ret >= 0:
        return "DA VALIDARE", "status-mid"
    return "DEBOLE", "status-bad"


def render_strategy_card(name: str, results: pd.DataFrame, paper: pd.DataFrame) -> None:
    info = STRATEGY_INFO.get(name, {"label": name, "summary": "N/D", "signals": [], "best_for": "N/D", "weak_when": "N/D"})
    r = results[results["strategy"] == name].copy() if not results.empty and "strategy" in results else pd.DataFrame()
    p = paper[paper["strategy"] == name].copy() if not paper.empty and "strategy" in paper else pd.DataFrame()

    if r.empty:
        status, cls = "IN ATTESA", "status-na"
        avg_pf, avg_ret, trades = None, None, 0
    else:
        trades = int(pd.to_numeric(r.get("trades"), errors="coerce").fillna(0).sum())
        avg_pf = pd.to_numeric(r.get("profit_factor"), errors="coerce").replace([float("inf"), float("-inf")], pd.NA).dropna().mean()
        avg_ret = pd.to_numeric(r.get("total_return_pct"), errors="coerce").dropna().mean()
        summary = pd.Series({"trades": trades, "profit_factor": avg_pf, "total_return_pct": avg_ret})
        status, cls = strategy_health(summary)

    paper_count = len(p)
    latest_state = p.iloc[0].get("status") if not p.empty else "N/D"
    signal_text = " · ".join(info.get("signals", [])[:4])

    st.markdown(
        f'<div class="strategy-card"><div class="strategy-name">{html.escape(info["label"])}</div>'
        f'<div class="strategy-meta"><span class="pill {cls}">{status}</span><span class="pill">Paper {paper_count}</span><span class="pill">{html.escape(str(latest_state))}</span></div>'
        f'<div style="font-size:.84rem;line-height:1.44;opacity:.88">{html.escape(info["summary"])}</div>'
        f'<div style="font-size:.72rem;line-height:1.4;opacity:.64;margin-top:8px">{html.escape(signal_text)}</div>'
        f'<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin-top:10px;font-size:.72rem"><div><b>Trade</b><br>{trades}</div><div><b>PF medio</b><br>{fmt_num(avg_pf,2)}</div><div><b>Return medio</b><br>{fmt_pct(avg_ret)}</div></div>'
        f'<div style="font-size:.71rem;line-height:1.36;opacity:.66;margin-top:9px"><b>Funziona meglio:</b> {html.escape(info["best_for"])}<br><b>Debole quando:</b> {html.escape(info["weak_when"])}</div></div>',
        unsafe_allow_html=True,
    )
