# ADR 0007 — New evidence types require a versioned replay contract

## Status

Accepted architectural boundary for M6A; typed execution is deferred to M6B.

## Context

`practice-observation-v1` contains six friendship-oriented Boolean
observations plus existing structured support, context, reciprocity, and
direction fields. Stretching those markers across conceptual, artifact,
health, qualified-review, community, or longitudinal protocols would create
false semantics and could change historical replay.

The future catalog needs Boolean observations, counts, bounded frequencies,
ordinal rubrics, duration, artifacts, conceptual or scenario performance,
objective indicators, consented observers, qualified evidence,
unknown/not-observed values, contradiction, and adverse outcomes.

## Decision

M6A preserves `GG-EVIDENCE-1.0` and `practice-observation-v1` exactly for the
five runtime projections. The rich packages describe accepted evidence and
withholding intent, but those fields do not execute or mutate state.

Any new evidence contract must:

- use a new stable schema and algorithm version;
- dispatch explicitly by the snapshotted version and fail closed on unknown
  versions;
- snapshot the rules and structured input needed for deterministic replay;
- treat free text as explanation, never an opaque score input;
- preserve explicit unknown, contradiction, adverse outcome, support,
  context, repetition, and provenance;
- include migration policy and exact golden replay fixtures before activation.

## Consequences

Historical events remain replayable and unchanged. Later protocol families
can use evidence that fits their actual intervention instead of relabeling
friendship checkboxes.

The canonical package is intentionally ahead of the runtime evidence engine.
Fields that describe future evidence design are governance commitments, not a
claim that typed evidence is implemented in M6A.
