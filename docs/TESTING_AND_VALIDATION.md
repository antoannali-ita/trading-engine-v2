# Testing & Validation — Trading Engine v2

**Version:** 1.0

## 1. Validation layers

The project must not confuse software correctness with strategy evidence. Validation therefore has distinct layers:

1. syntax/unit/regression tests;
2. frozen baseline integrity;
3. function-map completeness;
4. OLD vs NEW parity;
5. production alert verification;
6. Laboratory paper evidence;
7. OOS/walk-forward strategy validation;
8. shadow execution before any real automation.

## 2. Baseline integrity

Reference USA/Italy files are frozen and protected by declared SHA-256 hashes plus automated tests. Function mapping is tested so top-level reference functions cannot silently remain unmapped during migration.

## 3. Utility/report parity

Shared utility functions have dedicated parity tests where behaviour is compared against reference implementations. Report binding must fail loudly when required reference functions are absent rather than silently degrading.

## 4. Decision parity

Phase A exit requires 10 consecutive valid parity runs under `FREEZE_BACKLOG.md` and frozen numeric tolerances in root `PARITY_TOLERANCES.md`.

Unknown failure types default to internal failure until classified/documented. External non-comparable runs neither advance nor reset the streak.

## 5. Alert validation

Fast Monitor and notifications graduate only after the documented number of verified events/trading days. Manual verification during this phase is intentional and produces defect/evidence records rather than being treated as informal testing.

## 6. Laboratory evidence

Per-strategy evidence should track at least:

- open and closed observations;
- valid opens/closes per week;
- sample target;
- ETA range, not a single promise;
- regimes represented;
- expectancy/win rate where statistically meaningful;
- drawdown;
- OOS/walk-forward stability;
- tier/verdict version.

Throughput depends on market regime. ETA must use optimistic/central/pessimistic observed throughput or show N/D when history is insufficient.

## 7. Promotion principle

No component/strategy is promoted because a calendar date arrived. Promotion is gate-driven.

```mermaid
flowchart LR
    P[PARITY] -->|gates pass| V[VALIDATED CORE]
    V --> E[EVIDENCE BUILDING]
    E -->|evidence gates| S[SHADOW EXECUTION]
    S -->|operational gates| A[SEMI-AUTO]
```

## 8. Regression policy

Every confirmed material defect should receive a regression test where practical. Tests must validate behaviour, not freeze obsolete UI strings unless those strings are themselves a contractual interface.