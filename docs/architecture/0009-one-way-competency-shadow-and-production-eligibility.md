# ADR 0009 — One-way competency shadow and separate production eligibility

## Status

Proposed for M6B owner and specialist review.

## Context

Typed protocol evidence, direct competency evidence, and lever state can be
represented by the same underlying event without being interchangeable. If a
lever-derived competency estimate is fed back through the same competency's
lever mapping, or if protocol and competency views are both applied, the
system creates circularity or double counting.

Evidence capture, deterministic shadow behavior, and permission to mutate a
production score are also separate decisions. M6B must test future evidence
families without expanding the friendship-only activation boundary.

## Decision

`GG-COMPETENCY-EVIDENCE-SHADOW-1.0` creates an evidence-only, non-persisted
competency projection from replay-verified `GG-TYPED-EVIDENCE-1.0` results.
It has no assessment-derived competency baseline. Zero eligible evidence
produces an explicit unknown state.

`GG-COMPETENCY-LEVER-SHADOW-1.0` consumes each designated competency
contribution at most once and projects it one way through the complete
canonical parent mapping. It:

- rejects duplicate immutable event keys;
- rejects missing, duplicate, malformed, or non-normalized lever weights;
- never consumes a lever-derived competency estimate;
- never substitutes the recommendation-target subset for the canonical
  mapping;
- retains unknown, inconclusive, policy-ineligible, adverse, and reversed
  events with explicit withholding reasons;
- produces the same final projection regardless of input order;
- restores the exact starting projection when an active event is reversed.

`GG-PRODUCTION-SCORE-ELIGIBILITY-1.0` evaluates eligibility separately. A
production update requires all of the following:

- an executable scoring policy satisfied by the evidence and provenance;
- a stable parent competency and valid canonical mapping;
- sufficient replay-verified evidence under the snapshotted rules;
- available assessment baseline mass for every affected lever;
- no blocking risk, source, specialist-review, or activation-ledger gate;
- an explicitly approved production contract and active ledger entry.

Passing the typed evaluator or either shadow projection is necessary but not
sufficient. M6B keeps every new typed path production-ineligible and leaves
`PRACTICE-FRIENDSHIP-01` as the only score-active protocol under the unchanged
v1 contracts. Its production eligibility is pinned by
`f7639a0c623f1baac9469f34fe49ca9e2eb0be8fc1c616ab662996b2e90bf2bf`,
which includes the exact three action IDs, sequences, v1 evidence rules,
targets, versions, and full parent allocation.

## Consequences

M6B can test competency and lever effects without writing `LeverState`,
`ScoreSnapshot`, recommendation order, or activation data. Existing
`GG-SCORING-SHADOW-1.0`, `GG-SCORE-STATE-1.0`, and
`GG-NEED-RANKING-1.0` behavior remains unchanged.

The contract prevents software circularity and duplicate application. It
does not prove that an intervention, evidence rule, competency estimate, or
lever mapping is psychometrically or longitudinally valid. The pending
`ER-M6A-003` specialist review blocks acceptance and mass authoring.
