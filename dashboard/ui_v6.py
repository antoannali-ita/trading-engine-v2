from __future__ import annotations

import html
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
.block-container{padding-top:1rem;padding-bottom:4rem}.hero{padding:.8rem 1rem;border:1px solid rgba(128,128,128,.2);border-radius:14px;margin-bottom:.6rem}
.note{padding:.65rem .85rem;border-left:4px solid #4f83ff;background:rgba(79,131,255,.06);border-radius:7px;margin:.45rem 0 .8rem}
.arch-wrap{display:flex;flex-wrap:wrap;gap:9px;align-items:center;margin:10px 0 16px;overflow:visible}.arch-arrow{opacity:.6;font-size:18px}.arch-node{position:relative;display:inline-block;border:1px solid rgba(128,128,128,.3);border-radius:12px;padding:10px 14px;background:rgba(128,128,128,.04);cursor:help}.arch-node:hover{border-color:#4f83ff;box-shadow:0 4px 14px rgba(0,0,0,.08)}
.arch-node:hover:after{content:attr(data-tip);position:absolute;left:0;top:calc(100% + 8px);z-index:9999;width:320px;white-space:normal;background:#111827;color:#fff;padding:10px 12px;border-radius:8px;font-size:12px;line-height:1.4;box-shadow:0 8px 24px rgba(0,0,0,.28)}
.site-footer{margin-top:36px;padding-top:14px;border-top:1px solid rgba(128,128,128,.25);text-align:center;opacity:.72;font-size:.84rem}
</style>
""", unsafe_allow_html=True)

HELP = {
    "engine_id":"Motore che ha prodotto il run o il segnale.","engine":"Famiglia del motore sorgente.","market":"Mercato di riferimento.","strategy":"Strategia applicata.","status":"Stato del processo o del setup.","signal_type":"Tipo di segnale/conferma.","decision":"Decisione normalizzata.","conviction":"Forza sintetica del setup.","is_actionable":"True = supera i gate minimi per avanzare.","ticker":"Titolo analizzato.","symbol":"Ticker del titolo nel Laboratory.","entry":"Ingresso proposto.","stop":"Livello di protezione.","tp1":"Primo target.","tp2":"Secondo target.","max_buy":"Prezzo massimo oltre cui non inseguire il setup.","alignment":"Giudizio TradingAgents: CONFIRM/NEUTRAL/CAUTION/VETO.","pnl_pct":"Rendimento misurato nell'orizzonte.","max_drawdown_pct":"Peggior drawdown peak-to-trough.","error_message":"Errore tecnico se presente.","score":"Punteggio del Laboratory.","trigger":"Condizione che attiva il setup.","distance_to_entry_pct":"Distanza percentuale dall'ingresso.","opened_at":"Data e ora di apertura della paper position.","detected_at":"Data e ora in cui il segnale è stato rilevato.","created_at":"Data e ora di creazione del record.","updated_at":"Data e ora dell'ultimo aggiornamento.","started_at":"Data e ora di avvio.","finished_at":"Data e ora di fine.","completed_at":"Data e ora di completamento.","occurred_at":"Data e ora dell'evento.","attempted_at":"Data e ora del tentativo di notifica.","sent_at":"Data e ora dell'invio.","signal_date":"Data logica del segnale. Se esiste created_at, quest'ultimo contiene anche l'ora reale.","source_signal_id":"Segnale padre/origine da cui deriva questo record.","parent_signal_id":"Segnale padre/origine.","signal_role":"Ruolo genealogico: PARENT, CHILD o DERIVED quando disponibile.","alert_type":"Tipo di alert prodotto dal Laboratory.","alert_price":"Prezzo associato all'alert.",
}
TIMESTAMP_COLS={"created_at","updated_at","detected_at","started_at","finished_at","completed_at","occurred_at","attempted_at","sent_at","opened_at","requested_at","dispatched_at","last_started_at","last_finished_at","last_run_at","next_expected_run_at","period_start","period_end"}

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
def _fmt_frame(frame):
    out=frame.copy()
    for c in out.columns:
        if c in TIMESTAMP_COLS or c.endswith("_at"):
            out[c]=out[c].map(utc_label)
    return out

def cols_cfg(cols): return {c:st.column_config.TextColumn(c,help=HELP[c]) for c in cols if c in HELP}
def show(frame, cols=None, limit=300):
    if frame.empty: st.info("Nessun dato disponibile."); return
    v=_fmt_frame(frame); c=[x for x in (cols or list(v.columns)) if x in v.columns]
    st.dataframe(v[c].head(limit),use_container_width=True,hide_index=True,column_config=cols_cfg(c))
def explain(title,text):
    with st.expander(f"ℹ️ Come leggere: {title}",expanded=False): st.write(text)
def badge(v):
    v=str(v or "UNKNOWN").upper(); icon={"HEALTHY":"🟢","SUCCESS":"🟢","CONFIRM":"🟢","RUNNING":"🔵","PENDING":"🟡","REQUESTED":"🟡","DISPATCHED":"🔵","STALE":"🟠","DEGRADED":"🟠","CAUTION":"🟠","FAILED":"🔴","VETO":"🔴"}.get(v,"⚪"); return f"{icon} {v}"
def footer(): st.markdown('<div class="site-footer">© 2026 Tutti i diritti riservati a <strong>Larocca Antonio</strong> · Trading Engine Control Center</div>',unsafe_allow_html=True)
def arch_node(label,tip): return f'<span class="arch-node" data-tip="{html.escape(tip,quote=True)}">{label}</span>'
def architecture():
    row1=[("🧭 CORE","Motore 3-6 mesi. Scansiona il mercato, calcola qualità/opportunità, Buy Zone, entry, stop e target. Produce i segnali base che alimentano Supabase e l'Orchestrator."),("🗄️ Supabase","Memoria centrale. Conserva motori, run, segnali, relazioni padre-figlio tramite source_signal_id, analisi AI, notifiche, eventi e performance."),("🧠 Orchestrator","Coordinatore centrale. Legge i segnali dei motori, costruisce le confluenze, evita duplicazioni e decide se invocare Multi-Horizon e TradingAgents."),("🔭 Multi-Horizon","Validazione indipendente su più orizzonti. Non sostituisce CORE/FAST: aggiunge una conferma tecnica separata prima dell'eventuale analisi AI."),("🤖 TradingAgents","Seconda opinione AI sui casi qualificati. Produce alignment, rischi, catalyst e verdetto; non genera il segnale iniziale."),("🔔 Email/WhatsApp","Canali finali. Gli alert Orchestrator partono solo quando esistono i requisiti previsti; CORE e FAST possono avere anche notifiche proprie.")]
    row2=[("⚡ FAST","Monitor operativo intraday. Controlla frequentemente i titoli già selezionati e segnala cambi di stato come ingresso in Buy Zone o Stop."),("⚙️ GitHub Actions","Scheduler ed esecutore dei workflow. Avvia CORE, FAST, Orchestrator, performance worker e i job del Laboratory secondo i cron configurati."),("🖥️ Dashboard","Control Center di gestione/lettura. Mostra stato, segnali, AI, performance, log e consente richieste manuali senza esporre i secret al browser."),("🧪 Laboratory","Ambiente separato dalla produzione per opportunity feed, paper trading, backtest, research e strategy evolution. Le strategie sperimentali non diventano produzione automaticamente.")]
    st.markdown('<div class="arch-wrap">'+'<span class="arch-arrow">→</span>'.join(arch_node(a,b) for a,b in row1)+'</div>',unsafe_allow_html=True)
    st.markdown('<div class="arch-wrap">'+'<span class="arch-arrow">↔</span>'.join(arch_node(a,b) for a,b in row2)+'</div>',unsafe_allow_html=True)

@st.cache_data(ttl=30,show_spinner=False)
def snapshot():
    return {"health":engine_health(),"signals":signals(1500),"conf":latest_confluence(400),"runs":runs(800),"ai":ai_analysis(500),"notifications":notifications(800),"events":system_events(500),"performance":performance(1500),"perf_summary":performance_summary(),"requests":manual_requests(300),"lab_watch":lab_watchlist(1500),"lab_positions":lab_paper_positions(1500),"lab_events":lab_paper_events(2500),"lab_signals":lab_paper_signals(1500),"lab_bt_runs":lab_backtest_runs(300),"lab_bt_results":lab_backtest_results(3000),"lab_calibration":lab_calibration_results(1500),"lab_outcomes":lab_signal_outcomes(5000),"lab_variants":lab_strategy_variants(1500),"lab_evals":lab_strategy_evaluations(5000),"core_high":core_high_conviction(1000),"loaded_at":datetime.now().astimezone().isoformat(timespec="seconds")}

require_access()
head1,head2=st.columns([6,1])
with head1: st.markdown('<div class="hero"><h1>📈 Trading Engine Control Center</h1><div style="opacity:.7">Produzione, Laboratory, Operations e Guida.</div></div>',unsafe_allow_html=True)
with head2:
    if st.button("↻ Aggiorna",use_container_width=True,help="Rilegge i dati da Supabase."): st.cache_data.clear(); st.rerun()
try: s=snapshot()
except Exception as exc: st.error(f"Connessione dati non disponibile: {type(exc).__name__}: {exc}"); st.stop()
H,S,C,R,A,N,E,P,PS,Q=[df(s[x]) for x in ["health","signals","conf","runs","ai","notifications","events","performance","perf_summary","requests"]]
LW,LP,LE,LS,LBR,LBT,LC,LO,LV,LVE,CH=[df(s[x]) for x in ["lab_watch","lab_positions","lab_events","lab_signals","lab_bt_runs","lab_bt_results","lab_calibration","lab_outcomes","lab_variants","lab_evals","core_high"]]
healthy=sum(str(r.get("computed_health") or r.get("registry_status") or "").upper()=="HEALTHY" for r in s["health"]); issues=sum(str(r.get("computed_health") or r.get("registry_status") or "").upper() in {"FAILED","STALE","DEGRADED"} for r in s["health"]); actionable=sum(bool(r.get("is_actionable")) for r in s["conf"]); ai_active=sum(str(r.get("status") or "").upper() in {"PENDING","RUNNING"} for r in s["ai"])
k1,k2,k3,k4=st.columns(4); k1.metric("🟢 Motori healthy",f"{healthy}/{len(s['health'])}"); k2.metric("🟠 Da verificare",issues); k3.metric("🎯 Actionable",actionable); k4.metric("🧠 AI attive",ai_active)
main=st.tabs(["🏠 Home","🏭 Produzione","🧪 Laboratorio","🛠️ Operations","📚 Guida"])
with main[0]:
    st.subheader("Stato motori"); explain("Stato motori","HEALTHY è regolare; STALE non gira da troppo; FAILED indica errore. Le date includono l'ora quando il database dispone di un timestamp reale.")
    if not H.empty:
        v=H.copy(); sc="computed_health" if "computed_health" in v.columns else "registry_status"; v["stato"]=v[sc].map(badge); show(v,["engine_id","strategy","market","horizon","stato","last_started_at","last_finished_at","signals_found"],50)
    a,b=st.columns(2)
    with a: st.subheader("🎯 Confluenze recenti"); show(C,["detected_at","market","ticker","signal_type","conviction","is_actionable"],30)
    with b:
        st.subheader("⚙️ Attività per motore")
        if not R.empty and "engine_id" in R: st.bar_chart(R.groupby("engine_id").size().sort_values(ascending=False))
        else: st.info("Nessun run disponibile.")
with main[1]:
    t=st.tabs(["🎯 Decisioni","⚙️ Motori","📡 Segnali","🧠 TradingAgents","📈 Performance"])
    with t[0]: st.subheader("Decision Board"); explain("Decisioni","Le confluenze actionable sono quelle che possono avanzare a Multi-Horizon/TradingAgents."); show(C,["detected_at","market","ticker","signal_type","decision","conviction","is_actionable"],150)
    with t[1]: st.subheader("Motori di produzione"); explain("Motori","Mostra salute, ultimo run, prossimo run atteso e strategia associata."); show(H,None,150)
    with t[2]: st.subheader("Segnali"); explain("Segnali e genealogia","source_signal_id è il collegamento padre-figlio: se valorizzato, il segnale corrente deriva da quel segnale origine. I segnali senza source_signal_id sono sorgenti/padri o segnali indipendenti."); show(S,["detected_at","market","ticker","engine","strategy","signal_type","decision","conviction","price","entry","stop","tp1","tp2","is_actionable","signal_id","source_signal_id"],400)
    with t[3]: st.subheader("TradingAgents"); explain("TradingAgents","Seconda opinione AI: non genera il segnale iniziale. source_signal_id collega l'analisi al segnale/confluenza che l'ha attivata."); show(A,["started_at","completed_at","market","ticker","status","alignment","confidence","verdict","summary","trigger_reason","source_signal_id","entry","stop","tp1","tp2","error_message"],250)
    with t[4]: st.subheader("Performance"); explain("Performance","Misura gli esiti dei segnali nel tempo, inclusi P&L, drawdown e durata."); show(PS,None,300); show(P,["created_at","engine_id","strategy","market","ticker","signal_id","outcome","entry_price","exit_price","pnl_pct","max_drawdown_pct","max_favorable_excursion_pct","holding_minutes"],500)
with main[2]:
    lab=st.tabs(["📡 Signals","💼 Portfolio","🎯 Action Center","🔬 Backtest / Research","🧬 Strategy Evolution","⭐ Core Opportunities","🩺 Engine Health"])
    with lab[0]:
        st.subheader("Laboratory Signals"); explain("Lab Signals","Scala sperimentale: WATCH → NEAR_SETUP → PRE_BUY → PAPER_OPEN. created_at/updated_at mostrano l'ora reale quando presente; signal_date resta la data logica. Il vecchio schema Lab non impone un parent_signal_id: se una tabella lo contiene viene mostrato, altrimenti non viene inventato.")
        if not LW.empty:
            v=LW.copy(); order={"PAPER_OPEN":0,"PRE_BUY":1,"NEAR_SETUP":2,"WATCH":3}; v["_rank"]=v.get("status",pd.Series(index=v.index,dtype=str)).fillna("").astype(str).str.upper().map(order).fillna(9); v=v.sort_values(["_rank","score"],ascending=[True,False]).drop(columns="_rank"); base=["symbol","strategy","status","score","trigger","price","entry","max_buy","distance_to_entry_pct","alert_type","alert_price","signal_date","created_at","updated_at"]; genealogy=[x for x in ["signal_id","source_signal_id","parent_signal_id","signal_role"] if x in v.columns]; show(v,base+genealogy,300)
        else: st.warning("lab_watchlist non contiene righe attive. Il feed Laboratory deve popolarla.")
        st.markdown("#### Paper signals"); show(LS,None,200)
    with lab[1]: st.subheader("Paper Portfolio"); explain("Portfolio","Posizioni simulate. OPEN/TP1_HIT restano aperte; nessun ordine broker viene inviato."); show(LP,["symbol","strategy","status","qty","capital","entry_price","last_price","stop_current","tp1","tp2","opened_at","created_at","updated_at","last_checked_date"],300); st.markdown("#### Eventi paper"); show(LE,None,250)
    with lab[2]:
        st.subheader("Action Center"); explain("Action Center","Concentra PRE_BUY, NEAR_SETUP e PAPER_OPEN, cioè ciò che è più vicino a un'azione simulata.")
        if LW.empty: st.info("Nessuna opportunità Laboratory disponibile.")
        else:
            mask=LW.get("status",pd.Series(index=LW.index,dtype=str)).fillna("").astype(str).str.upper().isin(["PAPER_OPEN","PRE_BUY","NEAR_SETUP"]); show(LW[mask],["created_at","symbol","strategy","status","score","trigger","price","entry","max_buy","distance_to_entry_pct","stop","tp1","tp2"],100)
        st.markdown("#### Outcome sperimentali"); show(LO,None,200)
    with lab[3]: st.subheader("Backtest / Research"); explain("Backtest","Run e risultati di ricerca fuori dalla produzione. COMPLETED indica che il job ha terminato; i risultati servono a confrontare strategie, non ad autorizzare ordini reali."); show(LBR,None,150); show(LBT,None,300); st.markdown("#### Calibrazione"); show(LC,None,250)
    with lab[4]: st.subheader("Strategy Evolution"); explain("Evolution","Varianti e valutazioni sperimentali. Una variante deve dimostrare miglioramenti misurabili prima di poter essere considerata per una futura promozione."); show(LV,None,250); show(LVE,None,400)
    with lab[5]: st.subheader("Core Opportunities"); explain("Core Opportunities","Opportunità CORE ad alta convinzione, mantenute separate dalle simulazioni Laboratory."); show(CH,None,300)
    with lab[6]: st.subheader("Engine Health"); explain("Engine Health","Controlla motori, errori e freschezza delle esecuzioni."); show(H,None,200); st.markdown("#### Run recenti"); show(R,["started_at","finished_at","engine_id","market","strategy","trigger_source","status","duration_seconds","records_processed","signals_found","error_message"],300)
with main[3]:
    ops=st.tabs(["📝 Run & Log","▶️ Esegui ora","🔔 Notifiche"])
    with ops[0]: st.subheader("Run & Log"); explain("Run & Log","Qui trovi l'ora esatta di avvio/fine e gli eventi tecnici. ERROR/CRITICAL richiedono verifica."); show(R,["started_at","finished_at","engine_id","market","strategy","trigger_source","status","duration_seconds","records_processed","signals_found","error_message"],400); st.markdown("#### System events"); show(E,["occurred_at","engine_id","run_id","severity","event_type","message","details"],300); st.markdown("#### Richieste manuali"); show(Q,["requested_at","engine_id","market","strategy","requested_by","status","github_run_id","run_id","completed_at","error_message"],250)
    with ops[1]:
        st.subheader("Esegui ora"); st.warning("La dashboard crea una richiesta in Supabase. L'Orchestrator la prende in carico e lancia GitHub Actions.")
        engines=[r for r in s["health"] if str(r.get("engine_id") or "").upper() not in {"ORCHESTRATOR","TRADINGAGENTS"}]; labels=[f"{r.get('engine_id')} | {r.get('strategy')} | {r.get('market')}" for r in engines]; selected=st.selectbox("Motore",labels) if labels else None; who=st.text_input("Richiesto da",value="Antonio")
        if st.button("▶️ ESEGUI ORA",type="primary",disabled=not selected): row=engines[labels.index(selected)]; created=request_run(str(row.get("engine_id")),str(row.get("market")),str(row.get("strategy") or ""),send_email=True,send_whatsapp=False,requested_by=who); st.cache_data.clear(); st.success(f"Richiesta {created.get('request_id','OK')} creata in stato REQUESTED")
    with ops[2]:
        st.subheader("Notifiche"); explain("Notifiche","L'alert finale Orchestrator richiede confluenza actionable + TradingAgents SUCCESS. CORE e FAST possono produrre notifiche proprie secondo le loro regole.")
        c1,c2,c3=st.columns(3); c1.metric("Confluenze actionable",actionable); ai_success=sum(str(x.get("status") or "").upper()=="SUCCESS" for x in s["ai"]); c2.metric("AI SUCCESS",ai_success); c3.metric("Notifiche registrate",len(s["notifications"])); show(N,["attempted_at","sent_at","ticker","event_type","channel","status","provider","error_message"],400)
with main[4]:
    guide=st.tabs(["🔎 Cerca","🗺️ Come usare","📖 Glossario","⏱️ Scheduler","🏗️ Architettura","📘 Guida completa"])
    topics={"Decision Board":"Vista operativa delle confluenze prodotte dall'Orchestrator.","Actionable":"True significa che il segnale supera i gate minimi per avanzare.","CORE":"Motore 3-6 mesi che produce i segnali base.","FAST":"Monitor operativo frequente delle zone di ingresso e stop.","Supabase":"Memoria centrale del sistema.","Orchestrator":"Coordina i motori, costruisce confluenze e decide i dispatch.","Multi-Horizon":"Validazione indipendente su più orizzonti.","TradingAgents":"Seconda opinione AI su segnali qualificati.","Laboratory":"Area separata per paper trading, ricerca, backtest ed evolution.","PRE_BUY":"Setup vicino all'attivazione ma non ancora ingresso.","NEAR_SETUP":"Setup promettente che non ha ancora raggiunto i gate PRE_BUY.","PAPER_OPEN":"Posizione simulata aperta dal Laboratory.","BLOCKED_DATA":"Setup bloccato perché i dati non sono sufficienti/affidabili; non equivale a segnale negativo.","FAILED":"Il processo è terminato con errore.","STALE":"Il motore non ha eseguito un run valido entro il tempo previsto.","VETO":"TradingAgents rileva una criticità incompatibile con la tesi.","source_signal_id":"Collegamento padre-figlio: identifica il segnale origine.","Max Drawdown":"Peggior perdita peak-to-trough nella finestra osservata."}
    with guide[0]:
        q=st.text_input("Cerca nella guida",placeholder="es. PRE_BUY, TradingAgents, FAILED...").strip().lower(); matches=[(k,v) for k,v in topics.items() if not q or q in k.lower() or q in v.lower()]
        for k,v in matches: st.markdown(f"**{k}**  \n{v}")
    with guide[1]: st.markdown("""### Percorso consigliato
1. **Home**: controlla salute dei motori e freschezza dei run.
2. **Produzione → Decisioni**: guarda le confluenze e se sono actionable.
3. **Produzione → Segnali**: ricostruisci segnale, motore sorgente e genealogia padre-figlio.
4. **TradingAgents**: verifica l'eventuale seconda opinione AI.
5. **Performance**: misura cosa è successo dopo i segnali.
6. **Laboratorio**: paper trading, backtest e strategy evolution restano separati dalla produzione.
7. **Operations**: controlla run, errori, richieste manuali e notifiche.

I timestamp tecnici sono mostrati come **GG/MM/AAAA HH:MM**. Una semplice `signal_date` resta solo una data se il database non ha memorizzato l'ora.""")
    with guide[2]: st.dataframe(pd.DataFrame(list(topics.items()),columns=["Termine","Significato"]),use_container_width=True,hide_index=True)
    with guide[3]: st.markdown("""### Scheduler operativo
- **FAST**: ogni 5 minuti nei feriali nella finestra cron, con gate della sessione reale.
- **CORE Italia**: `40 15 * * 1-5` → 17:40 CEST in estate.
- **CORE USA**: `0 17 * * 1-5` → 19:00 CEST in estate.
- **Orchestrator**: ogni 15 minuti.
- **Performance worker**: giornaliero feriale.
- **Laboratory Opportunity Feed**: `30 21 * * 1-5` → 23:30 CEST in estate.
- **Laboratory Research**: sabato `30 6 * * 6` → 08:30 CEST in estate.
- **Strategy Evolution**: sabato `30 7 * * 6` → 09:30 CEST in estate.

Con ora solare italiana gli equivalenti locali cambiano di un'ora.""")
    with guide[4]: st.caption("Passa il mouse sui blocchi: compare la descrizione completa del componente."); architecture()
    with guide[5]:
        st.markdown("""## Guida completa al Trading Engine
### 1. Scopo
Il **Trading Engine Control Center** è il punto unico per leggere produzione, orchestrazione, Laboratory, performance e stato tecnico. L'Orchestrator è un coordinatore: non sostituisce le strategie finanziarie dei singoli motori.

### 2. Flusso di produzione
**CORE / FAST → Supabase → Orchestrator → Multi-Horizon → TradingAgents → Email/WhatsApp**. CORE e FAST producono segnali secondo regole proprie. Supabase conserva lo stato. L'Orchestrator normalizza e correla. Multi-Horizon aggiunge una validazione indipendente. TradingAgents viene invocato nei casi previsti. Le notifiche finali vengono deduplicate e inviate solo quando i gate richiesti sono soddisfatti.

### 3. Come leggere le decisioni
- **SINGLE_SIGNAL**: un solo motore base positivo.
- **DOUBLE_CONFIRMATION**: due motori base coerenti.
- **TRIPLE_CONFIRMATION**: tre motori base coerenti.
- **Actionable = True**: la confluenza può avanzare nel workflow previsto.
- **CONFIRM / NEUTRAL / CAUTION / VETO**: giudizio TradingAgents.

### 4. Produzione
**Decisioni** è la vista principale. **Motori** mostra salute e run. **Segnali** contiene i record e `source_signal_id`, cioè il padre del segnale derivato. **TradingAgents** mostra la seconda opinione. **Performance** misura l'esito successivo.

### 5. Laboratory
Il Laboratory è separato dalla produzione. Pipeline: **WATCH → NEAR_SETUP → PRE_BUY → PAPER_OPEN → OUTCOME → BACKTEST → STRATEGY EVOLUTION**. `BLOCKED_DATA` significa setup sospeso per insufficienza/qualità dati. Nessuna posizione Laboratory genera ordini broker reali.

### 6. Padre / figlio e adattamento strategie
Nel modello centrale `signals.source_signal_id` collega un segnale derivato al segnale origine. Le tabelle Laboratory storiche non impongono una genealogia uniforme: la dashboard mostra i campi parent/source quando esistono e non inventa relazioni assenti. Strategy Evolution resta separata e deve essere validata prima di una futura promozione.

### 7. Operations e notifiche
`Run & Log` mostra orari, durata, stato ed errori. `Esegui ora` crea una richiesta controllata in Supabase. `Notifiche` distingue zero notifiche corrette da errori di delivery. CORE/FAST possono avere canali propri oltre al notifier finale.

### 8. Timestamp
Quando esiste un `timestamptz` (`created_at`, `detected_at`, `started_at`, ecc.) il sito mostra **data e ora**. Campi `date`, come alcune vecchie `signal_date`, non contengono un'ora: il sito affianca `created_at/updated_at` quando disponibile invece di inventarla.

### 9. Sicurezza
Le credenziali Supabase e GitHub restano lato server/Actions. Il browser non riceve `SUPABASE_SECRET_KEY` né token GitHub. Il dashboard può essere protetto con `DASHBOARD_PASSWORD`.

### 10. Regola pratica
Controlla nell'ordine **stato motore → segnale → confluenza → Multi-Horizon/TradingAgents → performance/notifiche**. Il Laboratory va letto come ambiente sperimentale separato.
""")
        st.info("Il PDF resta nel repository come copia di archivio; la guida operativa principale è ora leggibile direttamente qui nel sito.")
        st.link_button("📄 PDF architettura (archivio)","https://github.com/antoannali-ita/trading-engine-v2/blob/main/docs/Trading_Engine_Guida_Architettura_2026-08-21.pdf")
st.caption(f"Snapshot: {s['loaded_at']} · Pagina: {datetime.now().astimezone().isoformat(timespec='seconds')}")
footer()
