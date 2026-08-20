# Strategy Lab v1 - Strategy Design

## Objective
The laboratory tests operations, not narratives. Every strategy must define: information set, signal, hard gates, entry timing, holding period, risk model, costs, validation method and invalidation conditions.

## Common anti-overfitting rules
- No future data, revised fundamentals or hindsight event labels.
- All fundamentals/events must be point-in-time.
- Price indicators use only information available at the signal close; simulated entry is the next session open.
- Commission and slippage are mandatory.
- If stop and target are both touched in the same daily bar, assume stop first.
- Calibration is train-only; untouched test/OOS results decide whether a parameter survives.
- Prefer broad stable parameter plateaus over a single optimum.
- Minimum sample requirements increase before any promotion to CORE.
- A calibration run may recommend NO CHANGE.
- LAB remains paper/research only; it never routes live orders.

## Strategies

### 1 Trend Continuation
Information: daily OHLCV.
Logic: Price > SMA50 > SMA200, pullback distance to SMA50 in ATR units, 60d momentum, relative volume and 20d breakout confirmation.
Default hold: 20 sessions.
Primary failure modes: late-cycle breakouts, gap risk, crowded momentum.

### 2 Cross-Sectional Momentum
Information: daily adjusted prices across a universe.
Logic: weighted 20/60/120-day momentum ranks. The production calibration must rank across the same contemporaneous universe, not only within one ticker history.
Default hold: 40 sessions.
Primary failure modes: momentum crashes and regime reversals.

### 3 Short-Term Reversal
Information: daily OHLCV.
Logic: RSI oversold, price stretch below SMA20 in ATR units, long-term trend gate and first stabilization day.
Default hold: 10 sessions.
Primary failure modes: catching structural breakdowns and earnings gaps.

### 4 PEAD
Information: PIT earnings release, revenue/EPS surprise, analyst revisions and event timestamp.
Logic: positive standardized surprise + positive revision momentum + early post-event confirmation, only in the first post-event window.
Default hold: 20 sessions.
Status until PIT source is connected: DATA_REQUIRED.

### 5 Event-Driven Mean Reversion
Information: PIT event timestamp, shock return, abnormal volume and binary-event flag.
Logic: extreme non-binary negative shock + abnormal volume + stabilization. Binary legal/FDA/M&A outcomes are excluded by hard gate.
Default hold: 10 sessions.
Status until PIT source is connected: DATA_REQUIRED.

### 6 Quality + Value Rerating
Information: PIT statements and contemporaneous valuation/sector data.
Logic: FCF yield, ROIC, revenue/EPS growth, leverage and sector-relative valuation discount.
Default hold: 60 sessions.
Status until PIT source is connected: DATA_REQUIRED.

### 7 Defensive Low-Vol Quality
Information v1: daily OHLCV. Quality overlay requires PIT fundamentals later.
Logic v1: low realized volatility, low ATR%, positive long trend and positive medium momentum.
Default hold: 60 sessions.

### 8 Macro / Intermarket
Information: PIT rates, curve, credit, commodities, USD and ex-ante asset sensitivities.
Logic: combine macro impulses only when historical sensitivity fit is adequate, with trend confirmation.
Default hold: 40 sessions.
Status until macro PIT adapters are connected: DATA_REQUIRED.

## Backtest defaults
- Entry: next session open after signal.
- Risk budget: 0.5% of research equity per trade.
- Position cap: 8% of research equity.
- Stop: 2 ATR.
- Target: 2.5R.
- Commission: 12 USD per side in the default Fineco-like research profile.
- Slippage: 5 bps per side.

These are starting hypotheses, not optimized truths.

## Calibration
Initial grid:
- score gate: 70 / 75 / 80
- ATR stop: 1.5 / 2.0 / 2.5
- target R: 2.0 / 2.5 / 3.0

Selection occurs on train only. The selected point is then evaluated on OOS. Promotion requires adequate sample size, positive net expectancy after costs, controlled drawdown/MAE and robustness across nearby parameter values, periods and sectors. A single high-return backtest is never sufficient.
