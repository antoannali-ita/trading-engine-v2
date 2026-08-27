from __future__ import annotations

import json
import pandas as pd
import streamlit as st

from dashboard.data_access import notifications, utc_label

st.set_page_config(page_title="Notifiche", page_icon="🔔", layout="wide")
st.title("🔔 Notifiche")
st.caption("Mostra solo le notifiche riferite a ticker reali. I report generali sono esclusi.")


def extract_message(payload):
    if payload is None:
        return "-"
    if isinstance(payload, str):
        text = payload.strip()
        if not text:
            return "-"
        try:
            parsed = json.loads(text)
            payload = parsed
        except Exception:
            return text
    if isinstance(payload, dict):
        for key in (
            "message", "text", "body", "summary", "whatsapp_message",
            "email_body", "content", "subject",
        ):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        for value in payload.values():
            if isinstance(value, dict):
                nested = extract_message(value)
                if nested != "-":
                    return nested
        try:
            return json.dumps(payload, ensure_ascii=False)
        except Exception:
            return str(payload)
    return str(payload)


try:
    rows = notifications(1000)
except Exception as exc:
    st.error(f"Impossibile leggere le notifiche: {type(exc).__name__}: {exc}")
    st.stop()

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
    st.stop()

frame = pd.DataFrame(filtered)
for col in ("attempted_at", "sent_at"):
    if col in frame.columns:
        frame[col] = frame[col].map(utc_label)

wanted = [
    "sent_at", "ticker", "event_type", "channel", "status", "provider",
    "Messaggio", "error_message",
]
wanted = [c for c in wanted if c in frame.columns]

c1, c2, c3 = st.columns(3)
c1.metric("Ticker notificati", frame["ticker"].nunique() if "ticker" in frame.columns else 0)
c2.metric("Notifiche mostrate", len(frame))
c3.metric("Inviate", int((frame["status"].astype(str).str.upper() == "SENT").sum()) if "status" in frame.columns else 0)

st.dataframe(frame[wanted], hide_index=True, use_container_width=True)
