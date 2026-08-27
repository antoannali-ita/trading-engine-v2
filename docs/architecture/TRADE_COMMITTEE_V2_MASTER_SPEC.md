# Trade Committee V2 — Master Specification

Status: ARCHITECTURE FROZEN FOR IMPLEMENTATION  
Scope: Research / pre-trade due diligence. CORE Production remains authoritative and read-only from the Committee.

## Mission

The CORE finds and constructs the trade. The Trade Committee performs independent due diligence and tries to invalidate it. The Watchlist follows interesting but not-yet-buyable candidates. The Laboratory later measures whether Committee vetoes and confirmations add value.

Flow:

`CORE -> immutable snapshot -> Committee -> Watchlist/Recheck -> Final Gate -> manual execution eligibility -> Laboratory evidence`

## 1. CORE is the operational Single Source of Truth

When a CORE setup exists, the Committee MUST NOT independently recalculate:

- Entry / Buy Range / Max Buy
- Stop / TP1 / TP2
- net R/R
- Trigger
- Earnings Gate
- Qty / commissions
- setup / CORE decision

The Committee may validate consistency. A discrepancy produces `WAIT_CONFLICT`; it does not silently select one value.

A Committee-only ticker may receive exploratory estimates marked `COMMITTEE_ESTIMATE / NOT_CORE_VALIDATED`, but it can never become APPROVE before CORE validation.

## 2. Immutable CORE snapshot

Persist the exact input evaluated by the Committee:

- ticker, market
- core_state, engine/strategy versions
- generated_at, market_price_at_generation
- operational trade fields listed above
- source signal/run IDs when available
- SHA-256 of canonical serialized payload

The Committee is read-only over this snapshot. If freshness rules invalidate it: `WAIT_STALE`.

## 3. Evidence contract

Every important metric/check uses:

`Value | Status | Source | Timestamp | TTL | Note`

Allowed evidence states:

- `REAL`: verified/available and fresh
- `PARTIAL`: incomplete coverage
- `STALE`: too old for its metric-specific TTL
- `N/D`: unavailable
- `N/A`: not applicable

Missing optional evidence lowers confidence; it does not automatically become zero investment quality.

Critical Evidence must be valid for APPROVE: valid CORE snapshot, sufficiently fresh market price, CORE trade plan/gates, earnings/event gate, minimum financial evidence, portfolio context.

No arbitrary global confidence threshold (e.g. 70%) is allowed until calibrated in Laboratory.

## 4. Asymmetric final gate

Implement as a pure function outside Streamlit and unit-test every meaningful combination.

Invariant: **Committee can remove a CORE BUY; Committee can never create a BUY that CORE did not authorize.**

| CORE | Committee/Evidence | Final |
|---|---|---|
| not BUY-authorized | any | WAIT_CORE |
| BUY | stale snapshot | WAIT_STALE |
| BUY | data conflict | WAIT_CONFLICT |
| BUY | critical evidence incomplete | WAIT_DATA |
| BUY | hard veto | REJECT_COMMITTEE |
| BUY | PASS and evidence valid | APPROVE |

## 5. Data conflicts and audit

The old verbose Run Log stays out of the operational UI.

Every material conflict is persisted as a structured backend event with at least:

`run_id, ticker, metric, core_value, observed_value, source, timestamp, severity`

UI shows only the concise conflict and resulting WAIT.

## 6. Separate scores

Never merge different concepts into one opaque number:

- CORE Score: screening/opportunity from CORE
- Committee/Investment Score: independent due diligence
- Trade Quality: quality of CORE setup, without redefining CORE gates
- Berkshire Review: independent business-quality view
- Data Confidence: completeness/reliability of evidence

## 7. Berkshire / Buffett module

Adapt reusable ideas/components from the researched AI Berkshire project behind our own interfaces. It is a second independent opinion, not a replacement for CORE fundamentals.

Sections:

- Business Quality
- Economic Moat
- Management & Capital Allocation
- Financial Strength
- Owner Earnings / cash conversion
- Earnings Quality
- Intrinsic Value / Margin of Safety
- Inversion

Qualitative judgments must be marked as `INFERENCE`, cite the evidence used, and must not masquerade as raw REAL data.

## 8. Bull / Bear adversarial review

Use the same evidence package for both sides. Output is structured, not essay prose:

`claim -> evidence -> source -> strength`

The Inversion layer reviews both cases.

## 9. Inversion Test

Each test returns:

`Result: PASS/WARNING/FAIL/N/D`  
`Severity: HARD/SOFT`  
`Evidence: REAL/INFERENCE`  
`Source`  
`Reason`

Hard and soft conditions are declared in advance. A HARD FAIL can veto; a SOFT warning affects the assessment but does not automatically block.

Areas include cash-vs-earnings quality, leverage/dilution, moat deterioration, management/capital allocation, event risk, catalyst already priced, valuation/margin of safety, portfolio allocation and explicit -20/-30% failure scenarios.

Do not force exactly three reasons for/against. Show only evidence-backed reasons found.

## 10. Real source layer

Progressively support and expose provenance for:

- market/fundamental providers
- SEC EDGAR 10-K / 10-Q / 8-K / Form 4
- Company IR where useful
- insider / institutional / 13F evidence
- earnings and material catalysts
- news providers
- benchmark and sector context
- Production portfolio context

Reuse/adapt validated open-source components identified in `docs/research/TRADE_COMMITTEE_SOURCE_RESEARCH.md` and `TRADE_COMMITTEE_REUSE_MAP.md`; do not vendor whole projects blindly.

## 11. Portfolio Risk

Before APPROVE check, when data exists:

- sector / industry concentration
- currency exposure
- capital/risk already deployed
- economically similar holdings
- correlation where meaningful and reliable

## 12. Operational chart

The page includes a lightweight interactive chart with candles, volume, SMA20/50/200 and, when CORE exists, CORE Buy Range / Entry / Max Buy / Stop / TP1 / TP2 plus relevant event markers. Operational levels shown as CORE must come from the immutable snapshot.

## 13. Committee Watchlist

Reuse existing `lab_watchlist`; do not create a disconnected fourth watchlist.

Initial addition is manual through `Add to Watchlist`. No automatic score threshold until Laboratory evidence supports one.

Persist/extend metadata for:

- `source=TRADE_COMMITTEE`
- initial and latest Committee verdict/score/confidence
- reason
- CORE state and source IDs
- trade plan source (`CORE` or `COMMITTEE_ESTIMATE`)
- operational levels when applicable
- lifecycle state
- created/last_checked timestamps
- active flag

Never hard-delete normal lifecycle removals; archive with `active=false` for later evidence analysis.

## 14. Dynamic Watchlist lifecycle

States:

- WATCH
- APPROACHING
- RECHECK_REQUIRED
- READY_FOR_COMMITTEE
- APPROVABLE
- NO_LONGER_INTERESTING
- EXPIRED

Use two analysis levels:

1. Light Monitor: price/distance, CORE state, R/R and trigger from CORE, event proximity, relevant technical/material changes.
2. Deep Recheck: only on material change, such as approaching/entering buy zone, CORE gate transition, new material filing/earnings, large price move or thesis deterioration.

Alert only on decision-relevant transitions. Dashboard may show lower-priority changes without notification.

Examples of alert-worthy transitions:

- APPROACHING BUY ZONE
- ENTERED BUY ZONE
- CORE R/R FAIL -> PASS
- TRIGGER WAITING -> CONFIRMED
- READY_FOR_COMMITTEE
- Committee -> APPROVABLE
- thesis invalidated / archived

## 15. Evidence validation

Persist lifecycle and future outcomes so Laboratory can evaluate:

- WATCH -> BUY conversion
- lead time to actionable setup
- false alerts
- avoided losses from Committee vetoes
- missed opportunities caused by vetoes
- incremental value of Berkshire, SEC, Bull/Bear, Inversion and Portfolio Risk modules

Only evidence may justify later automatic thresholds or module weight changes.

## 16. UI target

Primary view must answer quickly:

- ticker / price
- CORE state
- Committee verdict
- CORE Score / Committee Score / Data Confidence
- concise reason
- chart
- CORE trade plan and source
- evidence-backed reasons for / against
- invalidation conditions
- Add to Watchlist

Details live in tabs: Business/Berkshire, Technical, SEC/Ownership, Catalyst, Bull/Bear, Inversion, Portfolio, Data Quality.

No raw debug wall and no persistent Run Log in the main page.

## 17. Delivery roadmap

### V2.0 Transparency & Governance
- remove misleading completed-count semantics
- REAL/PARTIAL/STALE/N/D + provenance/TTL contract
- separate score vs confidence
- no automatic penalty of optional N/D as investment quality
- pure asymmetric decision resolver + unit tests
- remove debug/log clutter from UI

### V2.1 CORE Integration
- immutable read-only CORE snapshot + SHA-256
- operational fields imported, not recalculated
- stale/conflict detection
- structured backend audit
- chart based on CORE levels

### V2.2 Deep Due Diligence
- Berkshire/Buffett module
- SEC/filings, insider/ownership/13F, news/catalyst
- sector/macro context
- Bull/Bear + Inversion hard/soft
- Portfolio Risk

### V2.3 Watchlist & Event Monitoring
- extend/reuse lab_watchlist
- manual add
- lifecycle states
- light monitor and material-change deep recheck
- decision-relevant highlighting/alerts

### V2.4 Evidence & Calibration
- outcome tracking
- module value measurement
- false veto / missed opportunity analysis
- calibrate thresholds only from evidence

## Non-negotiable guardrails

- Research/read-only Committee cannot mutate CORE Production logic.
- No real order is sent automatically.
- No duplicated operational truth when CORE already provides a value.
- N/D is never silently invented.
- Qualitative inference is labelled as inference.
- New thresholds require evidence, not aesthetic preference.
