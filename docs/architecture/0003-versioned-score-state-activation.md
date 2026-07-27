# ADR 0003 — Versioned score-state activation

## Status

Accepted after M3B review.

## Context

M3A established reviewed, golden-tested posterior and confidence mathematics
without writing profile state. Activation now needs a current state that
cannot overwrite the assessment baseline, double-apply events, hide a repair,
or make a recommendation impossible to reproduce.

The full canonical developmental-priority model also names per-user context
inputs that the product does not yet collect. Treating absent applicability,
importance, readiness, or urgency as hidden defaults would imply more
precision than the data supports.

## Decision

M3B:

- retains `LeverBaseline` as the immutable assessment starting point;
- creates separate per-assessment `LeverState` rows;
- activates the exact `GG-SCORING-SHADOW-1.0` mathematics only for the
  reviewed friendship protocol;
- appends full, hashed, immutable before/after `ScoreSnapshot` transitions;
- processes evidence and score state atomically and idempotently;
- rebuilds state from baselines and versioned events at startup;
- supports audited, permanent event reversal without deleting evidence;
- recalculates the existing assessment v1.1 provisional need function as
  `GG-NEED-RANKING-1.0`;
- ranks active protocols from canonical parent-competency weights;
- fails closed when required baseline mass is unavailable.

M3B does not fabricate the uncollected contextual priority factors and does
not apply orientation or archetype modifiers.

## Consequences

Current estimates and recommendations can respond to eligible evidence while
the original assessment remains inspectable. A database inconsistency is
visible and repairable through an append-only transition rather than an
unlogged overwrite. Startup does more deterministic verification work, which
is acceptable for the local single-instance deployment.

Pilot 002 has four baseline-only levers and cannot score a future practice
that requires one of them without reassessment. The current recommendation
order remains provisional rather than the complete context-aware priority
model. The scoring contract remains a product hypothesis, not a validated
measure of human value or mastery.
