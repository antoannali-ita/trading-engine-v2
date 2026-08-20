from __future__ import annotations

import html
from typing import Any

import pandas as pd
import streamlit as st


UI_BUILD = "2026.08.20-2055"
COPYRIGHT_TEXT = "Questo sito è stato prodotto da Antonio Larocca · Tutti i diritti riservati."

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
        [data-testid="stSidebar"] .stPageLink {margin-bottom:.15rem;}
        [data-testid="stSidebar"] .stPageLink a {border-radius:10px; padding:.5rem .62rem; font-weight:700; letter-spacing:.02em;}
        [data-testid="stSidebar"] .stPageLink a:hover {background:rgba(99,102,241,.09);}
        .block-container {padding-top:1.6rem; padding-bottom:5.2rem; max-width:1500px;}
        h1, h2, h3 {letter-spacing:-0.02em;}
        [data-testid="stMetric"] {border:1px solid rgba(128,128,128,.18); border-radius:14px; padding:10px 12px; background:rgba(128,128,128,.045); min-height:82px;}
        [data-testid="stMetricLabel"] {font-weight:600; opacity:.78; font-size:.76rem;}
        [data-testid="stMetricValue"] {font-weight:750; font-size:1.55rem; line-height:1.1;}
        .lab-hero {border:1px solid rgba(128,128,128,.18); border-radius:22px; padding:22px 24px; margin-bottom:18px; background:linear-gradient(135deg, rgba(99,102,241,.12), rgba(14,165,233,.05));}
        .lab-eyebrow {font-size:.75rem; letter-spacing:.12em; text-transform:uppercase; opacity:.62; font-weight:700;}
        .lab-title {font-size:2rem; font-weight:800; margin-top:4px;}
        .lab-subtitle {font-size:1rem; opacity:.74; margin-top:5px; max-width:900px;}
        .strategy-card {border:1px solid rgba(128,128,128,.18); border-radius:18px; padding:18px; min-height:210px; background:rgba(128,128,128,.035);}
        .strategy-name {font-size:1.05rem; font-weight:760; margin-bottom:4px;}
        .strategy-meta {font-size:.8rem; opacity:.68; margin-bottom:10px;}
        .pill {display:inline-block; padding:4px 9px; border-radius:999px; font-size:.73rem; font-weight:700; margin-right:5px; margin-bottom:5px; background:rgba(99,102,241,.12);}
        .status-good {background:rgba(34,197,94,.14);}
        .status-mid {background:rgba(234,179,8,.16);}
        .status-bad {background:rgba(239,68,68,.13);}
        .status-na {background:rgba(148,163,184,.16);}
        div[data-testid="stDataFrame"] {border:1px solid rgba(128,128,128,.13); border-radius:14px; overflow:hidden;}
        .candidate-detail {font-size:.82rem; opacity:.78; line-height:1.45; margin-top:.25rem;}
        .site-footer {position:fixed; left:0; right:0; bottom:0; z-index:999; padding:.55rem 1rem; text-align:center; font-size:.76rem; opacity:.78; backdrop-filter:blur(10px); background:rgba(250,250,250,.88); border-top:1px solid rgba(128,128,128,.14);}
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
    return fmt_num(value, 2)


def fmt_qty(value: Any) -> str:
    number = _number(value)
    return "N/D" if number is None else f"{int(number):,}"


def fmt_trigger(value: Any) -> str:
    text = str(_scalar(value) or "N/D").strip().upper().replace("_", " ")
    mapping = {
        "WAITING": "ATTENDI",
        "WAIT": "ATTENDI",
        "CONFIRMED": "CONFERMATO",
        "BUY ZONE": "BUY ZONE",
        "INVALID": "INVALIDO",
    }
    return mapping.get(text, text)


def strategy_health(profit_factor: Any, trades: Any, return_pct: Any) -> tuple[str, str]:
    pf = _number(profit_factor)
    n = _number(trades)
    ret = _number(return_pct)
    if pf is None or n is None or ret is None:
        return "N/D", "status-na"
    if n >= 80 and pf >= 1.5 and ret > 0:
        return "Robusta", "status-good"
    if n >= 35 and pf >= 1.15 and ret > 0:
        return "Da validare", "status-mid"
    if n >= 20 and (pf < 1 or ret < 0):
        return "Debole", "status-bad"
    return "Campione piccolo", "status-na"


def render_strategy_card(strategy: str, row: dict[str, Any] | None = None) -> None:
    meta = STRATEGY_INFO.get(strategy, {"label": strategy, "summary": "Descrizione non disponibile.", "signals": [], "best_for": "N/D", "weak_when": "N/D"})
    data = row if isinstance(row, dict) else {}
    pf = _number(data.get("profit_factor"))
    trades = _number(data.get("trades"))
    ret = _number(data.get("return_pct"))
    wr = _number(data.get("win_rate"))
    health, klass = strategy_health(pf, trades, ret)
    signals = list(meta.get("signals", []))
    pills = "".join(f'<span class="pill">{html.escape(str(x))}</span>' for x in signals[:5])
    label = html.escape(str(meta.get("label", strategy)))
    summary = html.escape(str(meta.get("summary", "N/D")))
    card_html = ('<div class="strategy-card">' f'<div class="strategy-name">{label} <span title="{summary}">ⓘ</span></div>' f'<div class="strategy-meta"><span class="pill {klass}">{health}</span> PF {fmt_num(pf)} · Return {fmt_pct(ret)} · Win {fmt_pct(wr)} · N {fmt_num(trades, 0)}</div>' f'<div style="font-size:.91rem; opacity:.82; margin-bottom:12px;">{summary}</div>' f'<div>{pills}</div></div>')
    st.markdown(card_html, unsafe_allow_html=True)
    with st.expander("COME FUNZIONA E QUANDO USARLA"):
        st.markdown(f"**Funziona meglio:** {meta.get('best_for', 'N/D')}")
        st.markdown(f"**Tende a soffrire:** {meta.get('weak_when', 'N/D')}")
        st.markdown("**Input principali:** " + ", ".join(str(x) for x in signals))


def info_help(label: str, text: str) -> None:
    st.markdown(f'**{html.escape(str(label))}** <span title="{html.escape(str(text))}">ⓘ</span>', unsafe_allow_html=True)
