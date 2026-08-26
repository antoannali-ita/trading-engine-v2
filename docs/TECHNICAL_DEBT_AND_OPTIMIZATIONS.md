# Technical Debt & Optimisation Register

**Version:** 1.0  
**Rule:** an optimisation candidate is not an implementation commitment.

## Status model

`IDEA → ANALYSIS → APPROVED → IN DEVELOPMENT → SHADOW → PRODUCTION`

Alternative terminal/holding states: `FROZEN`, `REJECTED`, `NOT NEEDED`.

## Register

| ID | Area | AS-IS / issue | Candidate optimisation | Benefit | Risk / cost | Evidence required | Priority | Status |
|---|---|---|---|---|---|---|---|---|
| OPT-CORE-001 | CORE | Modular engine still depends on frozen reference behaviour/wrappers | Complete function-by-function modular extraction with parity tests | Maintainability, isolation, safer evolution | High regression risk if rushed | Phase A parity + extraction tests | HIGH | FROZEN until parity exit |
| OPT-DATA-001 | Providers | Yahoo/TradingView are external dependencies with availability/format risk | Explicit provider adapters, freshness/error taxonomy and fallback policy | Resilience and observability | Added complexity | Measured provider failures | HIGH | ANALYSIS |
| OPT-DB-001 | Data/DB | Persistence responsibilities span local state/cache and database-backed areas | Audit authority, retention, indexing, constraints and idempotency | Reliability and simpler recovery | Migration risk | Schema/query/runtime measurements | MEDIUM | ANALYSIS |
| OPT-GHA-001 | GitHub Actions | Dependencies installed repeatedly; cache/state behaviour requires care | Pin dependencies/actions, optimise cache keys and separate dependency cache from state | Faster/stabler runs | Stale-cache risk | Runtime/failure metrics | MEDIUM | ANALYSIS |
| OPT-NOTIFY-001 | Notifications | Delivery success and engine-state correctness are distinct | Delivery receipts/status logging + deduplication/event IDs | Fewer silent failures/duplicates | Provider limitations | Alert validation statistics | HIGH | ANALYSIS |
| OPT-LAB-001 | Laboratory | Evidence can look mature before sample/regime coverage is adequate | Permanent Engine Health vs Strategy Evidence badges + ETA ranges | Prevents false confidence | UI/data work | Throughput history | HIGH | APPROVED DOC / CODE FROZEN |
| OPT-WEB-001 | Site/UI | Dashboard complexity grows with system | Navigation by CORE/LAB/PRODUCTION + maturity badges + linked documentation | Faster interpretation | Maintenance overhead | User friction / page audit | MEDIUM | IDEA |
| OPT-PERF-001 | Performance | No demonstrated need for distributed cache | Redis only if measured latency/runtime requires it | Potential performance | Operational complexity | Bottleneck measurement | LOW | FROZEN |
| OPT-ARCH-001 | Architecture | Current workflows do not require message broker | Queue/event bus only for measured reliability/decoupling requirement | Scalability/decoupling | Large complexity increase | Concrete missed-SLA/event-loss evidence | LOW | FROZEN |
| OPT-RISK-001 | Portfolio | Advanced correlation estimates statistically fragile with small samples | Delay advanced optimiser; keep simple heat/concentration controls | Avoids pseudo-precision | Less sophistication short term | Adequate position history | MEDIUM | FROZEN |
| OPT-AI-001 | AI | TradingAgents/AI remains research-oriented | Promote only after predefined OOS A/B benefit | Potential qualitative enrichment | Cost, bias, instability | Repeatable OOS uplift | LOW | LAB ONLY |
| OPT-EXEC-001 | Execution | No real automatic trading | Shadow execution → semi-auto only after maturity gates | Operational efficiency | Highest financial/operational risk | Modular CORE + validated alerts + failure handling + shadow evidence | FUTURE | DISABLED |

## Code optimisation policy

Optimisation must not change trading semantics accidentally. Refactors require behaviour/parity tests. If an optimisation changes a threshold, gate, score or decision, it is a functional strategy change and must be reviewed as such rather than hidden under "cleanup".

## Database optimisation checklist

Future DB audit should explicitly review:

- authoritative source for each entity;
- primary/unique keys;
- idempotent writes;
- retention/history policy;
- indexes based on real queries;
- transaction boundaries;
- timezone/timestamp consistency;
- recovery/backfill procedure;
- schema migrations/versioning;
- separation of operational state from Laboratory evidence.

## Site/dashboard optimisation checklist

- immediate distinction AS-IS operational state vs research evidence;
- Engine Health and Strategy Evidence shown separately;
- links from UI states to documentation definitions;
- explicit data freshness timestamp;
- no presentation state that contradicts CORE decision state;
- mobile/readability and alert-oriented views only when justified.