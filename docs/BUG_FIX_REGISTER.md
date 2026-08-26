# Bug & Fix Register

**Version:** 1.0  
**Purpose:** permanent record of defects that affected or could affect decisions, reports, alerts, data, persistence or production reliability.

## Severity

- **P0** — unsafe/catastrophic operational behaviour or corruption.
- **P1** — material wrong decision/risk/notification behaviour.
- **P2** — meaningful defect with bounded operational impact.
- **P3** — presentation/maintainability defect without decision impact.

## Register

| ID | Date | Area | Symptom | Root cause / classification | Fix | Regression protection | Status |
|---|---|---|---|---|---|---|---|
| BUG-001 | Aug 2026 | Production config | Master Scan crashed converting `TRADING_CAPITAL` to float | Runtime variable existed as empty string | Workflow/config corrected to provide a numeric fallback/value | Workflow rerun + test suite gate | FIXED |
| BUG-002 | Aug 2026 | Fast Monitor / WhatsApp | Workflow succeeded but no WhatsApp message was received during initial validation | Notification path/config required explicit validation; successful workflow alone did not prove delivery | Added temporary explicit WhatsApp test step and validated CallMeBot delivery | Manual delivery validation during Phase A | FIXED / MONITORING |
| BUG-003 | Aug 2026 | Italy decision/report | Candidate could appear `LIMIT_READY` / BUY LIMIT while current price was above Max Buy and trigger was waiting | Unified/reference decision semantics allowed a presentation/operational contradiction | Added market-specific v2 guardrail outside frozen reference: above Max Buy normalises to waiting/approaching; baseline untouched | Dedicated regression tests for above vs at/below Max Buy | FIXED |
| BUG-004 | Aug 2026 | Laboratory tests | Master Scan workflow blocked by tests expecting obsolete Laboratory Overview column/label strings | Tests asserted stale UI representation after page evolution | Updated stale assertions to current UI semantics rather than changing trading logic | Full pytest gate | FIXED |

## Required fields for future entries

Every material defect should record:

1. observed symptom;
2. affected market/component;
3. whether trading decisions could change;
4. root cause;
5. exact code/config fix;
6. test added or reason no automated test is practical;
7. commit/PR reference where available;
8. first validated production run;
9. residual risk.

## Freeze rule

A BUGFIX_ALLOWED change corrects behaviour that contradicts an already documented rule, configured value, external fact or expected interface. Strategy retuning because recent trades performed poorly is **not** a bugfix.