from __future__ import annotations

import time
import streamlit as st

from dashboard.data_access import engine_health, manual_requests, request_run

st.set_page_config(page_title="Esegui ora", page_icon="▶️", layout="wide")
st.title("▶️ Esegui ora")
st.caption("Avvio manuale dei motori registrati. La richiesta passa da Supabase e viene presa in carico dall'Orchestrator.")

try:
    engines = engine_health()
except Exception as exc:
    st.error(f"Impossibile leggere i motori: {type(exc).__name__}: {exc}")
    st.stop()

options = []
lookup = {}
for row in engines:
    engine_id = str(row.get("engine_id") or "").strip()
    if not engine_id:
        continue
    strategy = str(row.get("strategy") or "-")
    market = str(row.get("market") or "-")
    label = f"{engine_id} | {strategy} | {market}"
    options.append(label)
    lookup[label] = row

if not options:
    st.info("Nessun motore registrato disponibile.")
    st.stop()

selected = st.selectbox("Motore", options)
requested_by = st.text_input("Richiesto da", value="Antonio")
row = lookup[selected]

c1, c2 = st.columns(2)
with c1:
    send_email = st.checkbox("Invia Email", value=False)
with c2:
    send_whatsapp = st.checkbox("Invia WhatsApp", value=False)

if st.button("▶️ ESEGUI ORA", type="primary"):
    engine_id = str(row.get("engine_id") or "")
    market = str(row.get("market") or "")
    strategy = row.get("strategy")
    try:
        created = request_run(
            engine_id,
            market,
            strategy,
            send_email=send_email,
            send_whatsapp=send_whatsapp,
            requested_by=requested_by.strip() or "dashboard",
        )
    except Exception as exc:
        st.error(f"Richiesta non creata: {type(exc).__name__}: {exc}")
        st.stop()

    request_id = str(created.get("request_id") or "").strip()
    if not request_id:
        st.warning("Richiesta creata ma senza request_id: impossibile seguirne lo stato.")
    else:
        labels = {
            "REQUESTED": (10, "Richiesta registrata"),
            "PENDING": (15, "In attesa di presa in carico"),
            "DISPATCHED": (35, "Workflow inviato a GitHub Actions"),
            "RUNNING": (65, "Motore in esecuzione"),
            "STARTED": (65, "Motore in esecuzione"),
            "SUCCESS": (100, "Esecuzione completata"),
            "COMPLETED": (100, "Esecuzione completata"),
            "FAILED": (100, "Esecuzione terminata con errore"),
            "ERROR": (100, "Esecuzione terminata con errore"),
            "CANCELLED": (100, "Esecuzione annullata"),
        }
        with st.status(f"Avvio {engine_id}", expanded=True) as box:
            progress = st.progress(5, text="Creazione richiesta...")
            st.write(f"Request ID: `{request_id}`")
            deadline = time.time() + 120
            last_state = None
            while time.time() < deadline:
                rows = manual_requests(250)
                current = next((r for r in rows if str(r.get("request_id") or "") == request_id), None)
                if current:
                    state = str(current.get("status") or "REQUESTED").upper()
                    pct, text = labels.get(state, (25, f"Stato: {state}"))
                    progress.progress(pct, text=text)
                    if state != last_state:
                        st.write(f"• {text}")
                        if current.get("github_run_id"):
                            st.write(f"• GitHub run: `{current.get('github_run_id')}`")
                        if current.get("run_id"):
                            st.write(f"• Engine run: `{current.get('run_id')}`")
                        last_state = state
                    if state in {"SUCCESS", "COMPLETED"}:
                        box.update(label=f"✅ {engine_id} completato", state="complete", expanded=False)
                        break
                    if state in {"FAILED", "ERROR", "CANCELLED"}:
                        st.error(str(current.get("error_message") or "Nessun dettaglio errore disponibile"))
                        box.update(label=f"❌ {engine_id}: {state}", state="error", expanded=True)
                        break
                time.sleep(2)
            else:
                progress.progress(80, text="Run avviato; completamento non ancora registrato entro 120 s")
                st.info("Il run continua in background. Puoi seguirlo dalla pagina Run e Log.")
                box.update(label=f"⏳ {engine_id} ancora in esecuzione", state="running", expanded=False)
