from __future__ import annotations

import os
from datetime import datetime

import pandas as pd
import streamlit as st

try:
    from dashboard.data_access import (
        ai_analysis,
        engine_health,
        latest_confluence,
        manual_requests,
        notifications,
        performance,
        performance_summary,
        request_run,
        runs,
        signals,
        utc_label,
    )
except ModuleNotFoundError:
    from data_access import (
        ai_analysis,
        engine_health,
        latest_confluence,
        manual_requests,
        notifications,
        performance,
        performance_summary,
        request_run,
        runs,
        signals,
        utc_label,
    )

st.set_page_config(page_title="Trading Engine Control Center", page_icon="📈", layout="wide")

st.markdown(
    """
    <style>
    .block-container {padding-top: 1.4rem; padding-bottom: 2rem;}
    .hero {padding: 1.0rem 1.2rem; border: 1px solid rgba(128,128,128,.22); border-radius: 16px; margin-bottom: .8rem;}
    .hero h1 {margin: 0 0 .2rem 0; font-size: 2.15rem;}
    .muted {opacity: .70; font-size: .92rem;}
    .ux-card {border: 1px solid rgba(128,128,128,.24); border-radius: 14px; padding: 14px 16px; min-height: 118px; transition: .18s ease; background: rgba(128,128,128,.035);}
    .ux-card:hover {transform: translateY(-2px); border-color: rgba(80,130,255,.65); box-shadow: 0 7px 24px rgba(0,0,0,.08);}
    .ux-card .icon {font-size: 1.65rem;}
    .ux-card .title {font-weight: 700; margin-top: 4px;}
    .ux-card .desc {opacity: .72; font-size: .86rem; margin-top: 6px;}
    .flow {display:flex; align-items:center; gap:8px; flex-wrap:wrap; margin: 12px 0 18px 0;}
    .node {border:1px solid rgba(128,128,128,.30); border-radius:14px; padding:12px 14px; min-width:150px; text-align:center; background:rgba(128,128,128,.04); transition:.18s ease; cursor:help;}
    .node:hover {transform:scale(1.025); border-color:rgba(80,130,255,.70); box-shadow:0 5px 18px rgba(0,0,0,.08);}
    .arrow {opacity:.55; font-size:1.35rem;}
    .section-note {padding:.7rem .9rem; border-left:4px solid rgba(80,130,255,.75); background:rgba(80,130,255,.06); border-radius:8px; margin:.5rem 0 1rem 0;}
    </style>
    """,
    unsafe_allow_html=True,
)

HELP = {
    "engine_id": "Identifica il motore che ha prodotto il run o il segnale.",
    "strategy": "Strategia operativa applicata dal motore.",
    "market": "Mercato di riferimento, per esempio USA o ITALY.",
    "horizon": "Orizzonte temporale principale del motore o della strategia.",
    "stato": "Stato sintetico calcolato usando ultimo run, errori e frequenza attesa.",
    "computed_health": "HEALTHY = regolare; RUNNING = in esecuzione; STALE = non gira da troppo tempo; FAILED = ultimo run fallito.",
    "last_started_at": "Ora di avvio dell'ultimo run registrato.",
    "last_finished_at": "Ora di completamento dell'ultimo run registrato.",
    "signals_found": "Numero di segnali prodotti dal run.",
    "detected_at": "Momento in cui il segnale è stato registrato.",
    "ticker": "Simbolo del titolo analizzato.",
    "engine": "Famiglia del motore che ha generato il segnale.",
    "signal_type": "Tipo di segnale. Le conferme multiple hanno peso maggiore di un singolo segnale.",
    "decision": "Decisione normalizzata prodotta dal motore/orchestratore.",
    "conviction": "Forza sintetica della decisione. Va letta insieme alla confluenza, non isolatamente.",
    "is_actionable": "True significa che il segnale supera i gate minimi per passare allo stadio successivo.",
    "price": "Prezzo osservato al momento del segnale.",
    "entry": "Livello di ingresso proposto dal motore.",
    "stop": "Livello di protezione previsto dal setup.",
    "tp1": "Primo obiettivo di profitto.",
    "tp2": "Secondo obiettivo di profitto.",
    "status": "Stato del processo o dell'analisi.",
    "alignment": "Giudizio TradingAgents: CONFIRM, NEUTRAL, CAUTION o VETO.",
    "confidence": "Confidenza dichiarata dall'analisi AI, se disponibile.",
    "verdict": "Verdetto sintetico di TradingAgents.",
    "summary": "Sintesi testuale dell'analisi AI.",
    "trigger_reason": "Motivo per cui l'Orchestrator ha deciso di chiamare TradingAgents.",
    "started_at": "Ora di avvio.",
    "finished_at": "Ora di fine.",
    "trigger_source": "Origine del run: schedule, manuale GitHub, manuale web o orchestrazione.",
    "duration_seconds": "Durata del run in secondi.",
    "records_processed": "Numero di record elaborati dal motore.",
    "error_message": "Dettaglio dell'errore, presente solo se qualcosa è fallito.",
    "requested_at": "Quando è stata inserita la richiesta manuale.",
    "requested_by": "Chi ha richiesto l'esecuzione.",
    "github_run_id": "ID del run GitHub Actions associato.",
    "run_id": "Identificativo applicativo del run.",
    "completed_at": "Quando il processo si è concluso.",
    "outcome": "Orizzonte di misurazione della performance, es. MARK_5D.",
    "entry_price": "Prezzo di riferimento iniziale usato per la misurazione.",
    "exit_price": "Prezzo rilevato alla fine dell'orizzonte.",
    "pnl_pct": "Variazione percentuale tra ingresso di riferimento e uscita.",
    "max_drawdown_pct": "Peggior drawdown peak-to-trough registrato nella finestra.",
    "max_favorable_excursion_pct": "Massimo movimento favorevole rispetto all'ingresso.",
    "holding_minutes": "Durata teorica della finestra di misurazione.",
    "attempted_at": "Momento in cui il sistema ha tentato la notifica.",
    "sent_at": "Momento di invio effettivo.",
    "event_type": "Tipo di evento notificato.",
    "channel": "Canale usato, per esempio EMAIL o WHATSAPP.",
    "provider": "Servizio tecnico usato per l'invio.",
}


def require_access() -> None:
    expected = (os.getenv("DASHBOARD_PASSWORD") or "").strip()
    if not expected:
        return
    if st.session_state.get("dashboard_auth"):
        return
    st.title("🔐 Trading Engine Control Center")
    pwd = st.text_input("Password", type="password")
    if st.button("Accedi", type="primary"):
        if pwd == expected:
            st.session_state["dashboard_auth"] = True
            st.rerun()
        st.error("Password non valida")
    st.stop()


def as_df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def badge(value: str | None) -> str:
    v = str(value or "UNKNOWN").upper()
    icon = {
        "HEALTHY": "🟢", "SUCCESS": "🟢", "SENT": "🟢", "CONFIRM": "🟢",
        "RUNNING": "🔵", "PENDING": "🟡", "REQUESTED": "🟡", "DISPATCHED": "🔵",
        "DEGRADED": "🟠", "CAUTION": "🟠", "NEUTRAL": "⚪", "STALE": "🟠",
        "FAILED": "🔴", "VETO": "🔴", "DISABLED": "⚫", "UNKNOWN": "⚪",
    }.get(v, "⚪")
    return f"{icon} {v}"


def column_config(cols) -> dict:
    return {c: st.column_config.TextColumn(c, help=HELP[c]) for c in cols if c in HELP}


def explain(title: str, body: str, bullets: list[str] | None = None) -> None:
    with st.expander(f"ℹ️ Come leggere: {title}", expanded=False):
        st.write(body)
        for item in bullets or []:
            st.markdown(f"- {item}")


def show_table(df: pd.DataFrame, cols: list[str], limit: int = 300) -> None:
    cols = [c for c in cols if c in df.columns]
    if not cols:
        st.info("Nessuna colonna disponibile per questa vista.")
        return
    st.dataframe(df[cols].head(limit), use_container_width=True, hide_index=True, column_config=column_config(cols))


def visual_cards(cards: list[tuple[str, str, str]]) -> None:
    columns = st.columns(len(cards))
    for col, (icon, title, desc) in zip(columns, cards):
        with col:
            st.markdown(
                f'<div class="ux-card" title="{desc}"><div class="icon">{icon}</div><div class="title">{title}</div><div class="desc">{desc}</div></div>',
                unsafe_allow_html=True,
            )


@st.cache_data(ttl=30, show_spinner=False)
def load_snapshot() -> dict:
    return {
        "health": engine_health(),
        "signals": signals(1200),
        "confluence": latest_confluence(300),
        "runs": runs(600),
        "ai": ai_analysis(400),
        "notifications": notifications(600),
        "performance": performance(1200),
        "performance_summary": performance_summary(),
        "requests": manual_requests(250),
        "loaded_at": datetime.now().isoformat(timespec="seconds"),
    }


def decision_board(conf_df: pd.DataFrame, ai_df: pd.DataFrame) -> pd.DataFrame:
    if conf_df.empty:
        return pd.DataFrame()
    view = conf_df.copy()
    if not ai_df.empty and {"ticker", "market"}.issubset(ai_df.columns):
        ai = ai_df.copy()
        ai = ai.sort_values("started_at", ascending=False) if "started_at" in ai.columns else ai
        ai = ai.drop_duplicates(subset=["market", "ticker"], keep="first")
        keep = [c for c in ["market", "ticker", "status", "alignment", "confidence", "verdict", "summary", "completed_at"] if c in ai.columns]
        ai = ai[keep].rename(columns={"status": "ai_status", "alignment": "ai_alignment", "confidence": "ai_confidence", "verdict": "ai_verdict", "summary": "ai_summary", "completed_at": "ai_completed_at"})
        view = view.merge(ai, on=["market", "ticker"], how="left")
    return view


require_access()

head_l, head_r = st.columns([5, 1])
with head_l:
    st.markdown('<div class="hero"><h1>📈 Trading Engine Control Center</h1><div class="muted">Produzione, Laboratory, Operations e guida nello stesso posto, ma finalmente separati come esseri umani ragionevoli.</div></div>', unsafe_allow_html=True)
with head_r:
    if st.button("↻ Aggiorna dati", use_container_width=True, help="Svuota la cache della dashboard e rilegge Supabase."):
        st.cache_data.clear()
        st.rerun()

try:
    snap = load_snapshot()
except Exception as exc:
    st.error(f"Connessione dati non disponibile: {type(exc).__name__}: {exc}")
    st.stop()

health_rows = snap["health"]
sig_rows = snap["signals"]
conf_rows = snap["confluence"]
run_rows = snap["runs"]
ai_rows = snap["ai"]
notif_rows = snap["notifications"]
perf_rows = snap["performance"]
perf_summary_rows = snap["performance_summary"]
request_rows = snap["requests"]

health_df = as_df(health_rows)
sig_df = as_df(sig_rows)
conf_df = as_df(conf_rows)
run_df = as_df(run_rows)
ai_df = as_df(ai_rows)
notif_df = as_df(notif_rows)
perf_df = as_df(perf_rows)
perf_summary_df = as_df(perf_summary_rows)
request_df = as_df(request_rows)
decision_df = decision_board(conf_df, ai_df)

healthy = sum(str(r.get("computed_health") or r.get("registry_status") or "").upper() == "HEALTHY" for r in health_rows)
failed = sum(str(r.get("computed_health") or r.get("registry_status") or "").upper() in {"FAILED", "STALE", "DEGRADED"} for r in health_rows)
actionable = sum(bool(r.get("is_actionable")) for r in conf_rows)
ai_pending = sum(str(r.get("status") or "").upper() in {"PENDING", "RUNNING"} for r in ai_rows)
manual_active = sum(str(r.get("status") or "").upper() in {"REQUESTED", "DISPATCHED", "RUNNING"} for r in request_rows)

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("🟢 Motori healthy", f"{healthy}/{len(health_rows)}", help="Motori il cui ultimo stato risulta regolare.")
k2.metric("🟠 Da verificare", failed, help="Motori FAILED, STALE o DEGRADED.")
k3.metric("🎯 Actionable", actionable, help="Confluenze che hanno superato i gate minimi per ulteriori verifiche.")
k4.metric("🧠 AI attive", ai_pending, help="TradingAgents PENDING o RUNNING.")
k5.metric("▶️ Manuali attive", manual_active, help="Richieste manuali non ancora concluse.")

main_tabs = st.tabs(["🏠 Home", "🏭 Produzione", "🧪 Laboratorio", "🛠️ Operations", "📚 Guida"])

with main_tabs[0]:
    st.subheader("Control Center")
    visual_cards([
        ("🏭", "Produzione", "CORE, FAST, Multi-Horizon, TradingAgents e decisioni operative."),
        ("🧪", "Laboratorio", "Ricerca, paper trading, backtest ed evoluzione delle strategie, separati dalla produzione."),
        ("🛠️", "Operations", "Run, log, richieste manuali, notifiche e architettura tecnica."),
        ("📚", "Guida", "Spiegazione delle pagine, dei motori e delle colonne principali."),
    ])
    st.markdown("### Stato motori")
    explain("Stato motori", "È la vista più veloce per capire se l'infrastruttura sta lavorando.", ["HEALTHY: regolare", "STALE: non gira da troppo tempo", "FAILED: ultimo run fallito", "RUNNING: esecuzione in corso"])
    if health_df.empty:
        st.info("Registry vuoto.")
    else:
        view = health_df.copy()
        status_col = "computed_health" if "computed_health" in view.columns else "registry_status"
        view["stato"] = view[status_col].map(badge)
        for c in ["last_started_at", "last_finished_at", "last_run_at", "next_expected_run_at"]:
            if c in view.columns:
                view[c] = view[c].map(utc_label)
        show_table(view, ["engine_id", "strategy", "market", "horizon", "stato", "last_started_at", "last_finished_at", "signals_found"], 50)
    left, right = st.columns(2)
    with left:
        st.markdown("### 🎯 Confluenze recenti")
        explain("Confluenze", "Riunisce i segnali dei motori sullo stesso ticker. Una doppia o tripla conferma pesa più di un singolo segnale.")
        if conf_df.empty:
            st.info("Nessuna confluenza registrata.")
        else:
            show_table(conf_df, ["detected_at", "market", "ticker", "signal_type", "conviction", "is_actionable"], 25)
    with right:
        st.markdown("### ⚙️ Attività per motore")
        st.caption("Numero di run registrati nel campione visualizzato.")
        if not run_df.empty and "engine_id" in run_df.columns:
            st.bar_chart(run_df.groupby("engine_id").size().sort_values(ascending=False))
        else:
            st.info("Nessun run disponibile.")

with main_tabs[1]:
    prod_tabs = st.tabs(["🎯 Decisioni", "⚙️ Motori", "📡 Segnali", "🧠 TradingAgents", "📈 Performance"])
    with prod_tabs[0]:
        st.subheader("Decision Board")
        st.markdown('<div class="section-note">Questa è la pagina da guardare per prima quando vuoi capire <b>cosa merita attenzione adesso</b>. Combina la confluenza dei motori con l’eventuale seconda opinione TradingAgents.</div>', unsafe_allow_html=True)
        explain("Decision Board", "Non è una lista di ordini. È una graduatoria decisionale.", ["SINGLE_SIGNAL = un solo motore positivo", "DOUBLE/TRIPLE_CONFIRMATION = più motori indipendenti concordano", "Actionable = supera i gate per il livello successivo", "CONFIRM/CAUTION/VETO = giudizio AI quando disponibile"])
        if decision_df.empty:
            st.info("Nessuna decisione aggregata disponibile.")
        else:
            only_action = st.checkbox("Mostra solo actionable", value=True, key="decision_action")
            view = decision_df.copy()
            if only_action and "is_actionable" in view.columns:
                view = view[view["is_actionable"] == True]
            if "ai_alignment" in view.columns:
                view["AI"] = view["ai_alignment"].map(badge)
            show_table(view, ["detected_at", "market", "ticker", "signal_type", "conviction", "is_actionable", "AI", "ai_confidence", "ai_verdict", "ai_summary"], 100)

    with prod_tabs[1]:
        st.subheader("Motori di produzione")
        visual_cards([
            ("🧭", "CORE", "Seleziona opportunità con orizzonte principale medio periodo."),
            ("⚡", "FAST", "Controlla condizioni operative e vicinanza alle zone di ingresso."),
            ("🔭", "Multi-Horizon", "Valida il titolo su orizzonti indipendenti senza duplicare CORE/FAST."),
            ("🧠", "TradingAgents", "Seconda opinione AI attivata solo quando la qualità del segnale lo giustifica."),
        ])
        explain("Motori", "Questa tab serve a capire se ogni componente sta girando con la frequenza prevista e se l'ultimo run è sano.")
        if not health_df.empty:
            view = health_df.copy()
            status_col = "computed_health" if "computed_health" in view.columns else "registry_status"
            view[status_col] = view[status_col].map(badge)
            for c in ["last_run_at", "last_started_at", "last_finished_at", "next_expected_run_at"]:
                if c in view.columns:
                    view[c] = view[c].map(utc_label)
            show_table(view, list(view.columns), 100)

    with prod_tabs[2]:
        st.subheader("Segnali di produzione")
        explain("Segnali", "Qui vedi il dato grezzo normalizzato dei motori. Per decidere cosa guardare davvero, usa poi Decision Board.", ["entry/stop/tp sono livelli del setup", "conviction indica forza, non garanzia", "is_actionable stabilisce se il segnale può avanzare"])
        if sig_df.empty:
            st.info("Nessun segnale registrato.")
        else:
            filters = st.columns(4)
            markets = ["TUTTI"] + sorted(sig_df["market"].dropna().astype(str).unique().tolist()) if "market" in sig_df.columns else ["TUTTI"]
            engines = ["TUTTI"] + sorted(sig_df["engine"].dropna().astype(str).unique().tolist()) if "engine" in sig_df.columns else ["TUTTI"]
            market = filters[0].selectbox("Mercato", markets)
            engine = filters[1].selectbox("Motore", engines)
            ticker = filters[2].text_input("Ticker contiene").strip().upper()
            only_action = filters[3].checkbox("Solo actionable")
            view = sig_df.copy()
            if market != "TUTTI": view = view[view["market"].astype(str) == market]
            if engine != "TUTTI": view = view[view["engine"].astype(str) == engine]
            if ticker and "ticker" in view.columns: view = view[view["ticker"].astype(str).str.upper().str.contains(ticker, regex=False)]
            if only_action and "is_actionable" in view.columns: view = view[view["is_actionable"] == True]
            show_table(view, ["detected_at", "market", "ticker", "engine", "strategy", "signal_type", "decision", "conviction", "price", "entry", "stop", "tp1", "tp2", "is_actionable"], 300)
            if "signal_type" in view.columns and not view.empty:
                st.bar_chart(view["signal_type"].fillna("UNKNOWN").value_counts())

    with prod_tabs[3]:
        st.subheader("TradingAgents")
        explain("TradingAgents", "È una seconda opinione, non il motore che genera da solo il segnale.", ["CONFIRM rafforza", "NEUTRAL non cambia la lettura", "CAUTION invita prudenza", "VETO segnala incompatibilità/rischio rilevante"])
        if ai_df.empty:
            st.info("Nessuna analisi AI registrata. È normale finché non scatta una confluenza qualificata.")
        else:
            show_table(ai_df, ["started_at", "completed_at", "market", "ticker", "status", "alignment", "confidence", "verdict", "summary", "trigger_reason", "entry", "stop", "tp1", "tp2", "error_message"], 200)
            if "alignment" in ai_df.columns:
                st.bar_chart(ai_df["alignment"].fillna("PENDING").value_counts())

    with prod_tabs[4]:
        st.subheader("Performance")
        explain("Performance", "Misura cosa è successo dopo i segnali. Serve a capire se una strategia mantiene valore nel tempo, non a valutare un singolo trade.", ["PnL% = rendimento dell'orizzonte", "Max drawdown = peggior arretramento peak-to-trough", "MFE = massimo movimento favorevole"])
        if not perf_summary_df.empty:
            show_table(perf_summary_df, list(perf_summary_df.columns), 300)
            if {"strategy", "avg_pnl_pct"}.issubset(perf_summary_df.columns):
                chart = perf_summary_df.copy()
                chart["avg_pnl_pct"] = pd.to_numeric(chart["avg_pnl_pct"], errors="coerce")
                st.bar_chart(chart.groupby("strategy")["avg_pnl_pct"].mean().dropna())
        elif perf_df.empty:
            st.info("I dati compariranno dopo che i segnali avranno maturato un orizzonte misurabile.")
        if not perf_df.empty:
            show_table(perf_df, ["created_at", "engine_id", "strategy", "market", "ticker", "outcome", "entry_price", "exit_price", "pnl_pct", "max_drawdown_pct", "max_favorable_excursion_pct", "holding_minutes"], 400)

with main_tabs[2]:
    lab_tabs = st.tabs(["🧪 Control Room", "🧾 Paper / Portfolio", "🔬 Ricerca & Backtest", "🧬 Strategy Evolution"])
    lab_mask = pd.Series(False, index=run_df.index) if not run_df.empty else pd.Series(dtype=bool)
    if not run_df.empty:
        for c in ["engine_id", "strategy"]:
            if c in run_df.columns:
                lab_mask = lab_mask | run_df[c].fillna("").astype(str).str.upper().str.contains("LAB|PAPER|RESEARCH|EVOLUTION", regex=True)
    lab_runs = run_df[lab_mask].copy() if not run_df.empty else pd.DataFrame()

    with lab_tabs[0]:
        st.subheader("Laboratory Control Room")
        st.warning("Il Laboratory è separato dalla produzione: può studiare, simulare e confrontare strategie senza cambiare i segnali live.")
        visual_cards([
            ("🧪", "Opportunity Feed", "Raccoglie opportunità da studiare senza trasformarle automaticamente in segnali di produzione."),
            ("🧾", "Paper Trading", "Simula posizioni e risultati senza ordini reali."),
            ("🔬", "Research", "Backtest e analisi periodiche per capire quali idee meritano di sopravvivere."),
            ("🧬", "Evolution", "Propone evoluzioni delle strategie in un percorso separato e controllato."),
        ])
        explain("Laboratorio", "Qui devi leggere tutto come sperimentazione. Nessun risultato del Laboratory deve essere confuso con un segnale operativo live.")
        if lab_runs.empty:
            st.info("Nessun run Laboratory è ancora presente nel registro centralizzato. I workflow Lab restano separati e verranno mostrati qui quando pubblicheranno i loro run nel DB centrale.")
        else:
            show_table(lab_runs, ["started_at", "finished_at", "engine_id", "strategy", "status", "records_processed", "signals_found", "error_message"], 100)

    with lab_tabs[1]:
        st.subheader("Paper / Portfolio")
        st.info("Vista riservata alle simulazioni. Al momento il nuovo schema centrale non espone ancora le vecchie tabelle paper-portfolio del branch Laboratory: preferisco dirtelo chiaramente invece di riempire la pagina di numeri decorativi.")
        if not perf_df.empty:
            st.caption("Nel frattempo puoi usare queste performance come misurazione post-segnale centralizzata.")
            show_table(perf_df, ["created_at", "strategy", "market", "ticker", "outcome", "entry_price", "exit_price", "pnl_pct", "max_drawdown_pct"], 100)

    with lab_tabs[2]:
        st.subheader("Ricerca & Backtest")
        st.markdown("**Workflow previsti:** Weekly Research e Strategy Lab backtest. Questa area deve diventare lo storico dei test, non un'altra copia della produzione.")
        if lab_runs.empty:
            st.info("Nessun risultato research centralizzato disponibile ancora.")
        else:
            show_table(lab_runs, list(lab_runs.columns), 150)

    with lab_tabs[3]:
        st.subheader("Strategy Evolution")
        st.markdown("Serve a confrontare varianti e promuovere solo ciò che dimostra un miglioramento misurabile. Nessuna strategia deve arrivare in produzione solo perché una curva backtest sembra fotogenica.")
        st.info("Quando l'evolution worker pubblicherà risultati strutturati nel DB, questa pagina mostrerà versione, baseline, delta KPI, decisione PROMOTE/REJECT e motivazione.")

with main_tabs[3]:
    ops_tabs = st.tabs(["📝 Run & Log", "▶️ Esegui ora", "🔔 Notifiche", "🏗️ Architettura"])
    with ops_tabs[0]:
        st.subheader("Run & Log")
        explain("Run", "Ogni riga è un'esecuzione di un motore. Parti da status; se è FAILED guarda error_message; poi confronta durata e signals_found con lo storico.")
        if not run_df.empty:
            show_table(run_df, ["started_at", "finished_at", "engine_id", "market", "strategy", "trigger_source", "status", "duration_seconds", "records_processed", "signals_found", "error_message"], 300)
        st.markdown("### Richieste manuali")
        explain("Richieste manuali", "Il percorso corretto è REQUESTED → DISPATCHED → RUNNING → SUCCESS. Un arresto intermedio indica un problema di dispatch o di workflow.")
        if request_df.empty:
            st.info("Nessuna richiesta manuale ancora.")
        else:
            show_table(request_df, ["requested_at", "engine_id", "market", "strategy", "requested_by", "status", "github_run_id", "run_id", "completed_at", "error_message"], 200)

    with ops_tabs[1]:
        st.subheader("Esegui ora")
        st.warning("Crea una richiesta in Supabase. L'Orchestrator la prende in carico e lancia il workflow GitHub: il browser non riceve token GitHub.")
        engines = [r for r in health_rows if str(r.get("engine_id") or "").upper() not in {"ORCHESTRATOR", "TRADINGAGENTS"}]
        labels = [f"{r.get('engine_id')} | {r.get('strategy')} | {r.get('market')}" for r in engines]
        selected = st.selectbox("Motore", labels, help="Scegli il motore da eseguire. TradingAgents non si avvia genericamente: viene chiamato dall'Orchestrator su un ticker qualificato.") if labels else None
        requested_by = st.text_input("Richiesto da", value="Antonio")
        if st.button("▶️ ESEGUI ORA", type="primary", disabled=not selected):
            row = engines[labels.index(selected)]
            created = request_run(str(row.get("engine_id")), str(row.get("market")), str(row.get("strategy") or ""), send_email=True, send_whatsapp=False, requested_by=requested_by)
            st.cache_data.clear()
            st.success(f"Richiesta creata: {created.get('request_id', 'OK')} · stato REQUESTED")

    with ops_tabs[2]:
        st.subheader("Notifiche")
        explain("Notifiche", "Qui controlli se una decisione finale è stata effettivamente inviata e se la deduplica ha evitato doppioni.", ["SENT = inviata", "FAILED = tentativo fallito", "SKIPPED = volutamente non inviata"])
        if notif_df.empty:
            st.info("Nessuna notifica registrata.")
        else:
            show_table(notif_df, ["attempted_at", "sent_at", "ticker", "event_type", "channel", "status", "provider", "error_message"], 400)
            if {"channel", "status"}.issubset(notif_df.columns):
                st.bar_chart(notif_df.groupby(["channel", "status"]).size())

    with ops_tabs[3]:
        st.subheader("Architettura logica")
        st.caption("Passa il mouse sui blocchi: ogni nodo contiene una descrizione rapida.")
        st.markdown(
            """
            <div class="flow">
              <div class="node" title="Motore medio periodo: seleziona opportunità e persiste i segnali.">🧭<br><b>CORE</b><br><small>3-6M</small></div>
              <div class="arrow">→</div>
              <div class="node" title="Supabase conserva segnali, run, AI, eventi, notifiche, richieste manuali e performance.">🗄️<br><b>Supabase</b><br><small>memoria centrale</small></div>
              <div class="arrow">→</div>
              <div class="node" title="Unisce i segnali, applica confluence, deduplica e decide quali livelli successivi attivare.">🧠<br><b>Orchestrator</b><br><small>coordina</small></div>
              <div class="arrow">→</div>
              <div class="node" title="Valida il titolo su più orizzonti indipendenti.">🔭<br><b>Multi-Horizon</b><br><small>validazione</small></div>
              <div class="arrow">→</div>
              <div class="node" title="Seconda opinione AI, chiamata solo su segnali qualificati.">🤖<br><b>TradingAgents</b><br><small>second opinion</small></div>
              <div class="arrow">→</div>
              <div class="node" title="Decisione finale deduplicata inviata sui canali configurati.">🔔<br><b>Alert finali</b><br><small>Email / WhatsApp</small></div>
            </div>
            <div class="flow">
              <div class="node" title="FAST controlla condizioni operative e vicinanza alle zone di ingresso.">⚡<br><b>FAST</b><br><small>monitor operativo</small></div>
              <div class="arrow">→</div>
              <div class="node" title="GitHub Actions esegue i workflow pianificati e manuali.">⚙️<br><b>GitHub Actions</b><br><small>execution layer</small></div>
              <div class="arrow">→</div>
              <div class="node" title="La dashboard legge Supabase e inserisce richieste manuali senza esporre token GitHub.">🖥️<br><b>Dashboard</b><br><small>control center</small></div>
              <div class="arrow">↔</div>
              <div class="node" title="Ambiente separato per paper trading, ricerca, backtest ed evoluzione strategie.">🧪<br><b>Laboratory</b><br><small>sperimentazione</small></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("**Sequenza tipica produzione:** CORE/FAST → Supabase → Confluence → Multi-Horizon → TradingAgents se qualificato → Decisione finale → Notifica → Performance.")

with main_tabs[4]:
    guide_tabs = st.tabs(["🗺️ Come usare il sito", "📖 Glossario", "⏱️ Cosa gira e quando"])
    with guide_tabs[0]:
        st.subheader("Come leggere la dashboard")
        st.markdown("""
        **1. Home**: guarda prima stato motori e confluenze recenti.  
        **2. Produzione → Decisioni**: è la vista operativa principale.  
        **3. Produzione → Segnali**: serve per entrare nel dettaglio tecnico del perché.  
        **4. TradingAgents**: controlla la seconda opinione solo quando è stata attivata.  
        **5. Performance**: valuta la strategia nel tempo, non il singolo segnale.  
        **6. Laboratorio**: tutto ciò che è sperimentale resta separato dalla produzione.  
        **7. Operations**: qui controlli run, errori, richieste manuali e notifiche.
        """)
        st.info("Sulle tabelle passa il mouse sul nome delle colonne: le colonne principali hanno un tooltip con il significato. Ogni sezione ha inoltre un box ℹ️ 'Come leggere'.")

    with guide_tabs[1]:
        st.subheader("Glossario essenziale")
        glossary = pd.DataFrame([
            ["Actionable", "Segnale che ha superato i gate minimi e può avanzare nel processo."],
            ["Confluence", "Accordo tra motori indipendenti sullo stesso ticker."],
            ["SINGLE_SIGNAL", "Una sola famiglia base positiva."],
            ["DOUBLE_CONFIRMATION", "Due famiglie base indipendenti positive."],
            ["TRIPLE_CONFIRMATION", "Tre famiglie base indipendenti positive."],
            ["Multi-Horizon", "Validazione indipendente su più orizzonti, non conta come duplicato di CORE/FAST."],
            ["CONFIRM", "TradingAgents allineato con la tesi."],
            ["CAUTION", "Tesi plausibile ma con rischi che richiedono prudenza."],
            ["VETO", "TradingAgents rileva una criticità incompatibile con la tesi."],
            ["STALE", "Motore che non ha eseguito un run valido entro la finestra attesa."],
            ["MFE", "Massimo movimento favorevole dopo il segnale."],
            ["Max Drawdown", "Peggior discesa peak-to-trough nella finestra osservata."],
        ], columns=["Termine", "Significato"])
        st.dataframe(glossary, use_container_width=True, hide_index=True)

    with guide_tabs[2]:
        st.subheader("Scheduler principali")
        st.markdown("""
        - **FAST**: controllo frequente nei giorni feriali, con gate sulla sessione di mercato.
        - **CORE Italia**: run giornaliero di fine sessione italiana.
        - **CORE USA**: run giornaliero dopo l'apertura/nel corso della sessione USA secondo il workflow configurato.
        - **Orchestrator**: ogni 15 minuti, per correlare i risultati e gestire dispatch/alert.
        - **Performance worker**: una volta al giorno nei feriali.
        - **Laboratory paper feed**: giornaliero feriale.
        - **Laboratory research / evolution**: settimanali.
        """)
        st.caption("Gli orari locali dipendono dall'offset UTC/ora legale. La fonte autorevole resta il cron GitHub Actions configurato nei workflow.")

st.caption(f"Snapshot dati: {snap['loaded_at']} · Pagina: {datetime.now().isoformat(timespec='seconds')}")
