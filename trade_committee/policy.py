from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


POLICY_VERSION = "TC_POLICY_V1"
DATA_CONFIDENCE_MODEL = "PATCH_1_PROVISIONAL_WEIGHTS_V1"
CORE_WARNING_PENALTY = 12.0
SOFT_WARNING_PENALTY = 4.0
MIN_APPROVE_SCORE = 75.0
MIN_WAIT_SCORE = 55.0
MIN_APPROVE_CONFIDENCE = 70.0
MIN_WAIT_CONFIDENCE = 45.0


class CheckClass(str, Enum):
    COMPLETE = "COMPLETE"
    HARD_VETO = "HARD_VETO"
    CORE_WARNING = "CORE_WARNING"
    SOFT_WARNING = "SOFT_WARNING"
    ENRICHMENT_ND = "ENRICHMENT_ND"
    FAILED = "FAILED"


class HardVeto(str, Enum):
    PRICE_DATA_CONFLICT = "price_data_conflict"
    CORPORATE_ACTION = "corporate_action"
    EARNINGS_LT_7D = "earnings_lt_7d"
    TRIGGER_INVALID = "trigger_invalid"
    PRICE_ABOVE_MAX_BUY = "price_above_max_buy"
    RR_NET_LT_MIN = "rr_net_lt_min"
    LIQUIDITY = "liquidity"
    POSITION_SIZE = "position_size"
    CRITICAL_DATA_STALE = "critical_data_stale"
    CORE_HARD_VETO = "core_hard_veto"


@dataclass(frozen=True)
class VerdictResult:
    verdict: str
    reason: str
    data_confidence: float
    core_warning_count: int
    soft_warning_count: int
    enrichment_nd_count: int
    hard_veto_count: int


def data_confidence(check_classes: Iterable[CheckClass], *, extra_core_penalty: float = 0.0) -> float:
    classes = list(check_classes)
    core = sum(1 for x in classes if x == CheckClass.CORE_WARNING)
    soft = sum(1 for x in classes if x == CheckClass.SOFT_WARNING)
    failed = sum(1 for x in classes if x == CheckClass.FAILED)
    confidence = 100.0
    confidence -= core * CORE_WARNING_PENALTY
    confidence -= soft * SOFT_WARNING_PENALTY
    confidence -= failed * 25.0
    confidence -= max(0.0, extra_core_penalty)
    return max(0.0, min(100.0, round(confidence, 1)))


def evaluate_verdict(
    *,
    committee_score: float,
    check_classes: Iterable[CheckClass],
    hard_vetoes: Iterable[HardVeto],
    extra_core_penalty: float = 0.0,
) -> VerdictResult:
    classes = list(check_classes)
    vetoes = list(hard_vetoes)
    confidence = data_confidence(classes, extra_core_penalty=extra_core_penalty)
    core = sum(1 for x in classes if x == CheckClass.CORE_WARNING)
    soft = sum(1 for x in classes if x == CheckClass.SOFT_WARNING)
    enrichment = sum(1 for x in classes if x == CheckClass.ENRICHMENT_ND)

    if vetoes:
        verdict = "REJECT_HARD_VETO"
        reason = "Uno o più hard veto impediscono l'approvazione"
    elif committee_score >= MIN_APPROVE_SCORE and confidence >= MIN_APPROVE_CONFIDENCE:
        verdict = "APPROVE" if not (core or soft) else "APPROVE_WITH_WARNING"
        reason = "La trade supera i controlli core senza hard veto"
    elif committee_score >= MIN_WAIT_SCORE:
        verdict = "WAIT_DATA" if core else "WAIT_CORE"
        reason = "La trade non è bocciata, ma servono dati o condizioni migliori"
    else:
        verdict = "REJECT_COMMITTEE"
        reason = "Il profilo complessivo non supera la soglia minima del Committee"

    return VerdictResult(
        verdict=verdict,
        reason=reason,
        data_confidence=confidence,
        core_warning_count=core,
        soft_warning_count=soft,
        enrichment_nd_count=enrichment,
        hard_veto_count=len(vetoes),
    )
