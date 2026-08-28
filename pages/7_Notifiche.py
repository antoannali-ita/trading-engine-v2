from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta, timezone

import pandas as pd
import streamlit as st

from dashboard.data_access import get_client, notifications, safe_table_rows, utc_label

st.set_page_config(page_title="Alert Center", page_icon="🔔", layout="wide")
st.title("🔔 Alert Center")
st.caption("Alert prezzo indipendenti dal resto del motore. Notifiche operative: solo WhatsApp. Fineco continua a essere letto dalla mail come prima.")


def extract_message(payload):
    if payload is None:
        return "-"
    if isinstance(payload, str):
        text = payload.strip()
        if not text:
            return "-"
        try:
            payload = json.loads(text)
        except Exception:
            return text
    if isinstance(payload, dict):
        for key in ("message", "text", "body", "summary", "whatsapp_message", "content", "subject"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        try:
            return json.dumps(payload, ensure_ascii=False)
        except Exception:
            return str(payload)
    return str(payload)


def alert_rows():
    return safe_table_rows("trading_alerts", order="created_at", limit=2000)


def refresh():
    st.rerun()


tab_active, tab_new, tab_history = st.tabs(["🎯 Alert", "➕ Nuovo alert", "📨 Storico WhatsApp"])

with tab_active:
    rows = alert_rows()
    if not rows:
        st.info("Nessun alert presente. Creane uno dalla scheda 'Nuovo alert'.")
    else:
        frame = pd.DataFrame(rows)
        for col in ("expires_at", "last_checked_at", "triggered_at", "last_notification_at", "created_at"):
            if col in frame.columns:
                frame[col] = frame[col].map(utc_label)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Attivi", int((frame["status"] == "ACTIVE").sum()))
        c2.metric("Scattati", int((frame["status"] == "TRIGGERED").sum()))
        c3.metric("Scaduti", int((frame["status"] == "EXPIRED").sum()))
        c4.metric("Errori", int((frame["status"] == "ERROR").sum()))

        status_filter = st.multiselect(
            "Stato",
            ["ACTIVE", "TRIGGERED", "EXPIRED", "DISABLED", "ERROR"],
            default=["ACTIVE", "TRIGGERED"],
        )
        view = frame[frame["status"].isin(status_filter)] if status_filter else frame
        wanted = [
            "ticker", "market", "condition_type", "trigger_level", "last_price", "status",
            "expires_at", "source", "dedup_minutes", "last_checked_at", "last_notification_at", "note",
        ]
        st.dataframe(view[[c for c in wanted if c in view.columns]], hide_index=True, use_container_width=True)

        st.divider()
        st.subheader("Gestione alert")
        labels = {
            str(r["alert_id"]): f"{r['ticker']} | {r['condition_type']} {r['trigger_level']} | {r['status']}"
            for r in rows
        }
        selected_id = st.selectbox("Alert", list(labels), format_func=lambda x: labels[x])
        selected = next(r for r in rows if str(r["alert_id"]) == selected_id)
        a, b, c = st.columns(3)
        if a.button("⏸️ Disattiva", use_container_width=True, disabled=selected.get("status") == "DISABLED"):
            get_client().table("trading_alerts").update({"status": "DISABLED"}).eq("alert_id", selected_id).execute()
            refresh()
        if b.button("▶️ Riattiva", use_container_width=True, disabled=selected.get("status") == "ACTIVE"):
            get_client().table("trading_alerts").update({"status": "ACTIVE", "triggered_at": None}).eq("alert_id", selected_id).execute()
            refresh()
        if c.button("🗑️ Elimina", type="secondary", use_container_width=True):
            get_client().table("trading_alerts").delete().eq("alert_id", selected_id).execute()
            refresh()

with tab_new:
    st.subheader("Inserimento rapido")
    st.caption("Il prezzo attuale viene letto automaticamente dal motore. Tu imposti soltanto la condizione e il livello.")
    with st.form("new_alert", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        ticker = c1.text_input("Ticker", placeholder="MSFT").strip().upper()
        market = c2.selectbox("Mercato", ["USA", "ITALY"])
        direction = c3.selectbox("Condizione", ["Prezzo >=", "Prezzo <="])

        c4, c5, c6 = st.columns(3)
        trigger_level = c4.number_input("Prezzo trigger", min_value=0.0001, value=100.0, step=0.01, format="%.4f")
        expiry_date = c5.date_input("Scadenza", value=date.today() + timedelta(days=30))
        dedup_hours = c6.number_input("Deduplica ore", min_value=0, max_value=24, value=3, step=1)

        c7, c8 = st.columns(2)
        source = c7.selectbox("Origine", ["MANUAL", "CHAT", "PORTFOLIO", "ENGINE"])
        repeatable = c8.checkbox("Ripetibile", value=False, help="Se disattivato, dopo il primo trigger passa a TRIGGERED.")
        note = st.text_input("Nota", placeholder="es. breakout sopra resistenza")

        submitted = st.form_submit_button("➕ Aggiungi Alert", type="primary", use_container_width=True)
        if submitted:
            if not ticker:
                st.error("Ticker obbligatorio.")
            else:
                expires = datetime.combine(expiry_date, time(23, 59), tzinfo=timezone.utc).isoformat()
                payload = {
                    "ticker": ticker,
                    "market": market,
                    "condition_type": "PRICE_ABOVE" if direction == "Prezzo >=" else "PRICE_BELOW",
                    "trigger_level": trigger_level,
                    "status": "ACTIVE",
                    "source": source,
                    "note": note or None,
                    "expires_at": expires,
                    "repeatable": repeatable,
                    "dedup_minutes": int(dedup_hours * 60),
                }
                get_client().table("trading_alerts").insert(payload).execute()
                st.success(f"Alert inserito: {ticker} {direction} {trigger_level:.4f}")

with tab_history:
    try:
        rows = notifications(1500)
    except Exception as exc:
        st.error(f"Impossibile leggere le notifiche: {type(exc).__name__}: {exc}")
        rows = []

    filtered = []
    for row in rows:
        ticker = str(row.get("ticker") or "").strip().upper()
        if not ticker or ticker in {"REPORT", "N/D", "NONE", "NULL"}:
            continue
        item = dict(row)
        item["Messaggio"] = extract_message(item.get("payload"))
        filtered.append(item)

    if not filtered:
        st.info("Nessuna notifica ticker disponibile.")
    else:
        frame = pd.DataFrame(filtered)
        for col in ("attempted_at", "sent_at"):
            if col in frame.columns:
                frame[col] = frame[col].map(utc_label)
        wanted = ["sent_at", "ticker", "event_type", "channel", "status", "provider", "Messaggio", "error_message"]
        st.dataframe(frame[[c for c in wanted if c in frame.columns]], hide_index=True, use_container_width=True)
