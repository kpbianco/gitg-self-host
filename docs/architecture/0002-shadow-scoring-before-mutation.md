# ADR 0002 — Shadow scoring before profile mutation

## Status

Accepted after M3A review.

## Context

M2 produced immutable, replayable evidence events but deliberately left two
questions unresolved: how evidence direction changes success/failure mass and
how a practice receives reviewed task-to-lever weights. Enabling stored score
updates while either contract remained implicit would make the result
difficult to audit or reverse.

The canonical assessment scorer contains a dormant posterior helper, but it
does not understand the M2 direction states. Pilot 002 also publishes rounded
baseline values rather than its original alpha and beta mass.

## Decision

M3A introduces `GG-SCORING-SHADOW-1.0` as a pure, deterministic, read-only
projection:

- the friendship protocol is explicitly linked by stable ID to competency
  `17.03` and inherits that competency's structured canonical weights;
- new assessments persist their exact canonical alpha and beta mass;
- published Pilot 002 mass is reconstructed only where its rounded values
  uniquely identify the result;
- supportive, mixed, and contradictory direction receives explicit versioned
  treatment, while inconclusive and legacy-unknown direction is withheld;
- confidence starts from the stored assessment value and receives a bounded
  monotonic evidence gain instead of using the dormant helper's incompatible
  mass-only recalculation;
- the profile may display a clearly labeled preview;
- no current score, recommendation, or score snapshot is stored.

M3B is a separate review gate for mutation, immutable before/after snapshots,
rebuild/reversal, and dynamic ranking.

## Consequences

Reviewers can inspect real projections and golden fixtures before accepting
state-changing behavior. Existing profile values remain stable. Some legacy or
neutral published baselines cannot be projected and fail closed. The M3A
preview is intentionally not a promise that the reviewed algorithm is
psychometrically validated.
