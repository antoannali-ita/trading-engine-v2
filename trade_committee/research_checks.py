from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

import numpy as np
import pandas as pd
import yfinance as yf

from .rigor import cross_validate, verify_market_cap, verify_pe

ROOT = Path(__file__).resolve().parents[1]
PORTFOLIO_CONFIG = ROOT / "config" / "production_portfolio.json"

YAHOO_SOURCE = "Yahoo Finance / yfinance"
TRADINGVIEW_SOURCE = "TradingView Screener"
SEC_SOURCE = "SEC EDGAR"

SECTOR_ETF = {
    "Technology": "XLK",
    "Financial Services": "XLF",
    "Healthcare": "XLV",
    "Consumer Cyclical": "XLY",
    "Consumer Defensive": "XLP",
    "Industrials": "XLI",
    "Energy": "XLE",
    "Basic Materials": "XLB",
    "Real Estate": "XLRE",
    "Utilities": "XLU",
    "Communication Services": "XLC",
}


def _num(v: Any) -> float | None:
    try:
        if v is None or pd.isna(v):
            return None
        return float(v)
    except Exception:
        return None


def _ret(series: pd.Series, bars: int) -> float | None:
    s = series.dropna()
    if len(s) <= bars or not _num(s.iloc[-bars - 1]):
        return None
    return float(s.iloc[-1] / s.iloc[-bars - 1] - 1.0)


def rsi(close: pd.Series, n: int = 14) -> float | None:
    if len(close) <= n:
        return None
    d = close.diff()
    up = d.clip(lower=0).rolling(n).mean()
    dn = (-d.clip(upper=0)).rolling(n).mean()
    rs = up / dn.replace(0, np.nan)
    return _num((100 - 100 / (1 + rs)).iloc[-1])


def atr(df: pd.DataFrame, n: int = 14) -> float | None:
    if len(df) <= n:
        return None
    pc = df["Close"].shift(1)
    tr = np.maximum(df["High"] - df["Low"], np.maximum((df["High"] - pc).abs(), (df["Low"] - pc).abs()))
    return _num(pd.Series(tr, index=df.index).rolling(n).mean().iloc[-1])


def macd(close: pd.Series) -> tuple[float | None, float | None]:
    if len(close) < 35:
        return None, None
    fast = close.ewm(span=12, adjust=False).mean()
    slow = close.ewm(span=26, adjust=False).mean()
    line = fast - slow
    signal = line.ewm(span=9, adjust=False).mean()
    return _num(line.iloc[-1]), _num(signal.iloc[-1])


def _date_payload(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {"date": "N/D", "days": None}
    values = raw if isinstance(raw, (list, tuple)) else [raw]
    for value in values:
        if isinstance(value, datetime):
            d = value.date()
        elif isinstance(value, date):
            d = value
        else:
            try:
                d = datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
            except Exception:
                continue
        return {"date": d.strftime("%d/%m/%Y"), "days": (d - datetime.now(timezone.utc).date()).days}
    return {"date": "N/D", "days": None}


def fetch_market_bundle(symbol: str) -> dict[str, Any]:
    t = yf.Ticker(symbol)
    hist = t.history(period="1y", auto_adjust=False)
    if hist.empty:
        raise RuntimeError(f"Nessun dato di mercato disponibile per {symbol}")
    close = hist["Close"].dropna()
    price = _num(close.iloc[-1])
    sma20 = _num(close.rolling(20).mean().iloc[-1]) if len(close) >= 20 else None
    sma50 = _num(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else None
    sma200 = _num(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else None
    atr14 = atr(hist)
    rsi14 = rsi(close)
    macd_line, macd_signal = macd(close)
    avg20 = _num(hist["Volume"].tail(20).mean())
    volume = _num(hist["Volume"].iloc[-1])
    rvol = volume / avg20 if volume is not None and avg20 else None
    low20 = _num(hist["Low"].tail(20).min())
    high60 = _num(hist["High"].tail(60).max())
    high120 = _num(hist["High"].tail(120).max())
    low52 = _num(hist["Low"].min())
    high52 = _num(hist["High"].max())
    return {
        "ticker_obj": t,
        "history": hist,
        "source": YAHOO_SOURCE,
        "price": price,
        "sma20": sma20,
        "sma50": sma50,
        "sma200": sma200,
        "rsi14": rsi14,
        "atr14": atr14,
        "macd": macd_line,
        "macd_signal": macd_signal,
        "volume": volume,
        "avg_volume20": avg20,
        "relative_volume": rvol,
        "support20": low20,
        "resistance60": high60,
        "resistance120": high120,
        "low52": low52,
        "high52": high52,
        "return_1m": _ret(close, 21),
        "return_3m": _ret(close, 63),
        "return_6m": _ret(close, 126),
    }


def fetch_info(t: yf.Ticker) -> dict[str, Any]:
    try:
        return t.info or {}
    except Exception:
        return {}


def fundamental_bundle(info: dict[str, Any], price: float | None) -> dict[str, Any]:
    keys = [
        "marketCap", "enterpriseValue", "trailingPE", "forwardPE", "pegRatio", "priceToBook",
        "enterpriseToEbitda", "returnOnEquity", "returnOnAssets", "currentRatio", "debtToEquity",
        "freeCashflow", "operatingCashflow", "totalCash", "totalDebt", "revenueGrowth", "earningsGrowth",
        "grossMargins", "operatingMargins", "profitMargins", "sharesOutstanding", "trailingEps", "forwardEps",
        "dividendYield", "beta", "shortPercentOfFloat", "shortRatio", "heldPercentInstitutions",
    ]
    data = {k: info.get(k) for k in keys}
    mc = _num(data.get("marketCap"))
    fcf = _num(data.get("freeCashflow"))
    data["fcfYield"] = fcf / mc if fcf is not None and mc else None
    data["netDebt"] = (_num(data.get("totalDebt")) or 0.0) - (_num(data.get("totalCash")) or 0.0) if (data.get("totalDebt") is not None or data.get("totalCash") is not None) else None
    rigor = {
        "market_cap_check": verify_market_cap(
            price=price,
            shares=data.get("sharesOutstanding"),
            reported_market_cap=data.get("marketCap"),
        ),
        "pe_check": verify_pe(price=price, eps=data.get("trailingEps"), reported_pe=data.get("trailingPE")),
    }
    return {"source": YAHOO_SOURCE, "data": data, "rigor": rigor}


def quality_assessment(f: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def add(name: str, value: Any, ok: bool | None, note: str):
        checks.append({"check": name, "value": value, "status": "PASS" if ok is True else ("FAIL" if ok is False else "N/D"), "note": note})

    roe = _num(f.get("returnOnEquity")); add("ROE", roe, None if roe is None else roe >= 0.12, ">=12% preferito")
    current = _num(f.get("currentRatio")); add("Current Ratio", current, None if current is None else current > 1.0, ">1 preferito")
    de = _num(f.get("debtToEquity")); add("Debt/Equity", de, None if de is None else de < 100.0, "Yahoo esprime spesso il dato in percentuale; <100 ~ <1x")
    ocf = _num(f.get("operatingCashflow")); add("Operating Cash Flow", ocf, None if ocf is None else ocf > 0, "positivo")
    fcf = _num(f.get("freeCashflow")); add("Free Cash Flow", fcf, None if fcf is None else fcf > 0, "positivo")
    rg = _num(f.get("revenueGrowth")); add("Revenue Growth", rg, None if rg is None else rg > 0.05, ">5% preferito")
    eg = _num(f.get("earningsGrowth")); add("Earnings Growth", eg, None if eg is None else eg > 0.05, ">5% preferito")
    pm = _num(f.get("profitMargins")); add("Profit Margin", pm, None if pm is None else pm > 0, "positivo")
    available = [c for c in checks if c["status"] != "N/D"]
    passed = [c for c in available if c["status"] == "PASS"]
    score = round(100 * len(passed) / len(available), 1) if available else 0.0
    red_flags = [c["check"] for c in available if c["status"] == "FAIL"]
    return {"score": score, "checks": checks, "red_flags": red_flags, "coverage": len(available)}


def valuation_assessment(f: dict[str, Any]) -> dict[str, Any]:
    score = 50.0
    notes: list[str] = []
    pe = _num(f.get("trailingPE")); fpe = _num(f.get("forwardPE")); peg = _num(f.get("pegRatio")); ev = _num(f.get("enterpriseToEbitda")); fcf_y = _num(f.get("fcfYield"))
    if pe is not None:
        score += 10 if 5 <= pe <= 25 else (-10 if pe > 35 else 0); notes.append(f"P/E {pe:.1f}x")
    if fpe is not None:
        score += 15 if 5 <= fpe <= 20 else (-10 if fpe > 30 else 0); notes.append(f"Forward P/E {fpe:.1f}x")
    if peg is not None:
        score += 10 if 0 < peg <= 1.5 else (-5 if peg > 2.5 else 0); notes.append(f"PEG {peg:.2f}")
    if ev is not None:
        score += 10 if ev < 15 else (-5 if ev > 25 else 0); notes.append(f"EV/EBITDA {ev:.1f}x")
    if fcf_y is not None:
        score += 10 if fcf_y >= 0.04 else (-5 if fcf_y < 0.02 else 0); notes.append(f"FCF yield {fcf_y*100:.1f}%")
    return {"score": max(0.0, min(100.0, round(score, 1))), "notes": notes}


def technical_assessment(m: dict[str, Any]) -> dict[str, Any]:
    score = 50.0
    price, s20, s50, s200, r = m.get("price"), m.get("sma20"), m.get("sma50"), m.get("sma200"), m.get("rsi14")
    if price is not None and s20 is not None: score += 8 if price > s20 else -8
    if price is not None and s50 is not None: score += 15 if price > s50 else -15
    if price is not None and s200 is not None: score += 12 if price > s200 else -12
    if s50 is not None and s200 is not None: score += 10 if s50 > s200 else -10
    if r is not None: score += 8 if 40 <= r <= 70 else (-8 if r >= 78 else 0)
    if m.get("macd") is not None and m.get("macd_signal") is not None: score += 7 if m["macd"] > m["macd_signal"] else -7
    return {"score": max(0.0, min(100.0, round(score, 1))), "trend_fail": bool(price and s50 and s200 and price < s50 < s200)}


def volume_assessment(m: dict[str, Any]) -> dict[str, Any]:
    rv = _num(m.get("relative_volume")); score = 50.0
    if rv is not None:
        if rv >= 1.5: score += 25
        elif rv >= 1.0: score += 15
        elif rv < 0.5: score -= 15
    return {"score": max(0.0, min(100.0, score)), "relative_volume": rv}


def earnings_and_catalysts(t: yf.Ticker) -> dict[str, Any]:
    try:
        cal = t.calendar or {}
        ep = _date_payload(cal.get("Earnings Date"))
    except Exception:
        ep = {"date": "N/D", "days": None}
    history: list[dict[str, Any]] = []
    try:
        ed = t.get_earnings_dates(limit=4)
        if ed is not None and not ed.empty:
            for idx, row in ed.head(4).iterrows():
                history.append({
                    "date": str(idx),
                    "eps_estimate": _num(row.get("EPS Estimate")),
                    "reported_eps": _num(row.get("Reported EPS")),
                    "surprise_pct": _num(row.get("Surprise(%)")),
                })
    except Exception:
        pass
    return {"source": YAHOO_SOURCE, "next": ep, "history": history, "status": "REAL" if ep["date"] != "N/D" else "PARTIAL"}


def _news_item(item: dict[str, Any]) -> dict[str, Any]:
    content = item.get("content") if isinstance(item.get("content"), dict) else item
    provider = content.get("provider") if isinstance(content.get("provider"), dict) else {}
    return {
        "title": content.get("title") or item.get("title") or "N/D",
        "publisher": provider.get("displayName") or item.get("publisher") or "N/D",
        "published": content.get("pubDate") or item.get("providerPublishTime") or "N/D",
    }


def news_analyst_ownership(t: yf.Ticker, info: dict[str, Any]) -> dict[str, Any]:
    news: list[dict[str, Any]] = []
    try:
        news = [_news_item(x) for x in (t.news or [])[:8]]
    except Exception:
        pass
    analyst = {
        "recommendation": info.get("recommendationKey"),
        "mean_target": _num(info.get("targetMeanPrice")),
        "low_target": _num(info.get("targetLowPrice")),
        "high_target": _num(info.get("targetHighPrice")),
        "analyst_count": info.get("numberOfAnalystOpinions"),
    }
    insiders: list[dict[str, Any]] = []
    try:
        df = t.insider_transactions
        if isinstance(df, pd.DataFrame) and not df.empty:
            cols = [c for c in ["Start Date", "Insider", "Position", "Transaction", "Shares", "Value"] if c in df.columns]
            insiders = df[cols].head(8).astype(object).where(pd.notna(df[cols]), None).to_dict("records")
    except Exception:
        pass
    institutions: list[dict[str, Any]] = []
    try:
        df = t.institutional_holders
        if isinstance(df, pd.DataFrame) and not df.empty:
            institutions = df.head(8).astype(object).where(pd.notna(df), None).to_dict("records")
    except Exception:
        pass
    short = {"short_float": _num(info.get("shortPercentOfFloat")), "days_to_cover": _num(info.get("shortRatio")), "institutional_pct": _num(info.get("heldPercentInstitutions"))}
    available = sum(bool(x) for x in [news, any(v is not None for v in analyst.values()), insiders, institutions])
    return {"source": YAHOO_SOURCE, "news": news, "analyst": analyst, "insiders": insiders, "institutions": institutions, "short": short, "status": "REAL" if available >= 2 else "PARTIAL"}


def _sec_json(url: str) -> Any:
    req = Request(url, headers={"User-Agent": "TradingEngineV2/1.0 research-only GitHub project", "Accept-Encoding": "identity"})
    with urlopen(req, timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))


def sec_recent_filings(symbol: str) -> dict[str, Any]:
    if symbol.endswith(".MI"):
        return {"status": "N/A", "source": SEC_SOURCE, "filings": [], "note": "Emittente non USA"}
    try:
        tickers = _sec_json("https://www.sec.gov/files/company_tickers.json")
        match = next((v for v in tickers.values() if str(v.get("ticker", "")).upper() == symbol.upper()), None)
        if not match:
            return {"status": "PARTIAL", "source": SEC_SOURCE, "filings": [], "note": "CIK non trovato"}
        cik = str(match["cik_str"]).zfill(10)
        data = _sec_json(f"https://data.sec.gov/submissions/CIK{cik}.json")
        recent = (data.get("filings") or {}).get("recent") or {}
        forms = recent.get("form") or []
        dates = recent.get("filingDate") or []
        accessions = recent.get("accessionNumber") or []
        filings = []
        wanted = {"10-K", "10-Q", "8-K", "4"}
        for form, filing_date, accession in zip(forms, dates, accessions):
            if form in wanted:
                filings.append({"form": form, "date": filing_date, "accession": accession})
            if len(filings) >= 12:
                break
        return {"status": "REAL", "source": SEC_SOURCE, "cik": cik, "filings": filings, "note": "Form 4 = insider filing; 13F non è attribuibile direttamente all'emittente"}
    except Exception as exc:
        return {"status": "PARTIAL", "source": SEC_SOURCE, "filings": [], "note": f"SEC non disponibile: {type(exc).__name__}"}


def benchmark_context(symbol: str, info: dict[str, Any], m: dict[str, Any]) -> dict[str, Any]:
    is_italy = symbol.endswith(".MI")
    benchmark = "FTSEMIB.MI" if is_italy else "SPY"
    sector = info.get("sector") or "N/D"
    sector_ticker = None if is_italy else SECTOR_ETF.get(sector)
    tickers = [benchmark] + ([sector_ticker] if sector_ticker else [])
    result = {"source": YAHOO_SOURCE, "benchmark": benchmark, "sector": sector, "sector_ticker": sector_ticker, "relative": {}, "status": "PARTIAL"}
    try:
        raw = yf.download(tickers, period="7mo", interval="1d", auto_adjust=True, progress=False, group_by="ticker")
        for ticker in tickers:
            try:
                close = raw["Close"].dropna() if len(tickers) == 1 else raw[(ticker, "Close")].dropna()
                result[ticker] = {"1m": _ret(close, 21), "3m": _ret(close, 63), "6m": _ret(close, 126)}
            except Exception:
                pass
        base = result.get(benchmark, {})
        for label, key in [("1m", "return_1m"), ("3m", "return_3m"), ("6m", "return_6m")]:
            stock_ret, bench_ret = m.get(key), base.get(label)
            result["relative"][label] = stock_ret - bench_ret if stock_ret is not None and bench_ret is not None else None
        result["status"] = "REAL" if base else "PARTIAL"
    except Exception:
        pass
    rel3 = _num(result["relative"].get("3m")); rel6 = _num(result["relative"].get("6m"))
    score = 50.0
    for rel in [rel3, rel6]:
        if rel is not None: score += 15 if rel > 0 else -15
    result["score"] = max(0.0, min(100.0, score))
    return result


def tradingview_crosscheck(symbol: str, price: float | None, rsi14: float | None) -> dict[str, Any]:
    try:
        from tradingview_screener import Column, Query
        market = "italy" if symbol.endswith(".MI") else "america"
        tv_symbol = symbol.replace(".MI", "")
        _, df = (
            Query()
            .set_markets(market)
            .select("name", "close", "RSI", "volume")
            .where(Column("name") == tv_symbol)
            .limit(5)
            .get_scanner_data()
        )
        if df is None or df.empty:
            return {"status": "PARTIAL", "source": TRADINGVIEW_SOURCE, "note": "Ticker non trovato"}
        row = df.iloc[0]
        price_check = cross_validate({"Yahoo": price, "TradingView": _num(row.get("close"))}, tolerance_pct=1.0)
        rsi_check = cross_validate({"Python": rsi14, "TradingView": _num(row.get("RSI"))}, tolerance_pct=5.0)
        return {"status": "REAL", "source": TRADINGVIEW_SOURCE, "price": _num(row.get("close")), "rsi": _num(row.get("RSI")), "price_check": price_check, "rsi_check": rsi_check}
    except Exception as exc:
        return {"status": "PARTIAL", "source": TRADINGVIEW_SOURCE, "note": f"Cross-check non disponibile: {type(exc).__name__}"}


def portfolio_context(symbol: str, price: float | None) -> dict[str, Any]:
    try:
        cfg = json.loads(PORTFOLIO_CONFIG.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"status": "N/D", "note": f"Config portafoglio non leggibile: {type(exc).__name__}"}
    equities = cfg.get("equities", [])
    values: dict[str, float] = {}
    for row in equities:
        p = _num(row.get("snapshot_price_usd")) or _num(row.get("avg_price_usd")) or 0.0
        q = _num(row.get("quantity")) or 0.0
        values[str(row.get("ticker"))] = p * q
    total = sum(values.values())
    current = next((r for r in equities if str(r.get("ticker", "")).upper() == symbol.upper()), None)
    current_value = values.get(symbol, 0.0)
    if current and price is not None:
        current_value = price * (_num(current.get("quantity")) or 0.0)
    weight = current_value / total if total > 0 and current_value else 0.0
    return {
        "status": "REAL",
        "source": "config/production_portfolio.json",
        "already_owned": current is not None,
        "position": current,
        "estimated_weight": weight,
        "portfolio_snapshot_value": total,
        "note": "Peso stimato sullo snapshot configurato; non sostituisce il broker live",
    }


def build_trade_plan(m: dict[str, Any], *, capital: float = 2500.0, commission_per_side: float = 18.0) -> dict[str, Any]:
    price = _num(m.get("price")); atr14 = _num(m.get("atr14")); support = _num(m.get("support20")); r60 = _num(m.get("resistance60")); r120 = _num(m.get("resistance120"))
    if price is None or atr14 is None:
        return {"status": "N/D"}
    structural = support * 0.99 if support else price - 1.5 * atr14
    atr_stop = price - 1.5 * atr14
    stop = min(structural, atr_stop)
    risk_share = price - stop
    if risk_share <= 0:
        return {"status": "N/D"}
    fallback_tp1, fallback_tp2 = price + 2 * risk_share, price + 3 * risk_share
    tp1 = r60 if r60 is not None and r60 > price + risk_share else fallback_tp1
    tp2 = r120 if r120 is not None and r120 > max(price + 2 * risk_share, tp1) else fallback_tp2
    qty = max(0, int((capital - commission_per_side) // price))
    round_trip = commission_per_side * 2
    loss = qty * risk_share + round_trip
    gain1 = qty * (tp1 - price) - round_trip
    gain2 = qty * (tp2 - price) - round_trip
    rr1 = gain1 / loss if loss > 0 else None
    rr2 = gain2 / loss if loss > 0 else None
    return {
        "status": "REAL", "entry": price, "stop": stop, "tp1": tp1, "tp2": tp2,
        "risk_per_share": risk_share, "risk_pct": risk_share / price, "qty": qty,
        "capital": qty * price + commission_per_side, "loss_max": loss,
        "gain_tp1": gain1, "gain_tp2": gain2, "rr1_net": rr1, "rr2_net": rr2,
        "commission_per_side": commission_per_side,
        "method": "supporto 20g + 1.5 ATR; target su resistenze 60/120g con fallback 2R/3R",
    }
