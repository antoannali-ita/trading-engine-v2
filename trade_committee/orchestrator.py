from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

from .research_checks import (
    benchmark_context,
    build_trade_plan,
    earnings_and_catalysts,
    fetch_info,
    fetch_market_bundle,
    fundamental_bundle,
    news_analyst_ownership,
    portfolio_context,
    quality_assessment,
    sec_recent_filings,
    technical_assessment,
    tradingview_crosscheck,
    valuation_assessment,
    volume_assessment,
)


def _progress(cb: Callable | None, step: int, label: str, status: str = "REAL"):
    if cb:
        cb(step, label, status)


def _coverage_status(status: str) -> float:
    return {"REAL": 1.0, "PARTIAL": 0.55, "N/A": 1.0, "N/D": 0.0, "FAILED": 0.0}.get(status, 0.0)


def _fmt_pct(value):
    return f"{value*100:+.1f}%" if isinstance(value, (int, float)) else "N/D"


def run_committee(ticker: str, progress_cb: Callable | None = None) -> dict:
    """Trade Committee V2.

    Modulo manuale e read-only. I check dichiarati REAL interrogano o calcolano davvero
    la fonte indicata. PARTIAL segnala copertura incompleta. Nessun check mancante viene
    mascherato come completato e nessun risultato modifica il CORE Production.
    """
    symbol = ticker.strip().upper()
    if not symbol:
        raise ValueError("Ticker obbligatorio")

    coverage: list[dict] = []

    def done(step: int, label: str, status: str, source: str, note: str = ""):
        coverage.append({"step": step, "check": label, "status": status, "source": source, "note": note})
        _progress(progress_cb, step, label, status)

    # 1. Market + technical data
    market = fetch_market_bundle(symbol)
    info = fetch_info(market["ticker_obj"])
    technical = technical_assessment(market)
    volume = volume_assessment(market)
    done(1, "Market & Technical", "REAL", "Yahoo Finance + calcoli Python", "Prezzi, SMA, RSI, MACD, ATR, RVOL, supporti/resistenze")

    # 2. Data quality: consistency + TradingView secondary source
    fundamentals = fundamental_bundle(info, market.get("price"))
    tv = tradingview_crosscheck(symbol, market.get("price"), market.get("rsi14"))
    rigor_warnings = sum(1 for x in fundamentals["rigor"].values() if x.get("status") == "WARNING")
    data_quality_status = "REAL" if tv.get("status") == "REAL" else "PARTIAL"
    done(2, "Data Quality / Cross-check", data_quality_status, "Yahoo Finance + TradingView Screener + Decimal checks", tv.get("note", "Controlli prezzo/RSI e coerenza market cap/P-E"))

    # 3. Fundamentals
    f = fundamentals["data"]
    available_fundamentals = sum(v is not None for v in f.values())
    fundamental_status = "REAL" if available_fundamentals >= 15 else "PARTIAL"
    done(3, "Fundamental Deep Dive", fundamental_status, "Yahoo Finance", f"Campi disponibili: {available_fundamentals}/{len(f)}")

    # 4. Business quality / financial strength - no fake moat score
    quality = quality_assessment(f)
    quality_status = "REAL" if quality["coverage"] >= 6 else "PARTIAL"
    done(4, "Business Quality / Financial Strength", quality_status, "Yahoo Finance + regole deterministiche", "Moat e qualità del management restano qualitativi e non vengono inventati")

    # 5. Valuation + arithmetic verification
    valuation = valuation_assessment(f)
    done(5, "Valuation", "REAL" if valuation["notes"] else "PARTIAL", "Yahoo Finance + calcoli interni", "; ".join(valuation["notes"][:4]))

    # 6. Earnings and catalyst window
    earnings = earnings_and_catalysts(market["ticker_obj"])
    done(6, "Earnings / Catalyst Window", earnings["status"], "Yahoo Finance", f"Prossimi earnings: {earnings['next']['date']}")

    # 7. News, analysts, insider, institutional ownership
    sentiment = news_analyst_ownership(market["ticker_obj"], info)
    done(7, "News / Analyst / Insider / Ownership", sentiment["status"], "Yahoo Finance", "News, consensus analisti, insider transactions, institutional holders e short data quando disponibili")

    # 8. Official filings
    sec = sec_recent_filings(symbol)
    done(8, "Official Filings", sec["status"], sec.get("source", "SEC EDGAR"), sec.get("note", ""))

    # 9. Benchmark and sector
    market_context = benchmark_context(symbol, info, market)
    done(9, "Market / Sector / Relative Strength", market_context["status"], f"Yahoo Finance · {market_context['benchmark']}" + (f" · {market_context['sector_ticker']}" if market_context.get("sector_ticker") else ""), "RS 1m/3m/6m contro benchmark; settore ETF per USA quando disponibile")

    # 10. Real portfolio context from the configured Production snapshot
    portfolio = portfolio_context(symbol, market.get("price"))
    done(10, "Portfolio Context", portfolio["status"], "config/production_portfolio.json", portfolio.get("note", ""))

    # 11. Trade plan
    trade = build_trade_plan(market)
    done(11, "Entry / Stop / Target / Sizing", trade.get("status", "N/D"), "Price structure + ATR + Fineco cost model", trade.get("method", ""))

    # 12. Adversarial bull/bear review
    bull: list[str] = []
    bear: list[str] = []
    if technical["score"] >= 65:
        bull.append("Trend e price action favorevoli")
    else:
        bear.append("Trend tecnico non abbastanza forte")
    if quality["score"] >= 70:
        bull.append("Qualità finanziaria buona sui dati verificabili")
    else:
        bear.append("Qualità finanziaria non supera con margine i check")
    if valuation["score"] >= 65:
        bull.append("Valutazione ragionevole rispetto ai criteri del Committee")
    else:
        bear.append("Valutazione senza margine di sicurezza evidente")
    rel3 = market_context.get("relative", {}).get("3m")
    rel6 = market_context.get("relative", {}).get("6m")
    if (rel3 or 0) > 0 and (rel6 or 0) > 0:
        bull.append(f"Forza relativa positiva: 3m {_fmt_pct(rel3)}, 6m {_fmt_pct(rel6)}")
    elif rel3 is not None or rel6 is not None:
        bear.append(f"Forza relativa non convincente: 3m {_fmt_pct(rel3)}, 6m {_fmt_pct(rel6)}")
    if portfolio.get("already_owned"):
        bear.append(f"Titolo già presente in portafoglio; peso stimato {portfolio.get('estimated_weight', 0)*100:.1f}%")
    if quality.get("red_flags"):
        bear.append("Red flag finanziarie: " + ", ".join(quality["red_flags"][:4]))
    earnings_days = earnings["next"].get("days")
    if isinstance(earnings_days, int) and earnings_days <= 14:
        bear.append(f"Earnings vicini: {earnings_days} giorni")
    if sec.get("status") == "REAL" and sec.get("filings"):
        bull.append("Filings SEC recenti verificati direttamente su EDGAR")
    done(12, "Bull / Bear / Inversion Review", "REAL", "Sintesi deterministica dei check precedenti", "Il Bear case cerca condizioni che invalidano l'acquisto")

    # Scores: the Committee is intentionally separate from CORE score.
    sentiment_score = 50.0
    analyst_rec = (sentiment.get("analyst") or {}).get("recommendation")
    if analyst_rec in {"strong_buy", "buy"}: sentiment_score += 15
    elif analyst_rec in {"sell", "strong_sell"}: sentiment_score -= 20
    short_float = (sentiment.get("short") or {}).get("short_float")
    if isinstance(short_float, (int, float)) and short_float > 0.15: sentiment_score -= 10
    sentiment_score = max(0.0, min(100.0, sentiment_score))

    portfolio_score = 70.0
    if portfolio.get("already_owned"):
        weight = portfolio.get("estimated_weight") or 0
        portfolio_score -= 20 if weight < 0.15 else 40

    committee_score = round(
        0.25 * technical["score"]
        + 0.10 * volume["score"]
        + 0.20 * quality["score"]
        + 0.15 * valuation["score"]
        + 0.10 * market_context.get("score", 50.0)
        + 0.10 * sentiment_score
        + 0.10 * portfolio_score,
        1,
    )

    weights = {1: 1.2, 2: 1.2, 3: 1.2, 4: 1.0, 5: 1.0, 6: 1.0, 7: 0.8, 8: 0.8, 9: 1.0, 10: 0.8, 11: 1.2, 12: 0.8}
    numerator = sum(_coverage_status(row["status"]) * weights[row["step"]] for row in coverage)
    denominator = sum(weights.values())
    data_confidence = round(100 * numerator / denominator, 1) if denominator else 0.0
    if rigor_warnings:
        data_confidence = max(0.0, data_confidence - min(10.0, rigor_warnings * 3.0))

    hard_reasons: list[str] = []
    if technical.get("trend_fail"):
        hard_reasons.append("Prezzo < SMA50 < SMA200")
    if isinstance(earnings_days, int) and 0 <= earnings_days < 7:
        hard_reasons.append("Earnings entro 7 giorni")
    if data_confidence < 70:
        hard_reasons.append("Data Confidence <70%")
    if trade.get("status") == "REAL" and isinstance(trade.get("rr1_net"), (int, float)) and trade["rr1_net"] < 1.5:
        hard_reasons.append("R/R netto TP1 <1.5")

    if committee_score >= 75 and technical["score"] >= 60 and not hard_reasons:
        verdict = "APPROVE"
    elif committee_score < 45:
        verdict = "REJECT"
    else:
        verdict = "WAIT"

    decision_reason = (
        "Committee conferma il candidato" if verdict == "APPROVE" else
        "Servono condizioni migliori prima dell'acquisto" if verdict == "WAIT" else
        "Il profilo rischio/rendimento non è sufficiente"
    )

    return {
        "version": "TRADE_COMMITTEE_V2",
        "run_at": datetime.now(timezone.utc).isoformat(),
        "ticker": symbol,
        "verdict": verdict,
        "decision_reason": decision_reason,
        "committee_score": committee_score,
        "data_confidence": data_confidence,
        "hard_reasons": hard_reasons,
        "price": market.get("price"),
        "market": {k: v for k, v in market.items() if k not in {"ticker_obj", "history"}},
        "fundamentals": f,
        "financial_rigor": fundamentals["rigor"],
        "quality": quality,
        "valuation": valuation,
        "technical": technical,
        "volume": volume,
        "earnings": earnings,
        "sentiment": sentiment,
        "sec": sec,
        "market_context": market_context,
        "portfolio": portfolio,
        "trade_plan": trade,
        "bull_case": bull[:5],
        "bear_case": bear[:6],
        "coverage": coverage,
        "coverage_summary": {
            "real": sum(1 for x in coverage if x["status"] == "REAL"),
            "partial": sum(1 for x in coverage if x["status"] == "PARTIAL"),
            "na": sum(1 for x in coverage if x["status"] == "N/A"),
            "missing": sum(1 for x in coverage if x["status"] in {"N/D", "FAILED"}),
        },
        "tradingview_crosscheck": tv,
        "guardrail": "RESEARCH ONLY · nessun ordine reale · nessuna modifica al CORE Production",
    }
