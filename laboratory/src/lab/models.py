from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class Decision(str, Enum):
    REJECT = "REJECT"
    WATCH = "WATCH"
    INTERESTING = "INTERESTING"
    PRE_BUY = "PRE_BUY"
    BUY_CANDIDATE = "BUY_CANDIDATE"
    HIGH_CONVICTION = "HIGH_CONVICTION"


@dataclass(frozen=True)
class MarketRegime:
    trend: str  # bull | bear | sideways | unknown
    volatility: str  # low | normal | high | unknown
    confidence: float
    as_of: datetime


@dataclass(frozen=True)
class AlphaSignal:
    signal_id: str
    symbol: str
    strategy: str
    timestamp: datetime
    raw_score: float
    side: str = "LONG"
    sector: str | None = None
    features: dict[str, Any] = field(default_factory=dict)
    rationale: tuple[str, ...] = ()


@dataclass(frozen=True)
class RiskPlan:
    entry: float
    stop: float
    targets: tuple[float, ...]
    risk_reward: float
    max_position_pct: float


@dataclass(frozen=True)
class ResearchDecision:
    signal: AlphaSignal
    regime: MarketRegime
    opportunity_score: float
    decision: Decision
    risk: RiskPlan | None
    gates_passed: bool
    gate_reasons: tuple[str, ...] = ()
    agent_verdict: str | None = None
