from __future__ import annotations

import pandas as pd
import streamlit as st

try:
    from dashboard import data_access
except ModuleNotFoundError:
    import dashboard.data_access as data_access

st.set_page_config(page_title="Strategie & Parametri", page_icon="🧠", layout="wide")

ACTIVE = [
    {
        "Strategia":"trend_continuation","Stato":"🟢 ATTIVA","Holding gg":20,
        "Cosa cerca":"Trend strutturale + pullback + momentum + volume + breakout",
        "Score":"Trend 35 · Pullback 25 · Momentum 20 · Volume 10 · Breakout 10",
        "Trigger":"Primario: Prezzo > SMA50 > SMA200",
        "Esperimento":"Shadow buffer: 0% vs +0,5% sopra SMA50",
    },
    {
        "Strategia":"cross_sectional_momentum","Stato":"🟢 ATTIVA","Holding gg":40,
        "Cosa cerca":"Forza relativa rispetto all'intero universo nella stessa sessione",
        "Score":"Percentile Ret20 30% · Ret60 35% · Ret120 35%",
        "Trigger":"Prezzo >= massimo 20 giorni",
        "Esperimento":"Score cross-sectional vero; non rendimenti assoluti",
    },
    {
        "Strategia":"short_term_reversal_rsi45","Stato":"🟢 A/B TEST","Holding gg":10,
        "Cosa cerca":"Reversal dopo eccesso ribassista moderato",
        "Score":"RSI 45 · Stretch 30 · Trend lungo 15 · Stabilizzazione 10",
        "Trigger":"Ret 1g > 0 e RSI14 < 45",
        "Esperimento":"Confrontata separatamente con RSI35 attraverso A/B/C",
    },
    {
        "Strategia":"short_term_reversal_rsi35","Stato":"🟢 A/B TEST","Holding gg":10,
        "Cosa cerca":"Reversal dopo eccesso ribassista più estremo",
        "Score":"RSI 45 · Stretch 30 · Trend lungo 15 · Stabilizzazione 10",
        "Trigger":"Ret 1g > 0 e RSI14 < 35",
        "Esperimento":"RSI score normalizzato sulla propria soglia; A/B/C separati",
    },
    {
        "Strategia":"defensive_low_vol","Stato":"🟢 ATTIVA","Holding gg":60,
        "Cosa cerca":"Bassa volatilità, stabilità, trend e momentum",
        "Score":"Low vol 40 · Trend sopra SMA200 25 · Stabilità ATR 20 · Momentum 60g 15",
        "Trigger":"Prezzo > SMA200",
        "Esperimento":"Rinominata: nessun fondamentale 'quality' nello score",
    },
]

NOT_ACTIVE = [
    {"Strategia":"pead","Stato":"🟠 IMPLEMENTATA MA NON ATTIVA","Holding gg":20,"Manca":"point_in_time_earnings + analyst_revisions"},
    {"Strategia":"event_driven_mean_reversion","Stato":"🟠 IMPLEMENTATA MA NON ATTIVA","Holding gg":10,"Manca":"point_in_time_events"},
    {"Strategia":"quality_value_rerating","Stato":"🟠 IMPLEMENTATA MA NON ATTIVA","Holding gg":60,"Manca":"point_in_time_fundamentals"},
    {"Strategia":"macro_intermarket","Stato":"🟠 IMPLEMENTATA MA NON ATTIVA","Holding gg":40,"Manca":"rates + credit_spreads + commodities + usd"},
]

TIERS = pd.DataFrame([
    {"Tier":"A","Uso":"Quasi Production, sempre paper","Data Quality":"Solo GREEN","Strategy score min":75,"Trade score min":70,"Trigger":"CONFIRMED","R/R netto min":1.75,"Estensione max":"0 ATR sopra MaxBuy","Earnings":">= 7 giorni"},
    {"Tier":"B","Uso":"Sperimentale","Data Quality":"GREEN/YELLOW","Strategy score min":65,"Trade score min":55,"Trigger":"CONFIRMED","R/R netto min":1.15,"Estensione max":"0,5 ATR","Earnings":">= 5 giorni"},
    {"Tier":"C","Uso":"🔬 RESEARCH ONLY · NON OPERATIVO","Data Quality":"GREEN/YELLOW","Strategy score min":55,"Trade score min":40,"Trigger":"Può essere WAITING","R/R netto min":0.75,"Estensione max":"1 ATR","Earnings":"Hard veto < 3 giorni"},
])

st.title("🧠 Strategie & Parametri")
st.caption("Quali strategie stanno girando nel Laboratory, con quali regole, quali esperimenti A/B sono attivi e quali strategie aspettano ancora dati affidabili.")

with st.sidebar:
    st.markdown("## Guida · Strategie & Parametri")
    st.markdown("""
Questa pagina è l'**anagrafica del Laboratory**.

### Cosa è cambiato nella V2
- **Cross-sectional momentum**: il punteggio operativo viene calcolato con percentile Ret20/60/120 **rispetto all'universo nella stessa sessione**. Il breakout 20 giorni resta solo il trigger.
- **Short-term reversal**: RSI35 e RSI45 sono due esperimenti distinti. Ognuno passa separatamente i gate A/B/C. Il peso RSI è normalizzato sulla propria soglia.
- **Defensive low vol**: rimosso `quality` dal nome perché lo score è tecnico, non fondamentale.
- **Trend continuation**: il trigger storico senza buffer resta primario; contemporaneamente registriamo lo shadow test con buffer +0,5% senza aprire una seconda posizione.
- **Cooldown**: 7 sessioni per `ticker + strategia` prima di una nuova apertura paper dopo una posizione precedente.

### Perché non ottimizziamo ogni settimana
I parametri vengono fissati **prima** dell'esperimento. Un eventuale cambio futuro crea una nuova variante/versione, così non scegliamo a posteriori il parametro che fa apparire migliore il passato.

### Holding
`Holding gg` è l'orizzonte massimo/di ricerca previsto. Strategie con holding diversi non vanno confrontate soltanto con il PF grezzo: Research deve considerare anche capitale e tempo impegnato.

### Tier A/B/C
Ogni variante passa separatamente la stessa policy A/B/C. **Tier C resta RESEARCH ONLY e non operativo.**
""")

try:
    signals = data_access.lab_paper_signals(10000)
except Exception:
    signals = []

seen = set(str(r.get("strategy")) for r in signals if r.get("strategy"))
active_df = pd.DataFrame(ACTIVE)
active_df["Visto nei dati"] = active_df["Strategia"].apply(lambda x: "✅ SI" if x in seen else "⚪ DAL PROSSIMO RUN")

c1,c2,c3=st.columns(3)
c1.metric("Strategie/varianti attive",len(ACTIVE))
c2.metric("Strategie presenti ma non attive",len(NOT_ACTIVE))
c3.metric("Totale registrate",len(ACTIVE)+len(NOT_ACTIVE))

st.subheader("🟢 Strategie e varianti attive")
st.dataframe(active_df,width="stretch",hide_index=True)

st.info("Baseline sperimentale congelata: cooldown 7 sessioni; trend buffer 0% primario + 0,5% shadow; reversal RSI35/RSI45 in parallelo. Non modificare queste soglie a posteriori senza creare una nuova versione dell'esperimento.")

st.subheader("⚙️ Parametri comuni di ammissione A/B/C")
st.dataframe(TIERS,width="stretch",hide_index=True)
st.caption("Veti comuni: Data Quality RED, qty <= 0, ATR <= 0, R/R non disponibile, earnings < 3 giorni. Tier C resta sempre non operativo.")

st.markdown("### Limiti del portafoglio paper")
st.dataframe(pd.DataFrame([
    {"Parametro":"Max nuove aperture per run","Valore":12},
    {"Parametro":"Max posizioni attive Laboratory","Valore":80},
    {"Parametro":"Max posizioni attive per strategia","Valore":24},
    {"Parametro":"Cooldown ticker + strategia","Valore":"7 sessioni"},
    {"Parametro":"Commissione scenario Fineco per lato","Valore":"$9,90"},
    {"Parametro":"Slippage di ricerca","Valore":"5 bps"},
]),width="stretch",hide_index=True)

st.subheader("💤 Strategie non ancora messe in campo")
st.dataframe(pd.DataFrame(NOT_ACTIVE),width="stretch",hide_index=True)
st.info("Queste quattro strategie non girano finché non disponiamo delle relative sorgenti point-in-time. Restano in attesa: non vengono surrogate con dati inventati o contemporanei.")
