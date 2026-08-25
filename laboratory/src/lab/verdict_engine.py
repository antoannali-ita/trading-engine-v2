from __future__ import annotations

from dataclasses import dataclass

VERDICT_POLICY_VERSION = "VERDICT_POLICY_V1"


@dataclass(frozen=True)
class VerdictResult:
    verdict: str
    maturity: str
    reason_codes: tuple[str, ...]
    policy_version: str = VERDICT_POLICY_VERSION


def maturity_for_closed(closed_count: int) -> str:
    n = int(closed_count)
    if n < 10:
        return "UNDERTESTED"
    if n < 30:
        return "EARLY"
    if n < 50:
        return "DEVELOPING"
    return "EVALUABLE"


def evaluate_verdict(
    *,
    closed_count: int,
    net_pf: float | None,
    expectancy_r: float | None,
    avg_net_return_pct: float | None,
    stress_status: str = "PASS",
    data_issue: bool = False,
) -> VerdictResult:
    maturity = maturity_for_closed(closed_count)
    if data_issue:
        return VerdictResult("DATA_ISSUE", maturity, ("MATERIAL_DATA_ISSUE",))
    if int(closed_count) < 30:
        return VerdictResult("EARLY", maturity, ("INSUFFICIENT_CLOSED_SAMPLE",))

    reasons: list[str] = []
    if stress_status != "PASS":
        reasons.append("LIVE_STRESS_NOT_PASS")
    if net_pf is None:
        reasons.append("PF_ND")
    elif float(net_pf) < 0.95:
        reasons.append("PF_BELOW_0_95")
    elif float(net_pf) < 1.20:
        reasons.append("PF_BELOW_1_20")
    if expectancy_r is None:
        reasons.append("EXPECTANCY_ND")
    elif float(expectancy_r) < 0:
        reasons.append("NEGATIVE_EXPECTANCY_R")
    if avg_net_return_pct is None:
        reasons.append("AVG_RETURN_ND")
    elif float(avg_net_return_pct) < 0:
        reasons.append("NEGATIVE_AVG_NET_RETURN")

    if (
        stress_status == "PASS"
        and net_pf is not None and float(net_pf) >= 1.20
        and expectancy_r is not None and float(expectancy_r) > 0
        and avg_net_return_pct is not None and float(avg_net_return_pct) > 0
    ):
        return VerdictResult("WORKING", maturity, ())

    if (
        (net_pf is not None and float(net_pf) < 0.95)
        or (expectancy_r is not None and float(expectancy_r) < 0)
    ):
        return VerdictResult("WEAK", maturity, tuple(reasons))
    return VerdictResult("WATCH", maturity, tuple(reasons) or ("MIXED_EVIDENCE",))
