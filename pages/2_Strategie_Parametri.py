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
        "Trigger":"Prezzo > SMA50 > SMA200",
        "Entry ideale":"SMA50, fallback SMA20",
    },
    {
        "Strategia":"cross_sectional_momentum","Stato":"🟢 ATTIVA","Holding gg":40,
        "Cosa cerca":"Titoli con forza relativa multi-orizzonte",
        "Score":"Ret 20g 30 · Ret 60g 35 · Ret 120g 35",
        "Trigger":"Prezzo >= massimo 20 giorni",
        "Entry ideale":"Massimo 20 giorni",
    },
    {
        "Strategia":"short_term_reversal","Stato":"🟢 ATTIVA","Holding gg":10,
        "Cosa cerca":"Eccesso ribassista con stabilizzazione",
        "Score":"RSI oversold 45 · Stretch vs SMA20/ATR 30 · Trend lungo 15 · Stabilizzazione 10",
        "Trigger":"Ret 1g > 0 e RSI14 < 45",
        "Entry ideale":"Prezzo corrente",
    },
    {
        "Strategia":"defensive_low_vol_quality","Stato":"🟢 ATTIVA","Holding gg":60,
        "Cosa cerca":"Bassa volatilità, stabilità, trend e momentum",
        "Score":"Low vol 40 · Trend sopra SMA200 25 · Stabilità ATR 20 · Momentum 60g 15",
        "Trigger":"Prezzo > SMA200",
        "Entry ideale":"SMA20, fallback prezzo",
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
st.caption("Quali strategie stanno girando nel Laboratory, con quali regole, e quali sono presenti ma non ancora messe in campo.")

with st.sidebar:
    st.markdown("## Guida · Strategie & Parametri")
    st.markdown("""
Questa pagina è l'**anagrafica del Laboratory**.

- **ATTIVA**: genera score/segnali nel run corrente del laboratorio.
- **IMPLEMENTATA MA NON ATTIVA**: esiste nel codice, ma non può ancora generare segnali perché richiede dati che oggi non alimentiamo in modo point-in-time.
- **Holding gg**: orizzonte di ricerca previsto, non una scadenza obbligatoria del trade.
- **Score**: come viene costruito il punteggio 0-100 della strategia.
- **Trigger**: condizione tecnica usata per distinguere un setup maturo da uno ancora in attesa.
- **Tier A/B/C**: policy comune che decide quanto deve essere forte il segnale per diventare esperimento paper.

La pagina descrive il codice attuale del Laboratory. Non è una raccomandazione operativa e non modifica Production.
""")

try:
    signals = data_access.lab_paper_signals(10000)
except Exception:
    signals = []

seen = set(str(r.get("strategy")) for r in signals if r.get("strategy"))
active_df = pd.DataFrame(ACTIVE)
active_df["Visto nei dati"] = active_df["Strategia"].apply(lambda x: "✅ SI" if x in seen else "⚪ NON ANCORA")

c1,c2,c3=st.columns(3)
c1.metric("Strategie attive",len(ACTIVE))
c2.metric("Strategie presenti ma non attive",len(NOT_ACTIVE))
c3.metric("Totale registrate",len(ACTIVE)+len(NOT_ACTIVE))

st.subheader("🟢 Strategie attive")
st.dataframe(active_df,width="stretch",hide_index=True)

st.subheader("⚙️ Parametri comuni di ammissione A/B/C")
st.dataframe(TIERS,width="stretch",hide_index=True)
st.caption("Veti comuni: Data Quality RED, qty <= 0, ATR <= 0, R/R non disponibile, earnings < 3 giorni. Tier C resta sempre non operativo.")

st.markdown("### Limiti del portafoglio paper")
st.dataframe(pd.DataFrame([
    {"Parametro":"Max nuove aperture per run","Valore":12},
    {"Parametro":"Max posizioni attive Laboratory","Valore":80},
    {"Parametro":"Max posizioni attive per strategia","Valore":24},
    {"Parametro":"Commissione scenario Fineco per lato","Valore":"$9,90"},
    {"Parametro":"Slippage di ricerca","Valore":"5 bps"},
]),width="stretch",hide_index=True)

st.subheader("💤 Strategie non ancora messe in campo")
st.dataframe(pd.DataFrame(NOT_ACTIVE),width="stretch",hide_index=True)
st.info("Queste quattro strategie sono già registrate nel codice, ma hanno generator=None: non girano finché non disponiamo delle relative sorgenti point-in-time. Non le considero fallite: semplicemente non sono ancora testabili in modo corretto.")
