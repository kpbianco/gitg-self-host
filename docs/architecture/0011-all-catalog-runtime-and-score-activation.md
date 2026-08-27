# ADR 0011 — All-catalog runtime and score activation

## Status

Accepted for implementation by owner direction on 2026-08-26. Consolidated
content and specialist audit remains pending.

## Context

The canonical source frontier contains exactly one protocol for every one of
383 competencies. Earlier milestones projected five legacy protocols into the
runtime and allowed only friendship to update current score state. That
boundary prevented the complete catalog from serving its intended feedback
function.

## Decision

Project all 383 protocols and 1,151 actions into the runtime and activate all
383 under `SP-STRUCTURED-EVIDENCE-ELIGIBLE` and `GG-SCORE-STATE-1.0`.

The five original protocols retain `practice-observation-v1`. The other 378
use `GG-PRACTICE-RUNTIME-PROJECTION-2.0` and typed structured evidence. Every
eligible event is replayed and allocated through its complete canonical parent
competency mapping. Recommendation target subsets do not replace the scoring
allocation.

Unknown, withheld, deferred, not-applicable, adverse, inconclusive, invalid,
unconsented, or cross-epoch observations remain explicit and contribute no
score when the evidence contract withholds them. Assessment baselines remain
immutable; current state changes are append-only, reversible, and rebuildable.

## Consequences

- Seeding and readiness require exactly 383 active and score-active protocols
  and 1,151 actions.
- Check-ins persist action-specific structured typed observations where
  applicable.
- Score projection accepts mixed legacy and typed events and aggregates shared
  lever contributions deterministically.
- A database activation flag, action definition, target mapping, or lever total
  that drifts from canonical data fails closed.
- Software activation is not evidence of mastery, worth, psychometric validity,
  clinical validity, cultural validity, accessibility validation, or
  intervention effectiveness.
