# Functional Specification — Trading Engine v2

**Version:** 1.0  
**Baseline:** 26/08/2026  
**Scope:** AS-IS functional behaviour + explicitly separated TO-BE direction.

## 1. Mission

Trading Engine v2 supports tactical stock selection and monitoring for USA and Italy. It is designed to identify actionable opportunities rather than simply rank good companies. The operating horizon is primarily 3–6 months, with separate monitoring of already-relevant candidates.

The system is intentionally split into three concerns:

1. **CORE** — screening, analysis, scoring, decision, entry/risk/reward and sizing.
2. **LABORATORY** — paper validation, strategy evidence, tiering and verdict research without directly teaching the live decision path from its own recent outcomes.
3. **PRODUCTION** — scheduling, execution, persistence, reporting, notifications and operational monitoring.

## 2. Markets

- USA
- Italy

Market-specific configuration selects the reference implementation, benchmark, fees and universe behaviour. Italian GEM/foreign-listing exclusions and financial-sector handling are market-specific concerns and must not silently leak into USA behaviour.

## 3. Master Scan

Master Scan is the broad discovery/analysis cycle. Functionally it:

1. loads market configuration;
2. loads the configured reference/analysis logic;
3. discovers/evaluates the market universe;
4. builds candidates;
5. calculates technical/fundamental/scoring fields;
6. evaluates entry geometry, R/R and sizing;
7. applies decision gates;
8. persists state when enabled;
9. generates the market report;
10. sends configured notifications/reports.

During Phase A parity, automated schedules may be constrained by workflow policy while OLD/NEW equivalence is validated.

## 4. Fast Monitor

Fast Monitor is not intended to repeat the complete market discovery scan. It monitors candidates/state already relevant to the operational process and is the natural place for time-sensitive transitions and alerts.

Operational notification states under validation include:

- BUY_NOW
- BUY_LIMIT / LIMIT_READY
- PRE-BUY / APPROACHING
- trigger confirmation
- TP1
- TP2
- SELL / exit events

Notification policy must prevent repeated noise from unchanged states and must remain consistent with the engine state that generated the alert.

## 5. Decision semantics

The engine separates analytical quality from operational timing. A high-quality company is not automatically a buy.

Relevant concepts include:

- Quality Score
- Opportunity Score
- decision gates
- trigger state
- Buy Zone
- Ideal Entry
- Max Buy
- Stop
- TP1 / TP2
- gross and net R/R
- position sizing
- earnings/event risk
- portfolio fit

### Price guardrail

A BUY_LIMIT/LIMIT_READY label must not imply that an order is ready when current price is above the permitted Max Buy. The v2 guardrail normalises such an Italian state to a waiting/approaching condition. This preserves the operational rule: **do not chase above Max Buy**.

## 6. Entry and risk/reward

Entry construction uses technical structure/ATR geometry inherited from the frozen reference baselines. The system maintains distinct current-price and entry-price R/R views and incorporates configured transaction-cost drag in net R/R.

Sizing must not fabricate an operational quantity when trading capital is unavailable/non-positive.

## 7. Portfolio considerations

Portfolio logic exists to avoid treating candidates in isolation. Current and future controls include capital usage, position risk, concentration/portfolio fit and, only when evidence is sufficient, more advanced portfolio/correlation analysis.

Advanced optimisation is currently governed as experimental/frozen until sufficient observations exist.

## 8. Laboratory

Laboratory is the evidence-building environment. Its purpose is to test strategy behaviour without allowing recent self-generated results to silently rewrite CORE rules.

Functional concepts include:

- opportunity collection;
- paper positions;
- strategy families;
- tiers;
- maturity/evidence;
- verdict versions;
- walk-forward / OOS discipline;
- strategy throughput;
- dashboard views.

A strategy verdict must not be interpreted as statistically strong merely because the software pipeline is healthy.

## 9. Permanent dual status

Two independent concepts must remain visible:

**ENGINE HEALTH** — whether software/data/pipeline/provider/notification execution is reliable.

**STRATEGY EVIDENCE** — whether enough statistical evidence exists to trust a strategy's observed edge.

A green engine with low strategy evidence is a valid and expected state.

## 10. Production notifications

Email provides the richer analytical report. WhatsApp is intended for operationally useful, time-sensitive alerts. Alert content must be traceable to engine output and manually verifiable during validation.

Secrets are configuration inputs and must never be embedded in documentation or source code.

## 11. Functional Freeze

Current governance prioritises consolidation and evidence collection over feature expansion. Allowed work is primarily:

- collect observations;
- verify operational alerts;
- measure parity;
- fix confirmed defects;
- add regression tests;
- populate Laboratory evidence;
- improve documentation/observability without changing strategy semantics.

See repository root `FREEZE_BACKLOG.md` and `PARITY_TOLERANCES.md`.

## 12. TO-BE functional direction

The TO-BE is deliberately not a commitment. Candidate directions include:

- fully validated Fast Monitor;
- stronger evidence-aware strategy promotion;
- mature portfolio risk only after adequate data;
- shadow execution before any semi-automatic execution;
- richer provider resilience/observability;
- AI/TradingAgents promotion only after predefined OOS A/B evidence.

No TO-BE item becomes AS-IS until code, tests and documentation confirm implementation.