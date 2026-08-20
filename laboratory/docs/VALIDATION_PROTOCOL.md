# Validation & Promotion Protocol

## Objective
A strategy is promoted by robust out-of-sample evidence, not by the best historical chart.

## Required experiment record
Every run stores: experiment_id, git commit, dataset/version, point-in-time cutoff, universe, strategy version, parameters, sector, regime definition, costs/slippage model, train/validation/test windows and metrics.

## Validation pipeline
1. Sanity/unit tests and deterministic reproduction.
2. In-sample research with intentionally small parameter space (target: <= 3-5 economically independent parameters per family).
3. Validation window for model selection.
4. Untouched out-of-sample window.
5. Rolling walk-forward across multiple market regimes.
6. Block bootstrap confidence intervals and Monte Carlo trade-order drawdown analysis.
7. Parameter sensitivity: prefer plateaus; reject isolated optimum peaks.
8. Compare against SPY, relevant sector benchmark and a simple baseline rule.
9. Paper trading before any proposal to CORE.

## Bias controls
- Point-in-time fundamentals and event timestamps.
- Delisted securities where available.
- Corporate actions/symbol history.
- Earnings after close become usable next session.
- Purge/embargo overlapping labels/holding windows.
- No tuning on final test.

## Mandatory metrics
CAGR, median trade return, expectancy, profit factor, payoff ratio, win rate, Sharpe, Sortino, max drawdown, Calmar, MAE, MFE, holding period, turnover, costs/slippage, alpha/beta, information ratio, tail loss, exposure, correlation with other strategies, stability by year/sector/regime and OOS degradation.

## Calibration
The scheduled calibration job may produce `NO_CHANGE`. A candidate configuration must beat the current version on pre-registered OOS criteria and robustness, not merely headline return. Keep versioning and rollback.

## TradingAgents A/B
Freeze Quant baseline first. TradingAgents may return only `approve`, `neutral`, `veto` plus rationale/risk tags; it cannot invent entries or rewrite Quant history. Compare:
- A: Quant only
- B: Quant + TradingAgents
- C: Quant + random veto at the same veto frequency
- D: Quant + deterministic non-LLM event/news gate
Evaluate by regime, sector and cohort, net of latency/cost. If B adds no stable OOS value, it stays explanatory only.

## CORE boundary
LAB never executes real orders. Promotion to CORE is a separate reviewed change with explicit evidence and rollback plan.