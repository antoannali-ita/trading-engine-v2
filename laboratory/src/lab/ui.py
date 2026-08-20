from __future__ import annotations

import html
from typing import Any

import pandas as pd
import streamlit as st


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
    st.sidebar.markdown("## 📈 Trading Lab")
    st.sidebar.caption("Decisione · rischio · ricerca")
    st.sidebar.page_link("app.py", label="🏠  Control Room")
    st.sidebar.page_link("pages/1_Signals.py", label="🎯  Opportunità")
    st.sidebar.page_link("pages/5_Action_Center.py", label="⚡  Action Center")
    st.sidebar.page_link("pages/2_Portfolio.py", label="💼  Portafoglio")
    st.sidebar.markdown("---")
    st.sidebar.caption("ANALISI & RICERCA")
    st.sidebar.page_link("pages/6_Backtest_Research.py", label="🧪  Strategy Lab")
    st.sidebar.page_link("pages/3_Laboratory.py", label="📊  Signal Outcomes")
    st.sidebar.page_link("pages/4_Engine_Health.py", label="🩺  Engine Health")
    st.sidebar.markdown("---")
    st.sidebar.caption("PAPER / RESEARCH · nessun ordine automatico")


def apply_theme() -> None:
    st.markdown(
        """
        <style>
        [data-testid="stSidebarNav"] {display:none;}
        [data-testid="stSidebar"] {border-right:1px solid rgba(128,128,128,.14);}
        [data-testid="stSidebar"] .stPageLink {margin-bottom:.15rem;}
        [data-testid="stSidebar"] .stPageLink a {border-radius:10px; padding:.48rem .62rem;}
        [data-testid="stSidebar"] .stPageLink a:hover {background:rgba(99,102,241,.09);}
        .block-container {padding-top: 1.6rem; padding-bottom: 3rem; max-width: 1500px;}
        h1, h2, h3 {letter-spacing: -0.02em;}
        [data-testid="stMetric"] {border:1px solid rgba(128,128,128,.18); border-radius:16px; padding:14px 16px; background:rgba(128,128,128,.045);}
        [data-testid="stMetricLabel"] {font-weight:600; opacity:.82;}
        [data-testid="stMetricValue"] {font-weight:750;}
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
        </style>
        """,
        unsafe_allow_html=True,
    )
    _sidebar_navigation()


def page_header(title: str, subtitle: str, eyebrow: str = "TRADING LAB 2.0") -> None:
    st.markdown(
        f'<div class="lab-hero"><div class="lab-eyebrow">{html.escape(eyebrow)}</div><div class="lab-title">{html.escape(title)}</div><div class="lab-subtitle">{html.escape(subtitle)}</div></div>',
        unsafe_allow_html=True,
    )


def _scalar(value: Any) -> Any:
    """Return a single scalar without ever asking pandas objects for truthiness."""
    if isinstance(value, pd.DataFrame):
        if value.empty:
            return None
        return _scalar(value.iloc[0, 0])
    if isinstance(value, pd.Series):
        if value.empty:
            return None
        non_null = value.dropna()
        return _scalar(non_null.iloc[0] if not non_null.empty else None)
    if isinstance(value, (list, tuple)):
        return _scalar(value[0]) if len(value) else None
    return value


def strategy_health(profit_factor: Any, trades: Any, return_pct: Any) -> tuple[str, str]:
    try:
        pf_raw, n_raw, ret_raw = _scalar(profit_factor), _scalar(trades), _scalar(return_pct)
        if pf_raw is None or n_raw is None or ret_raw is None:
            return "N/D", "status-na"
        pf, n, ret = float(pf_raw), float(n_raw), float(ret_raw)
        if pd.isna(pf) or pd.isna(n) or pd.isna(ret):
            return "N/D", "status-na"
    except (TypeError, ValueError):
        return "N/D", "status-na"
    if n >= 80 and pf >= 1.5 and ret > 0:
        return "Robusta", "status-good"
    if n >= 35 and pf >= 1.15 and ret > 0:
        return "Da validare", "status-mid"
    if n >= 20 and (pf < 1 or ret < 0):
        return "Debole", "status-bad"
    return "Campione piccolo", "status-na"


def render_strategy_card(strategy: str, row: pd.Series | dict[str, Any] | pd.DataFrame | None = None) -> None:
    meta = STRATEGY_INFO.get(strategy, {"label": strategy, "summary": "Descrizione non disponibile.", "signals": [], "best_for": "N/D", "weak_when": "N/D"})
    if row is None:
        row_data: Any = {}
    elif isinstance(row, pd.DataFrame):
        row_data = row.iloc[0] if not row.empty else {}
    else:
        row_data = row

    def get_value(key: str) -> Any:
        if hasattr(row_data, "get"):
            return _scalar(row_data.get(key))
        return None

    pf = get_value("profit_factor")
    trades = get_value("trades")
    ret = get_value("return_pct")
    wr = get_value("win_rate")
    health, klass = strategy_health(pf, trades, ret)

    def fmt(value: Any, suffix: str = "") -> str:
        scalar = _scalar(value)
        if scalar is None:
            return "N/D"
        try:
            number = float(scalar)
            if pd.isna(number):
                return "N/D"
            return f"{number:.2f}{suffix}"
        except (TypeError, ValueError):
            return "N/D"

    pills = "".join(f'<span class="pill">{html.escape(str(x))}</span>' for x in meta["signals"][:5])
    card_html = (
        '<div class="strategy-card">'
        f'<div class="strategy-name">{html.escape(str(meta["label"]))} <span title="{html.escape(str(meta["summary"]))}">ⓘ</span></div>'
        f'<div class="strategy-meta"><span class="pill {klass}">{health}</span> PF {fmt(pf)} · Return {fmt(ret, "%")} · Win {fmt(wr, "%")} · N {fmt(trades)}</div>'
        f'<div style="font-size:.91rem; opacity:.82; margin-bottom:12px;">{html.escape(str(meta["summary"]))}</div>'
        f'<div>{pills}</div></div>'
    )
    st.markdown(card_html, unsafe_allow_html=True)
    with st.expander("Come funziona e quando usarla"):
        st.markdown(f"**Funziona meglio:** {meta['best_for']}")
        st.markdown(f"**Tende a soffrire:** {meta['weak_when']}")
        st.markdown("**Input principali:** " + ", ".join(meta["signals"]))


def info_help(label: str, text: str) -> None:
    st.markdown(f'**{html.escape(label)}** <span title="{html.escape(text)}">ⓘ</span>', unsafe_allow_html=True)
