# Dynamic Exit V1 · Laboratory

Status: LAB RESEARCH ONLY

Path: IDEA → LAB → EVIDENCE → SHADOW → CORE PRODUCTION

The policy manages open paper positions only. It does not create trades and does not send broker orders.

## Core principles

- Stop management is asymmetric: `stop_current` may only stay unchanged or move upward.
- TP1 remains the original first target.
- TP2 starts fixed and may only stay unchanged or move upward.
- Missing/weak confirmation never justifies widening risk.
- Existing lifecycle remains authoritative for actual paper STOP/TP2 closure and fill accounting.

## Closed enums

`TargetMode`
- `FIXED`
- `POST_TP1_TRAILING`
- `POST_BREAKOUT_TRAILING`

`RecalibrationReason`
- `TP1_HIT`
- `BREAKOUT_CONFIRMED`
- `TREND_DETERIORATION`
- `STRUCTURE_BREAK`
- `TIME_DECAY`

Do not add free-text alternatives. Extending either enum requires code, tests and documentation in the same change.

## Breakout rule V1

A breakout is confirmed only when both are true:

- close > highest prior 20-session high × 1.005
- Relative Volume >= 1.20

These are provisional V1 parameters and must be changed only through a new version after evidence review.

## Trailing rules V1

After `TP1_HIT`:

- target mode becomes `POST_TP1_TRAILING`;
- stop may move to the highest valid value among break-even, ATR-based trailing and recent structure, but never below the current/initial stop.

After `BREAKOUT_CONFIRMED`:

- target mode becomes `POST_BREAKOUT_TRAILING`;
- TP2 may be extended using current price/high plus ATR expansion;
- stop may tighten using ATR;
- neither value may move in the adverse direction.

Trend deterioration below SMA20 may tighten the stop, never loosen it.

## Persistence

No schema migration is required for V1.

- `lab_paper_positions.stop_current` remains the operational stop.
- `lab_paper_positions.tp2` remains the operational/current TP2 for backward compatibility.
- original and current exit-policy values are preserved in `details.dynamic_exit`:
  - `policy_version`
  - `target_mode`
  - `stop_initial`
  - `stop_current`
  - `tp2_initial`
  - `tp2_current`
  - `last_recalibration_at`
  - `recalibration_reason`
- `details.exit_variant = DYNAMIC_EXIT_V1` allows research separation from legacy fixed-exit trades.

Lifecycle events include `EXIT_POLICY_INITIALIZED`, `TARGET_MODE_CHANGED`, `STOP_MOVED`, and `TP2_RAISED` with a closed reason code.

## Research comparability

Dynamic exit is a versioned management variant. Research reports must separate `DYNAMIC_EXIT_V1` from legacy/fixed-exit history before judging expectancy, Profit Factor, average R, drawdown or holding period.

Promotion to production is explicitly out of scope until evidence and shadow validation are completed.

## Required invariants

- `stop_current >= stop_initial`
- a raised stop never moves down
- `tp2_current >= tp2_initial`
- a raised TP2 never moves down
- breakout needs both price and volume confirmation
- identical position + market path + config produces identical decision
