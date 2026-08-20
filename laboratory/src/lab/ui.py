from __future__ import annotations

import html
from typing import Any

import pandas as pd
import streamlit as st


UI_BUILD = "2026.08.20-2305"
COPYRIGHT_TEXT = "Questo sito è stato prodotto da Antonio Larocca · Tutti i diritti riservati."

COMPANY_NAMES = {
    "AAPL": "Apple Inc.",
    "ADBE": "Adobe Inc.",
    "AMZN": "Amazon.com Inc.",
    "AMD": "Advanced Micro Devices Inc.",
    "ASML": "ASML Holding N.V.",
    "AVGO": "Broadcom Inc.",
    "AXP": "American Express Co.",
    "BKNG": "Booking Holdings Inc.",
    "BUD": "Anheuser-Busch InBev",
    "CAT": "Caterpillar Inc.",
    "COST": "Costco Wholesale Corp.",
    "CRM": "Salesforce Inc.",
    "CSCO": "Cisco Systems Inc.",
    "CVS": "CVS Health Corp.",
    "CVX": "Chevron Corp.",
    "FTNT": "Fortinet Inc.",
    "GE": "GE Aerospace",
    "GOOG": "Alphabet Inc.",
    "GOOGL": "Alphabet Inc.",
    "GS": "Goldman Sachs Group Inc.",
    "HD": "Home Depot Inc.",
    "JPM": "JPMorgan Chase & Co.",
    "LIN": "Linde plc",
    "LLY": "Eli Lilly and Co.",
    "MA": "Mastercard Inc.",
    "META": "Meta Platforms Inc.",
    "MSFT": "Microsoft Corp.",
    "MUFG": "Mitsubishi UFJ Financial Group",
    "NFLX": "Netflix Inc.",
    "NVDA": "NVIDIA Corp.",
    "NVO": "Novo Nordisk A/S",
    "ORCL": "Oracle Corp.",
    "PANW": "Palo Alto Networks Inc.",
    "PGR": "Progressive Corp.",
    "QQQ": "Invesco QQQ Trust",
    "RTX": "RTX Corp.",
    "SPY": "SPDR S&P 500 ETF Trust",
    "TJX": "TJX Companies Inc.",
    "TSM": "Taiwan Semiconductor Manufacturing Co.",
    "UBER": "Uber Technologies Inc.",
    "UNH": "UnitedHealth Group Inc.",
    "V": "Visa Inc.",
    "WMT": "Walmart Inc.",
    "XOM": "Exxon Mobil Corp.",
}

STRATEGY_INFO = {
    "trend_continuation": {
        "label": "Continuazione del trend",
        "summary": "Cerca titoli già in trend positivo e prova a entrare su continuazione o ritracciamenti ordinati, evitando prezzi troppo estesi.",
        "signals": ["Prezzo vs SMA50/SMA200", "Ritracciamento su SMA50", "ATR", "Momentum 60g", "Volume relativo", "Breakout 20g"],
        "best_for": "Trend direzionali puliti e leadership persistente.",
        "weak_when": "Mercato laterale, falsi breakout, inversioni rapide.",
    },
    "cross_sectional_momentum": {
        "label": "Forza relativa",
        "summary": "Premia i titoli più forti rispetto all'universo. La versione v2 dovrà usare una vera classifica cross-sectional sullo stesso giorno.",
        "signals": ["Rendimento 20g", "Rendimento 60g", "Rendimento 120g", "Classifica relativa"],
        "best_for": "Regimi rialzisti con leadership stabile.",
        "weak_when": "Rotazioni violente e inversioni improvvise.",
    },
    "short_term_reversal": {
        "label": "Rimbalzo di breve periodo",
        "summary": "Cerca eccessi ribassisti di breve periodo dentro una struttura di fondo ancora accettabile, puntando a un rimbalzo controllato.",
        "signals": ["RSI14", "Distanza da SMA20", "ATR", "Trend lungo", "Stabilizzazione giornaliera"],
        "best_for": "Vendite tecniche non accompagnate da rottura strutturale.",
        "weak_when": "Crolli fondamentali, gap negativi, trend ribassisti persistenti.",
    },
    "defensive_low_vol_quality": {
        "label": "Difensiva a bassa volatilità",
        "summary": "Favorisce titoli meno volatili, sopra la media lunga e con momentum ancora positivo. Il filtro fondamentale completo arriverà in una fase successiva.",
        "signals": ["Volatilità 20g", "SMA200", "ATR%", "Momentum 60g"],
        "best_for": "Fasi difensive o mercati incerti con preferenza per stabilità.",
        "weak_when": "Mercati rialzisti molto aggressivi dominati da beta elevato.",
    },
    "pead": {
        "label": "PEAD · deriva post utili",
        "summary": "Cerca la continuazione dopo sorprese trimestrali positive o negative usando esclusivamente dati point-in-time.",
        "signals": ["Sorpresa EPS", "Sorpresa ricavi", "Revisioni analisti", "Età evento", "Reazione post utili"],
        "best_for": "Trimestrali con sorpresa credibile e revisioni coerenti.",
        "weak_when": "Dati evento incompleti o reazioni già completamente assorbite.",
    },
    "event_driven_mean_reversion": {
        "label": "Rientro dopo evento",
        "summary": "Cerca eccessi di prezzo dopo eventi non binari, quando la reazione appare sproporzionata rispetto al comportamento normale del titolo.",
        "signals": ["Rendimento evento", "Volume z-score", "Reazione giorno 1", "Filtro eventi binari"],
        "best_for": "Shock temporanei e non strutturali.",
        "weak_when": "Eventi binari o cambiamenti permanenti del business.",
    },
    "quality_value_rerating": {
        "label": "Qualità e valore",
        "summary": "Combina qualità economica, crescita, leva e sconto di valutazione per cercare rivalutazioni di società solide ma non care.",
        "signals": ["FCF yield", "ROIC", "Crescita ricavi", "Crescita EPS", "Debito netto/EBITDA", "Sconto valutativo"],
        "best_for": "Normalizzazione dei multipli e miglioramento degli utili.",
        "weak_when": "Trappole value e deterioramento strutturale del business.",
    },
    "macro_intermarket": {
        "label": "Macro intermercato",
        "summary": "Integra trend e impulsi macro per capire quali asset o settori sono coerenti con tassi, credito, materie prime e dollaro.",
        "signals": ["Punteggio trend", "Impulso tassi", "Impulso credito", "Impulso materie prime", "Impulso USD", "Coerenza macro"],
        "best_for": "Regimi macro riconoscibili e persistenti.",
        "weak_when": "Transizioni di regime rapide o segnali macro conflittuali.",
    },
}

STATUS_LABELS = {
    "PAPER_OPEN": "SIMULAZIONE APERTA",
    "OPEN": "APERTA",
    "TP1_HIT": "TP1 RAGGIUNTO",
    "PRE_BUY": "PRE-ACQUISTO",
    "PRE_BUY_HIGH": "PRE-ACQUISTO ALTO",
    "NEAR_SETUP": "VICINO AL SETUP",
    "WATCH": "OSSERVA",
    "CONFIRMED": "CONFERMATO",
    "WAITING": "IN ATTESA",
    "BLOCKED": "BLOCCATO",
    "BLOCKED_DATA": "BLOCCATO PER DATI",
    "REJECTED": "SCARTATO",
    "PROMOTABLE": "PROMOVIBILE",
    "CANDIDATE": "CANDIDATA",
    "BENCHMARK": "BENCHMARK",
    "SHADOW_BUY": "ACQUISTO SIMULATO",
    "BUY NOW": "ACQUISTA ORA",
    "BUY LIMIT": "ACQUISTO LIMIT",
    "AVOID": "EVITA",
}

REGIME_LABELS = {
    "BULL_QUIET": "RIALZISTA CALMO",
    "BULL_VOLATILE": "RIALZISTA VOLATILE",
    "RANGE_NEUTRAL": "LATERALE / NEUTRALE",
    "NEUTRAL": "NEUTRALE",
    "BEAR_HIGH_VOL": "RIBASSISTA / ALTA VOLATILITÀ",
    "BEAR": "RIBASSISTA",
}

QUALITY_LABELS = {"GREEN": "VERDE", "YELLOW": "GIALLO", "RED": "ROSSO"}

COLUMN_LABELS = {
    "created_at": "Data/ora",
    "last_seen_at": "Ultimo aggiornamento",
    "last_checked_date": "Ultimo controllo",
    "signal_date": "Data segnale",
    "source_signal_date": "Data segnale origine",
    "opened_at": "Apertura",
    "symbol": "Ticker",
    "ticker": "Ticker",
    "azienda": "Azienda",
    "company_name_display": "Azienda",
    "market": "Mercato",
    "horizon": "Orizzonte",
    "strategy": "Strategia",
    "parent_strategy": "Strategia madre",
    "status": "Stato",
    "source_signal_status": "Stato segnale",
    "trade_status": "Stato posizione",
    "decision": "Decisione",
    "score": "Punteggio",
    "score_total": "Punteggio totale",
    "strategy_score": "Punteggio strategia",
    "trade_score": "Punteggio operazione",
    "portfolio_fit": "Idoneità portafoglio",
    "portfolio_fit_score": "Idoneità portafoglio",
    "trigger": "Conferma",
    "setup": "Configurazione tecnica",
    "price": "Prezzo",
    "entry": "Ingresso",
    "entry_price": "Prezzo ingresso",
    "proposed_entry": "Ingresso proposto",
    "buy_range_low": "Acquisto min",
    "buy_range_high": "Acquisto max",
    "max_buy": "Prezzo massimo",
    "stop": "Stop",
    "stop_initial": "Stop iniziale",
    "stop_current": "Stop attuale",
    "proposed_stop": "Stop proposto",
    "tp1": "TP1",
    "tp2": "TP2",
    "proposed_target": "Target proposto",
    "last_price": "Ultimo prezzo",
    "exit_price": "Prezzo uscita",
    "qty": "Quantità",
    "capital": "Capitale",
    "gross_pnl": "P&L lordo",
    "net_pnl": "P&L netto",
    "return_pct": "Rendimento",
    "win_rate": "Percentuale successi",
    "profit_factor": "Profit Factor",
    "trades": "Operazioni",
    "rr_net_tp1": "R/R netto TP1",
    "rr_net_tp2": "R/R netto TP2",
    "distance_to_entry_pct": "Distanza ingresso",
    "alert_type": "Tipo avviso",
    "alert_price": "Prezzo avviso",
    "reason": "Motivo",
    "data_quality": "Qualità dati",
    "regime": "Regime",
    "regime_state": "Regime",
    "gate_result": "Esito controlli",
    "ret_d1": "Rendimento D+1",
    "ret_d3": "Rendimento D+3",
    "ret_d5": "Rendimento D+5",
    "ret_d10": "Rendimento D+10",
    "ret_d20": "Rendimento D+20",
    "ret_d60": "Rendimento D+60",
    "excess_ret_d1": "Extra rendimento D+1 vs SPY",
    "excess_ret_d3": "Extra rendimento D+3 vs SPY",
    "excess_ret_d5": "Extra rendimento D+5 vs SPY",
    "excess_ret_d10": "Extra rendimento D+10 vs SPY",
    "excess_ret_d20": "Extra rendimento D+20 vs SPY",
    "excess_ret_d60": "Extra rendimento D+60 vs SPY",
    "mfe_pct": "MFE %",
    "mae_pct": "MAE %",
    "mfe_r": "MFE in R",
    "mae_r": "MAE in R",
    "bars_to_mfe": "Barre fino a MFE",
    "bars_to_mae": "Barre fino a MAE",
    "block_reasons": "Motivi blocco",
    "position_id": "ID posizione",
    "event_type": "Evento",
    "old_stop": "Stop precedente",
    "new_stop": "Nuovo stop",
    "note": "Nota",
    "run_timestamp": "Data/ora esecuzione",
    "run_id": "ID esecuzione",
    "engine_version": "Versione motore",
    "candidates_count": "Candidati",
    "variant_id": "ID variante",
    "generation": "Generazione",
    "promoted_to_core": "Promossa al Core",
    "mutation_reason": "Motivo modifica",
    "parameters": "Parametri",
    "notes": "Note",
    "entry_score": "Punteggio ingresso",
    "atr_stop_mult": "Moltiplicatore ATR stop",
    "target_r_multiple": "Target in R",
    "train_return_pct": "Rendimento training",
    "test_return_pct": "Rendimento test",
    "test_trades": "Operazioni test",
}


def _sidebar_navigation() -> None:
    st.sidebar.markdown("## 📈 TRADING LAB")
    st.sidebar.caption("DECISIONE · RISCHIO · RICERCA")
    st.sidebar.page_link("app.py", label="🏠  PANNELLO OPERATIVO")
    st.sidebar.page_link("pages/1_Signals.py", label="🎯  OPPORTUNITÀ")
    st.sidebar.page_link("pages/5_Action_Center.py", label="⚡  CENTRO OPERATIVO")
    st.sidebar.page_link("pages/2_Portfolio.py", label="💼  PORTAFOGLIO")
    st.sidebar.markdown("---")
    st.sidebar.caption("ANALISI E RICERCA")
    st.sidebar.page_link("pages/6_Backtest_Research.py", label="🧪  RICERCA STRATEGIE")
    st.sidebar.page_link("pages/3_Laboratory.py", label="📊  ESITI DEI SEGNALI")
    st.sidebar.page_link("pages/4_Engine_Health.py", label="🩺  STATO DEL MOTORE")
    st.sidebar.markdown("---")
    st.sidebar.caption(f"VERSIONE INTERFACCIA {UI_BUILD}")
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


def fmt_status(value: Any) -> str:
    text = "N/D" if value is None else str(value).strip().upper()
    return STATUS_LABELS.get(text, text.replace("_", " "))


def fmt_strategy(value: Any) -> str:
    key = "" if value is None else str(value).strip()
    return STRATEGY_INFO.get(key, {}).get("label", key.replace("_", " ").strip().title() or "N/D")


def fmt_regime(value: Any) -> str:
    text = "N/D" if value is None else str(value).strip().upper()
    return REGIME_LABELS.get(text, text.replace("_", " "))


def fmt_quality(value: Any) -> str:
    text = "N/D" if value is None else str(value).strip().upper()
    return QUALITY_LABELS.get(text, text)


def fmt_trigger(value: Any) -> str:
    text = "N/D" if value is None else str(value).strip().upper().replace("_", " ")
    mapping = {
        "CONFIRMED": "CONFERMATO",
        "WAITING": "ATTENDI",
        "WAIT": "ATTENDI",
        "BUY ZONE": "ZONA ACQUISTO",
        "ENTRY REACHED": "INGRESSO RAGGIUNTO",
        "INVALID": "INVALIDO",
    }
    return mapping.get(text, text)


def trigger_class(trigger: str) -> str:
    t = str(trigger).upper()
    if "CONFERMATO" in t or "CONFIRMED" in t:
        return "trigger-confirmed"
    if "ACQUISTO" in t or "INGRESSO" in t or "BUY" in t or "ENTRY" in t:
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


def localize_table(df: pd.DataFrame) -> pd.DataFrame:
    """Translate only the presentation layer. Database and engine field names remain unchanged."""
    out = df.copy()
    for col in ["strategy", "parent_strategy"]:
        if col in out:
            out[col] = out[col].map(fmt_strategy)
    for col in ["status", "source_signal_status", "trade_status", "decision"]:
        if col in out:
            out[col] = out[col].map(fmt_status)
    if "trigger" in out:
        out["trigger"] = out["trigger"].map(fmt_trigger)
    for col in ["regime", "regime_state"]:
        if col in out:
            out[col] = out[col].map(fmt_regime)
    if "data_quality" in out:
        out["data_quality"] = out["data_quality"].map(fmt_quality)
    return out.rename(columns={c: COLUMN_LABELS[c] for c in out.columns if c in COLUMN_LABELS})


def strategy_health(row_or_pf: Any, trades: Any = None, ret: Any = None) -> tuple[str, str]:
    if isinstance(row_or_pf, pd.Series):
        trades_n = _number(row_or_pf.get("trades")) or 0
        pf = _number(row_or_pf.get("profit_factor"))
        ret_n = _number(row_or_pf.get("total_return_pct", row_or_pf.get("return_pct")))
    else:
        pf = _number(row_or_pf)
        trades_n = _number(trades) or 0
        ret_n = _number(ret)
    if trades_n < 5:
        return "DATI LIMITATI", "status-na"
    if pf is not None and pf >= 1.5 and ret_n is not None and ret_n > 0:
        return "ROBUSTA", "status-good"
    if pf is not None and pf >= 1.0 and ret_n is not None and ret_n >= 0:
        return "DA VALIDARE", "status-mid"
    return "DEBOLE", "status-bad"


def render_strategy_card(name: str, results: Any, paper: pd.DataFrame | None = None) -> None:
    info = STRATEGY_INFO.get(name, {"label": fmt_strategy(name), "summary": "N/D", "signals": [], "best_for": "N/D", "weak_when": "N/D"})

    if isinstance(results, dict):
        trades = int(_number(results.get("trades")) or 0)
        avg_pf = _number(results.get("profit_factor"))
        avg_ret = _number(results.get("return_pct"))
        status, cls = strategy_health(avg_pf, trades, avg_ret)
        paper_count = 0
        latest_state = "N/D"
    else:
        r = results[results["strategy"] == name].copy() if isinstance(results, pd.DataFrame) and not results.empty and "strategy" in results else pd.DataFrame()
        p = paper[paper["strategy"] == name].copy() if isinstance(paper, pd.DataFrame) and not paper.empty and "strategy" in paper else pd.DataFrame()
        if r.empty:
            status, cls = "IN ATTESA", "status-na"
            avg_pf, avg_ret, trades = None, None, 0
        else:
            trades = int(pd.to_numeric(r.get("trades"), errors="coerce").fillna(0).sum())
            avg_pf = pd.to_numeric(r.get("profit_factor"), errors="coerce").replace([float("inf"), float("-inf")], pd.NA).dropna().mean()
            avg_ret = pd.to_numeric(r.get("total_return_pct", r.get("return_pct")), errors="coerce").dropna().mean()
            status, cls = strategy_health(avg_pf, trades, avg_ret)
        paper_count = len(p)
        latest_state = fmt_status(p.iloc[0].get("status")) if not p.empty else "N/D"

    signal_text = " · ".join(info.get("signals", [])[:4])
    st.markdown(
        f'<div class="strategy-card"><div class="strategy-name">{html.escape(info["label"])}</div>'
        f'<div class="strategy-meta"><span class="pill {cls}">{status}</span><span class="pill">Segnali simulati {paper_count}</span><span class="pill">{html.escape(str(latest_state))}</span></div>'
        f'<div style="font-size:.84rem;line-height:1.44;opacity:.88">{html.escape(info["summary"])}</div>'
        f'<div style="font-size:.72rem;line-height:1.4;opacity:.64;margin-top:8px">{html.escape(signal_text)}</div>'
        f'<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin-top:10px;font-size:.72rem"><div><b>Operazioni</b><br>{trades}</div><div><b>PF medio</b><br>{fmt_num(avg_pf,2)}</div><div><b>Rendimento medio</b><br>{fmt_pct(avg_ret)}</div></div>'
        f'<div style="font-size:.71rem;line-height:1.36;opacity:.66;margin-top:9px"><b>Funziona meglio:</b> {html.escape(info["best_for"])}<br><b>Debole quando:</b> {html.escape(info["weak_when"])}</div></div>',
        unsafe_allow_html=True,
    )
