# Trading Laboratory Maintenance Policy

## Scope
This policy applies only to `laboratory/` and the `strategy-lab-v1` branch unless a change explicitly states otherwise.

## Direct fixes allowed
The Laboratory may be corrected directly when the change is a verified, low-risk engineering fix that does not intentionally alter the trading hypothesis. Typical examples:

- broken imports, runtime errors, failed workflows or persistence bugs;
- stale or malformed data handling;
- duplicate records or inconsistent timestamps;
- UI regressions, confusing labels or broken dashboard rendering;
- Data Quality checks and anomaly detection;
- corporate-action / split safeguards;
- earnings-date validation and source-quality checks;
- Signal Outcomes persistence and D+1/D+3/D+5/D+10/D+20/D+60 bookkeeping;
- MFE/MAE calculation bugs;
- paper lifecycle bookkeeping;
- scheduler/configuration mismatches;
- tests that expose a reproducible defect.

Whenever practical, a direct fix should include a regression test or an explicit validation step.

## Research changes are not silent fixes
Any change that can materially alter which trades are selected, their ranking, sizing, entry, stop, target, or expected backtest result must be treated as a research change, not disguised as a bug fix.

Examples:

- Strategy Score or Trade Score weights;
- Portfolio Fit logic;
- eligibility gates or thresholds;
- risk budget or position-sizing logic;
- stop/target methodology;
- strategy parameters;
- regime classification logic;
- Cross-Sectional Momentum methodology;
- new strategies or new alpha factors;
- automatic strategy promotion.

Research changes must be versioned, documented, tested against the current baseline and validated out-of-sample / paper where applicable before replacing the baseline.

## Hard boundaries

- Do not modify the Core engine merely to satisfy Laboratory experiments.
- Do not create or send real broker orders from the Laboratory.
- Do not fabricate missing data. Unverified data is `N/D` or explicitly low confidence.
- Do not silently overwrite the current research baseline after seeing favorable backtest results.
- Keep Strategy Score, Trade Score and Portfolio Fit auditable; avoid an opaque optimized mega-score.

## Current maintenance priorities

P0:
- Data Quality and data freshness;
- corporate actions / split anomalies;
- earnings-date reliability;
- Signal Outcomes D1-D60;
- MFE/MAE correctness;
- watchlist lifecycle/history;
- funnel diagnostics and block reasons;
- paper lifecycle correctness;
- risk sizing and max-position configuration;
- GitHub Actions scheduler reliability;
- dashboard consistency.

P1:
- true Cross-Sectional Momentum V2;
- Regime Engine V2;
- Portfolio Risk improvements;
- portfolio-level backtesting;
- automated MFE/MAE diagnostics;
- Strategy Evolution GEN2 with stronger OOS and robustness controls.

P2:
- SEC/IR catalyst engine;
- PEAD point-in-time;
- Quality Value point-in-time;
- Event Driven and Macro Intermarket strategies;
- larger USA universe;
- separate Italy Laboratory architecture.

## Operational principle
The Laboratory should become more measurable before it becomes more complicated. Engineering defects may be fixed immediately. Changes to alpha or decision logic must earn promotion through evidence.