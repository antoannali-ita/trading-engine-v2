from __future__ import annotations

import os
import traceback
from datetime import datetime
from pathlib import Path

import streamlit as st

# TEMPORARY: autenticazione dashboard sospesa su richiesta.
os.environ["DASHBOARD_PASSWORD"] = ""

# Streamlit Cloud avvia dashboard/app.py, mentre le pagine storiche del progetto
# sono nella directory /pages alla root del repository. Usiamo path assoluti
# per evitare che st.navigation cerchi erroneamente dashboard/pages/...
REPO_ROOT = Path(__file__).resolve().parent.parent
PAGES_DIR = REPO_ROOT / "pages"


def _render_recovery(exc: Exception) -> None:
    st.error("⚠️ Trading Engine Control Center temporaneamente non disponibile")
    st.write("L'app è partita, ma si è verificato un errore durante il caricamento della dashboard.")
    c1, c2 = st.columns([1, 3])
    with c1:
        if st.button("🔄 Riprova", type="primary", use_container_width=True):
            try:
                st.cache_data.clear()
                st.cache_resource.clear()
            except Exception:
                pass
            st.rerun()
    with c2:
        st.caption("Se dopo il redeploy la pagina resta in errore, controllare il dettaglio tecnico.")
    st.markdown("### Stato bootstrap")
    st.write(f"**Ora:** {datetime.now().astimezone().strftime('%d/%m/%Y %H:%M:%S %Z')}")
    st.write(f"**Errore:** `{type(exc).__name__}`")
    st.write(f"**Messaggio:** {str(exc) or 'N/D'}")
    with st.expander("🔧 Dettaglio tecnico", expanded=False):
        st.code(traceback.format_exc(), language="text")
    st.info("Un errore del sito non modifica Production, le posizioni Fineco o i workflow già avviati.")


GUIDE = {
    "Home": "Vista sintetica del sistema. Serve per capire in pochi secondi se ci sono motori in errore, candidati da seguire o attività che richiedono attenzione.",
    "Portafoglio reale": "Posizioni e livelli operativi del portafoglio reale. È la fonte di contesto per concentrazione e rischio prima di nuovi acquisti.",
    "Watchlist": "Titoli interessanti da seguire nel tempo. Non equivale a BUY: evidenzia avvicinamento a entry, cambi di stato e necessità di rianalisi.",
    "Trade Committee": "Due diligence manuale pre-trade. Il CORE resta la fonte dei livelli operativi; il Committee può confermare o bloccare, non creare un BUY autonomo.",
    "Esegui ora": "Avvio manuale controllato dei motori disponibili. Mostra avanzamento e stato senza generare ordini automatici.",
    "Notifiche": "Storico dei ticker per cui è stata generata una notifica. Mostra canale, esito e messaggio quando disponibile.",
    "Panoramica Laboratorio": "Sintesi del Laboratory: candidati, paper signal, esperimenti e risultati senza impatto automatico sulla Produzione.",
    "Controllo Laboratorio": "Controlli operativi e stato delle pipeline sperimentali del Laboratory.",
    "Strategie": "Area di ricerca sulle strategie: confronti, prove e validazioni prima di una eventuale promozione.",
    "Parametri strategie": "Parametri e soglie delle strategie di laboratorio. Le modifiche qui non devono diventare Production senza evidenza e promozione esplicita.",
    "Feature Enrichment": "Arricchimento dei candidati con nuove feature e sorgenti sperimentali. È ricerca, non segnale operativo autonomo.",
    "Paper Portfolio": "Portafoglio simulato del Laboratory. Serve a misurare le strategie senza capitale reale.",
    "Evoluzione ricerca": "Storico di esperimenti, varianti e risultati usati per decidere cosa mantenere, modificare o scartare.",
    "App completa": "Interfaccia storica completa. Contiene le viste non ancora portate nel menu principale ed è mantenuta come accesso di sicurezza.",
}


def _page(filename: str, title: str, icon: str):
    path = PAGES_DIR / filename
    if not path.is_file():
        raise FileNotFoundError(f"Pagina dashboard non trovata: {path}")
    return st.Page(str(path), title=title, icon=icon)


try:
    navigation = {
        "🟢 PRODUZIONE": [
            _page("0_Home.py", "Home", "🏠"),
            _page("1_Portafoglio_Reale.py", "Portafoglio reale", "💼"),
            _page("1_Watchlist.py", "Watchlist", "👀"),
            _page("5_Trade_Committee.py", "Trade Committee", "🔬"),
            _page("6_Esegui_Ora.py", "Esegui ora", "▶️"),
            _page("7_Notifiche.py", "Notifiche", "🔔"),
        ],
        "🧪 LABORATORIO": [
            _page("2_Laboratory_Overview.py", "Panoramica Laboratorio", "🧭"),
            _page("2_Laboratory_Control.py", "Controllo Laboratorio", "🧪"),
            _page("2_Strategy_Lab.py", "Strategie", "🧠"),
            _page("2_Strategie_Parametri.py", "Parametri strategie", "🎛️"),
            _page("2_Feature_Enrichment.py", "Feature Enrichment", "🧬"),
            _page("3_Paper_Portfolio.py", "Paper Portfolio", "📄"),
            _page("4_Research_Evolution.py", "Evoluzione ricerca", "📈"),
        ],
        "ALTRO": [
            _page("99_App_Completa.py", "App completa", "🧰"),
        ],
    }

    pg = st.navigation(navigation, position="sidebar", expanded=True)

    with st.sidebar:
        st.divider()
        title = getattr(pg, "title", "")
        guide = GUIDE.get(title)
        if guide:
            with st.expander("ℹ️ Guida della pagina", expanded=False):
                st.write(guide)
        st.caption("Produzione = capitale reale · Laboratorio = ricerca e simulazione")

    pg.run()
except Exception as exc:
    _render_recovery(exc)
