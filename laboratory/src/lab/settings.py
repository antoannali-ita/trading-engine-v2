from __future__ import annotations

# Trading policy used by the dashboard/research layer.
# Capital base is intentionally currency-neutral because the Fineco account can mix EUR/USD exposure.
CAPITAL_TOTAL_BASE = 35_000.0
MAX_POSITION_USD = 5_000.0
USA_COMMISSION_USD = 12.0
MAX_NEW_BUYS = 2
PREFERRED_ORDER_TYPE = "LIMIT"

# Risk-first sizing. MAX_POSITION_USD is a ceiling, not a target size.
RISK_PER_TRADE_PCT = 0.75
MAX_RISK_PER_TRADE_PCT = 1.00

# Research-only execution model. Slippage is an estimate, not a historical bid/ask observation.
ESTIMATED_SLIPPAGE_BPS = 5.0
MIN_NET_RR = 2.0

# Event-risk policy for non event-driven strategies.
EARNINGS_BLOCK_DAYS = 7
EARNINGS_CAUTION_DAYS = 14

# Paper portfolio V1 deliberately uses deterministic constraints; correlation/factor gates come later.
MAX_ACTIVE_PAPER_POSITIONS = 8
