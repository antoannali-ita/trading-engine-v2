from __future__ import annotations

from typing import Any


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
    larger forward sample, so only true data/execution problems are hard vetoes.
    A/B/C preserve the quality of the setup at entry instead of silently
    loosening one global threshold.
    """
    hard_failed: list[str] = []
    softened: list[str] = []

    if data_quality.get("status") == "RED":
        hard_failed.append("DATA_QUALITY_RED")
    if qty <= 0:
        hard_failed.append("QTY_INVALID")
    if atr <= 0:
        hard_failed.append("ATR_INVALID")
    if rr_net is None:
        hard_failed.append("RR_UNAVAILABLE")
    if earnings_days is not None and earnings_days < 3:
        hard_failed.append("EARNINGS_LT_3D")

    if hard_failed:
        return {
            "eligible": False,
            "tier": None,
            "hard_failed": hard_failed,
            "softened": softened,
            "model": "LAB_PAPER_TIERS_V2",
        }

    trigger_ok = str(trigger).upper() == "CONFIRMED"
    extension_atr = max(0.0, (price - max_buy) / atr) if atr > 0 else 99.0
    rr = float(rr_net or 0.0)

    # A: near-production quality baseline.
    if (
        strategy_score >= 75
        and trade_score >= 70
        and trigger_ok
        and rr >= 1.75
        and extension_atr <= 0.0
        and (earnings_days is None or earnings_days >= 7)
    ):
        return {
            "eligible": True,
            "tier": "A",
            "hard_failed": [],
            "softened": [],
            "extension_atr": round(extension_atr, 3),
            "model": "LAB_PAPER_TIERS_V2",
        }

    # B: qualified experiment. Keeps the trigger, accepts lower R/R and modest
    # extension so we can measure whether the production gates are too strict.
    if (
        strategy_score >= 65
        and trade_score >= 55
        and trigger_ok
        and rr >= 1.15
        and extension_atr <= 0.50
        and (earnings_days is None or earnings_days >= 5)
    ):
        softened.extend(["LOWER_SCORE_OR_RR_THAN_TIER_A", "EXTENSION_UP_TO_0_5_ATR"])
        return {
            "eligible": True,
            "tier": "B",
            "hard_failed": [],
            "softened": softened,
            "extension_atr": round(extension_atr, 3),
            "model": "LAB_PAPER_TIERS_V2",
        }

    # C: exploratory forward test. Trigger may still be WAITING. This is not a
    # broker recommendation; it exists to learn whether early entries add value.
    if (
        strategy_score >= 55
        and trade_score >= 40
        and rr >= 0.75
        and extension_atr <= 1.00
    ):
        softened.extend(["TRIGGER_MAY_BE_WAITING", "RR_MIN_0_75", "EXTENSION_UP_TO_1_ATR"])
        return {
            "eligible": True,
            "tier": "C",
            "hard_failed": [],
            "softened": softened,
            "extension_atr": round(extension_atr, 3),
            "model": "LAB_PAPER_TIERS_V2",
        }

    failed: list[str] = []
    if strategy_score < 55:
        failed.append("STRATEGY_SCORE_LT_55")
    if trade_score < 40:
        failed.append("TRADE_SCORE_LT_40")
    if rr < 0.75:
        failed.append("RR_LT_0_75")
    if extension_atr > 1.00:
        failed.append("EXTENSION_GT_1_ATR")
    if not failed:
        failed.append("NO_TIER_MATCH")

    return {
        "eligible": False,
        "tier": None,
        "hard_failed": failed,
        "softened": softened,
        "extension_atr": round(extension_atr, 3),
        "model": "LAB_PAPER_TIERS_V2",
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
) -> dict[str, Any]:
    """Portfolio guardrail for research paper trading.

    The same ticker may be held by different strategies because comparing those
    independent virtual trades is the point of the Laboratory. Only an existing
    position for the same ticker+strategy is considered a duplicate.
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

    return {
        "eligible": not failed,
        "failed": failed,
        "active_total": len(active),
        "active_strategy": len(strategy_active),
        "model": "LAB_PORTFOLIO_V2_RESEARCH",
    }
