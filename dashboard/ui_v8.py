from __future__ import annotations

import html
import os
import time
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd
import streamlit as st

try:
    import dashboard.data_access as data_access
except ModuleNotFoundError:
    import data_access  # type: ignore

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
    "engine_id":"Motore che ha prodotto il run o il segnale.","engine":"Famiglia del motore sorgente.","market":"Mercato di riferimento.","strategy":"Strategia applicata.","status":"Stato del processo o del setup.","signal_type":"Tipo di segnale/conferma.","decision":"Decisione normalizzata.","conviction":"Forza sintetica del setup.","is_actionable":"True = supera i gate minimi per avanzare.","ticker":"Titolo analizzato.","symbol":"Ticker del titolo nel Laboratory.","entry":"Ingresso proposto.","stop":"Livello di protezione.","tp1":"Primo target.","tp2":"Secondo target.","max_buy":"Prezzo massimo oltre cui non inseguire il setup.","alignment":"Giudizio TradingAgents: CONFIRM/NEUTRAL/CAUTION/VETO.","pnl_pct":"Rendimento misurato nell'orizzonte.","max_drawdown_pct":"Peggior drawdown peak-to-trough.","error_message":"Errore tecnico se presente.","score":"Punteggio del Laboratory.","trigger":"Condizione che attiva il setup.","distance_to_entry_pct":"Distanza percentuale dall'ingresso.","opened_at":"Data e ora di apertura della paper position.","detected_at":"Data e ora in cui il segnale è stato rilevato.","created_at":"Data e ora di creazione del record.","updated_at":"Data e ora dell'ultimo aggiornamento.","started_at":"Data e ora di avvio.","finished_at":"Data e ora di fine.","completed_at":"Data e ora di completamento.","occurred_at":"Data e ora dell'evento.","attempted_at":"Data e ora del tentativo di notifica.","sent_at":"Data e ora dell'invio.","signal_date":"Data logica del segnale.","source_signal_id":"Segnale padre/origine da cui deriva questo record.","parent_signal_id":"Segnale padre/origine.","signal_role":"Ruolo genealogico: PARENT, CHILD o DERIVED quando disponibile.","alert_type":"Tipo di alert prodotto dal Laboratory.","alert_price":"Prezzo associato all'alert.",
}
TIMESTAMP_COLS={"created_at","updated_at","detected_at","started_at","finished_at","completed_at","occurred_at","attempted_at","sent_at","opened_at","requested_at","dispatched_at","last_started_at","last_finished_at","last_run_at","next_expected_run_at","period_start","period_end"}
PERCENT_COLUMNS={"pnl_pct","max_drawdown_pct","max_favorable_excursion_pct","distance_to_entry_pct","return_pct","change_pct","win_rate_pct","risk_pct","drawdown_pct"}
MONEY_COLUMNS={"price","entry","entry_price","exit_price","proposed_entry","proposed_stop","proposed_target","stop","stop_current","tp1","tp2","target","max_buy","alert_price","capital","market_value","pnl_amount","profit","loss","risk_amount"}
INTEGER_COLUMNS={"qty","quantity","records_processed","signals_found","holding_minutes","universe_size","candidates_count"}
MISSING_TEXT={"nan","nat","none","null","<na>","n/a"}


def require_access():
    expected=(os.getenv("DASHBOARD_PASSWORD") or "").strip()
    if not expected or st.session_state.get("dashboard_auth"): return
    st.title("🔐 Trading Engine Control Center")
    pwd=st.text_input("Password",type="password")
    if st.button("Accedi",type="primary"):
        if pwd==expected:
            st.session_state["dashboard_auth"]=True
            st.rerun()
        st.error("Password non valida")
    st.stop()


def df(rows): return pd.DataFrame(rows) if rows else pd.DataFrame()

def _clean_missing(v: Any):
    if v is None: return None
    if isinstance(v,str) and v.strip().lower() in MISSING_TEXT: return None
    try:
        if pd.isna(v): return None
    except Exception: pass
    return v

def _itnum(v: Any,decimals=2):
    v=_clean_missing(v)
    if v is None: return "-"
    try: n=float(v)
    except Exception: return str(v)
    if not np.isfinite(n): return "-"
    text=f"{n:,.{decimals}f}"
    return text.replace(",","§").replace(".",",").replace("§",".")

def _duration(v: Any):
    v=_clean_missing(v)
    if v is None: return "-"
    if v=="N/D": return "N/D"
    try: n=float(v)
    except Exception: return str(v)
    text=f"{n:.2f}".rstrip("0").rstrip(".")
    return text.replace(".",",")

def _fmt_frame(frame: pd.DataFrame):
    out=frame.copy()
    for c in out.columns:
        out[c]=out[c].map(_clean_missing)
        if c in TIMESTAMP_COLS or c.endswith("_at"):
            out[c]=out[c].map(data_access.utc_label)
    return out

def cols_cfg(cols): return {c:st.column_config.TextColumn(c,help=HELP[c]) for c in cols if c in HELP}

def show(frame,cols=None,limit=300):
    if frame.empty:
        st.info("Nessun dato disponibile.")
        return
    v=_fmt_frame(frame)
    c=[x for x in (cols or list(v.columns)) if x in v.columns]
    v=v[c].head(limit)
    fmt={}
    for name in v.columns:
        low=str(name).lower()
        if low=="duration_seconds": fmt[name]=_duration
        elif low in PERCENT_COLUMNS or low.endswith("_pct"): fmt[name]=lambda x:_itnum(x,2)+"%" if _clean_missing(x) is not None else "-"
        elif low in MONEY_COLUMNS or low.endswith("_price"): fmt[name]=lambda x:_itnum(x,2)
        elif low in INTEGER_COLUMNS: fmt[name]=lambda x:str(int(float(x))) if _clean_missing(x) not in {None,"N/D"} else ("N/D" if x=="N/D" else "-")
    styler=v.style.format(fmt,na_rep="-")
    st.dataframe(styler,use_container_width=True,hide_index=True,column_config=cols_cfg(c))

def badge(v):
    v=str(v or "UNKNOWN").upper(); icon={"HEALTHY":"🟢","SUCCESS":"🟢","CONFIRM":"🟢","RUNNING":"🔵","PENDING":"🟡","REQUESTED":"🟡","DISPATCHED":"🔵","STALE":"🟠","DEGRADED":"🟠","CAUTION":"🟠","FAILED":"🔴","VETO":"🔴","NOT_RUN":"⚪"}.get(v,"⚪")
    return f"{icon} {v}"

def footer(): st.markdown('<div class="site-footer">© 2026 Tutti i diritti riservati a <strong>Larocca Antonio</strong> · Trading Engine Control Center</div>',unsafe_allow_html=True)

def architecture():
    row1=[("🧭 CORE","Motore 3-6 mesi: selezione, Buy Zone, entry, stop e target."),("🗄️ Supabase","Memoria centrale di run, segnali, relazioni, AI, notifiche e performance."),("🧠 Orchestrator","Coordina i segnali, costruisce confluenze e decide i dispatch."),("🔭 Multi-Horizon","Validazione indipendente su più orizzonti."),("🤖 TradingAgents","Seconda opinione AI sui casi qualificati."),("🔔 Email/WhatsApp","Canali finali di notifica.")]
    row2=[("⚡ FAST","Monitor intraday delle zone operative."),("⚙️ GitHub Actions","Scheduler ed esecutore dei workflow."),("🖥️ Dashboard","Control Center di lettura e gestione."),("🧪 Laboratory","Paper trading, ricerca, backtest ed evolution separati dalla produzione.")]
    def node(a,b): return f'<span class="arch-node" data-tip="{html.escape(b,quote=True)}">{a}</span>'
    st.markdown('<div class="arch-wrap">'+'<span class="arch-arrow">→</span>'.join(node(a,b) for a,b in row1)+'</div>',unsafe_allow_html=True)
    st.markdown('<div class="arch-wrap">'+'<span class="arch-arrow">↔</span>'.join(node(a,b) for a,b in row2)+'</div>',unsafe_allow_html=True)

@st.cache_data(ttl=30,show_spinner=False)
def snapshot():
    return {"health":data_access.engine_health(),"signals":data_access.signals(1500),"conf":data_access.latest_confluence(400),"runs":data_access.runs(800),"ai":data_access.ai_analysis(500),"notifications":data_access.notifications(800),"events":data_access.system_events(500),"performance":data_access.performance(1500),"perf_summary":data_access.performance_summary(),"requests":data_access.manual_requests(300),"lab_watch":data_access.lab_watchlist(1500),"lab_positions":data_access.lab_paper_positions(1500),"lab_events":data_access.lab_paper_events(2500),"lab_signals":data_access.lab_paper_signals(1500),"lab_bt_runs":data_access.lab_backtest_runs(300),"lab_bt_results":data_access.lab_backtest_results(3000),"lab_calibration":data_access.lab_calibration_results(1500),"lab_outcomes":data_access.lab_signal_outcomes(5000),"lab_variants":data_access.lab_strategy_variants(1500),"lab_evals":data_access.lab_strategy_evaluations(5000),"core_high":data_access.core_high_conviction(1000),"loaded_at":datetime.now().astimezone().isoformat(timespec="seconds")}

GUIDES={
("🏠 Home","Panoramica"):{"look":"Salute generale, confluenze recenti e attività dei motori.","fields":"HEALTHY/STALE/FAILED, ultimo run, signals_found, actionable.","alarm":"Motori STALE/FAILED o nessun run recente durante sessione attiva.","action":"Se tutto è HEALTHY passa a Produzione → Segnali/Decisioni."},
("🏭 Produzione","🎯 Decisioni"):{"look":"Le confluenze che l'Orchestrator considera più importanti.","fields":"signal_type, decision, conviction, is_actionable.","alarm":"Actionable senza piano operativo completo a monte o conviction incoerente.","action":"Apri Segnali per controllare prezzo, entry, stop e target."},
("🏭 Produzione","⚙️ Motori"):{"look":"Salute e frequenza dei motori di produzione.","fields":"engine_id, strategy, market, last_run, duration, signals_found.","alarm":"STALE, FAILED, NOT_RUN inatteso o intervallo mancante.","action":"Controlla Operations → Run & Log se un motore non gira."},
("🏭 Produzione","📡 Segnali"):{"look":"È la tabella operativa principale: cosa ha prodotto ogni motore.","fields":"ticker, engine, decision, conviction, price, entry, stop, TP1, TP2, actionable, source_signal_id.","alarm":"IN_BUY_ZONE/BUY con entry-stop-TP mancanti; actionable senza piano completo.","action":"Per un titolo interessante ricostruisci sorgente e conferme prima di un ordine."},
("🏭 Produzione","🧠 TradingAgents"):{"look":"Seconda opinione AI sui segnali qualificati.","fields":"alignment, confidence, verdict, summary, trigger_reason, entry/stop/TP.","alarm":"VETO, CAUTION forte, FAILED o analisi scollegata dal source_signal_id.","action":"Usalo come conferma o veto, non come generatore autonomo di BUY."},
("🏭 Produzione","📈 Performance"):{"look":"Misura cosa è successo dopo i segnali.","fields":"outcome, P&L, max drawdown, max favorable excursion, holding_minutes.","alarm":"Drawdown elevato, win rate/expectancy in deterioramento, segnali che non raggiungono i target.","action":"Serve per validare il sistema nel tempo, non per decidere un singolo trade."},
("🧪 Laboratorio","🔬 Segnali"):{"look":"Candidati sperimentali WATCH → NEAR_SETUP → PRE_BUY → PAPER_OPEN.","fields":"score, trigger, price, entry, max_buy, distanza, alert, date.","alarm":"BLOCKED_DATA o campi operativi mancanti su stati avanzati.","action":"Sono esperimenti: nessun ordine reale."},
("🧪 Laboratorio","💼 Paper Portfolio"):{"look":"Posizioni simulate aperte dal Laboratory.","fields":"qty, capital, entry, last_price, stop, TP1, TP2, stato.","alarm":"Stop/target mancanti o posizione non aggiornata.","action":"Usa gli esiti per valutare la strategia, non per replicare automaticamente il trade."},
("🧪 Laboratorio","🎯 Action Center"):{"look":"Solo i candidati più vicini a un'azione simulata.","fields":"PRE_BUY, NEAR_SETUP, PAPER_OPEN, score, trigger, entry/max_buy/stop/TP.","alarm":"PRE_BUY con R/R o piano incompleto.","action":"È la shortlist del Laboratory."},
("🧪 Laboratorio","🧪 Backtest / Research"):{"look":"Test storici, run di ricerca e calibrazione.","fields":"stato run, metriche, risultati per strategia e calibrazione.","alarm":"Campioni piccoli, drawdown alto o risultati non robusti.","action":"Confronta versioni; non promuovere una strategia per un solo backtest buono."},
("🧪 Laboratorio","🧬 Strategy Evolution"):{"look":"Varianti sperimentali e loro valutazioni.","fields":"variant, evaluation, metriche di confronto, stato.","alarm":"Miglioramento solo su una metrica o overfitting.","action":"Una variante va validata prima di arrivare in produzione."},
("🧪 Laboratorio","⭐ Core Opportunities"):{"look":"Opportunità CORE ad alta convinzione separate dal paper trading.","fields":"ticker, score, stato e dati operativi disponibili.","alarm":"Alta convinzione senza entry/RR verificati.","action":"Usale come lista di approfondimento."},
("🧪 Laboratorio","❤️ Engine Health"):{"look":"Salute tecnica dei motori e run recenti.","fields":"HEALTHY/STALE/FAILED, orari, durata, records, signals.","alarm":"FAILED/STALE o run mancanti durante la finestra prevista.","action":"Passa a Operations per il dettaglio tecnico."},
("🛠️ Operations","📝 Run & Log"):{"look":"Registro tecnico delle esecuzioni e degli eventi.","fields":"started/finished, engine, trigger_source, status, duration_seconds, records_processed, signals_found, error.","alarm":"FAILED, ERROR/CRITICAL, durata anomala o records=0 inatteso.","action":"Qui capisci se il problema è scheduler, motore o dati."},
("🛠️ Operations","▶️ Esegui ora"):{"look":"Avvio manuale controllato di un motore.","fields":"REQUESTED → DISPATCHED → RUNNING → SUCCESS/FAILED, GitHub run id, engine run id.","alarm":"Richiesta ferma troppo a lungo o FAILED.","action":"Dopo il click segui la clessidra; se supera 120s controlla Run & Log."},
("🛠️ Operations","🔔 Notifiche"):{"look":"Conferma cosa è stato realmente inviato via Email/WhatsApp.","fields":"attempted_at, sent_at, ticker, event_type, channel, status, provider.","alarm":"FAILED, sent_at mancante su SENT o segnale atteso senza notifica.","action":"Distingui sempre segnale prodotto da notifica effettivamente consegnata."},
("📚 Guida","🔎 Cerca"):{"look":"Ricerca rapida di termini e concetti del sistema.","fields":"Inserisci un termine come PRE_BUY, FAST, VETO, source_signal_id.","alarm":"Nessuno.","action":"Usala quando un campo non è chiaro."},
("📚 Guida","🗺️ Come usare"):{"look":"Percorso consigliato per leggere il Control Center.","fields":"Health → Segnali → Decisioni → TradingAgents → Notifiche → Performance.","alarm":"Saltare direttamente al BUY senza verificare il piano.","action":"Segui il flusso in ordine."},
("📚 Guida","📖 Glossario"):{"look":"Definizione sintetica dei termini.","fields":"CORE, FAST, PRE_BUY, STALE, VETO, source_signal_id, ecc.","alarm":"Nessuno.","action":"Consulta il termine che non riconosci."},
("📚 Guida","⏱️ Scheduler"):{"look":"Quando dovrebbero girare i workflow.","fields":"frequenza e orari locali/UTC.","alarm":"Run assente oltre la finestra prevista.","action":"Confronta con Engine Health e Run & Log."},
("📚 Guida","🏗️ Architettura"):{"look":"Come comunicano CORE, FAST, Supabase, Orchestrator, Multi-Horizon e TradingAgents.","fields":"flusso e responsabilità di ogni componente.","alarm":"Confondere un validatore con il motore sorgente.","action":"Usala per capire da dove nasce un dato."},
("📚 Guida","📘 Guida completa"):{"look":"Manuale sintetico dell'intero sistema.","fields":"produzione, laboratory, operations, timestamp, sicurezza.","alarm":"Nessuno.","action":"È il riferimento generale; la sidebar resta specifica per la pagina corrente."},
}

SUBPAGES={
"🏠 Home":["Panoramica"],
"🏭 Produzione":["🎯 Decisioni","⚙️ Motori","📡 Segnali","🧠 TradingAgents","📈 Performance"],
"🧪 Laboratorio":["🔬 Segnali","💼 Paper Portfolio","🎯 Action Center","🧪 Backtest / Research","🧬 Strategy Evolution","⭐ Core Opportunities","❤️ Engine Health"],
"🛠️ Operations":["📝 Run & Log","▶️ Esegui ora","🔔 Notifiche"],
"📚 Guida":["🔎 Cerca","🗺️ Come usare","📖 Glossario","⏱️ Scheduler","🏗️ Architettura","📘 Guida completa"],
}


def contextual_help(section,page):
    g=GUIDES.get((section,page),{})
    with st.sidebar:
        st.markdown(f"### ℹ️ {page}")
        st.caption(f"Guida della pagina corrente · {section}")
        st.markdown("**Cosa guardare qui**")
        st.write(g.get("look","Guida non disponibile."))
        st.markdown("**Campi chiave**")
        st.write(g.get("fields","-"))
        st.markdown("**Segnali d'allarme**")
        st.write(g.get("alarm","-"))
        st.markdown("**Cosa fare**")
        st.write(g.get("action","-"))
        st.divider()
        st.caption("La guida cambia automaticamente quando cambi pagina.")


def run_with_progress(engine_id,market,strategy,requested_by):
    created=data_access.request_run(engine_id,market,strategy,send_email=True,send_whatsapp=False,requested_by=requested_by)
    request_id=str(created.get("request_id") or "")
    if not request_id:
        st.error("Richiesta creata senza request_id.")
        return created
    labels={"REQUESTED":(10,"Richiesta registrata"),"PENDING":(15,"In attesa di presa in carico"),"DISPATCHED":(35,"Workflow inviato a GitHub Actions"),"RUNNING":(65,"Motore in esecuzione"),"STARTED":(65,"Motore in esecuzione"),"SUCCESS":(100,"Esecuzione completata"),"COMPLETED":(100,"Esecuzione completata"),"FAILED":(100,"Esecuzione terminata con errore"),"ERROR":(100,"Esecuzione terminata con errore"),"CANCELLED":(100,"Esecuzione annullata")}
    with st.status(f"⏳ Avvio {engine_id} | {market.upper()}",expanded=True) as box:
        p=st.progress(5,text="Creazione richiesta...")
        st.write(f"Request ID: `{request_id}`")
        deadline=time.time()+120; last=None; latest=created
        while time.time()<deadline:
            rows=data_access.manual_requests(250)
            cur=next((r for r in rows if str(r.get("request_id") or "")==request_id),None)
            if cur:
                latest=cur; state=str(cur.get("status") or "REQUESTED").upper(); pct,label=labels.get(state,(25,f"Stato: {state}")); p.progress(pct,text=label)
                if state!=last:
                    st.write(f"• {label}")
                    if cur.get("github_run_id"): st.write(f"• GitHub run: `{cur.get('github_run_id')}`")
                    if cur.get("run_id"): st.write(f"• Engine run: `{cur.get('run_id')}`")
                    last=state
                if state in {"SUCCESS","COMPLETED"}:
                    box.update(label=f"✅ {engine_id} completato",state="complete",expanded=False); st.cache_data.clear(); return latest
                if state in {"FAILED","ERROR","CANCELLED"}:
                    st.error(str(cur.get("error_message") or "Nessun dettaglio errore disponibile")); box.update(label=f"❌ {engine_id}: {state}",state="error",expanded=True); return latest
            time.sleep(2)
        p.progress(80,text="Run avviato; completamento non ancora registrato entro 120 s")
        st.info("Il run continua in background. Controlla Operations → Run & Log.")
        box.update(label=f"⏳ {engine_id} ancora in esecuzione",state="running",expanded=False)
        return latest

require_access()
head1,head2=st.columns([6,1])
with head1: st.markdown('<div class="hero"><h1>📈 Trading Engine Control Center</h1><div style="opacity:.7">Produzione, Laboratory, Operations e Guida contestuale.</div></div>',unsafe_allow_html=True)
with head2:
    if st.button("↻ Aggiorna",use_container_width=True): st.cache_data.clear(); st.rerun()

section=st.radio("Sezione",list(SUBPAGES),horizontal=True,label_visibility="collapsed",key="nav_section")
page=st.radio("Pagina",SUBPAGES[section],horizontal=True,label_visibility="collapsed",key=f"nav_{section}")
contextual_help(section,page)

try: s=snapshot()
except Exception as exc: st.error(f"Connessione dati non disponibile: {type(exc).__name__}: {exc}"); st.stop()
H,S,C,R,A,N,E,P,PS,Q=[df(s[x]) for x in ["health","signals","conf","runs","ai","notifications","events","performance","perf_summary","requests"]]
LW,LP,LE,LS,LBR,LBT,LC,LO,LV,LVE,CH=[df(s[x]) for x in ["lab_watch","lab_positions","lab_events","lab_signals","lab_bt_runs","lab_bt_results","lab_calibration","lab_outcomes","lab_variants","lab_evals","core_high"]]
healthy=sum(str(r.get("computed_health") or r.get("registry_status") or "").upper()=="HEALTHY" for r in s["health"]); issues=sum(str(r.get("computed_health") or r.get("registry_status") or "").upper() in {"FAILED","STALE","DEGRADED"} for r in s["health"]); actionable=sum(bool(r.get("is_actionable")) for r in s["conf"]); ai_active=sum(str(r.get("status") or "").upper() in {"PENDING","RUNNING"} for r in s["ai"])
k1,k2,k3,k4=st.columns(4); k1.metric("🟢 Motori healthy",f"{healthy}/{len(s['health'])}"); k2.metric("🟠 Da verificare",issues); k3.metric("🎯 Actionable",actionable); k4.metric("🧠 AI attive",ai_active)

if section=="🏠 Home":
    st.subheader("Stato motori")
    if not H.empty:
        v=H.copy(); sc="computed_health" if "computed_health" in v.columns else "registry_status"; v["stato"]=v[sc].map(badge); show(v,["engine_id","strategy","market","horizon","stato","last_started_at","last_finished_at","signals_found"],50)
    a,b=st.columns(2)
    with a: st.subheader("🎯 Confluenze recenti"); show(C,["detected_at","market","ticker","signal_type","conviction","is_actionable"],30)
    with b:
        st.subheader("⚙️ Attività per motore")
        if not R.empty and "engine_id" in R: st.bar_chart(R.groupby("engine_id").size().sort_values(ascending=False))
        else: st.info("Nessun run disponibile.")

elif section=="🏭 Produzione":
    if page=="🎯 Decisioni": st.subheader("Decision Board"); show(C,["detected_at","market","ticker","signal_type","decision","conviction","is_actionable"],150)
    elif page=="⚙️ Motori": st.subheader("Motori di produzione"); show(H,None,150)
    elif page=="📡 Segnali": st.subheader("Segnali"); show(S,["detected_at","market","ticker","engine","strategy","signal_type","decision","conviction","price","entry","stop","tp1","tp2","is_actionable","signal_id","source_signal_id"],400)
    elif page=="🧠 TradingAgents": st.subheader("TradingAgents"); show(A,["started_at","completed_at","market","ticker","status","alignment","confidence","verdict","summary","trigger_reason","source_signal_id","entry","stop","tp1","tp2","error_message"],250)
    elif page=="📈 Performance": st.subheader("Performance"); show(PS,None,300); show(P,["created_at","engine_id","strategy","market","ticker","signal_id","outcome","entry_price","exit_price","pnl_pct","max_drawdown_pct","max_favorable_excursion_pct","holding_minutes"],500)

elif section=="🧪 Laboratorio":
    if page=="🔬 Segnali":
        st.subheader("Laboratory Signals")
        if not LW.empty:
            v=LW.copy(); order={"PAPER_OPEN":0,"PRE_BUY":1,"NEAR_SETUP":2,"WATCH":3}; v["_rank"]=v.get("status",pd.Series(index=v.index,dtype=str)).fillna("").astype(str).str.upper().map(order).fillna(9); v=v.sort_values(["_rank","score"],ascending=[True,False]).drop(columns="_rank"); base=["symbol","strategy","status","score","trigger","price","entry","max_buy","distance_to_entry_pct","alert_type","alert_price","signal_date","created_at","updated_at"]; genealogy=[x for x in ["signal_id","source_signal_id","parent_signal_id","signal_role"] if x in v.columns]; show(v,base+genealogy,300)
        else: st.warning("lab_watchlist non contiene righe attive.")
        st.markdown("#### Paper signals"); show(LS,None,200)
    elif page=="💼 Paper Portfolio": st.subheader("Paper Portfolio"); show(LP,["symbol","strategy","status","qty","capital","entry_price","last_price","stop_current","tp1","tp2","opened_at","created_at","updated_at","last_checked_date"],300); st.markdown("#### Eventi paper"); show(LE,None,250)
    elif page=="🎯 Action Center":
        st.subheader("Action Center")
        if LW.empty: st.info("Nessuna opportunità Laboratory disponibile.")
        else:
            mask=LW.get("status",pd.Series(index=LW.index,dtype=str)).fillna("").astype(str).str.upper().isin(["PAPER_OPEN","PRE_BUY","NEAR_SETUP"]); show(LW[mask],["created_at","symbol","strategy","status","score","trigger","price","entry","max_buy","distance_to_entry_pct","stop","tp1","tp2"],100)
        st.markdown("#### Outcome sperimentali"); show(LO,None,200)
    elif page=="🧪 Backtest / Research": st.subheader("Backtest / Research"); show(LBR,None,150); show(LBT,None,300); st.markdown("#### Calibrazione"); show(LC,None,250)
    elif page=="🧬 Strategy Evolution": st.subheader("Strategy Evolution"); show(LV,None,250); show(LVE,None,400)
    elif page=="⭐ Core Opportunities": st.subheader("Core Opportunities"); show(CH,None,300)
    elif page=="❤️ Engine Health": st.subheader("Engine Health"); show(H,None,200); st.markdown("#### Run recenti"); show(R,["started_at","finished_at","engine_id","market","strategy","trigger_source","status","duration_seconds","records_processed","signals_found","error_message"],300)

elif section=="🛠️ Operations":
    if page=="📝 Run & Log": st.subheader("Run & Log"); show(R,["started_at","finished_at","engine_id","market","strategy","trigger_source","status","duration_seconds","records_processed","signals_found","error_message"],400); st.markdown("#### System events"); show(E,["occurred_at","engine_id","run_id","severity","event_type","message","details"],300); st.markdown("#### Richieste manuali"); show(Q,["requested_at","engine_id","market","strategy","requested_by","status","github_run_id","run_id","completed_at","error_message"],250)
    elif page=="▶️ Esegui ora":
        st.subheader("Esegui ora"); st.warning("La dashboard crea una richiesta in Supabase. L'Orchestrator la prende in carico e lancia GitHub Actions.")
        engines=[r for r in s["health"] if str(r.get("engine_id") or "").upper() not in {"ORCHESTRATOR","TRADINGAGENTS"}]; labels=[f"{r.get('engine_id')} | {r.get('strategy')} | {r.get('market')}" for r in engines]; selected=st.selectbox("Motore",labels) if labels else None; who=st.text_input("Richiesto da",value="Antonio")
        if st.button("▶️ ESEGUI ORA",type="primary",disabled=not selected): row=engines[labels.index(selected)]; run_with_progress(str(row.get("engine_id")),str(row.get("market")),str(row.get("strategy") or ""),who)
    elif page=="🔔 Notifiche":
        st.subheader("Notifiche"); c1,c2,c3=st.columns(3); c1.metric("Confluenze actionable",actionable); ai_success=sum(str(x.get("status") or "").upper()=="SUCCESS" for x in s["ai"]); c2.metric("AI SUCCESS",ai_success); c3.metric("Notifiche registrate",len(s["notifications"])); show(N,["attempted_at","sent_at","ticker","event_type","channel","status","provider","error_message"],400)

elif section=="📚 Guida":
    topics={"Decision Board":"Vista operativa delle confluenze prodotte dall'Orchestrator.","Actionable":"True significa che il segnale supera i gate minimi per avanzare.","CORE":"Motore 3-6 mesi che produce i segnali base.","FAST":"Monitor frequente delle zone di ingresso e stop.","Supabase":"Memoria centrale del sistema.","Orchestrator":"Coordina i motori e costruisce confluenze.","Multi-Horizon":"Validazione indipendente su più orizzonti.","TradingAgents":"Seconda opinione AI su segnali qualificati.","Laboratory":"Area separata per paper trading, ricerca, backtest ed evolution.","PRE_BUY":"Setup vicino all'attivazione ma non ancora ingresso.","NEAR_SETUP":"Setup promettente non ancora PRE_BUY.","PAPER_OPEN":"Posizione simulata aperta.","BLOCKED_DATA":"Setup sospeso per insufficienza/qualità dati.","FAILED":"Processo terminato con errore.","STALE":"Motore non eseguito entro il tempo previsto.","VETO":"TradingAgents rileva criticità incompatibile con la tesi.","source_signal_id":"Collegamento al segnale origine.","Max Drawdown":"Peggior perdita peak-to-trough nella finestra osservata."}
    if page=="🔎 Cerca":
        q=st.text_input("Cerca nella guida",placeholder="es. PRE_BUY, TradingAgents, FAILED...").strip().lower(); matches=[(k,v) for k,v in topics.items() if not q or q in k.lower() or q in v.lower()]
        for k,v in matches: st.markdown(f"**{k}**  \n{v}")
    elif page=="🗺️ Come usare": st.markdown("""### Percorso consigliato
1. **Home**: controlla salute e freschezza dei run.
2. **Produzione → Segnali**: guarda setup e piano operativo.
3. **Produzione → Decisioni**: verifica confluenza/actionable.
4. **TradingAgents**: controlla seconda opinione e veto.
5. **Notifiche**: verifica cosa è stato inviato.
6. **Performance**: misura cosa è successo dopo.
7. **Laboratorio**: resta sperimentale e separato dalla produzione.
""")
    elif page=="📖 Glossario": show(pd.DataFrame(list(topics.items()),columns=["Termine","Significato"]),None,100)
    elif page=="⏱️ Scheduler": st.markdown("""### Scheduler operativo
- **FAST**: frequente durante sessione, con gate di mercato.
- **CORE Italia**: workflow feriale dedicato.
- **CORE USA**: workflow feriale dedicato.
- **Orchestrator**: controllo periodico delle confluenze.
- **Performance worker**: giornaliero feriale.
- **Laboratory**: opportunity feed giornaliero e research/evolution settimanali.

Gli orari tecnici in dashboard sono convertiti in **Europe/Rome**.
""")
    elif page=="🏗️ Architettura": architecture()
    elif page=="📘 Guida completa": st.markdown("""## Guida completa al Trading Engine
**Flusso produzione:** CORE / FAST → Supabase → Orchestrator → Multi-Horizon → TradingAgents → Email/WhatsApp → Performance.

**Regola di lettura:** prima stato motore, poi segnale, poi confluenza, poi validazioni, infine performance. `source_signal_id` ricostruisce la genealogia quando disponibile. `Actionable=True` significa che il record supera i gate previsti per avanzare, non che esista automaticamente un ordine broker.

**Laboratory:** WATCH → NEAR_SETUP → PRE_BUY → PAPER_OPEN → OUTCOME → BACKTEST → STRATEGY EVOLUTION. Rimane separato dalla produzione reale.

**Operations:** Run & Log mostra esecuzioni ed errori; Esegui ora crea una richiesta controllata; Notifiche mostra ciò che è stato realmente inviato.

**Timestamp:** mostrati in ora italiana Europe/Rome quando il database contiene un timestamp reale.

**Sicurezza:** secret Supabase/GitHub restano lato server e non sono esposti al browser.
""")

st.caption(f"Snapshot: {s['loaded_at']} · Ora pagina: {datetime.now().astimezone().isoformat(timespec='seconds')}")
footer()
