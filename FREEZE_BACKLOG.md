# Trading Engine v2 — Functional Freeze Governance V1

**Start:** 26/08/2026  
**Status:** ACTIVE  
**Principle:** consolidate, measure, validate. Do not add architecture unless it solves an observed and measurable problem.

## 1. Allowed changes during freeze

### BUGFIX_ALLOWED
A change is an allowed bugfix only when it corrects behaviour that contradicts an already documented rule, configured value, external fact, or expected interface.

Examples: wrong commission/cost, inconsistent entry/stop/target, incorrect BUY state above Max Buy, broken notification, provider parsing regression.

Requirements:
- document the defect and impact;
- add/update a regression test when practical;
- do not change strategy thresholds merely because recent outcomes were poor;
- record the change in this file or the project changelog.

### FEATURE_FROZEN
Any change that introduces a new capability, new strategy, new architectural component, new decision input, new optimisation rule, or materially changes an existing strategic threshold is frozen unless an observed production problem demonstrates that it is necessary.

"Could be useful" is not sufficient evidence.

## 2. Maturity gates

| Component | Current state | Exit criteria | Next state |
|---|---|---|---|
| CORE | PROD / PARITY | 10 consecutive valid OLD/NEW parity runs; no unexplained decision divergence; tests green; no open P0/P1 | PROD |
| Fast Monitor | PROD / SHADOW | >=30 verified operational events and >=10 trading days without critical logical bugs | PROD / VALIDATED |
| Email / WhatsApp | VALIDATION | >=30 notifications manually matched to engine output; 0 critical discrepancies in latest 20 | VALIDATED |
| Laboratory | DATA COLLECTION | strategy-specific sample target reached and multiple market regimes represented | EVALUATION |
| Strategy Verdict | LOW/MED EVIDENCE | strategy sample threshold + OOS/walk-forward stability + regime coverage | VALIDATED |
| Portfolio Risk advanced | EXPERIMENTAL | stable CORE + sufficient position history to support estimates | SHADOW |
| TradingAgents / AI | LAB ONLY | predefined A/B test shows repeatable OOS improvement | SHADOW |
| Auto-trading | DISABLED | modular CORE + validated alerts + extended shadow execution + failure handling | SHADOW EXECUTION |
| Redis / Queue | BACKLOG | measured runtime/latency/reliability problem that current architecture cannot meet | DESIGN |

## 3. PARITY exit policy

Phase A PARITY ends only after **10 consecutive valid Master Scan parity runs** covering USA and Italy under the agreed comparison process.

A valid run requires:
- test suite green;
- no unexplained divergence in BUY_NOW / BUY_LIMIT / WAIT / AVOID decisions;
- no material divergence in Entry, Max Buy, Stop, TP or sizing outside frozen tolerances;
- no open P0/P1 regression affecting the comparison.

### Run classification

**EXTERNAL_FAILURE — does not increment or reset the streak**
- provider timeout / connection failure;
- HTTP rate limit or provider-side service error;
- explicitly detected missing/unavailable upstream dataset;
- provider response rejected because the provider changed/unavailable format, provided the engine fails closed and does not emit a decision.

**INTERNAL_FAILURE — resets the parity streak**
- uncaught application exception not classified above;
- incorrect state/decision calculation;
- persistence/state corruption caused by our code;
- notification/report inconsistency with engine output;
- failed regression/unit test;
- malformed configuration or internal parsing/validation bug.

Unknown failures default to **INTERNAL_FAILURE** until classified and documented. This prevents convenient retrospective relabelling.

## 4. Frozen parity tolerances

The exact numerical OLD/NEW comparison tolerances must be stored in a separate versioned file (`PARITY_TOLERANCES.md`) before automated parity certification is enabled.

Rules:
- tolerances are fixed before evaluating the certification streak;
- changes require a dated commit with rationale;
- a tolerance must never be widened solely to make a failing historical run pass;
- the repository history is the approval/audit record.

## 5. Strategy evidence and ETA

Do not use a universal 50/100-trade gate blindly. Track per strategy:

`N open | N closed | opens/week | closes/week | target N | ETA range | regimes covered`

ETA must be shown as a **range**, not a promise:
- optimistic ETA: based on higher observed valid throughput;
- central estimate: rolling throughput;
- pessimistic ETA: based on lower observed valid throughput.

If history is insufficient to estimate a meaningful range, display `N/D — insufficient history`.

## 6. Permanent UI principle

Every operational dashboard should keep two independent indicators:

**ENGINE HEALTH** — execution reliability: tests, data freshness, providers, DB, pipeline, notifications, errors.

**STRATEGY EVIDENCE** — statistical evidence: closed trades, OOS results, expectancy, drawdown, walk-forward stability and regime coverage.

A healthy engine does not imply a validated strategy. Example: `ENGINE HEALTH: GREEN` together with `STRATEGY EVIDENCE: LOW` is valid and expected during evidence collection.

## 7. Frozen backlog

| ID | Date | Proposal / correction | Class | Reason / evidence needed | Review trigger | Status |
|---|---|---|---|---|---|---|
| ARCH-001 | 26/08/2026 | Redis cache | FEATURE | No measured bottleneck yet | Measured latency/runtime breach | FROZEN |
| ARCH-002 | 26/08/2026 | Message queue | FEATURE | Current scheduler/pipeline sufficient | Reliability/throughput problem demonstrated | FROZEN |
| STRAT-001 | 26/08/2026 | Add new strategy families | FEATURE | Existing strategies need evidence first | Evidence targets reached / coverage gap demonstrated | FROZEN |
| RISK-001 | 26/08/2026 | Advanced portfolio correlation/optimisation | FEATURE | Current sample too small for robust estimates | Sufficient position history | FROZEN |
| AI-001 | 26/08/2026 | Promote TradingAgents/AI into CORE | FEATURE | No repeatable OOS advantage established | Predefined A/B success | FROZEN |
| EXEC-001 | 26/08/2026 | Real/semi-automatic trading | FEATURE | CORE/alerts/shadow execution not fully validated | All auto-trading maturity gates pass | FROZEN |
| FIX-001 | 26/08/2026 | Commission configuration consistency | BUGFIX CANDIDATE | Verify configured cost against actual broker cost and all calculation paths | Confirm mismatch | REVIEW |
| FIX-002 | 26/08/2026 | SMA/entry buffer behaviour | CHANGE CANDIDATE | Must distinguish documented bug from strategy retuning | Demonstrated rule inconsistency | FROZEN/REVIEW |
| FIX-003 | 26/08/2026 | Cooldown behaviour | CHANGE CANDIDATE | Could alter signal frequency/strategy semantics | Demonstrated documented-rule violation | FROZEN/REVIEW |
| FIX-004 | 26/08/2026 | Earnings gate by holding horizon | FEATURE/STRATEGY CHANGE | Changes decision policy, not merely implementation | Formal evidence + post-freeze review | FROZEN |

## 8. Freeze operating rule

During the freeze, normal work is limited to:
1. collect real observations;
2. verify email/WhatsApp operational alerts against engine state;
3. measure parity discrepancies;
4. populate Laboratory evidence and throughput statistics;
5. fix confirmed bugs under BUGFIX_ALLOWED;
6. add regression tests for confirmed defects;
7. update evidence/status tables without moving strategic thresholds retrospectively.

The freeze is gate-driven. Three to four weeks is a **minimum observation window**, not an automatic expiry date.

---

**Governance decision:** PARITY → VALIDATED CORE → EVIDENCE BUILDING → SHADOW EXECUTION → SEMI-AUTO. Advancement is determined by documented gates, not elapsed calendar time.