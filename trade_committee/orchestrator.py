from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

import numpy as np
import yfinance as yf


def _num(v):
    try:
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _sma(close, n):
    return _num(close.rolling(n).mean().iloc[-1]) if len(close) >= n else None


def _rsi(close, n=14):
    if len(close) <= n:
        return None
    d = close.diff(); up = d.clip(lower=0).rolling(n).mean(); dn = (-d.clip(upper=0)).rolling(n).mean()
    rs = up / dn.replace(0, np.nan)
    return _num((100 - 100 / (1 + rs)).iloc[-1])


def _atr(df, n=14):
    if len(df) <= n:
        return None
    pc = df["Close"].shift(1)
    tr = np.maximum(df["High"]-df["Low"], np.maximum((df["High"]-pc).abs(), (df["Low"]-pc).abs()))
    return _num(tr.rolling(n).mean().iloc[-1])


def _progress(cb: Callable | None, step: int, label: str, status="COMPLETE"):
    if cb:
        cb(step, label, status)


def run_committee(ticker: str, progress_cb: Callable | None = None) -> dict:
    """Esegue una V1 manuale, read-only, del Committee.

    Usa dati pubblici disponibili via yfinance e calcoli deterministici. I blocchi che
    richiedono fonti non configurate restano esplicitamente N/D, senza inventare dati.
    """
    symbol = ticker.strip().upper()
    if not symbol:
        raise ValueError("Ticker obbligatorio")

    steps = []
    def done(i, label, status="COMPLETE", note=""):
        steps.append({"step": i, "label": label, "status": status, "note": note})
        _progress(progress_cb, i, label, status)

    done(1, "Caricamento candidato")
    t = yf.Ticker(symbol)
    hist = t.history(period="1y", auto_adjust=False)
    if hist.empty:
        raise RuntimeError(f"Nessun dato di mercato disponibile per {symbol}")
    done(2, "Market data")

    close = hist["Close"].dropna()
    price = _num(close.iloc[-1]); sma20 = _sma(close,20); sma50 = _sma(close,50); sma200 = _sma(close,200)
    rsi14 = _rsi(close); atr14 = _atr(hist)
    avg20 = _num(hist["Volume"].tail(20).mean()); vol = _num(hist["Volume"].iloc[-1])
    rvol = (vol/avg20) if vol is not None and avg20 else None
    done(3, "Data Quality / indicatori")

    try: info = t.info or {}
    except Exception: info = {}
    fundamentals = {k: info.get(k) for k in ["marketCap","trailingPE","forwardPE","pegRatio","returnOnEquity","debtToEquity","freeCashflow","operatingCashflow","revenueGrowth","earningsGrowth","profitMargins"]}
    done(4, "Fundamental Deep Dive", "COMPLETE" if info else "WARNING", "Provider fundamentals parziale" if not info else "")

    quality = 50
    if _num(info.get("returnOnEquity")) and _num(info.get("returnOnEquity")) > .12: quality += 10
    if _num(info.get("freeCashflow")) and _num(info.get("freeCashflow")) > 0: quality += 10
    if _num(info.get("operatingCashflow")) and _num(info.get("operatingCashflow")) > 0: quality += 10
    if _num(info.get("revenueGrowth")) and _num(info.get("revenueGrowth")) > .05: quality += 10
    quality = min(100, quality)
    done(5, "Business Quality / Management", "WARNING", "Moat e management qualitativi richiedono research provider dedicato")

    valuation = 50
    fpe = _num(info.get("forwardPE")); peg = _num(info.get("pegRatio"))
    if fpe is not None: valuation += 15 if 5 <= fpe <= 20 else (-10 if fpe > 35 else 0)
    if peg is not None: valuation += 10 if 0 < peg <= 1.5 else (-5 if peg > 2.5 else 0)
    valuation = max(0,min(100,valuation)); done(6,"Valuation")

    technical = 50
    if price and sma20: technical += 10 if price>sma20 else -10
    if price and sma50: technical += 15 if price>sma50 else -15
    if price and sma200: technical += 15 if price>sma200 else -15
    if rsi14 is not None and 40 <= rsi14 <= 70: technical += 10
    technical=max(0,min(100,technical)); done(7,"Technical / Price Action")

    volume_score = 50
    if rvol is not None: volume_score += 20 if rvol>=1 else (-10 if rvol<0.5 else 0)
    volume_score=max(0,min(100,volume_score)); done(8,"Volume / Relative Strength")

    try: cal=t.calendar or {}; earnings=str(cal.get("Earnings Date","N/D"))
    except Exception: earnings="N/D"
    done(9,"Earnings & Catalyst Calendar", "COMPLETE" if earnings!="N/D" else "WARNING")
    done(10,"News / Analyst / Insider / 13F","WARNING","V1 non usa ancora SEC/13F/news cross-provider")
    done(11,"Market & Sector","WARNING","Market Health dedicato previsto come adapter separato")

    positives=[]; negatives=[]
    if technical>=65: positives.append("Struttura tecnica favorevole")
    else: negatives.append("Struttura tecnica non pienamente confermata")
    if quality>=70: positives.append("Qualità finanziaria favorevole sui dati disponibili")
    else: negatives.append("Qualità/business da confermare con ricerca profonda")
    if volume_score>=65: positives.append("Partecipazione dei volumi favorevole")
    else: negatives.append("Volumi non confermano pienamente il setup")
    if valuation>=65: positives.append("Valutazione compatibile con i criteri V1")
    else: negatives.append("Valutazione non offre un margine evidente")
    done(12,"Bull Case"); done(13,"Bear Case / Inversion")
    done(14,"Portfolio Risk","WARNING","V1 non modifica il portfolio e non esegue ordini")

    stop = price - 1.5*atr14 if price and atr14 else None
    risk = price-stop if price and stop else None
    tp1 = price + 2*risk if price and risk else None
    tp2 = price + 3*risk if price and risk else None
    done(15,"Entry / Stop / Target")

    committee_score = round(0.35*technical + 0.25*quality + 0.20*valuation + 0.20*volume_score,1)
    data_conf = 90 if info else 65
    if committee_score>=75 and technical>=65: verdict="APPROVE"
    elif committee_score>=55: verdict="WAIT"
    else: verdict="REJECT"
    done(16,"Final Investment Committee")

    return {
        "run_at": datetime.now(timezone.utc).isoformat(), "ticker": symbol, "verdict": verdict,
        "committee_score": committee_score, "data_confidence": data_conf,
        "price": price, "sma20": sma20, "sma50": sma50, "sma200": sma200, "rsi14": rsi14,
        "atr14": atr14, "relative_volume": rvol, "fundamentals": fundamentals,
        "quality_score": quality, "valuation_score": valuation, "technical_score": technical,
        "volume_score": volume_score, "earnings": earnings, "entry": price, "stop": stop,
        "tp1": tp1, "tp2": tp2, "bull_case": positives, "bear_case": negatives,
        "steps": steps,
        "guardrail": "RESEARCH ONLY · nessun ordine reale · nessuna modifica al CORE Production",
    }
