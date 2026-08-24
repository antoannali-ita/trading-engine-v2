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
    return


def j(value: Any) -> dict:
    if isinstance(value, dict): return value
    try: return json.loads(str(value)) if value else {}
    except Exception: return {}


def n(value: Any) -> float | None:
    try: return float(value) if value is not None else None
    except Exception: return None


def session_of(row: dict[str, Any]) -> str | None:
    value=row.get("signal_date") or row.get("source_signal_date") or row.get("created_at") or row.get("opened_at")
    return str(value)[:10] if value else None


def tier_of(row: dict[str, Any]) -> str | None:
    d=j(row.get("details")); policy=j(d.get("paper_policy")); value=d.get("paper_tier") or policy.get("tier")
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
        if c in {"Entry $","Prezzo $","Stop $","TP1 $","TP2 $","P&L netto $","P&L aperto $","P&L chiuso $"}: formats[c]="{:.2f}"
        elif "%" in c or c=="Conversione": formats[c]="{:.2f}%"
        elif pd.api.types.is_float_dtype(frame[c]): formats[c]="{:.2f}"
    return frame.style.format(formats,na_rep="-")


def color_trade_rows(styler, pnl_column: str):
    def row_style(row):
        value=n(row.get(pnl_column))
        if value is None or abs(value) < 1e-12: return [""]*len(row)
        css="background-color: rgba(46, 160, 67, 0.16); color: #137333; font-weight: 600;" if value>0 else "background-color: rgba(248, 81, 73, 0.16); color: #b42318; font-weight: 600;"
        return [css]*len(row)
    return styler.apply(row_style,axis=1)


def color_strategy_rows(styler):
    def row_style(row):
        value=(n(row.get("P&L aperto $")) or 0)+(n(row.get("P&L chiuso $")) or 0)
        if abs(value)<1e-12: return [""]*len(row)
        css="background-color: rgba(46, 160, 67, 0.16); color: #137333; font-weight: 600;" if value>0 else "background-color: rgba(248, 81, 73, 0.16); color: #b42318; font-weight: 600;"
        return [css]*len(row)
    return styler.apply(row_style,axis=1)


def gate_rows(signal: dict[str, Any]) -> list[dict[str,str]]:
    d=j(signal.get("details")); policy=j(d.get("paper_policy")); out=[]
    for gate in policy.get("data_gate_failures",[]) or []: out.append({"family":"DATA","policy":"PAPER_POLICY","tier":"ALL","gate":str(gate)})
    for gate in policy.get("policy_hard_failures",[]) or []: out.append({"family":"POLICY","policy":"PAPER_POLICY","tier":"ALL","gate":str(gate)})
    checks=policy.get("tier_checks") or {}
    if isinstance(checks,dict):
        for tier,check in checks.items():
            if isinstance(check,dict):
                for gate in check.get("failed",[]) or []: out.append({"family":"DATA" if str(gate).startswith("DATA_") else "POLICY","policy":"PAPER_POLICY","tier":str(tier),"gate":str(gate)})
    strict=j(d.get("strict_trade_eligibility") or d.get("trade_eligibility"))
    for gate in strict.get("failed",[]) or []: out.append({"family":"DATA" if "DATA" in str(gate) else "POLICY","policy":"LEGACY_STRICT","tier":"LEGACY","gate":str(gate)})
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
Il Laboratory è il **campo di prova** del Trading Engine. Non decide cosa comprare nel portafoglio reale: prova strategie e regole con capitale virtuale.

### Colori
- 🟢 **riga verde** = strategia/trade in guadagno netto.
- 🔴 **riga rossa** = strategia/trade in perdita netta.
- Nessun colore = risultato neutro o non ancora calcolabile.

### Le 5 domande da farsi
1. **Sta lavorando?** Guarda segnali analizzati e operazioni paper aperte.
2. **Sta guadagnando?** Guarda P&L netto, vinte/perse e performance.
3. **Quale strategia va meglio?** Confronta operazioni, P&L e risultati per strategia.
4. **Cosa sta testando adesso?** Guarda le posizioni aperte.
5. **Perché non apre più trade?** Apri la Diagnostica avanzata e guarda i gate.

### Tier A / B / C
- **A:** quasi Production.
- **B:** sperimentale.
- **C:** 🔬 **RESEARCH ONLY · NON OPERATIVO**.

### Costi
Il P&L è paper netto: commissioni Fineco-like **$9,90 per lato** + slippage di ricerca **5 bps**.

### Data Quality
- **RED:** veto.
- **YELLOW:** ammesso solo B/C, mai A.

### Gate
**DATA GATES** = problemi/limiti dei dati. **POLICY GATES** = regole strategiche come score, trigger, R/R, Max Buy ed earnings.

### Shadow outcomes
I rejected-C con dati validi possono essere seguiti a D+1/D+3/D+5/D+10/D+20 per misurare l'efficacia dei gate.

### Regola importante
Il Laboratory accumula evidenza ma **non promuove automaticamente** una strategia in Production.
""")

try: data=load_data()
except Exception as exc:
    st.error(f"Impossibile leggere i dati Laboratory: {type(exc).__name__}: {exc}"); st.stop()
signals=data["signals"]; positions=data["positions"]; outcomes=data["outcomes"]
sessions=sorted({x for x in (session_of(r) for r in signals) if x}); latest=sessions[-1] if sessions else None; previous=sessions[-2] if len(sessions)>1 else None
cur=[r for r in signals if session_of(r)==latest] if latest else []; prev=[r for r in signals if session_of(r)==previous] if previous else []
cur_pos=[p for p in positions if session_of(p)==latest] if latest else []
open_pos=[p for p in positions if str(p.get("status") or "").upper() in {"OPEN","TP1_HIT"}]; closed_pos=[p for p in positions if str(p.get("status") or "").upper()=="CLOSED"]
cur_tier=Counter(tier_of(r) for r in cur if tier_of(r)); cur_status=Counter(str(r.get("status") or "N/D").upper() for r in cur)
open_pnls=[paper_pnl(p) for p in open_pos]; open_total=sum(x for x in open_pnls if x is not None); closed_pnls=[paper_pnl(p) for p in closed_pos]; closed_total=sum(x for x in closed_pnls if x is not None)
wins=sum(1 for x in closed_pnls if x is not None and x>0); losses=sum(1 for x in closed_pnls if x is not None and x<0); winrate=100*wins/len(closed_pos) if closed_pos else None

if latest: st.success(f"🟢 LABORATORIO ATTIVO · Ultima sessione {latest}. Ha analizzato {len(cur)} segnali e aperto {len(cur_pos)} nuovi esperimenti paper.")
else: st.warning("Nessuna sessione Laboratory disponibile.")
c=st.columns(6); c[0].metric("Segnali ultima sessione",len(cur)); c[1].metric("Nuove aperture paper",len(cur_pos)); c[2].metric("Posizioni aperte",len(open_pos)); c[3].metric("P&L aperto netto",f"${open_total:,.2f}"); c[4].metric("Operazioni chiuse",len(closed_pos)); c[5].metric("Win rate chiuse",f"{winrate:.2f}%" if winrate is not None else "N/D")
st.caption(f"Tier ultima sessione: A {cur_tier.get('A',0)} · B {cur_tier.get('B',0)} · C {cur_tier.get('C',0)} 🔬 · Data reject {cur_status.get('BLOCKED_DATA',0)}")

st.subheader("📊 Quali strategie stanno lavorando")
strategies=sorted({str(r.get("strategy")) for r in signals if r.get("strategy")} | {str(p.get("strategy")) for p in positions if p.get("strategy")}); summary=[]
for strategy in strategies:
    sig=[r for r in cur if str(r.get("strategy"))==strategy]; pp=[p for p in positions if str(p.get("strategy"))==strategy]; op=[p for p in pp if str(p.get("status") or "").upper() in {"OPEN","TP1_HIT"}]; cp=[p for p in pp if str(p.get("status") or "").upper()=="CLOSED"]
    opnl=sum(x for x in (paper_pnl(p) for p in op) if x is not None); cpnl=[paper_pnl(p) for p in cp]; ctotal=sum(x for x in cpnl if x is not None); cw=sum(1 for x in cpnl if x is not None and x>0); cl=sum(1 for x in cpnl if x is not None and x<0)
    summary.append({"Strategia":strategy,"Segnali oggi":len(sig),"Aperte":len(op),"Chiuse":len(cp),"Vinte":cw,"Perse":cl,"P&L aperto $":opnl,"P&L chiuso $":ctotal,"Stato":"🟢 ATTIVA" if sig or op else "⚪ SENZA ATTIVITÀ"})
summary_df=pd.DataFrame(summary); st.dataframe(color_strategy_rows(fmt(summary_df)),width="stretch",hide_index=True)

st.subheader("🟢 Cosa sta girando adesso"); open_rows=[]
for p in open_pos:
    pnlv=paper_pnl(p); ret=paper_return(p,pnlv); tier=tier_of(p) or j(p.get("details")).get("paper_tier") or "N/D"
    open_rows.append({"Ticker":p.get("symbol"),"Strategia":p.get("strategy"),"Tier":f"C 🔬" if str(tier)=="C" else tier,"Entry $":n(p.get("entry_price")),"Prezzo $":n(p.get("last_price")),"P&L netto $":pnlv,"Performance %":ret,"Stop $":n(p.get("stop_current")) or n(p.get("stop_initial")),"TP1 $":n(p.get("tp1")),"TP2 $":n(p.get("tp2")),"Esito":"🟢 GUADAGNO" if pnlv is not None and pnlv>0 else ("🔴 PERDITA" if pnlv is not None and pnlv<0 else "⚪ N/D")})
if open_rows:
    open_df=pd.DataFrame(open_rows); st.dataframe(color_trade_rows(fmt(open_df),"P&L netto $"),width="stretch",hide_index=True)
else: st.info("Nessuna posizione paper aperta in questo momento.")

st.subheader("🏁 Operazioni chiuse · cosa abbiamo realmente imparato")
cc=st.columns(5); cc[0].metric("Chiuse",len(closed_pos)); cc[1].metric("Vinte",wins); cc[2].metric("Perse",losses); cc[3].metric("P&L chiuso netto",f"${closed_total:,.2f}"); cc[4].metric("Win rate",f"{winrate:.2f}%" if winrate is not None else "N/D"); closed_rows=[]
for p in closed_pos:
    pnlv=paper_pnl(p); ret=paper_return(p,pnlv); tier=tier_of(p) or j(p.get("details")).get("paper_tier") or "N/D"
    closed_rows.append({"Ticker":p.get("symbol"),"Strategia":p.get("strategy"),"Tier":f"C 🔬" if str(tier)=="C" else tier,"Entry $":n(p.get("entry_price")),"Prezzo $":n(p.get("exit_price")) or n(p.get("last_price")),"P&L netto $":pnlv,"Performance %":ret,"Esito":"🟢 GUADAGNO" if pnlv is not None and pnlv>0 else ("🔴 PERDITA" if pnlv is not None and pnlv<0 else "⚪ N/D"),"Motivo":p.get("exit_reason")})
if closed_rows:
    closed_df=pd.DataFrame(closed_rows); st.dataframe(color_trade_rows(fmt(closed_df),"P&L netto $"),width="stretch",hide_index=True)
else: st.info("Non ci sono ancora operazioni paper chiuse. Finché non maturano trade chiusi, non ha senso giudicare una strategia dal solo P&L aperto.")

with st.expander("🔧 Diagnostica avanzata · perché il laboratorio accetta o rifiuta i segnali",expanded=False):
    st.markdown("Questa sezione serve quando il laboratorio apre troppo poco, troppo, oppure mostra un comportamento anomalo. Per l'uso quotidiano puoi ignorarla.")
    st.markdown("#### Gate Analysis · DATA vs POLICY · A/B/C vs LEGACY"); counter=Counter()
    for row in cur:
        strategy=str(row.get("strategy") or "N/D")
        for item in gate_rows(row): counter[(strategy,item["family"],item["policy"],item["tier"],item["gate"])]+=1
    gates=[{"Strategia":k[0],"Famiglia":k[1],"Policy":k[2],"Tier":k[3],"Gate":k[4],"Conteggio":v} for k,v in counter.most_common()]
    if gates: st.dataframe(pd.DataFrame(gates),width="stretch",hide_index=True)
    else: st.info("Nessun dettaglio gate disponibile.")
    st.markdown("#### Shadow outcomes"); obs=Counter()
    for row in outcomes:
        group=j(row.get("details")).get("observation_group")
        if group: obs[str(group)]+=1
    if obs: st.dataframe(pd.DataFrame([{"Gruppo":k,"Osservazioni":v} for k,v in obs.items()]),width="stretch",hide_index=True)
    else: st.info("Nessuno shadow outcome disponibile.")
    st.markdown("#### Confronto ultima sessione vs precedente"); prev_pos=[p for p in positions if session_of(p)==previous] if previous else []; prev_tier=Counter(tier_of(r) for r in prev if tier_of(r))
    st.dataframe(pd.DataFrame([{"Metrica":"Segnali","Ultima":len(cur),"Precedente":len(prev)},{"Metrica":"Paper Open","Ultima":len(cur_pos),"Precedente":len(prev_pos)},{"Metrica":"Tier A","Ultima":cur_tier.get("A",0),"Precedente":prev_tier.get("A",0)},{"Metrica":"Tier B","Ultima":cur_tier.get("B",0),"Precedente":prev_tier.get("B",0)},{"Metrica":"Tier C","Ultima":cur_tier.get("C",0),"Precedente":prev_tier.get("C",0)}]),width="stretch",hide_index=True)

st.caption(f"Cost model Laboratory: $9,90 per lato + {SLIPPAGE_BPS:.0f} bps slippage · Aggiornato {datetime.now().astimezone().strftime('%d/%m/%Y %H:%M:%S %Z')}")
