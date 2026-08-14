from dataclasses import dataclass, asdict, field
from typing import Any, Dict, List, Optional

@dataclass
class AnalysisResult:
    market: str
    ticker: str
    company_name: str = ""
    sector: str = ""
    price: Optional[float] = None
    quality_score: Optional[int] = None
    opportunity_score: Optional[int] = None
    score_components: Dict[str, Optional[float]] = field(default_factory=dict)
    data_coverage_pct: Optional[float] = None
    technical_state: str = "N/D"
    rs_state: str = "N/D"
    ideal_entry: Optional[float] = None
    buy_zone_low: Optional[float] = None
    buy_zone_high: Optional[float] = None
    max_buy: Optional[float] = None
    stop: Optional[float] = None
    tp1: Optional[float] = None
    tp2: Optional[float] = None
    gross_rr_tp1: Optional[float] = None
    gross_rr_tp2: Optional[float] = None
    net_rr_tp1: Optional[float] = None
    net_rr_tp2: Optional[float] = None
    gross_rr_current_tp1: Optional[float] = None
    gross_rr_current_tp2: Optional[float] = None
    net_rr_current_tp1: Optional[float] = None
    net_rr_current_tp2: Optional[float] = None
    trigger_state: str = "N/D"
    trigger_reason: str = ""
    shares: int = 0
    invested: Optional[float] = None
    net_risk_total: Optional[float] = None
    risk_pct_trading_capital: Optional[float] = None
    risk_sizing_configured: bool = False
    data_quality: str = "N/D"
    data_anomaly_flags: List[str] = field(default_factory=list)
    data_anomaly_categories: List[str] = field(default_factory=list)
    data_review_required: bool = False
    corporate_action_status: str = "N/D"
    earnings_date: Optional[str] = None
    days_to_earnings: Optional[int] = None
    decision: str = "WATCH"
    operational_state: str = "N/D"
    display_state: str = "WAIT"
    prebuy_score: Optional[int] = None
    prebuy_label: Optional[str] = None
    gate_status: Dict[str, bool] = field(default_factory=dict)
    failed_gates: List[str] = field(default_factory=list)
    veto_reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    change_state: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_candidate(cls, market: str, c: Dict[str, Any]) -> "AnalysisResult":
        known = {f.name for f in cls.__dataclass_fields__.values()}
        payload = {k: c.get(k) for k in known if k not in {"market", "raw"}}
        payload["market"] = market
        payload["ticker"] = str(c.get("ticker") or payload.get("ticker") or "")
        payload["raw"] = c
        return cls(**payload)
