# Innovation Backlog

Ideas belong here before they belong in the architecture.

| ID | Idea | Problem it would solve | Evidence required | State |
|---|---|---|---|---|
| INN-001 | Additional market/fundamental providers | Coverage/reliability gaps | Measured missing/stale fields and provider comparison | IDEA |
| INN-002 | Provider fallback layer | Upstream outages | Failure-rate evidence and deterministic fallback semantics | ANALYSIS |
| INN-003 | Notification event IDs/deduplication | Duplicate/silent alerts | Alert validation data | ANALYSIS |
| INN-004 | Strategy evidence ETA ranges | Unclear time-to-maturity | Several weeks of throughput history | APPROVED CONCEPT |
| INN-005 | Enhanced site architecture view | Harder system interpretation as modules grow | UI/navigation audit | IDEA |
| INN-006 | Redis | Runtime/cache bottleneck | Measured SLA/runtime breach | FROZEN |
| INN-007 | Queue/event bus | Reliability/decoupling need | Demonstrated event-loss/throughput issue | FROZEN |
| INN-008 | Advanced portfolio optimiser | Cross-position risk optimisation | Sufficient position history and stable estimates | FROZEN |
| INN-009 | AI enrichment in operational flow | Qualitative catalyst/context enrichment | Predefined OOS A/B uplift | LAB ONLY |
| INN-010 | Semi-automatic execution | Reduce manual execution latency | All execution maturity gates | DISABLED |

## Rule

An idea can be useful without deserving implementation. Promotion requires an observed problem, measurable benefit or predefined evidence gate. When implemented, move its behaviour into AS-IS documentation and retain this row/history rather than deleting the past decision.