from __future__ import annotations

from typing import Any, Sequence


def _cluster_field(cluster: Any, name: str, default: Any = None) -> Any:
    if isinstance(cluster, dict):
        return cluster.get(name, default)
    return getattr(cluster, name, default)


def _cluster_containing(symbol: str, clusters: Sequence[Any]) -> Any | None:
    upper = symbol.upper()
    for cluster in clusters:
        members = _cluster_field(cluster, "members")
        if members and upper in {str(m).upper() for m in members}:
            return cluster
    return None


def _tier_check(name: str, failures: list[str], *, research_only: bool = False) -> dict[str, Any]:
    return {
        "tier": name,
        "eligible": not failures,
        "failed": failures,
        "research_only": research_only,
        "operational": False if research_only else None,
    }


def classify_paper_tier(
    *,
    strategy_score: float,
    trade_score: float,
    trigger: str,
    data_quality: dict[str, Any],
    rr_net: float | None,
    price: float,
    max_buy: float,
    atr: float,
    earnings_days: int | None,
    qty: int,
) -> dict[str, Any]:
    """Research-only paper admission policy.

    Production rules are intentionally NOT reused here. The Laboratory needs a
    larger forward sample, so A/B/C are three explicit experiments rather than
    one silently loosened threshold.

    Data policy:
    - RED: hard veto for every tier.
    - YELLOW: admissible only for B/C and always flagged.
    - GREEN: may enter A/B/C according to policy conditions.

    Tier C is counterfactual research only and must never be interpreted as an
    operational BUY recommendation.
    """
    data_status = str(data_quality.get("status") or "UNKNOWN").upper()
    data_failed: list[str] = []
    policy_hard_failed: list[str] = []
    warnings: list[str] = []

    if data_status == "RED":
        data_failed.append("DATA_QUALITY_RED")
    elif data_status == "YELLOW":
        warnings.append("DATA_QUALITY_YELLOW")

    if qty <= 0:
        policy_hard_failed.append("QTY_INVALID")
    if atr <= 0:
        policy_hard_failed.append("ATR_INVALID")
    if rr_net is None:
        policy_hard_failed.append("RR_UNAVAILABLE")
    if earnings_days is not None and earnings_days < 3:
        policy_hard_failed.append("EARNINGS_LT_3D")

    trigger_ok = str(trigger).upper() == "CONFIRMED"
    extension_atr = max(0.0, (price - max_buy) / atr) if atr > 0 else 99.0
    rr = float(rr_net or 0.0)

    tier_a_failed: list[str] = []
    if data_status != "GREEN":
        tier_a_failed.append("DATA_NOT_GREEN_FOR_TIER_A")
    if strategy_score < 75:
        tier_a_failed.append("STRATEGY_SCORE_LT_75")
    if trade_score < 70:
        tier_a_failed.append("TRADE_SCORE_LT_70")
    if not trigger_ok:
        tier_a_failed.append("TRIGGER_NOT_CONFIRMED")
    if rr < 1.75:
        tier_a_failed.append("RR_LT_1_75")
    if extension_atr > 0.0:
        tier_a_failed.append("PRICE_ABOVE_MAX_BUY")
    if earnings_days is not None and earnings_days < 7:
        tier_a_failed.append("EARNINGS_LT_7D")

    tier_b_failed: list[str] = []
    if strategy_score < 65:
        tier_b_failed.append("STRATEGY_SCORE_LT_65")
    if trade_score < 55:
        tier_b_failed.append("TRADE_SCORE_LT_55")
    if not trigger_ok:
        tier_b_failed.append("TRIGGER_NOT_CONFIRMED")
    if rr < 1.15:
        tier_b_failed.append("RR_LT_1_15")
    if extension_atr > 0.50:
        tier_b_failed.append("EXTENSION_GT_0_5_ATR")
    if earnings_days is not None and earnings_days < 5:
        tier_b_failed.append("EARNINGS_LT_5D")

    tier_c_failed: list[str] = []
    if strategy_score < 55:
        tier_c_failed.append("STRATEGY_SCORE_LT_55")
    if trade_score < 40:
        tier_c_failed.append("TRADE_SCORE_LT_40")
    if rr < 0.75:
        tier_c_failed.append("RR_LT_0_75")
    if extension_atr > 1.00:
        tier_c_failed.append("EXTENSION_GT_1_ATR")

    common_failed = data_failed + policy_hard_failed
    checks = {
        "A": _tier_check("A", list(dict.fromkeys(common_failed + tier_a_failed))),
        "B": _tier_check("B", list(dict.fromkeys(common_failed + tier_b_failed))),
        "C": _tier_check("C", list(dict.fromkeys(common_failed + tier_c_failed)), research_only=True),
    }

    selected: str | None = None
    for tier in ("A", "B", "C"):
        if checks[tier]["eligible"]:
            selected = tier
            break

    if selected == "A":
        safety_label = "PAPER_A_QUASI_PRODUCTION"
        softened: list[str] = []
    elif selected == "B":
        safety_label = "PAPER_B_EXPERIMENTAL"
        softened = ["LOWER_SCORE_OR_RR_THAN_TIER_A", "EXTENSION_UP_TO_0_5_ATR"]
        if data_status == "YELLOW":
            softened.append("DATA_QUALITY_YELLOW")
    elif selected == "C":
        safety_label = "RESEARCH_ONLY_NON_OPERATIONAL"
        softened = ["TRIGGER_MAY_BE_WAITING", "RR_MIN_0_75", "EXTENSION_UP_TO_1_ATR"]
        if data_status == "YELLOW":
            softened.append("DATA_QUALITY_YELLOW")
    else:
        safety_label = "REJECTED_BY_PAPER_POLICY"
        softened = []

    selected_failed = checks[selected]["failed"] if selected else list(dict.fromkeys(common_failed + tier_c_failed))

    return {
        "eligible": selected is not None,
        "tier": selected,
        "safety_label": safety_label,
        "research_only": selected == "C",
        "operational": False if selected == "C" else None,
        "data_quality_status": data_status,
        "data_gate_failures": data_failed,
        "policy_hard_failures": policy_hard_failed,
        "hard_failed": selected_failed,
        "softened": softened,
        "warnings": warnings,
        "extension_atr": round(extension_atr, 3),
        "tier_checks": checks,
        "model": "LAB_PAPER_TIERS_V2_1",
    }


def lab_portfolio_fit(
    *,
    symbol: str,
    strategy: str,
    open_positions: list[dict[str, Any]],
    opened_this_run: int,
    max_new_buys: int = 12,
    max_active_positions: int = 80,
    max_active_per_strategy: int = 24,
    correlation_clusters: Sequence[Any] | None = None,
    correlated_exposure_warn_at: int = 3,
) -> dict[str, Any]:
    """Portfolio guardrail for research paper trading.

    The same ticker may be held by different strategies because comparing those
    independent virtual trades is the point of the Laboratory. The shared
    underlying is retained through risk_key in signal/position details.

    correlation_clusters (from lab.correlation.correlation_clusters) is the
    Portfolio Risk Engine referenced above: when provided, correlated exposure
    across DIFFERENT symbols in the same strongly-correlated cluster is
    surfaced under "correlated_exposure" for dashboards/research. This is
    informational only and never blocks eligibility, so it does not shrink the
    Laboratory's learning sample.
    """
    failed: list[str] = []
    active = [
        p for p in open_positions
        if str(p.get("status") or "").upper() in {"OPEN", "TP1_HIT"}
    ]
    same_experiment = [
        p for p in active
        if str(p.get("symbol") or "").upper() == symbol.upper()
        and str(p.get("strategy") or "") == strategy
    ]
    strategy_active = [p for p in active if str(p.get("strategy") or "") == strategy]

    if same_experiment:
        failed.append("DUPLICATE_SYMBOL_STRATEGY")
    if len(active) >= max_active_positions:
        failed.append("MAX_ACTIVE_LAB_POSITIONS")
    if len(strategy_active) >= max_active_per_strategy:
        failed.append("MAX_ACTIVE_PER_STRATEGY")
    if opened_this_run >= max_new_buys:
        failed.append("MAX_NEW_LAB_BUYS_THIS_RUN")

    correlated_exposure: dict[str, Any] | None = None
    warnings: list[str] = []
    if correlation_clusters:
        cluster = _cluster_containing(symbol, correlation_clusters)
        if cluster is not None:
            members = {str(m).upper() for m in _cluster_field(cluster, "members", [])}
            correlated_positions = [p for p in active if str(p.get("symbol") or "").upper() in members]
            other_symbols = sorted({str(p.get("symbol") or "").upper() for p in correlated_positions} - {symbol.upper()})
            correlated_exposure = {
                "cluster_members": sorted(members),
                "cluster_avg_abs_correlation": round(float(_cluster_field(cluster, "average_abs_correlation", 0.0)), 3),
                "already_held_in_cluster": other_symbols,
                "already_held_count": len(other_symbols),
            }
            if len(other_symbols) >= correlated_exposure_warn_at:
                warnings.append("CORRELATED_CLUSTER_EXPOSURE")

    return {
        "eligible": not failed,
        "failed": failed,
        "warnings": warnings,
        "active_total": len(active),
        "active_strategy": len(strategy_active),
        "correlated_exposure": correlated_exposure,
        "model": "LAB_PORTFOLIO_V2_RESEARCH" if correlation_clusters is None else "LAB_PORTFOLIO_V2_1_WITH_CORRELATION",
    }
