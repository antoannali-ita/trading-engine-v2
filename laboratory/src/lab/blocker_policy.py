from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable

BLOCKER_POLICY_VERSION = "BLOCKER_PRIORITY_V1"
BLOCKER_LOOKBACK_SESSIONS = 20
MIN_REJECTED_SAMPLE = 20

CATEGORY_ORDER = (
    "DATA",
    "STRUCTURE",
    "EVENT",
    "PRICE",
    "TRIGGER",
    "RISK_REWARD",
    "PORTFOLIO",
    "OTHER",
)

_CODE_CATEGORY = {
    "DATA_QUALITY_RED": "DATA",
    "DATA_REJECT": "DATA",
    "ATR_INVALID": "DATA",
    "STRATEGY_SCORE_LT_75": "STRUCTURE",
    "STRATEGY_SCORE_LT_65": "STRUCTURE",
    "TRADE_SCORE_LT_70": "STRUCTURE",
    "TRADE_SCORE_LT_60": "STRUCTURE",
    "EARNINGS_LT_3D": "EVENT",
    "EARNINGS_LT_7D": "EVENT",
    "PRICE_ABOVE_MAX_BUY": "PRICE",
    "EXTENSION_GT_0_5_ATR": "PRICE",
    "TRIGGER_NOT_CONFIRMED": "TRIGGER",
    "RR_LT_MIN": "RISK_REWARD",
    "RR_NET_LT_MIN": "RISK_REWARD",
    "PORTFOLIO_CAPACITY": "PORTFOLIO",
    "PER_STRATEGY_CAPACITY": "PORTFOLIO",
}

_UI_LABELS = {
    "STRATEGY_SCORE_LT_75": "Score below Tier A",
    "STRATEGY_SCORE_LT_65": "Score below Tier B",
    "TRADE_SCORE_LT_70": "Trade score too low",
    "TRADE_SCORE_LT_60": "Trade score too low",
    "TRIGGER_NOT_CONFIRMED": "Trigger not confirmed",
    "PRICE_ABOVE_MAX_BUY": "Price above buy zone",
    "EXTENSION_GT_0_5_ATR": "Too extended",
    "EARNINGS_LT_3D": "Earnings too close",
    "EARNINGS_LT_7D": "Earnings too close",
    "RR_LT_MIN": "Risk/reward below minimum",
    "RR_NET_LT_MIN": "Net risk/reward below minimum",
    "DATA_QUALITY_RED": "Data quality issue",
    "PORTFOLIO_CAPACITY": "Portfolio capacity reached",
    "PER_STRATEGY_CAPACITY": "Strategy capacity reached",
}


@dataclass(frozen=True)
class MainBlocker:
    code: str | None
    label: str
    count: int
    sample: int
    pct: float | None
    reason_code: str | None = None
    policy_version: str = BLOCKER_POLICY_VERSION


def blocker_category(code: str) -> str:
    value = str(code or "").upper()
    if value in _CODE_CATEGORY:
        return _CODE_CATEGORY[value]
    if value.startswith("DATA_") or value.startswith("MISSING_"):
        return "DATA"
    if "EARNINGS" in value or "EVENT" in value:
        return "EVENT"
    if "TRIGGER" in value:
        return "TRIGGER"
    if "MAX_BUY" in value or "EXTENSION" in value or "PRICE" in value:
        return "PRICE"
    if "RR" in value or "RISK_REWARD" in value:
        return "RISK_REWARD"
    if "PORTFOLIO" in value or "CAPACITY" in value:
        return "PORTFOLIO"
    if "SCORE" in value or "TREND" in value or "SETUP" in value:
        return "STRUCTURE"
    return "OTHER"


def primary_blocker(codes: Iterable[str]) -> str | None:
    values = [str(c).upper() for c in codes if c]
    if not values:
        return None
    ranked = sorted(values, key=lambda c: (CATEGORY_ORDER.index(blocker_category(c)), c))
    return ranked[0]


def ui_label(code: str | None) -> str:
    if not code:
        return "N/D"
    return _UI_LABELS.get(str(code).upper(), str(code).replace("_", " ").title())


def main_blocker(primary_codes: Iterable[str], *, min_sample: int = MIN_REJECTED_SAMPLE) -> MainBlocker:
    values = [str(c).upper() for c in primary_codes if c]
    sample = len(values)
    if sample < int(min_sample):
        return MainBlocker(None, "N/D", 0, sample, None, "INSUFFICIENT_BLOCKER_SAMPLE")
    code, count = Counter(values).most_common(1)[0]
    return MainBlocker(code, ui_label(code), count, sample, 100.0 * count / sample)
