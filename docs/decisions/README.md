# Architecture Decision Records (ADR)

ADR files preserve **why** a decision was made, not only what the current code does.

## Format

Each ADR should contain:

- ID/title
- date
- status: PROPOSED / ACCEPTED / SUPERSEDED / REJECTED
- context
- decision
- alternatives considered
- consequences
- affected components/docs
- superseding ADR if applicable

## Initial decision index

| ADR | Decision | Status |
|---|---|---|
| ADR-001 | Parity-first migration from frozen USA/Italy references | ACCEPTED |
| ADR-002 | Keep CORE and Laboratory logically separated | ACCEPTED |
| ADR-003 | Functional Freeze: consolidate before expanding architecture | ACCEPTED |
| ADR-004 | Permanent separation of Engine Health and Strategy Evidence | ACCEPTED |
| ADR-005 | TO-BE infrastructure requires measured need | ACCEPTED |

Git history is part of the audit trail. Decisions should be superseded by new ADRs rather than silently rewritten.