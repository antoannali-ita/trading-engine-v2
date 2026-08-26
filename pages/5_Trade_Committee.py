from __future__ import annotations

from datetime import datetime
import streamlit as st

from trade_committee import run_committee
from trade_committee.persistence import (
    fail_run,
    finish_run,
    log_step,
    make_run_id,
    recent_runs,
    run_steps,
    start_run,
)

st.set_page_config(page_title="Trade Committee", page_icon="🔬", layout="wide")
st.title("🔬 Trade Committee · Deep Pre-Trade Analysis")
st.caption("LAB-RESEARCH-001 · Modulo manuale indipendente. Ulteriore conferma prima di un acquisto reale.")
st.info("MANUAL · RESEARCH ONLY · READ-ONLY VERSO PRODUCTION · NESSUN ORDINE AUTOMATICO")

with st.sidebar:
    st.markdown("## Trade Committee")
    st.markdown("**Scopo:** due diligence sui soli candidati reali")
    st.markdown("**Input:** ticker manuale")
    st.markdown("**Output:** APPROVE / WAIT / REJECT")
    st.markdown("**CORE:** invariato")

c1,c2=st.columns([3,1])
with c1:
    ticker=st.text_input("Ticker", placeholder="Es. ORCL, GSK, CSCO").strip().upper()
with c2:
    st.write("")
    start=st.button("🔬 AVVIA ANALISI", type="primary", use_container_width=True, disabled=not bool(ticker))

if start:
    run_id = make_run_id(ticker)
    st.session_state["trade_committee_run_id"] = run_id
    st.session_state["trade_committee_live_steps"] = []
    persistence = start_run(run_id, ticker)
    progress=st.progress(0, text=f"Avvio Trade Committee · {run_id}")
    status=st.status(f"Analisi {ticker} in corso · {run_id}", expanded=True)

    def cb(step,label,state):
        progress.progress(step/16, text=f"{step}/16 · {label}")
        icon="✅" if state=="COMPLETE" else "⚠️"
        status.write(f"{icon} {step:02d} · {label}")
        st.session_state["trade_committee_live_steps"].append({"step": step, "label": label, "status": state})
        log_step(run_id, step, label, state)

    try:
        result=run_committee(ticker, cb)
        result["run_id"] = run_id
        finish_result = finish_run(run_id, result)
        status.update(label=f"Trade Committee {ticker} completato · {run_id}", state="complete", expanded=False)
        progress.progress(1.0, text="16/16 · Analisi completata")
        st.session_state["trade_committee_result"]=result
        st.session_state["trade_committee_persistence"]={"start": persistence, "finish": finish_result}
    except Exception as exc:
        fail_result = fail_run(run_id, exc)
        status.update(label=f"Analisi {ticker} FALLITA · {run_id}", state="error")
        st.session_state["trade_committee_persistence"]={"start": persistence, "fail": fail_result}
        st.error(f"Errore: {type(exc).__name__}: {exc}")

r=st.session_state.get("trade_committee_result")
if r:
    st.divider(); st.subheader(f"Final Committee · {r['ticker']}")
    if r.get("run_id"):
        st.caption(f"Run ID: `{r['run_id']}`")
    a,b,c,d=st.columns(4)
    verdict=r['verdict']; a.metric("Verdetto", verdict); b.metric("Committee Score", f"{r['committee_score']}/100")
    c.metric("Data Confidence", f"{r['data_confidence']}%")
    d.metric("Prezzo", f"{r['price']:.2f}" if r['price'] else "N/D")
    if verdict=="APPROVE": st.success("🟢 APPROVE · candidato idoneo alla valutazione operativa manuale")
    elif verdict=="WAIT": st.warning("🟡 WAIT · condizioni non ancora sufficienti per confermare l'acquisto")
    else: st.error("🔴 REJECT · il Committee non conferma l'acquisto")
    if r.get("warning_count"):
        st.info(f"ℹ️ {r['warning_count']} step sono WARNING: analisi eseguita, ma fonte/dato dedicato non ancora disponibile. Non sono errori runtime e riducono la Data Confidence.")

    st.subheader("Trade Plan indicativo")
    def f(x): return f"{x:.2f}" if isinstance(x,(int,float)) else "N/D"
    st.dataframe({"Voce":["Entry","Stop","TP1","TP2","ATR14","RSI14","RVOL","Earnings"],"Valore":[f(r['entry']),f(r['stop']),f(r['tp1']),f(r['tp2']),f(r['atr14']),f(r['rsi14']),f(r['relative_volume']),r['earnings']]},hide_index=True,width="stretch")

    x,y=st.columns(2)
    with x:
        st.subheader("Perché sì")
        for item in r['bull_case'] or ["Nessuna evidenza forte rilevata"]: st.write(f"• {item}")
    with y:
        st.subheader("Perché no")
        for item in r['bear_case'] or ["Nessuna criticità forte rilevata"]: st.write(f"• {item}")

    st.subheader("Trend e qualità")
    st.dataframe({"Check":["Technical","Business/Quality","Valuation","Volume","SMA20","SMA50","SMA200","Earnings"],"Valore":[f"{r['technical_score']}/100",f"{r['quality_score']}/100",f"{r['valuation_score']}/100",f"{r['volume_score']}/100",f(r['sma20']),f(r['sma50']),f(r['sma200']),r['earnings']]},hide_index=True,width="stretch")

    st.subheader("Fondamentali disponibili")
    labels={"marketCap":"Market Cap","trailingPE":"P/E","forwardPE":"Forward P/E","pegRatio":"PEG","returnOnEquity":"ROE","debtToEquity":"Debt/Equity","freeCashflow":"Free Cash Flow","operatingCashflow":"Operating Cash Flow","revenueGrowth":"Revenue Growth","earningsGrowth":"Earnings Growth","profitMargins":"Profit Margin"}
    rows=[{"Metrica":labels.get(k,k),"Valore":v if v is not None else "N/D"} for k,v in r['fundamentals'].items()]
    st.dataframe(rows,hide_index=True,width="stretch")

    with st.expander("Timeline e Data Quality", expanded=False):
        st.caption("COMPLETE = step coperto. WARNING = step eseguito ma incompleto per fonte/dato mancante. WARNING non significa errore del programma.")
        st.dataframe(r['steps'],hide_index=True,width="stretch")
    with st.expander("Dati grezzi / Debug", expanded=False):
        st.json(r['fundamentals'])
    st.warning(r['guardrail'])

st.divider()
st.subheader("🧾 Run Log / Diagnostics")
persist_state = st.session_state.get("trade_committee_persistence")
if persist_state:
    failures=[f"{k}: {v.get('reason')}" for k,v in persist_state.items() if isinstance(v,dict) and not v.get("ok")]
    if failures:
        st.warning("Persistenza DB non completa: " + " | ".join(failures))
    else:
        st.success("Log del run salvato su Supabase.")

runs, runs_error = recent_runs(20)
if runs_error:
    st.info(f"Storico DB non disponibile: {runs_error}. Il log del run corrente resta comunque visibile in pagina.")
elif not runs:
    st.caption("Nessun run persistito ancora.")
else:
    st.dataframe(runs, hide_index=True, width="stretch")
    run_ids=[x.get("run_id") for x in runs if x.get("run_id")]
    selected=st.selectbox("Dettaglio run", run_ids, index=0)
    details, details_error = run_steps(selected)
    if details_error:
        st.warning(f"Dettaglio non disponibile: {details_error}")
    else:
        st.dataframe(details, hide_index=True, width="stretch")

st.caption(f"LAB-RESEARCH-001 · Updated: {datetime.now().astimezone().strftime('%d/%m/%Y %H:%M:%S %Z')}")
