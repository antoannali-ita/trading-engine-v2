from __future__ import annotations

# Trading policy used by the dashboard/research layer.
# Capital base is intentionally currency-neutral because the Fineco account can mix EUR/USD exposure.
CAPITAL_TOTAL_BASE = 35_000.0
MAX_POSITION_USD = 5_000.0
USA_COMMISSION_USD = 12.0
MAX_NEW_BUYS = 2
PREFERRED_ORDER_TYPE = "LIMIT"
