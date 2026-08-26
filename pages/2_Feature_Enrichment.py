from __future__ import annotations

from datetime import datetime

import streamlit as st

st.set_page_config(page_title="LAB-FEAT-001 · Feature Enrichment", page_icon="🧪", layout="wide")

st.title("🧪 LAB-FEAT-001 · TradingView Feature Enrichment")
st.caption("Layer trasversale di ricerca del Laboratory. Non è una strategia e non modifica alcuna decisione Production.")

st.info("🧪 DATA COLLECTION · LAB ONLY · PROD-001 FROZEN")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Stato", "DATA COLLECTION")
c2.metric("Ambiente", "LAB ONLY")
c3.metric("Production", "FROZEN")
c4.metric("Impatto CORE", "NESSUNO")

st.subheader("Cosa fa")
st.markdown(
    """
LAB-FEAT-001 arricchisce **passivamente** i segnali già prodotti dalle strategie Laboratory.
Raccoglie feature candidate per capire, con dati reali e analisi post-hoc, se una singola variabile
aggiunge informazione utile. **Non genera nuovi trade** e non cambia eligibility, score, Entry, Stop,
Max Buy, sizing, trigger o decisione.
"""
)

st.subheader("Feature candidate")
st.dataframe(
    {
        "Feature": [
            "Relative Volume", "Relative Strength 1M", "Relative Strength 3M", "Relative Strength 6M",
            "Distanza SMA20", "Distanza SMA50", "Distanza SMA200", "ATR14", "ATR14 %",
            "Gap %", "Distanza 52W High", "Distanza 52W Low",
        ],
        "Uso attuale": ["METADATO PASSIVO"] * 12,
        "Influenza decisione": ["NO"] * 12,
    },
    width="stretch",
    hide_index=True,
)

st.subheader("Benchmark Relative Strength")
b1, b2 = st.columns(2)
b1.success("🇺🇸 USA → SPY · RS-BENCHMARK.v1")
b2.success("🇮🇹 ITALIA → FTSEMIB · RS-BENCHMARK.v1")
st.caption("Il benchmark è versionato. Un cambio futuro crea una nuova versione e non riscrive retroattivamente i dati raccolti.")

st.subheader("Percorso di validazione")
st.markdown(
    """
**LAB DATA → POST-HOC → LAB ONLY / REJECT oppure A/B VARIANT → EVIDENCE → SHADOW → PRODUCTION CANDIDATE**

La prima fase usa valori continui grezzi. Non viene scelta a tavolino una soglia tipo `RelVol > 1.5`.
Una feature viene testata singolarmente; solo se mostra evidence può diventare variante A/B della
strategia interessata. L'eventuale uso decisionale in Production appartiene a **PROD-001**, che resta congelato.
"""
)

st.subheader("Guardrail")
st.markdown(
    """
- Non è una nona strategia.
- Non apre paper trade aggiuntivi.
- Non modifica i trade che le strategie avrebbero aperto senza enrichment.
- Non introduce soglie nel CORE.
- Non combina molte feature in un unico filtro durante la prima validazione.
- Production non deve dipendere dal modulo Laboratory di enrichment.
"""
)

st.warning(
    "PROD-001 è FROZEN: questi dati non possono modificare segnali o ordini Production finché non esistono evidence, regressione e shadow validation sufficienti."
)

with st.sidebar:
    st.markdown("## Guida · LAB-FEAT-001")
    st.markdown("**Tipo:** Feature Enrichment Layer")
    st.markdown("**Stato:** DATA COLLECTION")
    st.markdown("**Ambiente:** Laboratory")
    st.markdown("**Production:** FROZEN")
    st.divider()
    st.caption("Questa pagina rende visibile l'esperimento senza confonderlo con le strategie operative del Laboratory.")

st.caption(f"UI LAB-FEAT-001 · Updated: {datetime.now().astimezone().strftime('%d/%m/%Y %H:%M:%S %Z')}")
