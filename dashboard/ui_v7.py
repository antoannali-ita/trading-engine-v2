from __future__ import annotations

"""Presentation hardening for the Trading Engine dashboard."""

import time
from typing import Any

import numpy as np
import pandas as pd
import streamlit as st

try:
    import dashboard.data_access as data_access
except ModuleNotFoundError:
    import data_access  # type: ignore

_original_lab_watchlist = data_access.lab_watchlist
_original_lab_paper_signals = data_access.lab_paper_signals
_original_request_run = data_access.request_run
_original_manual_requests = data_access.manual_requests


def _enriched_lab_watchlist(limit: int = 1000) -> list[dict[str, Any]]:
    rows = _original_lab_watchlist(limit)
    if not rows:
        return rows
    signals = _original_lab_paper_signals(max(limit * 4, 2000))
    latest: dict[tuple[str, str], str] = {}
    for item in signals:
        symbol = str(item.get("symbol") or "").upper().strip()
        strategy = str(item.get("strategy") or "").strip()
        created_at = item.get("created_at")
        if symbol and created_at:
            latest.setdefault((symbol, strategy), str(created_at))
    enriched = []
    for item in rows:
        row = dict(item)
        key = (str(row.get("symbol") or "").upper().strip(), str(row.get("strategy") or "").strip())
        if latest.get(key):
            row["signal_date"] = latest[key]
        enriched.append(row)
    return enriched


def _request_run_with_progress(
    engine_id: str,
    market: str,
    strategy: str | None,
    *,
    send_email: bool,
    send_whatsapp: bool,
    requested_by: str = "dashboard",
) -> dict:
    """Create a manual run request and keep the operator informed while it advances.

    The actual execution is asynchronous (Supabase -> Orchestrator -> GitHub Actions),
    so the UI polls the request record for up to two minutes. The user sees a real
    progress state instead of a blank/static page.
    """
    created = _original_request_run(
        engine_id,
        market,
        strategy,
        send_email=send_email,
        send_whatsapp=send_whatsapp,
        requested_by=requested_by,
    )
    request_id = str(created.get("request_id") or "").strip()
    if not request_id:
        st.error("Richiesta creata senza request_id: impossibile seguirne lo stato.")
        return created

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

    with st.status(f"⏳ Avvio {engine_id} | {market.upper()}", expanded=True) as status_box:
        progress = st.progress(5, text="Creazione richiesta...")
        st.write(f"Request ID: `{request_id}`")
        deadline = time.time() + 120
        last_state = None
        latest = created

        while time.time() < deadline:
            rows = _original_manual_requests(250)
            current = next((r for r in rows if str(r.get("request_id") or "") == request_id), None)
            if current:
                latest = current
                state = str(current.get("status") or "REQUESTED").upper()
                pct, label = labels.get(state, (25, f"Stato: {state}"))
                progress.progress(pct, text=label)

                if state != last_state:
                    st.write(f"• {label}")
                    if current.get("github_run_id"):
                        st.write(f"• GitHub run: `{current.get('github_run_id')}`")
                    if current.get("run_id"):
                        st.write(f"• Engine run: `{current.get('run_id')}`")
                    last_state = state

                if state in {"SUCCESS", "COMPLETED"}:
                    progress.progress(100, text="Completato")
                    status_box.update(label=f"✅ {engine_id} completato", state="complete", expanded=False)
                    st.cache_data.clear()
                    return latest

                if state in {"FAILED", "ERROR", "CANCELLED"}:
                    err = current.get("error_message") or "Nessun dettaglio errore disponibile"
                    st.error(str(err))
                    status_box.update(label=f"❌ {engine_id}: {state}", state="error", expanded=True)
                    return latest

            time.sleep(2)

        progress.progress(80, text="Run avviato; completamento non ancora registrato entro 120 s")
        st.info("Il run continua in background. Lo stato sarà visibile in Operations → Run & Log.")
        status_box.update(label=f"⏳ {engine_id} ancora in esecuzione", state="running", expanded=False)
        return latest


data_access.lab_watchlist = _enriched_lab_watchlist
data_access.request_run = _request_run_with_progress


# Quick operator guide: always available, independent of the current tab.
with st.sidebar:
    st.markdown("### 🧭 Guida rapida")
    st.caption("Cosa guardare senza perdersi tra tabelle nate per moltiplicarsi durante la notte.")
    with st.expander("Controllo quotidiano", expanded=False):
        st.markdown(
            """
1. **Engine Health** → i motori devono essere HEALTHY.
2. **Segnali** → cerca setup con prezzo, entry, stop e TP valorizzati.
3. **Decisioni** → verifica confluenza e `is_actionable`.
4. **TradingAgents** → seconda opinione, eventuali CAUTION/VETO.
5. **Notifiche** → conferma che Email/WhatsApp siano state realmente inviate.
6. **Performance** → misura se i segnali funzionano davvero nel tempo.
"""
        )
    with st.expander("Flusso del sistema", expanded=False):
        st.code("CORE / FAST → Supabase → Orchestrator → Multi-Horizon → TradingAgents → Notifiche → Performance")
    with st.expander("Stati principali", expanded=False):
        st.markdown(
            """
- **HEALTHY**: motore regolare.
- **NOT_RUN**: registrato ma non ancora eseguito/tracciato.
- **STALE**: non gira da troppo tempo.
- **FAILED**: errore tecnico.
- **IN_BUY_ZONE / PRE_BUY_HIGH**: candidato da verificare, non ordine automatico.
- **Actionable = True**: ha superato i gate previsti per avanzare.
- **CONFIRM / NEUTRAL / CAUTION / VETO**: giudizio TradingAgents.
"""
        )


_original_dataframe = st.dataframe

PERCENT_COLUMNS = {"pnl_pct", "max_drawdown_pct", "max_favorable_excursion_pct", "distance_to_entry_pct", "return_pct", "change_pct", "win_rate_pct", "risk_pct", "drawdown_pct"}
MONEY_COLUMNS = {"price", "entry", "entry_price", "exit_price", "proposed_entry", "proposed_stop", "proposed_target", "stop", "stop_current", "tp1", "tp2", "target", "max_buy", "alert_price", "capital", "market_value", "pnl_amount", "profit", "loss", "risk_amount"}
INTEGER_COLUMNS = {"qty", "quantity", "records_processed", "signals_found", "holding_minutes", "universe_size", "candidates_count"}
SIGNED_STYLE_COLUMNS = {"pnl_pct", "max_drawdown_pct", "max_favorable_excursion_pct", "distance_to_entry_pct", "return_pct", "change_pct", "pnl_amount", "profit", "loss"}
MISSING_TEXT = {"nan", "nat", "none", "null", "<na>", "n/a"}


def _clean_missing(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str) and value.strip().lower() in MISSING_TEXT:
        return None
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    return value


def _italian_number(value: Any, decimals: int = 2) -> str:
    if value is None:
        return "-"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if not np.isfinite(number):
        return "-"
    text = f"{number:,.{decimals}f}"
    return text.replace(",", "§").replace(".", ",").replace("§", ".")


def _duration(value: Any) -> str:
    """Seconds with at most two decimals: 9 -> 9, 0.96 -> 0,96, 9.176 -> 9,18."""
    value = _clean_missing(value)
    if value is None or value == "N/D":
        return "N/D" if value == "N/D" else "-"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if not np.isfinite(number):
        return "-"
    text = f"{number:.2f}".rstrip("0").rstrip(".")
    return text.replace(".", ",")


def _percent(value: Any) -> str:
    if value is None:
        return "-"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if not np.isfinite(number):
        return "-"
    return f"{_italian_number(number, 2)}%"


def _integer(value: Any) -> str:
    if value is None:
        return "-"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if not np.isfinite(number):
        return "-"
    return f"{int(round(number)):,}".replace(",", ".")


def _is_percent_column(column: str) -> bool:
    name = column.lower()
    return name in PERCENT_COLUMNS or name.endswith("_pct") or "percent" in name


def _is_money_column(column: str) -> bool:
    name = column.lower()
    if name in MONEY_COLUMNS:
        return True
    return name.endswith("_price") or name.startswith("price_") or name.endswith("_capital") or (name.endswith("_amount") and "duration" not in name)


def _looks_like_date_column(column: str) -> bool:
    name = column.lower()
    return name.endswith("_at") or name.endswith("_date") or name == "signal_date" or "timestamp" in name


def _format_date_value(value: Any) -> Any:
    value = _clean_missing(value)
    if value is None:
        return "-"
    text = str(value).strip()
    if "/" in text and ":" in text:
        return text
    try:
        parsed = pd.to_datetime(text, utc=True, errors="raise")
        if len(text) <= 10 and "T" not in text and ":" not in text:
            return parsed.strftime("%d/%m/%Y")
        return parsed.tz_convert("Europe/Rome").strftime("%d/%m/%Y %H:%M")
    except Exception:
        return text


def _currency_for_row(row: pd.Series) -> str:
    explicit = row.get("currency")
    if explicit is None:
        explicit = row.get("valuta")
    if explicit is not None and str(explicit).strip():
        return str(explicit).upper().strip()
    market = str(row.get("market") or "").upper()
    if "ITAL" in market or market in {"EUR", "MIL", "MTA"}:
        return "EUR"
    if "USA" in market or market in {"US", "NYSE", "NASDAQ"}:
        return "USD"
    if row.get("symbol") is not None:
        return "USD"
    return ""


def _prepare_dataframe(data: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any], pd.DataFrame]:
    frame = data.copy()
    for column in frame.columns:
        frame[column] = frame[column].map(_clean_missing)
    for column in frame.columns:
        if _looks_like_date_column(str(column)):
            frame[column] = frame[column].map(_format_date_value)

    money_cols = [c for c in frame.columns if _is_money_column(str(c))]
    pct_cols = [c for c in frame.columns if _is_percent_column(str(c))]
    int_cols = [c for c in frame.columns if str(c).lower() in INTEGER_COLUMNS]
    raw_numeric = pd.DataFrame(index=frame.index)
    for column in set(pct_cols) | (set(frame.columns) & SIGNED_STYLE_COLUMNS):
        raw_numeric[column] = pd.to_numeric(frame[column], errors="coerce")

    if money_cols and "currency" not in frame.columns and "Valuta" not in frame.columns:
        currencies = frame.apply(_currency_for_row, axis=1)
        if currencies.astype(str).str.len().gt(0).any():
            insert_at = 1
            for candidate in ("market", "symbol", "ticker"):
                if candidate in frame.columns:
                    insert_at = list(frame.columns).index(candidate) + 1
                    break
            frame.insert(insert_at, "Valuta", currencies.replace("", "-"))

    formatters: dict[str, Any] = {}
    for column in frame.columns:
        name = str(column)
        if name == "duration_seconds":
            formatters[name] = _duration
        elif name in pct_cols:
            formatters[name] = _percent
        elif name in money_cols:
            formatters[name] = lambda value: _italian_number(value, 2)
        elif name in int_cols:
            formatters[name] = _integer
        elif pd.api.types.is_numeric_dtype(frame[name]):
            formatters[name] = lambda value: _italian_number(value, 2)
    return frame, formatters, raw_numeric


def _smart_dataframe(data=None, *args, **kwargs):
    if not isinstance(data, pd.DataFrame):
        return _original_dataframe(data, *args, **kwargs)
    frame, formatters, raw_numeric = _prepare_dataframe(data)
    styler = frame.style.format(formatters, na_rep="-")
    if not raw_numeric.empty:
        css = pd.DataFrame("", index=frame.index, columns=frame.columns)
        for column in raw_numeric.columns:
            if column in css.columns:
                negative = raw_numeric[column] < 0
                css.loc[negative.fillna(False), column] = "color:#c62828;font-weight:600;"
        styler = styler.apply(lambda _: css, axis=None)
    return _original_dataframe(styler, *args, **kwargs)


st.dataframe = _smart_dataframe

try:
    from dashboard.ui_v6 import *  # noqa: F401,F403,E402
except ModuleNotFoundError:
    from ui_v6 import *  # type: ignore  # noqa: F401,F403,E402
