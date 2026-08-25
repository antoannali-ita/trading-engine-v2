from __future__ import annotations

import os
import traceback
from datetime import datetime

# TEMPORARY: autenticazione dashboard sospesa su richiesta.
# Per riattivarla rimuovere questa riga e ripristinare DASHBOARD_PASSWORD.
os.environ["DASHBOARD_PASSWORD"] = ""


def _render_recovery(exc: Exception) -> None:
    """Mostra una pagina di recupero invece di lasciare una schermata bianca.

    Questa funzione viene usata solo quando il bootstrap della dashboard fallisce
    prima che la UI normale riesca a gestire l'errore. Non espone secret.
    """
    import streamlit as st

    st.error("⚠️ Trading Engine Control Center temporaneamente non disponibile")
    st.write(
        "L'app è partita, ma una dipendenza o una sorgente dati ha generato un errore durante il caricamento. "
        "Può succedere durante un redeploy Streamlit o per un problema temporaneo di rete/Supabase/Yahoo."
    )

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
        st.caption(
            "Se dopo 1-2 tentativi la pagina resta in errore, controllare i log Streamlit Cloud: "
            "il problema non viene nascosto e il dettaglio tecnico è disponibile qui sotto."
        )

    st.markdown("### Stato bootstrap")
    st.write(f"**Ora:** {datetime.now().astimezone().strftime('%d/%m/%Y %H:%M:%S %Z')}")
    st.write(f"**Errore:** `{type(exc).__name__}`")
    st.write(f"**Messaggio:** {str(exc) or 'N/D'}")

    with st.expander("🔧 Dettaglio tecnico", expanded=False):
        # Il traceback contiene solo stack applicativo; non stampiamo environment/secrets.
        st.code(traceback.format_exc(), language="text")

    st.info(
        "La dashboard non genera ordini reali da questa pagina. Un errore del sito non modifica Production, "
        "le posizioni Fineco o i workflow già avviati."
    )


try:
    try:
        from dashboard.ui_v7 import *  # noqa: F401,F403
    except ModuleNotFoundError:
        from ui_v7 import *  # type: ignore  # noqa: F401,F403
except Exception as exc:
    _render_recovery(exc)
