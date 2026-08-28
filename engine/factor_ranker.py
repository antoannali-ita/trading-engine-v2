from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping

import pandas as pd
import yfinance as yf


FACTOR_RANKER_VERSION = "FACTOR_RANKER_V1"


def _safe_float(value: Any) -> float | None:
    try:
        if value is None or pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _linear(value: float | None, bad: float, good: float) -> float | None:
    if value is None:
        return None
    if good == bad:
        return 50.0
    return _clamp((value - bad) / (good - bad) * 100.0)


def _positive_cash(value: Any) -> float | None:
    v = _safe_float(value)
    if v is None:
        return None
    return 100.0 if v > 0 else 0.0


def _mean(values: Iterable[float | None]) -> float | None:
    valid = [float(v) for v in values if v is not None]
    return None if not valid else sum(valid) / len(valid)


def _eps_row(df: Any) -> Mapping[str, Any] | None:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return None
    for label in ("0y", "+1y", "0q", "+1q"):
        if label in df.index:
            row = df.loc[label]
            return row.to_dict() if hasattr(row, "to_dict") else None
    row = df.iloc[0]
    return row.to_dict() if hasattr(row, "to_dict") else None


def _revision_pct(current: Any, previous: Any) -> float | None:
    cur = _safe_float(current)
    prev = _safe_float(previous)
    if cur is None or prev in (None, 0):
        return None
    return (cur / prev - 1.0) * 100.0


def _query_symbol(ticker: str, cfg: Mapping[str, Any]) -> str:
    symbol = str(ticker or "").strip().upper()
    suffix = str(cfg.get("yfinance_suffix") or "").strip().upper()
    if suffix and symbol and "." not in symbol:
        symbol += suffix
    return symbol


def fetch_earnings_revisions(ticker: str, cfg: Mapping[str, Any]) -> Dict[str, Any]:
    """Best-effort Yahoo estimate momentum. Missing data remains N/D and never vetoes."""
    symbol = _query_symbol(ticker, cfg)
    result: Dict[str, Any] = {
        "eps_revision_30d_pct": None,
        "eps_revision_60d_pct": None,
        "eps_up_30d": None,
        "eps_down_30d": None,
        "earnings_revision_source": "Yahoo Finance",
        "earnings_revision_status": "N/D",
    }
    if not symbol:
        return result

    try:
        stock = yf.Ticker(symbol)
        trend = getattr(stock, "eps_trend", None)
        row = _eps_row(trend)
        if row:
            current = row.get("current")
            result["eps_revision_30d_pct"] = _revision_pct(current, row.get("30daysAgo"))
            result["eps_revision_60d_pct"] = _revision_pct(current, row.get("60daysAgo"))

        revisions = getattr(stock, "eps_revisions", None)
        rev_row = _eps_row(revisions)
        if rev_row:
            result["eps_up_30d"] = _safe_float(rev_row.get("upLast30days"))
            result["eps_down_30d"] = _safe_float(rev_row.get("downLast30days"))

        if any(result[k] is not None for k in ("eps_revision_30d_pct", "eps_revision_60d_pct", "eps_up_30d", "eps_down_30d")):
            result["earnings_revision_status"] = "REAL"
    except Exception as exc:
        result["earnings_revision_status"] = "N/D"
        result["earnings_revision_note"] = f"{type(exc).__name__}: {exc}"
    return result


def factor_components(candidate: Mapping[str, Any]) -> Dict[str, float | None]:
    price = _safe_float(candidate.get("price"))
    ma50 = _safe_float(candidate.get("ma50"))
    ma200 = _safe_float(candidate.get("ma200"))
    trend = None
    if price is not None and ma50 is not None and ma200 is not None:
        trend = 100.0 if price > ma50 > ma200 else 55.0 if price >= ma200 else 0.0

    momentum = _mean([
        _linear(_safe_float(candidate.get("rs_3m")), -10.0, 15.0),
        _linear(_safe_float(candidate.get("rs_6m")), -15.0, 25.0),
        _linear(_safe_float(candidate.get("perf3m")), -10.0, 25.0),
        _linear(_safe_float(candidate.get("perf6m")), -15.0, 45.0),
        trend,
    ])

    quality_score = _safe_float(candidate.get("quality_score"))
    quality = _mean([
        quality_score,
        _linear(_safe_float(candidate.get("roic")), 0.0, 20.0),
        _linear(_safe_float(candidate.get("roe")), 0.0, 25.0),
        _positive_cash(candidate.get("free_cashflow")),
        _positive_cash(candidate.get("operating_cashflow")),
    ])

    growth = _mean([
        _linear(_safe_float(candidate.get("revenue_growth")), -5.0, 20.0),
        _linear(_safe_float(candidate.get("eps_growth")), -10.0, 25.0),
        _linear(_safe_float(candidate.get("fcf_growth")), -15.0, 30.0),
    ])

    up = _safe_float(candidate.get("eps_up_30d"))
    down = _safe_float(candidate.get("eps_down_30d"))
    breadth = None
    if up is not None or down is not None:
        up = up or 0.0
        down = down or 0.0
        total = up + down
        breadth = 50.0 if total <= 0 else _clamp(up / total * 100.0)

    revisions = _mean([
        _linear(_safe_float(candidate.get("eps_revision_30d_pct")), -5.0, 8.0),
        _linear(_safe_float(candidate.get("eps_revision_60d_pct")), -8.0, 12.0),
        breadth,
    ])

    return {
        "momentum_rs": momentum,
        "quality_profitability": quality,
        "growth": growth,
        "earnings_revisions": revisions,
    }


def score_candidate(candidate: Mapping[str, Any]) -> Dict[str, Any]:
    components = factor_components(candidate)
    weights = {
        "momentum_rs": 35.0,
        "quality_profitability": 30.0,
        "growth": 15.0,
        "earnings_revisions": 20.0,
    }
    available = {k: v for k, v in components.items() if v is not None}
    available_weight = sum(weights[k] for k in available)
    if not available_weight:
        score = 0.0
    else:
        score = sum(available[k] * weights[k] for k in available) / available_weight

    coverage = available_weight / sum(weights.values()) * 100.0
    return {
        "factor_ranker_version": FACTOR_RANKER_VERSION,
        "factor_score": round(_clamp(score), 1),
        "factor_coverage_pct": round(coverage, 1),
        "factor_components": {k: None if v is None else round(v, 1) for k, v in components.items()},
    }


def rank_candidates(candidates: List[Dict[str, Any]], cfg: Mapping[str, Any]) -> Dict[str, Any]:
    """Rank candidates before final CORE selection without changing CORE trade decisions.

    The ranker narrows only the research pool. BUY/WAIT/AVOID, entry, stop, targets,
    R/R and sizing remain authoritative outputs of the existing CORE reference engine.
    """
    enabled = bool(cfg.get("factor_ranker_enabled", False))
    if not enabled:
        return {
            "enabled": False,
            "candidates": candidates,
            "selection_pool": candidates,
            "pool_size": len(candidates),
            "revision_enriched": 0,
        }

    pool_size = max(10, int(cfg.get("factor_ranker_pool_size", 40)))
    revision_top_n = max(0, int(cfg.get("factor_ranker_revision_top_n", 20)))
    revisions_enabled = bool(cfg.get("factor_ranker_revisions_enabled", True))

    for candidate in candidates:
        candidate.update(score_candidate(candidate))

    eligible = [c for c in candidates if c.get("passes_survival")]
    eligible.sort(
        key=lambda c: (c.get("factor_score") or 0.0, c.get("factor_coverage_pct") or 0.0, c.get("opportunity_score") or c.get("score") or 0.0),
        reverse=True,
    )

    revision_enriched = 0
    if revisions_enabled and revision_top_n:
        for candidate in eligible[:revision_top_n]:
            candidate.update(fetch_earnings_revisions(str(candidate.get("ticker") or ""), cfg))
            candidate.update(score_candidate(candidate))
            revision_enriched += 1

        eligible.sort(
            key=lambda c: (c.get("factor_score") or 0.0, c.get("factor_coverage_pct") or 0.0, c.get("opportunity_score") or c.get("score") or 0.0),
            reverse=True,
        )

    selected_ids = {id(c) for c in eligible[:pool_size]}
    rank = 0
    for candidate in eligible:
        rank += 1
        candidate["factor_rank"] = rank
        candidate["factor_pool_selected"] = id(candidate) in selected_ids

    selection_pool = eligible[:pool_size]
    return {
        "enabled": True,
        "version": FACTOR_RANKER_VERSION,
        "candidates": candidates,
        "selection_pool": selection_pool,
        "pool_size": len(selection_pool),
        "eligible_count": len(eligible),
        "revision_enriched": revision_enriched,
    }
