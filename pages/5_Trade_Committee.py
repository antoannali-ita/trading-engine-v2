from __future__ import annotations

from datetime import datetime
import streamlit as st

from trade_committee import run_committee

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
    progress=st.progress(0, text="Avvio Trade Committee...")
    status=st.status(f"Analisi {ticker} in corso", expanded=True)
    labels={}
    def cb(step,label,state):
        labels[step]=(label,state)
        progress.progress(step/16, text=f"{step}/16 · {label}")
        icon="✅" if state=="COMPLETE" else "⚠️"
        status.write(f"{icon} {step:02d} · {label}")
    try:
        result=run_committee(ticker, cb)
        status.update(label=f"Trade Committee {ticker} completato", state="complete", expanded=False)
        progress.progress(1.0, text="16/16 · Analisi completata")
        st.session_state["trade_committee_result"]=result
    except Exception as exc:
        status.update(label=f"Analisi {ticker} non completata", state="error")
        st.error(f"Errore: {exc}")

r=st.session_state.get("trade_committee_result")
if r:
    st.divider(); st.subheader(f"Final Committee · {r['ticker']}")
    a,b,c,d=st.columns(4)
    verdict=r['verdict']; a.metric("Verdetto", verdict); b.metric("Committee Score", f"{r['committee_score']}/100")
    c.metric("Data Confidence", f"{r['data_confidence']}%")
    d.metric("Prezzo", f"{r['price']:.2f}" if r['price'] else "N/D")
    if verdict=="APPROVE": st.success("🟢 APPROVE · candidato idoneo alla valutazione operativa manuale")
    elif verdict=="WAIT": st.warning("🟡 WAIT · condizioni non ancora sufficienti per confermare l'acquisto")
    else: st.error("🔴 REJECT · il Committee non conferma l'acquisto")

    st.subheader("Trade Plan indicativo")
    def f(x): return f"{x:.2f}" if isinstance(x,(int,float)) else "N/D"
    st.dataframe({"Voce":["Entry","Stop","TP1","TP2","ATR14","RSI14","RVOL"],"Valore":[f(r['entry']),f(r['stop']),f(r['tp1']),f(r['tp2']),f(r['atr14']),f(r['rsi14']),f(r['relative_volume'])]},hide_index=True,width="stretch")

    x,y=st.columns(2)
    with x:
        st.subheader("Perché sì")
        for item in r['bull_case'] or ["Nessuna evidenza forte rilevata"]: st.write(f"• {item}")
    with y:
        st.subheader("Perché no")
        for item in r['bear_case'] or ["Nessuna criticità forte rilevata"]: st.write(f"• {item}")

    st.subheader("Trend e qualità")
    st.dataframe({"Check":["Technical","Business/Quality","Valuation","Volume","SMA20","SMA50","SMA200","Earnings"],"Valore":[f"{r['technical_score']}/100",f"{r['quality_score']}/100",f"{r['valuation_score']}/100",f"{r['volume_score']}/100",f(r['sma20']),f(r['sma50']),f(r['sma200']),r['earnings']]},hide_index=True,width="stretch")

    with st.expander("Timeline e Data Quality", expanded=False):
        st.dataframe(r['steps'],hide_index=True,width="stretch")
        st.json(r['fundamentals'])
    st.warning(r['guardrail'])

st.caption(f"LAB-RESEARCH-001 · Updated: {datetime.now().astimezone().strftime('%d/%m/%Y %H:%M:%S %Z')}")
