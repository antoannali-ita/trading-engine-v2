from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Mapping

from .core_snapshot import CoreSnapshot, snapshot_hash, snapshot_payload, snapshot_value
from .policy import CheckClass, HardVeto, POLICY_VERSION, evaluate_verdict
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


VERSION = "TRADE_COMMITTEE_V2_2"
MIN_NET_RR = 2.0
MAX_POSITION_USD = 2500.0


def _progress(cb: Callable | None, step: int, label: str, status: str = "COMPLETE"):
    if cb:
        cb(step, label, status)


def _fmt_pct(value):
    return f"{value*100:+.1f}%" if isinstance(value, (int, float)) else "N/D"


def _safe_float(value: Any) -> float | None:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def _class_for_status(status: str, *, enrichment: bool = False, soft: bool = False) -> CheckClass:
    if status in {"REAL", "COMPLETE", "N/A"}:
        return CheckClass.COMPLETE
    if enrichment:
        return CheckClass.ENRICHMENT_ND
    if soft:
        return CheckClass.SOFT_WARNING
    return CheckClass.CORE_WARNING


def _core_trade_plan(core: CoreSnapshot | Mapping[str, Any] | None, fallback: dict[str, Any]) -> dict[str, Any]:
    if core is None:
        result = dict(fallback)
        result["source"] = "COMMITTEE_FALLBACK"
        result["authoritative"] = False
        return result
    entry = snapshot_value(core, "ideal_entry", snapshot_value(core, "price"))
    result = {
        "status": "REAL",
        "source": "CORE_SNAPSHOT",
        "authoritative": True,
        "entry": entry,
        "max_buy": snapshot_value(core, "max_buy"),
        "stop": snapshot_value(core, "stop"),
        "tp1": snapshot_value(core, "tp1"),
        "tp2": snapshot_value(core, "tp2"),
        "qty": snapshot_value(core, "shares"),
        "capital": snapshot_value(core, "invested"),
        "loss_max": snapshot_value(core, "net_risk_total"),
        "rr1_net": snapshot_value(core, "net_rr_tp1"),
        "rr2_net": snapshot_value(core, "net_rr_tp2"),
        "method": "Entry/Stop/Target/RR importati dal CORE snapshot; il Committee non li ricalcola",
    }
    return result


def _engine_validation(core: CoreSnapshot | Mapping[str, Any] | None, current_price: float | None, trade: dict[str, Any]) -> dict[str, Any]:
    if core is None:
        return {"score": 0.0, "points": 0, "max_points": 20, "checks": [], "status": "N/D"}

    checks: list[dict[str, Any]] = []
    points = 0

    trigger = str(snapshot_value(core, "trigger_state", "N/D")).upper()
    trigger_ok = trigger not in {"INVALID", "FAILED", "N/D", ""}
    points += 6 if trigger_ok else 0
    checks.append({"check": "Trigger CORE ancora valido", "points": 6 if trigger_ok else 0, "max": 6, "value": trigger})

    max_buy = _safe_float(snapshot_value(core, "max_buy"))
    inside_max_buy = current_price is not None and (max_buy is None or current_price <= max_buy)
    points += 4 if inside_max_buy else 0
    checks.append({"check": "Prezzo non oltre Max Buy", "points": 4 if inside_max_buy else 0, "max": 4, "value": max_buy})

    entry = _safe_float(trade.get("entry")); stop = _safe_float(trade.get("stop"))
    stop_ok = entry is not None and stop is not None and stop < entry
    points += 4 if stop_ok else 0
    checks.append({"check": "Stop coerente sotto entry", "points": 4 if stop_ok else 0, "max": 4, "value": stop})

    rr2 = _safe_float(trade.get("rr2_net"))
    rr_ok = rr2 is not None and rr2 >= MIN_NET_RR
    points += 4 if rr_ok else 0
    checks.append({"check": f"R/R netto TP2 >= {MIN_NET_RR:.1f}", "points": 4 if rr_ok else 0, "max": 4, "value": rr2})

    technical_state = str(snapshot_value(core, "technical_state", "N/D")).upper()
    failed_gates = {str(x).lower() for x in (snapshot_value(core, "failed_gates", []) or [])}
    structure_ok = technical_state not in {"BREAKDOWN", "BEARISH", "INVALID"} and not ({"structure", "trend"} & failed_gates)
    points += 2 if structure_ok else 0
    checks.append({"check": "Nessuna rottura struttura/trigger CORE", "points": 2 if structure_ok else 0, "max": 2, "value": technical_state})

    return {"score": round(points / 20 * 100, 1), "points": points, "max_points": 20, "checks": checks, "status": "REAL"}


def _hard_vetoes(
    core: CoreSnapshot | Mapping[str, Any] | None,
    *,
    current_price: float | None,
    earnings_days: int | None,
    trade: dict[str, Any],
    tv: dict[str, Any],
) -> tuple[list[HardVeto], list[str]]:
    vetoes: list[HardVeto] = []
    reasons: list[str] = []

    def add(veto: HardVeto, reason: str):
        if veto not in vetoes:
            vetoes.append(veto)
            reasons.append(reason)

    if isinstance(earnings_days, int) and 0 <= earnings_days < 7:
        add(HardVeto.EARNINGS_LT_7D, f"Earnings entro {earnings_days} giorni")

    price_check = tv.get("price_check") if isinstance(tv, dict) else None
    if isinstance(price_check, dict) and str(price_check.get("status", "")).upper() in {"FAIL", "ERROR", "CONFLICT"}:
        add(HardVeto.PRICE_DATA_CONFLICT, "Conflitto materiale tra fonti sul prezzo")

    if core is None:
        return vetoes, reasons

    if bool(snapshot_value(core, "data_review_required", False)):
        add(HardVeto.PRICE_DATA_CONFLICT, "CORE richiede DATA REVIEW")

    corporate = str(snapshot_value(core, "corporate_action_status", "N/D")).upper()
    if corporate in {"CONFLICT", "INVALID", "REVIEW", "FAILED"}:
        add(HardVeto.CORPORATE_ACTION, f"Corporate action CORE: {corporate}")

    trigger = str(snapshot_value(core, "trigger_state", "N/D")).upper()
    if trigger == "INVALID":
        add(HardVeto.TRIGGER_INVALID, "Trigger CORE INVALID")

    max_buy = _safe_float(snapshot_value(core, "max_buy"))
    if current_price is not None and max_buy is not None and current_price > max_buy:
        add(HardVeto.PRICE_ABOVE_MAX_BUY, f"Prezzo {current_price:.2f} > Max Buy {max_buy:.2f}")

    rr2 = _safe_float(trade.get("rr2_net"))
    if rr2 is not None and rr2 < MIN_NET_RR:
        add(HardVeto.RR_NET_LT_MIN, f"R/R netto TP2 {rr2:.2f} < {MIN_NET_RR:.2f}")

    invested = _safe_float(snapshot_value(core, "invested"))
    if invested is not None and invested > MAX_POSITION_USD + 1e-9:
        add(HardVeto.POSITION_SIZE, f"Posizione CORE {invested:.0f} USD > {MAX_POSITION_USD:.0f} USD")

    core_vetoes = snapshot_value(core, "veto_reasons", []) or []
    if core_vetoes:
        add(HardVeto.CORE_HARD_VETO, "CORE veto: " + "; ".join(str(x) for x in core_vetoes[:4]))

    return vetoes, reasons


def run_committee(
    ticker: str,
    progress_cb: Callable | None = None,
    *,
    core_snapshot: CoreSnapshot | Mapping[str, Any] | None = None,
) -> dict:
    """Valida una trade prima dell'acquisto senza sostituire il CORE.

    Se viene fornito ``core_snapshot``, entry/stop/target/RR e stato operativo del CORE
    sono la single source of truth. I calcoli locali sono cross-check/enrichment e non
    possono cancellare un hard veto del CORE.

    Senza snapshot il Committee resta utilizzabile in modalità manual research, ma la
    mancanza del CORE viene classificata CORE_WARNING: non viene simulato un secondo CORE.
    """
    symbol = ticker.strip().upper()
    if not symbol:
        raise ValueError("Ticker obbligatorio")

    core_payload = snapshot_payload(core_snapshot)
    if core_payload and str(core_payload.get("ticker", symbol)).upper() != symbol:
        raise ValueError("Ticker CORE snapshot diverso dal ticker richiesto")

    coverage: list[dict[str, Any]] = []

    def done(step: int, label: str, check_class: CheckClass, source: str, note: str = ""):
        coverage.append({
            "step": step,
            "check": label,
            "status": check_class.value,
            "class": check_class.value,
            "source": source,
            "note": note,
        })
        _progress(progress_cb, step, label, check_class.value)

    market = fetch_market_bundle(symbol)
    info = fetch_info(market["ticker_obj"])
    current_price = _safe_float(market.get("price"))
    done(1, "Market data corrente", CheckClass.COMPLETE, "Yahoo Finance", "Usato come cross-check del CORE")

    fundamentals = fundamental_bundle(info, current_price)
    tv = tradingview_crosscheck(symbol, current_price, market.get("rsi14"))
    tv_class = _class_for_status(tv.get("status", "PARTIAL"))
    done(2, "Data Quality / Cross-check", tv_class, "Yahoo Finance + TradingView Screener", tv.get("note", "Cross-check prezzo/indicatori"))

    f = fundamentals["data"]
    available_fundamentals = sum(v is not None for v in f.values())
    fundamental_class = CheckClass.COMPLETE if available_fundamentals >= 15 else CheckClass.CORE_WARNING
    done(3, "Fundamental Deep Dive", fundamental_class, "Yahoo Finance", f"Campi disponibili: {available_fundamentals}/{len(f)}")

    quality = quality_assessment(f)
    quality_class = CheckClass.COMPLETE if quality["coverage"] >= 6 else CheckClass.CORE_WARNING
    done(4, "Business Quality / Financial Strength", quality_class, "Yahoo Finance + regole deterministiche", "Moat/management qualitativi non vengono inventati")

    valuation = valuation_assessment(f)
    valuation_class = CheckClass.COMPLETE if valuation["notes"] else CheckClass.CORE_WARNING
    done(5, "Valuation", valuation_class, "Yahoo Finance + calcoli interni", "; ".join(valuation["notes"][:4]))

    earnings = earnings_and_catalysts(market["ticker_obj"])
    earnings_class = _class_for_status(earnings.get("status", "PARTIAL"))
    done(6, "Earnings / Catalyst Window", earnings_class, "Yahoo Finance", f"Prossimi earnings: {earnings['next']['date']}")

    sentiment = news_analyst_ownership(market["ticker_obj"], info)
    sentiment_class = _class_for_status(sentiment.get("status", "PARTIAL"), enrichment=True)
    done(7, "News / Analyst / Insider / Ownership", sentiment_class, "Yahoo Finance", "Enrichment: N/D non blocca e non riduce Core Data Confidence")

    sec = sec_recent_filings(symbol)
    sec_class = _class_for_status(sec.get("status", "PARTIAL"), soft=True)
    done(8, "Official Filings", sec_class, sec.get("source", "SEC EDGAR"), sec.get("note", ""))

    market_context = benchmark_context(symbol, info, market)
    market_class = _class_for_status(market_context.get("status", "PARTIAL"), soft=True)
    done(9, "Market / Sector / Relative Strength", market_class, f"Yahoo Finance · {market_context['benchmark']}", "RS 1m/3m/6m contro benchmark")

    portfolio = portfolio_context(symbol, current_price)
    portfolio_class = _class_for_status(portfolio.get("status", "N/D"), soft=True)
    done(10, "Portfolio Context", portfolio_class, "config/production_portfolio.json", portfolio.get("note", ""))

    fallback_trade = build_trade_plan(market, commission_per_side=12.0)
    trade = _core_trade_plan(core_snapshot, fallback_trade)
    if core_snapshot is None:
        trade_class = CheckClass.CORE_WARNING
        trade_note = "CORE snapshot assente: piano locale solo diagnostico, non authoritative"
    else:
        trade_class = CheckClass.COMPLETE
        trade_note = "Piano importato dal CORE; nessun ricalcolo di entry/stop/target/RR"
    done(11, "CORE Trade Plan", trade_class, trade.get("source", "CORE_SNAPSHOT"), trade_note)

    validation = _engine_validation(core_snapshot, current_price, trade)
    validation_class = CheckClass.COMPLETE if core_snapshot is not None else CheckClass.CORE_WARNING
    done(12, "Trade Thesis Validation", validation_class, "CORE snapshot + cross-check corrente", "Validazione deterministica, non nuovo stock score")

    technical = technical_assessment(market)
    volume = volume_assessment(market)

    bull: list[str] = []
    bear: list[str] = []
    if core_snapshot is not None:
        bull.append(f"CORE state: {snapshot_value(core_snapshot, 'operational_state', snapshot_value(core_snapshot, 'decision', 'N/D'))}")
        if validation["points"] >= 16:
            bull.append(f"Tesi CORE ancora coerente: {validation['points']}/20")
        else:
            bear.append(f"Validazione tesi CORE incompleta: {validation['points']}/20")
    else:
        bear.append("CORE snapshot assente: il Committee non può approvare una trade ricostruita autonomamente")
    if quality["score"] >= 70:
        bull.append("Qualità finanziaria buona sui dati verificabili")
    else:
        bear.append("Qualità finanziaria non supera con margine i check")
    if valuation["score"] >= 65:
        bull.append("Valutazione ragionevole")
    else:
        bear.append("Valutazione senza margine evidente")
    rel3 = market_context.get("relative", {}).get("3m")
    rel6 = market_context.get("relative", {}).get("6m")
    if (rel3 or 0) > 0 and (rel6 or 0) > 0:
        bull.append(f"Forza relativa positiva: 3m {_fmt_pct(rel3)}, 6m {_fmt_pct(rel6)}")
    elif rel3 is not None or rel6 is not None:
        bear.append(f"Forza relativa non convincente: 3m {_fmt_pct(rel3)}, 6m {_fmt_pct(rel6)}")
    if portfolio.get("already_owned"):
        bear.append(f"Titolo già in portafoglio; peso stimato {portfolio.get('estimated_weight', 0)*100:.1f}%")

    earnings_days = earnings["next"].get("days")
    if core_snapshot is not None and snapshot_value(core_snapshot, "days_to_earnings") is not None:
        earnings_days = int(snapshot_value(core_snapshot, "days_to_earnings"))

    hard_vetoes, hard_reasons = _hard_vetoes(
        core_snapshot,
        current_price=current_price,
        earnings_days=earnings_days,
        trade=trade,
        tv=tv,
    )

    # Trade Validation Score, non un secondo stock score.
    validation_points = validation["points"] if core_snapshot is not None else 0
    quality_points = 20.0 * quality["score"] / 100.0
    valuation_points = 15.0 * valuation["score"] / 100.0
    if isinstance(earnings_days, int):
        earnings_points = 15.0 if earnings_days > 14 else (8.0 if earnings_days >= 7 else 0.0)
    else:
        earnings_points = 5.0
    market_points = 10.0 * _safe_float(market_context.get("score") or 50.0) / 100.0
    portfolio_points = 10.0 if not portfolio.get("already_owned") else 6.0
    data_quality_points = 10.0 if tv_class == CheckClass.COMPLETE else 5.0
    committee_score = round(
        validation_points + quality_points + valuation_points + earnings_points + market_points + portfolio_points + data_quality_points,
        1,
    )

    classes = [CheckClass(row["class"]) for row in coverage]
    verdict_result = evaluate_verdict(
        committee_score=committee_score,
        check_classes=classes,
        hard_vetoes=hard_vetoes,
        extra_core_penalty=0.0,
    )

    # Manual research without CORE snapshot must never masquerade as an APPROVE.
    verdict = verdict_result.verdict
    decision_reason = verdict_result.reason
    if core_snapshot is None and verdict in {"APPROVE", "APPROVE_WITH_WARNING"}:
        verdict = "WAIT_CORE"
        decision_reason = "CORE snapshot assente: serve la trade authoritative del motore"

    enrichment_total = 2  # sentiment/ownership + optional ownership/13F family
    enrichment_available = 1 if sentiment_class == CheckClass.COMPLETE else 0
    enrichment_coverage = round(100.0 * enrichment_available / enrichment_total, 1)

    return {
        "version": VERSION,
        "policy_version": POLICY_VERSION,
        "run_at": datetime.now(timezone.utc).isoformat(),
        "ticker": symbol,
        "verdict": verdict,
        "decision_reason": decision_reason,
        "committee_score": committee_score,
        "trade_validation_score": committee_score,
        "data_confidence": verdict_result.data_confidence,
        "core_data_confidence": verdict_result.data_confidence,
        "enrichment_coverage": enrichment_coverage,
        "hard_vetoes": [x.value for x in hard_vetoes],
        "hard_reasons": hard_reasons,
        "warning_summary": {
            "core": verdict_result.core_warning_count,
            "soft": verdict_result.soft_warning_count,
            "enrichment_nd": verdict_result.enrichment_nd_count,
            "hard_veto": verdict_result.hard_veto_count,
        },
        "core_snapshot": core_payload,
        "core_snapshot_hash": snapshot_hash(core_snapshot),
        "core_snapshot_authoritative": core_snapshot is not None,
        "price": current_price,
        "market": {k: v for k, v in market.items() if k not in {"ticker_obj", "history"}},
        "fundamentals": f,
        "financial_rigor": fundamentals["rigor"],
        "quality": quality,
        "valuation": valuation,
        "technical_crosscheck": technical,
        "volume_crosscheck": volume,
        "earnings": earnings,
        "sentiment": sentiment,
        "sec": sec,
        "market_context": market_context,
        "portfolio": portfolio,
        "trade_plan": trade,
        "engine_validation": validation,
        "bull_case": bull[:5],
        "bear_case": bear[:6],
        "coverage": coverage,
        "coverage_summary": {
            "complete": sum(1 for x in coverage if x["class"] == CheckClass.COMPLETE.value),
            "core_warning": verdict_result.core_warning_count,
            "soft_warning": verdict_result.soft_warning_count,
            "enrichment_nd": verdict_result.enrichment_nd_count,
            "hard_veto": verdict_result.hard_veto_count,
            # Backward-compatible keys for the current UI.
            "real": sum(1 for x in coverage if x["class"] == CheckClass.COMPLETE.value),
            "partial": verdict_result.core_warning_count + verdict_result.soft_warning_count,
            "missing": verdict_result.enrichment_nd_count,
        },
        "tradingview_crosscheck": tv,
        "guardrail": "RESEARCH ONLY · nessun ordine reale · il Committee valida il CORE e non lo sostituisce",
    }
