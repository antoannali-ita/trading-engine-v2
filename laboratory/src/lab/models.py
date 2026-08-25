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


class Side(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"


class FillType(str, Enum):
    ENTRY = "ENTRY"
    TP1 = "TP1"
    TP2 = "TP2"
    STOP = "STOP"
    MANUAL_EXIT = "MANUAL_EXIT"


@dataclass(frozen=True)
class ExecutionContract:
    """Laboratory forward-test source of truth.

    fill_price is the performance/risk anchor. ideal_entry is diagnostic only.
    stop_initial defines initial R; stop_current defines remaining capital risk or
    locked profit. The contract is deliberately independent from Production/Core.
    """

    side: Side
    ideal_entry: float
    fill_price: float
    qty_initial: int
    stop_initial: float
    stop_current: float
    atr14_at_entry: float | None
    strategy: str
    strategy_version: str
    tier: str | None
    policy_version: str | None
    opened_at: datetime


@dataclass(frozen=True)
class PaperFill:
    position_id: int
    strategy: str
    strategy_version: str
    symbol: str
    side: Side
    fill_type: FillType
    qty: int
    price: float
    commission: float = 0.0
    slippage_bps: float | None = None
    executed_at: datetime | None = None
    details: dict[str, Any] = field(default_factory=dict)


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
