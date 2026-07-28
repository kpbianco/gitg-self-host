# ADR 0007 — New evidence types require a versioned replay contract

## Status

Accepted architectural boundary from M6A. The concrete M6B typed contract is
proposed for owner and specialist review.

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

M6B preserves `GG-EVIDENCE-1.0` and `practice-observation-v1` exactly for the
five runtime projections. The new parallel contract is
`GG-TYPED-EVIDENCE-1.0`, with materialized rule snapshots under
`typed-evidence-rules-v1`. It is pure and shadow-only in M6B.

The typed contract:

- dispatches explicitly by event algorithm and rule-schema version and fails
  closed on unknown versions;
- snapshots the materialized rules, rule version and hash, stable
  protocol/action/competency IDs, scoring policy, structured input, and
  minimal provenance needed for deterministic replay;
- treat free text as explanation, never an opaque score input;
- represents Boolean observations, bounded counts/frequencies, ordinal
  rubrics, durations, artifact criteria, conceptual/scenario performance,
  bounded objective indicators, consented-observer evidence, and minimal
  qualified attestations;
- keeps `unknown`, `not_observed`, `inconclusive`, `not_applicable`, and
  `deferred` distinct;
- keeps evidence direction and adverse outcome orthogonal: adversity is
  always retained and may require withholding or a safety stop, but does not
  become contradiction unless the snapshotted rule says so;
- represents support, independence, context, repetition, recency, transfer,
  provenance, consent, and qualification without unnecessary sensitive
  narrative;
- requires an explicit rule to normalize a typed value. The engine never
  assumes that a larger count, longer duration, or higher ordinal value is
  better;
- includes exact golden replay fixtures and a migration policy before any
  activation.

Existing v1 rows are never rewritten or up-converted. The v1 replay entry
point remains available, while a version dispatcher selects v1 or the new
typed evaluator from the immutable event version. A new assessment does not
silently reassign old evidence to the new assessment epoch.

## Consequences

Historical events remain replayable and unchanged. Later protocol families
can use evidence that fits their actual intervention instead of relabeling
friendship checkboxes.

M6B proves a software contract using synthetic fixtures. It does not add a
typed check-in UI, persist a new event type, convert the five legacy
protocols, or establish measurement validity. Those integrations remain
blocked until M6C and the representative Phase B content batch are reviewed.
