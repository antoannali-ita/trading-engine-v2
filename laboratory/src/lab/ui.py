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


def apply_theme() -> None:
    st.markdown(
        """
        <style>
        .block-container {padding-top: 1.6rem; padding-bottom: 3rem; max-width: 1500px;}
        h1, h2, h3 {letter-spacing: -0.02em;}
        [data-testid="stMetric"] {
            border: 1px solid rgba(128,128,128,.18);
            border-radius: 16px;
            padding: 14px 16px;
            background: rgba(128,128,128,.045);
        }
        [data-testid="stMetricLabel"] {font-weight: 600; opacity: .82;}
        [data-testid="stMetricValue"] {font-weight: 750;}
        .lab-hero {
            border: 1px solid rgba(128,128,128,.18);
            border-radius: 22px;
            padding: 22px 24px;
            margin-bottom: 18px;
            background: linear-gradient(135deg, rgba(99,102,241,.12), rgba(14,165,233,.05));
        }
        .lab-eyebrow {font-size: .75rem; letter-spacing: .12em; text-transform: uppercase; opacity: .62; font-weight: 700;}
        .lab-title {font-size: 2rem; font-weight: 800; margin-top: 4px;}
        .lab-subtitle {font-size: 1rem; opacity: .74; margin-top: 5px; max-width: 900px;}
        .strategy-card {
            border: 1px solid rgba(128,128,128,.18);
            border-radius: 18px;
            padding: 18px;
            min-height: 210px;
            background: rgba(128,128,128,.035);
        }
        .strategy-name {font-size: 1.05rem; font-weight: 760; margin-bottom: 4px;}
        .strategy-meta {font-size: .8rem; opacity: .68; margin-bottom: 10px;}
        .pill {display:inline-block; padding:4px 9px; border-radius:999px; font-size:.73rem; font-weight:700; margin-right:5px; margin-bottom:5px; background:rgba(99,102,241,.12);}
        .status-good {background:rgba(34,197,94,.14);}
        .status-mid {background:rgba(234,179,8,.16);}
        .status-bad {background:rgba(239,68,68,.13);}
        .status-na {background:rgba(148,163,184,.16);}
        div[data-testid="stDataFrame"] {border:1px solid rgba(128,128,128,.13); border-radius:14px; overflow:hidden;}
        .small-note {font-size:.82rem; opacity:.66;}
        </style>
        """,
        unsafe_allow_html=True,
    )


def page_header(title: str, subtitle: str, eyebrow: str = "TRADING LAB 2.0") -> None:
    st.markdown(
        f"""
        <div class="lab-hero">
          <div class="lab-eyebrow">{html.escape(eyebrow)}</div>
          <div class="lab-title">{html.escape(title)}</div>
          <div class="lab-subtitle">{html.escape(subtitle)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def strategy_health(profit_factor: Any, trades: Any, return_pct: Any) -> tuple[str, str]:
    try:
        pf = float(profit_factor)
        n = float(trades)
        ret = float(return_pct)
    except (TypeError, ValueError):
        return "N/D", "status-na"
    if n >= 80 and pf >= 1.5 and ret > 0:
        return "Robusta", "status-good"
    if n >= 35 and pf >= 1.15 and ret > 0:
        return "Da validare", "status-mid"
    if n >= 20 and (pf < 1 or ret < 0):
        return "Debole", "status-bad"
    return "Campione piccolo", "status-na"


def render_strategy_card(strategy: str, row: pd.Series | dict[str, Any] | None = None) -> None:
    meta = STRATEGY_INFO.get(strategy, {"label": strategy, "summary": "Descrizione non disponibile.", "signals": [], "best_for": "N/D", "weak_when": "N/D"})
    if row is None:
        row = {}
    pf = row.get("profit_factor") if hasattr(row, "get") else None
    trades = row.get("trades") if hasattr(row, "get") else None
    ret = row.get("return_pct") if hasattr(row, "get") else None
    wr = row.get("win_rate") if hasattr(row, "get") else None
    health, klass = strategy_health(pf, trades, ret)

    def fmt(v: Any, suffix: str = "") -> str:
        try:
            if pd.isna(v):
                return "N/D"
            return f"{float(v):.2f}{suffix}"
        except (TypeError, ValueError):
            return "N/D"

    pills = "".join(f'<span class="pill">{html.escape(x)}</span>' for x in meta["signals"][:5])
    st.markdown(
        f"""
        <div class="strategy-card">
          <div class="strategy-name">{html.escape(meta['label'])} <span title="{html.escape(meta['summary'])}">ⓘ</span></div>
          <div class="strategy-meta"><span class="pill {klass}">{health}</span> PF {fmt(pf)} · Return {fmt(ret, '%')} · Win {fmt(wr, '%')} · N {fmt(trades)}</div>
          <div style="font-size:.91rem; opacity:.82; margin-bottom:12px;">{html.escape(meta['summary'])}</div>
          <div>{pills}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.expander("Come funziona e quando usarla"):
        st.markdown(f"**Funziona meglio:** {meta['best_for']}")
        st.markdown(f"**Tende a soffrire:** {meta['weak_when']}")
        st.markdown("**Input principali:** " + ", ".join(meta["signals"]))


def info_help(label: str, text: str) -> None:
    st.markdown(f"**{html.escape(label)}** <span title=\"{html.escape(text)}\">ⓘ</span>", unsafe_allow_html=True)
