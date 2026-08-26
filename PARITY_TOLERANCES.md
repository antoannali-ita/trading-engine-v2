# Trading Engine v2 — PARITY TOLERANCES V1

**Effective:** 26/08/2026  
**Status:** FROZEN FOR PHASE A  
**Scope:** OLD reference engine vs Trading Engine v2 parity certification.

These tolerances must be fixed before a run is counted toward the 10-run parity exit streak. They may not be widened retrospectively to make an already failing comparison pass.

## Decision fields — exact match required

The following fields require semantic equality after normalising aliases:

- Decision / Operational State: BUY_NOW, BUY_LIMIT, WAIT, WATCH/APPROACHING, AVOID
- Trigger state
- Veto/gate outcome
- Market/ticker identity

Any unexplained mismatch is a parity failure.

## Numerical fields

Until an automated comparator proves that provider rounding requires a different value, use these conservative comparison rules:

| Field | Tolerance |
|---|---:|
| Entry / Ideal Entry | max(0.01 currency units, 0.10%) |
| Buy Range bounds | max(0.01 currency units, 0.10%) |
| Max Buy | max(0.01 currency units, 0.10%) |
| Stop | max(0.01 currency units, 0.10%) |
| TP1 / TP2 | max(0.01 currency units, 0.10%) |
| R/R | 0.02 absolute |
| Score | 0.10 points |
| Position quantity | exact integer match |
| Position capital | max(1.00 currency unit, 0.10%) |
| Estimated max loss | max(1.00 currency unit, 0.50%) |

Tolerance means the larger of the absolute floor and percentage threshold where both are specified.

## Data-provider differences

A comparison is not certified when OLD and NEW consumed materially different market snapshots unless the comparator records the difference and the run is explicitly marked `NON_COMPARABLE_EXTERNAL`.

`NON_COMPARABLE_EXTERNAL` neither increments nor resets the parity streak.

## Change control

Any tolerance change requires:
1. a new version of this policy;
2. dated rationale in the commit;
3. evidence showing why the previous tolerance was technically inappropriate;
4. no retrospective reclassification of previously failed runs solely because of the new tolerance.

Git history is the audit/approval record for this project.