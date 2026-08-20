from __future__ import annotations

from .models import Decision


def clamp_score(value: float) -> float:
    return max(0.0, min(100.0, float(value)))


def ladder_decision(score: float, gates_passed: bool = True) -> Decision:
    """Map a validated score to a human decision bucket.

    The ladder is an output layer. It must never manufacture alpha.
    A failed hard gate always rejects the candidate regardless of score.
    """
    if not gates_passed:
        return Decision.REJECT

    score = clamp_score(score)
    if score < 40:
        return Decision.REJECT
    if score < 55:
        return Decision.WATCH
    if score < 65:
        return Decision.INTERESTING
    if score < 75:
        return Decision.PRE_BUY
    if score < 85:
        return Decision.BUY_CANDIDATE
    return Decision.HIGH_CONVICTION


def weighted_score(components: dict[str, float], weights: dict[str, float]) -> float:
    """Simple deterministic scorer; calibration must occur outside this function."""
    active = {k: weights[k] for k in components if k in weights and weights[k] > 0}
    if not active:
        return 0.0
    denominator = sum(active.values())
    return clamp_score(sum(clamp_score(components[k]) * w for k, w in active.items()) / denominator)
