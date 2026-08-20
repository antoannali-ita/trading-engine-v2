# Strategy Laboratory v1

Research-only environment, strictly separated from CORE production logic.

## Mission
Test, falsify and compare systematic strategies with point-in-time data, walk-forward validation, paper trading and reproducible experiments. LAB never places real orders and never silently changes CORE parameters.

## Current stack
- PostgreSQL / Supabase for persistent run, signal, outcome, trade and watchlist history.
- Python client in `src/lab/db.py`.
- Persistence helpers in `src/lab/persistence.py`.
- Streamlit dashboard in `dashboard/`.
- Versioned SQL schema in `sql/001_trading_lab_schema.sql`.

## Database tables
- `engine_runs`
- `signals`
- `signal_outcomes`
- `trades`
- `trade_events`
- `watchlist`
- `engine_config`

## Dashboard pages
- Control Room: recent runs and signals.
- Signals: filters, technical/entry data and TradingView links.
- Portfolio: registered trades and active watchlist.
- Laboratory: signal outcome statistics and setup comparison.
- Engine Health: score/status/trigger distributions and data-quality warnings.
- Action Center: candidates only; order preview and TradingView link. No broker execution.

## Local setup
Create `laboratory/.env` locally from `.env.example`:

```text
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_SECRET_KEY=sb_secret_...
```

Never commit `.env` or Streamlit secrets.

From `laboratory/`:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python test_supabase.py
streamlit run dashboard/app.py
```

## CORE integration contract
CORE should write one row to `engine_runs` for every execution and one row to `signals` for every analyzed candidate, not only notified BUY/PRE-BUY signals. Use `src/lab/persistence.py` for inserts/upserts. Keep the write path fail-safe: database failure must not mutate trading logic or silently alter CORE decisions.

## Alpha families v1
1. Trend Continuation: pullback, breakout and volatility-compression entry modes.
2. Cross-Sectional Momentum / Sector Rotation.
3. Short-Term / Extreme Reversal.
4. PEAD / Fundamental Revision Momentum.
5. Event-Driven Mean Reversion, including earnings/gap fade experiments.
6. Quality + Value Rerating.
7. Defensive Low-Vol Quality.
8. Macro / Intermarket, ETF and rate/commodity-sensitive sectors.

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

Status: Supabase persistence layer and Streamlit dashboard bootstrap are present on `strategy-lab-v1`. CORE remains untouched until explicit integration.
