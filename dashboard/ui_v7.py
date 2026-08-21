from __future__ import annotations

"""Presentation hardening for the Trading Engine dashboard.

This module intentionally does not change trading logic. It installs a small
presentation layer before loading ui_v6 so every Streamlit dataframe gets the
same formatting rules (timestamps, currencies, percentages, missing values and
negative-value highlighting). It also enriches the legacy Laboratory watchlist
with a real timestamp from lab_paper_signals when one is available.
"""

from typing import Any

import numpy as np
import pandas as pd
import streamlit as st

try:
    import dashboard.data_access as data_access
except ModuleNotFoundError:
    import data_access  # type: ignore


# ---------------------------------------------------------------------------
# Legacy Laboratory enrichment
# ---------------------------------------------------------------------------
_original_lab_watchlist = data_access.lab_watchlist
_original_lab_paper_signals = data_access.lab_paper_signals


def _enriched_lab_watchlist(limit: int = 1000) -> list[dict[str, Any]]:
    """Use the latest real paper-signal timestamp for the watchlist row.

    lab_watchlist historically stores signal_date as DATE, therefore it has no
    time component. lab_paper_signals stores created_at. Matching by
    symbol+strategy lets the UI show an actual timestamp without inventing one.
    """
    rows = _original_lab_watchlist(limit)
    if not rows:
        return rows

    signals = _original_lab_paper_signals(max(limit * 4, 2000))
    latest: dict[tuple[str, str], str] = {}
    for item in signals:
        symbol = str(item.get("symbol") or "").upper().strip()
        strategy = str(item.get("strategy") or "").strip()
        created_at = item.get("created_at")
        if not symbol or not created_at:
            continue
        key = (symbol, strategy)
        # data_access already returns newest first, so first match is latest.
        if key not in latest:
            latest[key] = str(created_at)

    enriched: list[dict[str, Any]] = []
    for item in rows:
        row = dict(item)
        key = (
            str(row.get("symbol") or "").upper().strip(),
            str(row.get("strategy") or "").strip(),
        )
        timestamp = latest.get(key)
        if timestamp:
            # ui_v6 already displays signal_date. Reusing that visible field
            # keeps the page compact while upgrading it from date to timestamp.
            row["signal_date"] = timestamp
        enriched.append(row)
    return enriched


data_access.lab_watchlist = _enriched_lab_watchlist


# ---------------------------------------------------------------------------
# Global dataframe presentation
# ---------------------------------------------------------------------------
_original_dataframe = st.dataframe

PERCENT_COLUMNS = {
    "pnl_pct",
    "max_drawdown_pct",
    "max_favorable_excursion_pct",
    "distance_to_entry_pct",
    "return_pct",
    "change_pct",
    "win_rate_pct",
    "risk_pct",
    "drawdown_pct",
}

MONEY_COLUMNS = {
    "price",
    "entry",
    "entry_price",
    "exit_price",
    "proposed_entry",
    "proposed_stop",
    "proposed_target",
    "stop",
    "stop_current",
    "tp1",
    "tp2",
    "target",
    "max_buy",
    "alert_price",
    "capital",
    "market_value",
    "pnl_amount",
    "profit",
    "loss",
    "risk_amount",
}

INTEGER_COLUMNS = {
    "qty",
    "quantity",
    "records_processed",
    "signals_found",
    "holding_minutes",
    "universe_size",
    "candidates_count",
}

SIGNED_STYLE_COLUMNS = {
    "pnl_pct",
    "max_drawdown_pct",
    "max_favorable_excursion_pct",
    "distance_to_entry_pct",
    "return_pct",
    "change_pct",
    "pnl_amount",
    "profit",
    "loss",
}

DATE_NAME_PARTS = ("date", "_at", "timestamp", "time")
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
    # 1,234.56 -> 1.234,56
    return text.replace(",", "§").replace(".", ",").replace("§", ".")


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
    return (
        name.endswith("_price")
        or name.startswith("price_")
        or name.endswith("_capital")
        or name.endswith("_amount") and "duration" not in name
    )


def _looks_like_date_column(column: str) -> bool:
    name = column.lower()
    return (
        name.endswith("_at")
        or name.endswith("_date")
        or name == "signal_date"
        or "timestamp" in name
    )


def _format_date_value(value: Any) -> Any:
    value = _clean_missing(value)
    if value is None:
        return "-"
    text = str(value).strip()
    # ui_v6 may already have converted timestamps to DD/MM/YYYY HH:MM.
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

    # The legacy Laboratory universe currently consists of US-listed symbols.
    if row.get("symbol") is not None:
        return "USD"
    return ""


def _prepare_dataframe(data: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any], pd.DataFrame]:
    frame = data.copy()
    for column in frame.columns:
        frame[column] = frame[column].map(_clean_missing)

    # Normalize date/timestamp-looking columns even when a legacy field is
    # called signal_date rather than created_at.
    for column in frame.columns:
        if _looks_like_date_column(str(column)):
            frame[column] = frame[column].map(_format_date_value)

    money_cols = [c for c in frame.columns if _is_money_column(str(c))]
    pct_cols = [c for c in frame.columns if _is_percent_column(str(c))]
    int_cols = [c for c in frame.columns if str(c).lower() in INTEGER_COLUMNS]

    # Preserve raw numeric values for conditional styling before formatting.
    raw_numeric = pd.DataFrame(index=frame.index)
    for column in set(pct_cols) | (set(frame.columns) & SIGNED_STYLE_COLUMNS):
        raw_numeric[column] = pd.to_numeric(frame[column], errors="coerce")

    # Currency is deliberately explicit instead of assuming that every numeric
    # price is USD. Mixed production tables can therefore show EUR/USD row-wise.
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
        if name in pct_cols:
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

    # User requirement: negative percentages/results red, positive values use
    # the normal theme text colour (black in the current light dashboard).
    if not raw_numeric.empty:
        css = pd.DataFrame("", index=frame.index, columns=frame.columns)
        for column in raw_numeric.columns:
            if column not in css.columns:
                continue
            negative = raw_numeric[column] < 0
            css.loc[negative.fillna(False), column] = "color:#c62828;font-weight:600;"
        styler = styler.apply(lambda _: css, axis=None)

    return _original_dataframe(styler, *args, **kwargs)


st.dataframe = _smart_dataframe


# Importing ui_v6 now executes the complete dashboard using the patched data
# access and presentation functions above.
try:
    from dashboard.ui_v6 import *  # noqa: F401,F403,E402
except ModuleNotFoundError:
    from ui_v6 import *  # type: ignore  # noqa: F401,F403,E402
