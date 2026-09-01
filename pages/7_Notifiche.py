from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta, timezone

import pandas as pd
import streamlit as st

from alert_center.alert_parser import parse_alert_text, validate_parsed_alerts
from dashboard.data_access import get_client, notifications, utc_label
from system_health.dashboard import render_run_ledger, render_system_status

st.set_page_config(page_title="Alert Center", page_icon="🔔", layout="wide")
st.title("🔔 Alert Center")
st.caption("Alert prezzo, notifiche e stato operativo dei processi in un unico centro di controllo.")


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


def platform_alert_rows() -> list[dict]:
    """Read the single alert source of truth."""
    try:
        return (
            get_client()
            .schema("alert_platform")
            .table("alerts")
            .select(
                "id,ticker,market,alert_type,threshold,threshold_min,threshold_max,status,"
                "valid_until,next_check_at,last_price,last_price_at,last_price_provider,created_at,updated_at"
            )
            .order("created_at", desc=True)
            .limit(3000)
            .execute()
            .data
            or []
        )
    except Exception:
        return []


def _validation_rows(rows: list[dict]) -> list[dict]:
    """Adapt platform rows to the local parser duplicate-check contract."""
    output = []
    for row in rows:
        alert_type = str(row.get("alert_type") or "").upper()
        if alert_type not in {"PRICE_ABOVE", "PRICE_BELOW"}:
            continue
        if row.get("threshold") is None:
            continue
        output.append(
            {
                "ticker": row.get("ticker"),
                "condition_type": alert_type,
                "trigger_level": row.get("threshold"),
            }
        )
    return output


def _condition_label(row: dict) -> str:
    alert_type = str(row.get("alert_type") or "").upper()
    threshold = row.get("threshold")
    low = row.get("threshold_min")
    high = row.get("threshold_max")
    if alert_type == "PRICE_ABOVE":
        return f">= {threshold}" if threshold is not None else "PRICE_ABOVE"
    if alert_type == "PRICE_BELOW":
        return f"<= {threshold}" if threshold is not None else "PRICE_BELOW"
    if alert_type == "MAX_BUY":
        return f"MAX BUY {threshold}" if threshold is not None else "MAX BUY"
    if alert_type == "ENTRY_ZONE":
        return f"ENTRY {low} - {high}" if low is not None and high is not None else "ENTRY ZONE"
    if threshold is not None:
        return f"{alert_type} {threshold}"
    return alert_type or "N/D"


def consolidate_platform_alerts(rows: list[dict]) -> list[dict]:
    """One logical dashboard row per market+ticker."""
    groups: dict[tuple[str, str], list[dict]] = {}
    for raw in rows:
        ticker = str(raw.get("ticker") or "").strip().upper()
        market = str(raw.get("market") or "").strip().upper()
        if not ticker:
            continue
        groups.setdefault((market, ticker), []).append(dict(raw))

    status_rank = {
        "V3_FAILED": 1,
        "CLAIMED": 2,
        "V3_RUNNING": 3,
        "V3_PENDING": 4,
        "V3_RETRY": 5,
        "TRIGGERED": 6,
        "ACTIVE": 7,
        "V3_COMPLETED": 8,
        "PROCESSED": 9,
        "EXPIRED": 10,
        "CANCELLED": 11,
    }
    consolidated: list[dict] = []
    for (market, ticker), items in groups.items():
        statuses = [str(x.get("status") or "N/D").upper() for x in items]
        effective_status = min(statuses, key=lambda x: status_rank.get(x, 99)) if statuses else "N/D"
        conditions = list(dict.fromkeys(_condition_label(x) for x in items))
        last_price_rows = [x for x in items if x.get("last_price") is not None]
        last_price_rows.sort(key=lambda x: str(x.get("last_price_at") or ""), reverse=True)
        latest = last_price_rows[0] if last_price_rows else items[0]
        valid_values = [x.get("valid_until") for x in items if x.get("valid_until")]
        next_values = [x.get("next_check_at") for x in items if x.get("next_check_at")]
        consolidated.append(
            {
                "Ticker": ticker,
                "Mercato": market or "N/D",
                "Alert": len(items),
                "Condizioni": " | ".join(conditions),
                "Prezzo": latest.get("last_price"),
                "Stato": effective_status,
                "Scadenza": utc_label(max(valid_values)) if valid_values else "-",
                "Prossimo controllo": utc_label(min(next_values)) if next_values else "-",
                "Ultimo prezzo": utc_label(latest.get("last_price_at")),
                "Provider": latest.get("last_price_provider") or "N/D",
            }
        )
    return sorted(consolidated, key=lambda x: (x["Mercato"], x["Ticker"]))


def insert_alerts(rows: list[dict]) -> int:
    payloads = []
    for row in rows:
        if row.get("validation") != "OK":
            continue
        payloads.append(
            {
                "ticker": row["ticker"],
                "market": row.get("market") or "USA",
                "alert_type": row["condition_type"],
                "threshold": row["trigger_level"],
                "status": "ACTIVE",
                "valid_until": row["expires_at"],
                "next_check_at": None,
            }
        )
    if not payloads:
        return 0
    get_client().schema("alert_platform").table("alerts").insert(payloads).execute()
    return len(payloads)


tab_active, tab_new, tab_history, tab_status, tab_runs = st.tabs([
    "🎯 Alert",
    "➕ Nuovo Alert",
    "📨 Storico notifiche",
    "📡 Stato sistema",
    "⚙️ Run & Heartbeat",
])

with tab_active:
    platform_rows = platform_alert_rows()

    if platform_rows:
        consolidated = consolidate_platform_alerts(platform_rows)
        raw_frame = pd.DataFrame(platform_rows)

        c1, c2, c3, c4 = st.columns(4)
        active_like = raw_frame["status"].isin(["ACTIVE", "CLAIMED"])
        c1.metric("Ticker monitorati", len(consolidated))
        c2.metric("Alert attivi", int(active_like.sum()))
        c3.metric("Scattati", int((raw_frame["status"] == "TRIGGERED").sum()))
        c4.metric("V3 Failed", int((raw_frame["status"] == "V3_FAILED").sum()))

        st.caption(
            "Source of truth: `alert_platform.alerts`. Una riga per ticker; condizioni multiple sono raggruppate."
        )
        status_options = sorted({row["Stato"] for row in consolidated})
        default_statuses = [
            s for s in ("ACTIVE", "CLAIMED", "TRIGGERED", "V3_PENDING", "V3_RUNNING", "V3_RETRY", "V3_FAILED")
            if s in status_options
        ]
        status_filter = st.multiselect("Stato", status_options, default=default_statuses)
        consolidated_view = [row for row in consolidated if not status_filter or row["Stato"] in status_filter]
        st.dataframe(pd.DataFrame(consolidated_view), hide_index=True, use_container_width=True)

        duplicates = sum(max(0, row["Alert"] - 1) for row in consolidated)
        if duplicates:
            st.warning(
                f"Rilevati {duplicates} record aggiuntivi sullo stesso ticker. La vista li raggruppa; "
                "la migration di deduplica rimuove solo i duplicati esatti attivi."
            )
    else:
        st.info("Nessun alert presente in `alert_platform.alerts`.")

with tab_new:
    st.subheader("🤖 CREA CON ALERT ASSISTANT")
    st.caption("Incolla uno o più alert in linguaggio naturale. Il parser crea una preview e inserisce gli alert solo dopo la tua conferma.")

    default_example = "MSFT sopra 525 fino al 15/09\nSPGI sopra 445 e sotto 425 fino al 25/09\nNVO sopra 48,2 fino al 15 settembre"
    assistant_text = st.text_area(
        "Scrivi o incolla gli alert",
        placeholder=default_example,
        height=140,
        key="alert_assistant_text",
    )

    parse_clicked = st.button("🔎 Analizza alert", type="primary", use_container_width=True)
    if parse_clicked:
        result = parse_alert_text(assistant_text)
        st.session_state["alert_parse_result"] = result

    result = st.session_state.get("alert_parse_result")
    if result is not None:
        if result.status == "HIGH_CONFIDENCE":
            st.success(f"Parser locale: alta confidenza. Riconosciuti {len(result.alerts)} alert.")
        elif result.status == "PARTIAL":
            st.warning(f"Parser locale: risultato parziale. Riconosciuti {len(result.alerts)} alert, ma ci sono parti da controllare.")
        else:
            st.error("Parser locale: confidenza bassa. Nessun inserimento automatico.")

        if result.errors:
            with st.expander("Dettagli da controllare", expanded=True):
                for err in result.errors:
                    st.write(f"• {err}")
                if result.needs_llm:
                    st.info("Fallback LLM previsto ma non attivo in V1: il sistema non inventa ticker, livelli o date mancanti.")

        if result.alerts:
            existing = _validation_rows(platform_alert_rows())
            validated = validate_parsed_alerts(result.alerts, existing)
            preview = pd.DataFrame(validated)
            preview["Condizione"] = preview["condition_type"].map({"PRICE_ABOVE": ">=", "PRICE_BELOW": "<="})
            preview["Scadenza"] = preview["expires_at"].astype(str).str.slice(0, 10)
            show = preview[["ticker", "Condizione", "trigger_level", "Scadenza", "validation"]].rename(columns={
                "ticker": "Ticker",
                "trigger_level": "Livello",
                "validation": "Validazione",
            })
            st.markdown("**Ho interpretato così:**")
            st.dataframe(show, hide_index=True, use_container_width=True)

            insertable = [row for row in validated if row["validation"] == "OK"]
            duplicates = [row for row in validated if row["validation"] == "DUPLICATE"]
            if duplicates:
                st.info(f"{len(duplicates)} alert già presenti: non verranno duplicati.")

            if st.button(
                f"✅ Inserisci {len(insertable)} alert",
                disabled=not insertable,
                use_container_width=True,
                key="confirm_bulk_insert",
            ):
                inserted = insert_alerts(validated)
                st.session_state.pop("alert_parse_result", None)
                st.success(f"Inseriti {inserted} alert in `alert_platform.alerts`.")

    st.divider()
    st.subheader("✍️ CREA MANUALMENTE")
    st.caption("Inserimento diretto nella piattaforma alert unica.")
    with st.form("new_alert", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        ticker = c1.text_input("Ticker", placeholder="MSFT").strip().upper()
        market = c2.selectbox("Mercato", ["USA", "ITALY"])
        direction = c3.selectbox("Condizione", ["Prezzo >=", "Prezzo <="])

        c4, c5 = st.columns(2)
        trigger_level = c4.number_input("Prezzo trigger", min_value=0.0001, value=100.0, step=0.01, format="%.4f")
        expiry_date = c5.date_input("Scadenza", value=date.today() + timedelta(days=30))

        submitted = st.form_submit_button("➕ Aggiungi Alert", type="primary", use_container_width=True)
        if submitted:
            if not ticker:
                st.error("Ticker obbligatorio.")
            else:
                expires = datetime.combine(expiry_date, time(23, 59), tzinfo=timezone.utc).isoformat()
                alert_type = "PRICE_ABOVE" if direction == "Prezzo >=" else "PRICE_BELOW"
                existing = _validation_rows(platform_alert_rows())
                duplicate = any(
                    str(row.get("ticker") or "").upper() == ticker
                    and str(row.get("condition_type") or "").upper() == alert_type
                    and float(row.get("trigger_level")) == float(trigger_level)
                    for row in existing
                )
                if duplicate:
                    st.warning("Alert identico già presente: nessun duplicato inserito.")
                else:
                    payload = {
                        "ticker": ticker,
                        "market": market,
                        "alert_type": alert_type,
                        "threshold": trigger_level,
                        "status": "ACTIVE",
                        "valid_until": expires,
                        "next_check_at": None,
                    }
                    get_client().schema("alert_platform").table("alerts").insert(payload).execute()
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

with tab_status:
    render_system_status()

with tab_runs:
    render_run_ledger()
