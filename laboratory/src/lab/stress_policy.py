from __future__ import annotations

from dataclasses import dataclass

LIVE_STRESS_POLICY_VERSION = "LIVE_STRESS_POLICY_V1"
TOTAL_MTM_R_MIN = -2.0
WORST_OPEN_R_MIN = -1.25
OPEN_RISK_R_MAX = 3.0
NEAR_STOP_COUNT_MAX = 3
NEAR_STOP_MIN_OPEN = 5


@dataclass(frozen=True)
class StressResult:
    status: str
    reason_codes: tuple[str, ...]
    policy_version: str = LIVE_STRESS_POLICY_VERSION


def evaluate_live_stress(
    *,
    total_mtm_r: float | None,
    worst_open_r: float | None,
    open_risk_r: float | None,
    near_stop_count: int = 0,
    open_count: int = 0,
) -> StressResult:
    reasons: list[str] = []
    if total_mtm_r is not None and float(total_mtm_r) < TOTAL_MTM_R_MIN:
        reasons.append("MTM_BELOW_MINUS_2R")
    if worst_open_r is not None and float(worst_open_r) < WORST_OPEN_R_MIN:
        reasons.append("WORST_OPEN_BELOW_MINUS_1_25R")
    if open_risk_r is not None and float(open_risk_r) > OPEN_RISK_R_MAX:
        reasons.append("OPEN_RISK_ABOVE_3R")
    if int(open_count) >= NEAR_STOP_MIN_OPEN and int(near_stop_count) >= NEAR_STOP_COUNT_MAX:
        reasons.append("MULTIPLE_TRADES_NEAR_STOP")
    if not reasons:
        return StressResult("PASS", ())
    if len(reasons) >= 2 or "OPEN_RISK_ABOVE_3R" in reasons:
        return StressResult("CRITICAL", tuple(reasons))
    return StressResult("STRESSED", tuple(reasons))
