from __future__ import annotations

import os
from datetime import datetime

import pandas as pd
import streamlit as st

try:
    from dashboard.data_access import (
        ai_analysis, core_high_conviction, engine_health, lab_backtest_results,
        lab_backtest_runs, lab_calibration_results, lab_paper_events,
        lab_paper_positions, lab_paper_signals, lab_signal_outcomes,
        lab_strategy_evaluations, lab_strategy_variants, lab_watchlist,
        latest_confluence, manual_requests, notifications, performance,
        performance_summary, request_run, runs, signals, system_events, utc_label,
    )
except ModuleNotFoundError:
    from data_access import (
        ai_analysis, core_high_conviction, engine_health, lab_backtest_results,
        lab_backtest_runs, lab_calibration_results, lab_paper_events,
        lab_paper_positions, lab_paper_signals, lab_signal_outcomes,
        lab_strategy_evaluations, lab_strategy_variants, lab_watchlist,
        latest_confluence, manual_requests, notifications, performance,
        performance_summary, request_run, runs, signals, system_events, utc_label,
    )

st.set_page_config(page_title="Trading Engine Control Center", page_icon="📈", layout="wide")
st.markdown("""
<style>
.block-container{padding-top:1rem;padding-bottom:2rem}.hero{padding:.8rem 1rem;border:1px solid rgba(128,128,128,.2);border-radius:14px;margin-bottom:.6rem}
.node{display:inline-block;border:1px solid rgba(128,128,128,.3);border-radius:12px;padding:10px 14px;margin:5px;background:rgba(128,128,128,.04);cursor:help}.node:hover{border-color:#4f83ff;box-shadow:0 4px 14px rgba(0,0,0,.08)}
.note{padding:.65rem .85rem;border-left:4px solid #4f83ff;background:rgba(79,131,255,.06);border-radius:7px;margin:.45rem 0 .8rem}
</style>
""", unsafe_allow_html=True)

HELP = {
    "engine_id":"Motore che ha prodotto il run o il segnale.","market":"Mercato di riferimento.","strategy":"Strategia applicata.",
    "status":"Stato del processo.","signal_type":"Tipo di segnale/conferma.","decision":"Decisione normalizzata.",
    "conviction":"Forza sintetica del setup.","is_actionable":"True = supera i gate minimi per avanzare.","ticker":"Titolo analizzato.",
    "entry":"Ingresso proposto.","stop":"Livello di protezione.","tp1":"Primo target.","tp2":"Secondo target.",
    "alignment":"Giudizio TradingAgents: CONFIRM/NEUTRAL/CAUTION/VETO.","pnl_pct":"Rendimento misurato nell'orizzonte.",
    "max_drawdown_pct":"Peggior drawdown peak-to-trough.","error_message":"Errore tecnico se presente.","score":"Punteggio del Laboratory.",
    "trigger":"Condizione che attiva il setup.","distance_to_entry_pct":"Distanza percentuale dall'ingresso.","opened_at":"Apertura paper position.",
}

def require_access():
    expected=(os.getenv("DASHBOARD_PASSWORD") or "").strip()
    if not expected or st.session_state.get("dashboard_auth"): return
    st.title("🔐 Trading Engine Control Center")
    pwd=st.text_input("Password",type="password")
    if st.button("Accedi",type="primary"):
        if pwd==expected: st.session_state["dashboard_auth"]=True; st.rerun()
        st.error("Password non valida")
    st.stop()

def df(rows): return pd.DataFrame(rows) if rows else pd.DataFrame()
def cols_cfg(cols): return {c:st.column_config.TextColumn(c,help=HELP[c]) for c in cols if c in HELP}
def show(frame, cols=None, limit=300):
    if frame.empty: st.info("Nessun dato disponibile."); return
    c=[x for x in (cols or list(frame.columns)) if x in frame.columns]
    st.dataframe(frame[c].head(limit),use_container_width=True,hide_index=True,column_config=cols_cfg(c))
def explain(title,text):
    with st.expander(f"ℹ️ Come leggere: {title}",expanded=False): st.write(text)
def badge(v):
    v=str(v or "UNKNOWN").upper(); icon={"HEALTHY":"🟢","SUCCESS":"🟢","CONFIRM":"🟢","RUNNING":"🔵","PENDING":"🟡","REQUESTED":"🟡","DISPATCHED":"🔵","STALE":"🟠","DEGRADED":"🟠","CAUTION":"🟠","FAILED":"🔴","VETO":"🔴"}.get(v,"⚪"); return f"{icon} {v}"

@st.cache_data(ttl=30,show_spinner=False)
def snapshot():
    return {
        "health":engine_health(),"signals":signals(1500),"conf":latest_confluence(400),"runs":runs(800),"ai":ai_analysis(500),"notifications":notifications(800),"events":system_events(500),"performance":performance(1500),"perf_summary":performance_summary(),"requests":manual_requests(300),
        "lab_watch":lab_watchlist(1500),"lab_positions":lab_paper_positions(1500),"lab_events":lab_paper_events(2500),"lab_signals":lab_paper_signals(1500),"lab_bt_runs":lab_backtest_runs(300),"lab_bt_results":lab_backtest_results(3000),"lab_calibration":lab_calibration_results(1500),"lab_outcomes":lab_signal_outcomes(5000),"lab_variants":lab_strategy_variants(1500),"lab_evals":lab_strategy_evaluations(5000),"core_high":core_high_conviction(1000),"loaded_at":datetime.now().isoformat(timespec="seconds")}

require_access()
head1,head2=st.columns([6,1])
with head1: st.markdown('<div class="hero"><h1>📈 Trading Engine Control Center</h1><div style="opacity:.7">Produzione, Laboratory, Operations e Guida.</div></div>',unsafe_allow_html=True)
with head2:
    if st.button("↻ Aggiorna",use_container_width=True,help="Rilegge i dati da Supabase."): st.cache_data.clear(); st.rerun()

try: s=snapshot()
except Exception as exc: st.error(f"Connessione dati non disponibile: {type(exc).__name__}: {exc}"); st.stop()

H,S,C,R,A,N,E,P,PS,Q=[df(s[x]) for x in ["health","signals","conf","runs","ai","notifications","events","performance","perf_summary","requests"]]
LW,LP,LE,LS,LBR,LBT,LC,LO,LV,LVE,CH=[df(s[x]) for x in ["lab_watch","lab_positions","lab_events","lab_signals","lab_bt_runs","lab_bt_results","lab_calibration","lab_outcomes","lab_variants","lab_evals","core_high"]]
healthy=sum(str(r.get("computed_health") or r.get("registry_status") or "").upper()=="HEALTHY" for r in s["health"])
issues=sum(str(r.get("computed_health") or r.get("registry_status") or "").upper() in {"FAILED","STALE","DEGRADED"} for r in s["health"])
actionable=sum(bool(r.get("is_actionable")) for r in s["conf"])
ai_active=sum(str(r.get("status") or "").upper() in {"PENDING","RUNNING"} for r in s["ai"])

k1,k2,k3,k4=st.columns(4); k1.metric("🟢 Motori healthy",f"{healthy}/{len(s['health'])}"); k2.metric("🟠 Da verificare",issues); k3.metric("🎯 Actionable",actionable); k4.metric("🧠 AI attive",ai_active)
main=st.tabs(["🏠 Home","🏭 Produzione","🧪 Laboratorio","🛠️ Operations","📚 Guida"])

with main[0]:
    # Home volutamente pulita: niente card descrittive ridondanti.
    st.subheader("Stato motori")
    explain("Stato motori","Parti dallo stato. HEALTHY è regolare; STALE non gira da troppo; FAILED indica errore. Poi guarda ultimo run e segnali prodotti.")
    if not H.empty:
        v=H.copy(); sc="computed_health" if "computed_health" in v.columns else "registry_status"; v["stato"]=v[sc].map(badge)
        for c in ["last_started_at","last_finished_at","last_run_at","next_expected_run_at"]:
            if c in v: v[c]=v[c].map(utc_label)
        show(v,["engine_id","strategy","market","horizon","stato","last_started_at","last_finished_at","signals_found"],50)
    a,b=st.columns(2)
    with a:
        st.subheader("🎯 Confluenze recenti"); show(C,["detected_at","market","ticker","signal_type","conviction","is_actionable"],30)
    with b:
        st.subheader("⚙️ Attività per motore")
        if not R.empty and "engine_id" in R: st.bar_chart(R.groupby("engine_id").size().sort_values(ascending=False))
        else: st.info("Nessun run disponibile.")

with main[1]:
    t=st.tabs(["🎯 Decisioni","⚙️ Motori","📡 Segnali","🧠 TradingAgents","📈 Performance"])
    with t[0]:
        st.subheader("Decision Board"); explain("Decisioni","Questa è la vista operativa principale. Le confluenze actionable sono quelle che possono avanzare a Multi-Horizon/TradingAgents.")
        show(C,["detected_at","market","ticker","signal_type","decision","conviction","is_actionable"],150)
    with t[1]: st.subheader("Motori di produzione"); show(H,None,150)
    with t[2]:
        st.subheader("Segnali"); show(S,["detected_at","market","ticker","engine","strategy","signal_type","decision","conviction","price","entry","stop","tp1","tp2","is_actionable"],400)
    with t[3]:
        st.subheader("TradingAgents"); explain("TradingAgents","Seconda opinione AI: non genera il segnale iniziale. Viene chiamato quando la confluenza supera i gate previsti."); show(A,["started_at","completed_at","market","ticker","status","alignment","confidence","verdict","summary","trigger_reason","entry","stop","tp1","tp2","error_message"],250)
    with t[4]:
        st.subheader("Performance"); show(PS,None,300); show(P,["created_at","engine_id","strategy","market","ticker","outcome","entry_price","exit_price","pnl_pct","max_drawdown_pct","max_favorable_excursion_pct","holding_minutes"],500)

with main[2]:
    lab=st.tabs(["📡 Signals","💼 Portfolio","🎯 Action Center","🔬 Backtest / Research","🧬 Strategy Evolution","⭐ Core Opportunities","🩺 Engine Health"])
    with lab[0]:
        st.subheader("Laboratory Signals"); explain("Lab Signals","È la scala opportunità sperimentale del vecchio sito: WATCH → NEAR_SETUP → PRE_BUY → PAPER_OPEN. Non sono ordini reali.")
        if not LW.empty:
            v=LW.copy(); order={"PAPER_OPEN":0,"PRE_BUY":1,"NEAR_SETUP":2,"WATCH":3}; v["_rank"]=v.get("status",pd.Series(index=v.index,dtype=str)).fillna("").astype(str).str.upper().map(order).fillna(9); v=v.sort_values(["_rank","score"],ascending=[True,False]).drop(columns="_rank")
            show(v,["symbol","strategy","status","score","trigger","price","entry","max_buy","distance_to_entry_pct","alert_type","alert_price","signal_date"],300)
        else: st.warning("lab_watchlist non contiene righe attive. Il feed Laboratory deve popolarla.")
        st.markdown("#### Paper signals"); show(LS,None,200)
    with lab[1]:
        st.subheader("Paper Portfolio"); explain("Portfolio","Posizioni simulate del Laboratory. OPEN/TP1_HIT restano aperte; nessun ordine broker viene inviato."); show(LP,["symbol","strategy","status","qty","capital","entry_price","last_price","stop_current","tp1","tp2","opened_at","last_checked_date"],300)
        st.markdown("#### Eventi paper"); show(LE,None,250)
    with lab[2]:
        st.subheader("Action Center"); explain("Action Center","Concentra ciò che è più vicino all'azione nel Laboratory: PRE_BUY, NEAR_SETUP e PAPER_OPEN.")
        if LW.empty: st.info("Nessuna opportunità Laboratory disponibile.")
        else:
            mask=LW.get("status",pd.Series(index=LW.index,dtype=str)).fillna("").astype(str).str.upper().isin(["PAPER_OPEN","PRE_BUY","NEAR_SETUP"]); show(LW[mask],["symbol","strategy","status","score","trigger","price","entry","max_buy","distance_to_entry_pct","stop","tp1","tp2"],100)
        st.markdown("#### Outcome sperimentali"); show(LO,None,200)
    with lab[3]:
        st.subheader("Backtest / Research"); explain("Backtest","Qui tornano i run e i risultati di ricerca del vecchio sito. Servono a confrontare strategie fuori dalla produzione."); show(LBR,None,150); show(LBT,None,300); st.markdown("#### Calibrazione"); show(LC,None,250)
    with lab[4]:
        st.subheader("Strategy Evolution"); explain("Evolution","Varianti e valutazioni sperimentali. Una variante deve dimostrare miglioramenti misurabili prima di essere promossa."); show(LV,None,250); show(LVE,None,400)
    with lab[5]:
        st.subheader("Core Opportunities"); explain("Core Opportunities","Vista dedicata alle opportunità CORE ad alta convinzione, mantenuta separata dalle simulazioni del Laboratory."); show(CH,None,300)
    with lab[6]:
        st.subheader("Engine Health"); show(H,None,200)
        st.markdown("#### Run recenti"); show(R,["started_at","finished_at","engine_id","market","strategy","trigger_source","status","duration_seconds","records_processed","signals_found","error_message"],300)

with main[3]:
    ops=st.tabs(["📝 Run & Log","▶️ Esegui ora","🔔 Notifiche"])
    with ops[0]:
        st.subheader("Run & Log"); show(R,["started_at","finished_at","engine_id","market","strategy","trigger_source","status","duration_seconds","records_processed","signals_found","error_message"],400)
        st.markdown("#### System events"); show(E,["occurred_at","engine_id","run_id","severity","event_type","message","details"],300)
        st.markdown("#### Richieste manuali"); show(Q,["requested_at","engine_id","market","strategy","requested_by","status","github_run_id","run_id","completed_at","error_message"],250)
    with ops[1]:
        st.subheader("Esegui ora"); st.warning("La dashboard crea una richiesta in Supabase. L'Orchestrator la prende in carico e lancia GitHub Actions.")
        engines=[r for r in s["health"] if str(r.get("engine_id") or "").upper() not in {"ORCHESTRATOR","TRADINGAGENTS"}]; labels=[f"{r.get('engine_id')} | {r.get('strategy')} | {r.get('market')}" for r in engines]; selected=st.selectbox("Motore",labels) if labels else None
        who=st.text_input("Richiesto da",value="Antonio")
        if st.button("▶️ ESEGUI ORA",type="primary",disabled=not selected):
            row=engines[labels.index(selected)]; created=request_run(str(row.get("engine_id")),str(row.get("market")),str(row.get("strategy") or ""),send_email=True,send_whatsapp=False,requested_by=who); st.cache_data.clear(); st.success(f"Richiesta {created.get('request_id','OK')} creata in stato REQUESTED")
    with ops[2]:
        st.subheader("Notifiche"); explain("Notifiche","L'alert finale richiede una confluenza actionable e una analisi TradingAgents SUCCESS. Se non esistono questi due elementi, zero mail/WhatsApp è comportamento corretto.")
        c1,c2,c3=st.columns(3); c1.metric("Confluenze actionable",actionable); ai_success=sum(str(x.get("status") or "").upper()=="SUCCESS" for x in s["ai"]); c2.metric("AI SUCCESS",ai_success); c3.metric("Notifiche registrate",len(s["notifications"])); show(N,["attempted_at","sent_at","ticker","event_type","channel","status","provider","error_message"],400)

with main[4]:
    guide=st.tabs(["🔎 Cerca","🗺️ Come usare","📖 Glossario","⏱️ Scheduler","🏗️ Architettura & PDF"])
    topics={
        "Decision Board":"Vista operativa delle confluenze prodotte dall'Orchestrator.","Actionable":"True significa che il segnale supera i gate minimi per avanzare.","CORE":"Motore medio periodo.","FAST":"Monitor operativo delle zone di ingresso.","Multi-Horizon":"Validazione indipendente su più orizzonti.","TradingAgents":"Seconda opinione AI su segnali qualificati.","Laboratory":"Area separata per paper trading, ricerca, backtest ed evolution.","PRE_BUY":"Setup vicino all'attivazione ma non ancora ingresso.","PAPER_OPEN":"Posizione simulata aperta dal Laboratory.","FAILED":"Il processo è terminato con errore.","STALE":"Il motore non ha eseguito un run valido entro il tempo previsto.","VETO":"TradingAgents rileva una criticità incompatibile con la tesi.","Max Drawdown":"Peggior perdita peak-to-trough nella finestra osservata."}
    with guide[0]:
        q=st.text_input("Cerca nella guida",placeholder="es. PRE_BUY, TradingAgents, FAILED...").strip().lower(); matches=[(k,v) for k,v in topics.items() if not q or q in k.lower() or q in v.lower()]
        for k,v in matches: st.markdown(f"**{k}**  \n{v}")
    with guide[1]: st.markdown("**Ordine consigliato:** Home → Produzione/Decisioni → Segnali → TradingAgents → Performance. Il Laboratory resta separato per test e paper trading. Operations serve a controllare run, errori e notifiche. Passa il mouse sui nomi delle colonne per il significato.")
    with guide[2]:
        g=pd.DataFrame(list(topics.items()),columns=["Termine","Significato"]); st.dataframe(g,use_container_width=True,hide_index=True)
    with guide[3]: st.markdown("- **FAST**: controllo frequente nei feriali con gate sessione.\n- **CORE Italia/USA**: run giornalieri secondo cron.\n- **Orchestrator**: ogni 15 minuti.\n- **Performance worker**: giornaliero feriale.\n- **Laboratory opportunity feed**: feriale.\n- **Research / Evolution**: settimanali.\n\nLa fonte autorevole degli orari resta GitHub Actions.")
    with guide[4]:
        st.caption("Passa il mouse sui blocchi per una descrizione rapida.")
        st.markdown('<div><span class="node" title="Motore medio periodo">🧭 CORE</span> → <span class="node" title="Memoria centrale: segnali, run, AI, eventi, performance">🗄️ Supabase</span> → <span class="node" title="Confluence, dispatch e deduplica">🧠 Orchestrator</span> → <span class="node" title="Validazione multi-timeframe">🔭 Multi-Horizon</span> → <span class="node" title="Seconda opinione AI">🤖 TradingAgents</span> → <span class="node" title="Alert finali qualificati">🔔 Email/WhatsApp</span></div>',unsafe_allow_html=True)
        st.markdown('<div><span class="node" title="Monitor operativo">⚡ FAST</span> → <span class="node" title="Esecuzione workflow">⚙️ GitHub Actions</span> ↔ <span class="node" title="Control Center">🖥️ Dashboard</span> ↔ <span class="node" title="Paper, backtest, research ed evolution separati dalla produzione">🧪 Laboratory</span></div>',unsafe_allow_html=True)
        st.link_button("📄 Apri PDF Guida e Architettura","https://github.com/antoannali-ita/trading-engine-v2/blob/main/docs/Trading_Engine_Guida_Architettura_2026-08-21.pdf")

st.caption(f"Snapshot: {s['loaded_at']} · Pagina: {datetime.now().isoformat(timespec='seconds')}")
