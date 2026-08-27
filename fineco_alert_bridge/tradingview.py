from __future__ import annotations

from typing import Iterable

from tradingview_screener import Column, Query

from fineco_alert_bridge.parser import FinecoAlert, TradingViewData


TV_FIELDS = [
    "name",
    "exchange",
    "close",
    "Recommend.All",
    "Recommend.All|60",
    "Recommend.All|240",
    "ATR",
    "SMA20",
    "SMA50",
    "SMA200",
]


def _market_candidates(market_name: str) -> list[str]:
    m = (market_name or "").upper()
    if any(x in m for x in ("MIL", "MTA", "BIT", "BORSA ITALIANA", "ITALIA")):
        return ["italy", "america"]
    if any(x in m for x in ("NYSE", "NASDAQ", "AMEX", "ARCA", "USA")):
        return ["america", "italy"]
    return ["america", "italy"]


def _safe_float(value) -> float | None:
    try:
        if value is None:
            return None
        v = float(value)
        if v != v:  # NaN
            return None
        return v
    except Exception:
        return None


def _rating(value: float | None) -> str:
    if value is None:
        return "N/D"
    if value >= 0.5:
        return "STRONG BUY"
    if value >= 0.1:
        return "BUY"
    if value > -0.1:
        return "NEUTRAL"
    if value > -0.5:
        return "SELL"
    return "STRONG SELL"


def _fmt_price(value: float | None) -> str | None:
    if value is None:
        return None
    return f"{value:.2f}"


def _fmt_pct(base: float | None, target: float | None) -> str | None:
    if base is None or target is None or base == 0:
        return None
    return f"{((target / base) - 1) * 100:+.1f}%"


def _query_one(symbol: str, markets: Iterable[str]):
    last_error: Exception | None = None
    for market in markets:
        try:
            _, df = (
                Query()
                .set_markets(market)
                .select(*TV_FIELDS)
                .where(Column("name") == symbol.upper())
                .limit(10)
                .get_scanner_data()
            )
            if df is not None and not df.empty:
                # Se ci sono omonimi, privilegia la riga il cui ticker termina con :SYMBOL.
                exact = df[df["ticker"].astype(str).str.upper().str.endswith(f":{symbol.upper()}")]
                return (exact.iloc[0] if not exact.empty else df.iloc[0]), market
        except Exception as exc:
            last_error = exc
    if last_error:
        raise last_error
    return None, None


def fetch_tradingview_data(alert: FinecoAlert) -> TradingViewData | None:
    """
    Recupera TradingView SOLO dopo un alert Fineco.

    I rating e i dati di mercato arrivano da TradingView.
    Entry/range/SL/TP sono calcolati in modo deterministico usando close, ATR e SMA20
    recuperati dalla stessa sorgente; non vengono presentati come raccomandazioni ufficiali TradingView.
    """
    row, _market = _query_one(alert.titolo, _market_candidates(alert.mercato))
    if row is None:
        return None

    close = _safe_float(row.get("close"))
    atr = _safe_float(row.get("ATR"))
    sma20 = _safe_float(row.get("SMA20"))
    sma50 = _safe_float(row.get("SMA50"))
    sma200 = _safe_float(row.get("SMA200"))
    rec_1h = _safe_float(row.get("Recommend.All|60"))
    rec_4h = _safe_float(row.get("Recommend.All|240"))
    rec_1d = _safe_float(row.get("Recommend.All"))

    if close is None:
        return None

    # Se ATR non è disponibile, usa una fascia prudente dell'1.5% solo come fallback tecnico.
    effective_atr = atr if atr and atr > 0 else close * 0.015

    # Zona ingresso ancorata al prezzo e, se disponibile, alla SMA20.
    anchor = sma20 if sma20 and sma20 > 0 else close
    entry = min(close, anchor)
    range_min = max(0.01, entry - 0.45 * effective_atr)
    range_max = entry + 0.35 * effective_atr
    stop = max(0.01, range_min - 1.10 * effective_atr)

    risk = max(entry - stop, effective_atr * 0.75)
    tp1 = entry + 1.5 * risk
    tp2 = entry + 2.5 * risk
    tp3 = entry + 3.5 * risk

    in_zone = range_min <= close <= range_max
    daily = _rating(rec_1d)
    intraday_positive = sum(v is not None and v >= 0.1 for v in (rec_1h, rec_4h))
    trend_ok = (sma50 is None or close >= sma50) and (sma200 is None or close >= sma200)

    if in_zone and rec_1d is not None and rec_1d >= 0.1 and intraday_positive >= 1 and trend_ok:
        action = "🟢 POSSIBILE INGRESSO ORA"
    elif close < range_min:
        action = "🟡 ATTENDI CONFERMA / PREZZO SOTTO ZONA"
    elif close > range_max:
        action = "🟡 ATTENDI PULLBACK / PREZZO SOPRA ZONA"
    elif daily in ("SELL", "STRONG SELL"):
        action = "🔴 NON ENTRARE ORA"
    else:
        action = "🟡 ATTENDI CONFERMA"

    return TradingViewData(
        prezzo_attuale=_fmt_price(close),
        segnale=daily,
        segnale_1h=_rating(rec_1h),
        segnale_4h=_rating(rec_4h),
        segnale_1d=daily,
        range_min=_fmt_price(range_min),
        range_max=_fmt_price(range_max),
        entry_ideale=_fmt_price(entry),
        stop_loss=_fmt_price(stop),
        tp1=_fmt_price(tp1),
        tp1_pct=_fmt_pct(close, tp1),
        tp2=_fmt_price(tp2),
        tp2_pct=_fmt_pct(close, tp2),
        tp3=_fmt_price(tp3),
        tp3_pct=_fmt_pct(close, tp3),
        prezzo_in_buy_zone="✅ SÌ" if in_zone else "❌ NO",
        azione=action,
    )
