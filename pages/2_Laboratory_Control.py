from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from typing import Any

import pandas as pd
import streamlit as st

try:
    from dashboard import data_access
except ModuleNotFoundError:
    import dashboard.data_access as data_access

st.set_page_config(page_title="Laboratory Dashboard", page_icon="🔬", layout="wide")
COMMISSION = 9.90
SLIPPAGE_BPS = 5.0


def require_access() -> None:
    # Accesso temporaneamente sospeso.
    return


def j(value: Any) -> dict:
    if isinstance(value, dict):
        return value
    try:
        return json.loads(str(value)) if value else {}
    except Exception:
        return {}


def n(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except Exception:
        return None


def session_of(row: dict[str, Any]) -> str | None:
    value = row.get("signal_date") or row.get("source_signal_date") or row.get("created_at") or row.get("opened_at")
    return str(value)[:10] if value else None


def tier_of(row: dict[str, Any]) -> str | None:
    d = j(row.get("details")); policy = j(d.get("paper_policy"))
    value = d.get("paper_tier") or policy.get("tier")
    return str(value) if value else None


def paper_pnl(row: dict[str, Any]) -> float | None:
    entry=n(row.get("entry_price")); last=n(row.get("last_price")) or n(row.get("exit_price")); qty=n(row.get("qty"))
    if entry is None or last is None or qty is None: return None
    slip=SLIPPAGE_BPS/10000
    return (last*(1-slip)-entry*(1+slip))*qty - 2*COMMISSION


def paper_return(row: dict[str, Any], pnl: float | None) -> float | None:
    entry=n(row.get("entry_price")); qty=n(row.get("qty"))
    if pnl is None or not entry or not qty: return n(row.get("return_pct"))
    return pnl/(entry*qty)*100


def fmt(frame: pd.DataFrame):
    formats={}
    for c in frame.columns:
        if c in {"Entry $","Prezzo $","Stop $","TP1 $","TP2 $","P&L netto $"}: formats[c]="{:.2f}"
        elif "%" in c or c in {"Conversione"}: formats[c]="{:.2f}%"
        elif pd.api.types.is_float_dtype(frame[c]): formats[c]="{:.2f}"
    return frame.style.format(formats,na_rep="-")


def gate_rows(signal: dict[str, Any]) -> list[dict[str,str]]:
    d=j(signal.get("details")); policy=j(d.get("paper_policy")); out=[]
    for gate in policy.get("data_gate_failures",[]) or []: out.append({"family":"DATA","policy":"PAPER_POLICY","tier":"ALL","gate":str(gate)})
    for gate in policy.get("policy_hard_failures",[]) or []: out.append({"family":"POLICY","policy":"PAPER_POLICY","tier":"ALL","gate":str(gate)})
    checks=policy.get("tier_checks") or {}
    if isinstance(checks,dict):
        for tier,check in checks.items():
            if isinstance(check,dict):
                for gate in check.get("failed",[]) or []:
                    out.append({"family":"DATA" if str(gate).startswith("DATA_") else "POLICY","policy":"PAPER_POLICY","tier":str(tier),"gate":str(gate)})
    strict=j(d.get("strict_trade_eligibility") or d.get("trade_eligibility"))
    for gate in strict.get("failed",[]) or []:
        out.append({"family":"DATA" if "DATA" in str(gate) else "POLICY","policy":"LEGACY_STRICT","tier":"LEGACY","gate":str(gate)})
    return out


@st.cache_data(ttl=60,show_spinner=False)
def load_data():
    return {"signals":data_access.lab_paper_signals(10000),"positions":data_access.lab_paper_positions(10000),"outcomes":data_access.lab_signal_outcomes(20000)}

require_access()
st.title("🔬 Laboratory Dashboard")
st.caption("Cosa sta testando il laboratorio, come stanno andando gli esperimenti e quali strategie stanno producendo risultati. Tutto è PAPER: nessun ordine reale viene generato da questa pagina.")

with st.sidebar:
    st.markdown("## Guida · Laboratory")
    st.markdown("""
### A cosa serve
Il Laboratory è il **campo di prova** del Trading Engine. Non decide cosa comprare nel portafoglio reale: prova strategie e regole con capitale virtuale per capire, con dati osservati, cosa merita ulteriore studio.

### Le 5 domande da farsi
1. **Sta lavorando?** Guarda segnali analizzati e operazioni paper aperte.
2. **Sta guadagnando?** Guarda P&L netto, vinte/perse e performance delle posizioni.
3. **Quale strategia va meglio?** Confronta operazioni, P&L e risultati per strategia.
4. **Cosa sta testando adesso?** Guarda la tabella delle posizioni aperte.
5. **Perché non apre più trade?** Solo allora apri la Diagnostica avanzata e guarda i gate.

### Tier A / B / C
- **A · quasi Production:** regole più severe, più vicine alla disciplina operativa.
- **B · sperimentale:** regole più elastiche per verificare se Production sta scartando opportunità utili.
- **C · 🔬 RESEARCH ONLY:** ricerca aggressiva. **NON è un BUY e NON è operativo.**

### Come leggere guadagni e perdite
Il P&L mostrato è un risultato **paper**. Il modello netto considera commissioni Fineco-like di **$9,90 per lato** e slippage di ricerca di **5 bps**. Serve a evitare di promuovere strategie che sembrano buone solo prima dei costi.

### Data Quality
- **RED:** dati non affidabili → veto. Non usiamo quel caso per giudicare la performance della strategia.
- **YELLOW:** può essere studiato nei Tier B/C, ma non nel Tier A.

### Gate
I **DATA GATES** segnalano problemi nei dati. I **POLICY GATES** sono regole della strategia: score, trigger, R/R, Max Buy, earnings ecc. Sono due problemi diversi e vanno letti separatamente.

### Shadow outcomes
Un segnale con dati validi respinto anche dal Tier C non viene comprato neppure in paper, ma può essere seguito a D+1/D+3/D+5/D+10/D+20. Serve per capire se i gate stanno proteggendo il sistema o stanno scartando troppo.

### Regola importante
Il Laboratory **non promuove automaticamente** una strategia in Production. Accumula evidenza. La decisione finale resta separata.
""")

try: data=load_data()
except Exception as exc:
    st.error(f"Impossibile leggere i dati Laboratory: {type(exc).__name__}: {exc}"); st.stop()
signals=data["signals"]; positions=data["positions"]; outcomes=data["outcomes"]
sessions=sorted({x for x in (session_of(r) for r in signals) if x}); latest=sessions[-1] if sessions else None; previous=sessions[-2] if len(sessions)>1 else None
cur=[r for r in signals if session_of(r)==latest] if latest else []; prev=[r for r in signals if session_of(r)==previous] if previous else []
cur_pos=[p for p in positions if session_of(p)==latest] if latest else []
open_pos=[p for p in positions if str(p.get("status") or "").upper() in {"OPEN","TP1_HIT"}]
closed_pos=[p for p in positions if str(p.get("status") or "").upper()=="CLOSED"]
cur_tier=Counter(tier_of(r) for r in cur if tier_of(r)); cur_status=Counter(str(r.get("status") or "N/D").upper() for r in cur)
open_pnls=[paper_pnl(p) for p in open_pos]; open_total=sum(x for x in open_pnls if x is not None)
closed_pnls=[paper_pnl(p) for p in closed_pos]; closed_total=sum(x for x in closed_pnls if x is not None)
wins=sum(1 for x in closed_pnls if x is not None and x>0); losses=sum(1 for x in closed_pnls if x is not None and x<0); winrate=100*wins/len(closed_pos) if closed_pos else None

if latest:
    st.success(f"🟢 LABORATORIO ATTIVO · Ultima sessione {latest}. Ha analizzato {len(cur)} segnali e aperto {len(cur_pos)} nuovi esperimenti paper.")
else: st.warning("Nessuna sessione Laboratory disponibile.")

c=st.columns(6)
c[0].metric("Segnali ultima sessione",len(cur)); c[1].metric("Nuove aperture paper",len(cur_pos)); c[2].metric("Posizioni aperte",len(open_pos)); c[3].metric("P&L aperto netto",f"${open_total:,.2f}"); c[4].metric("Operazioni chiuse",len(closed_pos)); c[5].metric("Win rate chiuse",f"{winrate:.2f}%" if winrate is not None else "N/D")
st.caption(f"Tier ultima sessione: A {cur_tier.get('A',0)} · B {cur_tier.get('B',0)} · C {cur_tier.get('C',0)} 🔬 · Data reject {cur_status.get('BLOCKED_DATA',0)}")

st.subheader("📊 Quali strategie stanno lavorando")
strategies=sorted({str(r.get("strategy")) for r in signals if r.get("strategy")} | {str(p.get("strategy")) for p in positions if p.get("strategy")})
summary=[]
for strategy in strategies:
    sig=[r for r in cur if str(r.get("strategy"))==strategy]; pp=[p for p in positions if str(p.get("strategy"))==strategy]; op=[p for p in pp if str(p.get("status") or "").upper() in {"OPEN","TP1_HIT"}]; cp=[p for p in pp if str(p.get("status") or "").upper()=="CLOSED"]
    opnl=sum(x for x in (paper_pnl(p) for p in op) if x is not None); cpnl=[paper_pnl(p) for p in cp]; ctotal=sum(x for x in cpnl if x is not None); cw=sum(1 for x in cpnl if x is not None and x>0); cl=sum(1 for x in cpnl if x is not None and x<0)
    summary.append({"Strategia":strategy,"Segnali oggi":len(sig),"Aperte":len(op),"Chiuse":len(cp),"Vinte":cw,"Perse":cl,"P&L aperto $":opnl,"P&L chiuso $":ctotal,"Stato":"🟢 ATTIVA" if sig or op else "⚪ SENZA ATTIVITÀ"})
st.dataframe(fmt(pd.DataFrame(summary)),width="stretch",hide_index=True)

st.subheader("🟢 Cosa sta girando adesso")
open_rows=[]
for p in open_pos:
    pnlv=paper_pnl(p); ret=paper_return(p,pnlv); tier=tier_of(p) or j(p.get("details")).get("paper_tier") or "N/D"
    open_rows.append({"Ticker":p.get("symbol"),"Strategia":p.get("strategy"),"Tier":f"C 🔬" if str(tier)=="C" else tier,"Entry $":n(p.get("entry_price")),"Prezzo $":n(p.get("last_price")),"P&L netto $":pnlv,"Performance %":ret,"Stop $":n(p.get("stop_current")) or n(p.get("stop_initial")),"TP1 $":n(p.get("tp1")),"TP2 $":n(p.get("tp2")),"Esito":"🟢 GUADAGNO" if pnlv is not None and pnlv>0 else ("🔴 PERDITA" if pnlv is not None and pnlv<0 else "⚪ N/D")})
if open_rows: st.dataframe(fmt(pd.DataFrame(open_rows)),width="stretch",hide_index=True)
else: st.info("Nessuna posizione paper aperta in questo momento.")

st.subheader("🏁 Operazioni chiuse · cosa abbiamo realmente imparato")
cc=st.columns(5); cc[0].metric("Chiuse",len(closed_pos)); cc[1].metric("Vinte",wins); cc[2].metric("Perse",losses); cc[3].metric("P&L chiuso netto",f"${closed_total:,.2f}"); cc[4].metric("Win rate",f"{winrate:.2f}%" if winrate is not None else "N/D")
closed_rows=[]
for p in closed_pos:
    pnlv=paper_pnl(p); ret=paper_return(p,pnlv); tier=tier_of(p) or j(p.get("details")).get("paper_tier") or "N/D"
    closed_rows.append({"Ticker":p.get("symbol"),"Strategia":p.get("strategy"),"Tier":f"C 🔬" if str(tier)=="C" else tier,"Entry $":n(p.get("entry_price")),"Prezzo $":n(p.get("exit_price")) or n(p.get("last_price")),"P&L netto $":pnlv,"Performance %":ret,"Esito":"🟢 GUADAGNO" if pnlv is not None and pnlv>0 else ("🔴 PERDITA" if pnlv is not None and pnlv<0 else "⚪ N/D"),"Motivo":p.get("exit_reason")})
if closed_rows: st.dataframe(fmt(pd.DataFrame(closed_rows)),width="stretch",hide_index=True)
else: st.info("Non ci sono ancora operazioni paper chiuse. Finché non maturano trade chiusi, non ha senso giudicare una strategia dal solo P&L aperto.")

with st.expander("🔧 Diagnostica avanzata · perché il laboratorio accetta o rifiuta i segnali",expanded=False):
    st.markdown("Questa sezione serve quando il laboratorio apre troppo poco, troppo, oppure mostra un comportamento anomalo. Per l'uso quotidiano puoi ignorarla.")
    st.markdown("#### Gate Analysis · DATA vs POLICY · A/B/C vs LEGACY")
    counter=Counter()
    for row in cur:
        strategy=str(row.get("strategy") or "N/D")
        for item in gate_rows(row): counter[(strategy,item["family"],item["policy"],item["tier"],item["gate"])]+=1
    gates=[{"Strategia":k[0],"Famiglia":k[1],"Policy":k[2],"Tier":k[3],"Gate":k[4],"Conteggio":v} for k,v in counter.most_common()]
    if gates: st.dataframe(pd.DataFrame(gates),width="stretch",hide_index=True)
    else: st.info("Nessun dettaglio gate disponibile.")
    st.markdown("#### Shadow outcomes")
    obs=Counter()
    for row in outcomes:
        group=j(row.get("details")).get("observation_group")
        if group: obs[str(group)]+=1
    if obs: st.dataframe(pd.DataFrame([{"Gruppo":k,"Osservazioni":v} for k,v in obs.items()]),width="stretch",hide_index=True)
    else: st.info("Nessuno shadow outcome disponibile.")
    st.markdown("#### Confronto ultima sessione vs precedente")
    prev_pos=[p for p in positions if session_of(p)==previous] if previous else []
    st.dataframe(pd.DataFrame([{"Metrica":"Segnali","Ultima":len(cur),"Precedente":len(prev)},{"Metrica":"Paper Open","Ultima":len(cur_pos),"Precedente":len(prev_pos)},{"Metrica":"Tier A","Ultima":cur_tier.get("A",0),"Precedente":Counter(tier_of(r) for r in prev if tier_of(r)).get("A",0)},{"Metrica":"Tier B","Ultima":cur_tier.get("B",0),"Precedente":Counter(tier_of(r) for r in prev if tier_of(r)).get("B",0)},{"Metrica":"Tier C","Ultima":cur_tier.get("C",0),"Precedente":Counter(tier_of(r) for r in prev if tier_of(r)).get("C",0)}]),width="stretch",hide_index=True)

st.caption(f"Cost model Laboratory: $9,90 per lato + {SLIPPAGE_BPS:.0f} bps slippage · Aggiornato {datetime.now().astimezone().strftime('%d/%m/%Y %H:%M:%S %Z')}")
