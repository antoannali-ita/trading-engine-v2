# Strategy Laboratory v1

Research-only environment, strictly separated from CORE production logic.

## Mission
Test, falsify and compare systematic strategies with point-in-time data, walk-forward validation, paper trading and reproducible experiments. LAB never places real orders and never silently changes CORE parameters.

## Alpha families v1
1. Trend Continuation — pullback, breakout and volatility-compression entry modes.
2. Cross-Sectional Momentum / Sector Rotation.
3. Short-Term / Extreme Reversal.
4. PEAD / Fundamental Revision Momentum.
5. Event-Driven Mean Reversion — including earnings/gap fade experiments.
6. Quality + Value Rerating.
7. Defensive Low-Vol Quality.
8. Macro / Intermarket — ETF and rate/commodity-sensitive sectors.

## Transversal layers
- Point-in-time Data Layer
- Market Regime Engine: bull/bear/sideways + volatility state
- Hard Gates
- Risk Management
- Opportunity Ladder 0-100 (output, never source alpha)
- Paper Portfolio
- A/B evaluation: Quant vs Quant+TradingAgents plus deterministic/random controls
- Backtest, walk-forward, OOS, block bootstrap and Monte Carlo
- Calibration with versioning and rollback
- Dashboard

## Phase 2
Microstructure Lab: AMT / Orderflow / Volume Profile / VAH / VAL / POC / LVN-HVN / CVD / failed auction. Kept separate because data, timeframe, execution model and costs are materially different.

## Guardrails
- No live order execution.
- No modification of frozen CORE baseline strategies from LAB.
- No promotion based only on in-sample performance.
- Fundamentals/events must be point-in-time.
- Include delisted names where datasets permit.
- Costs/slippage are mandatory in performance estimates.
- Prefer global robust parameters; sector coefficients require repeated OOS evidence.
- A calibration run may recommend NO CHANGE.

## Repository layout
- `config/` strategy/regime configuration
- `src/lab/` research engine
- `src/lab/strategies/` independent alpha modules
- `src/lab/data/` point-in-time adapters and schemas
- `src/lab/backtest/` event-driven simulation and validation
- `src/lab/agents/` TradingAgents experiment boundary
- `src/lab/paper/` paper portfolio
- `dashboard/` private web dashboard
- `tests/lab/` unit/integration tests
- `docs/lab/` methodology and promotion rules

Status: architecture bootstrap. CORE remains untouched on this branch.