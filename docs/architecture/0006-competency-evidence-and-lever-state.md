# ADR 0006 — Keep protocol evidence, competency evidence, and lever state distinct

## Status

Accepted architectural boundary from M6A. The concrete M6B implementation
described below is proposed for owner and specialist review.

## Context

The current evidence event describes performance within one practice action.
The scoring engine then allocates eligible friendship evidence through the
parent competency's canonical lever weights into separate current lever
state. Treating those layers as interchangeable would make action completion
look like broad competency evidence and would obscure how a lever estimate
changed.

The 383-competency expansion needs a stable answer for baseline evidence,
direct competency evidence, transfer across contexts, and lever projection
before additional scoring can be activated.

## Decision

The architecture keeps five concepts separate:

1. immutable assessment baseline and its mass;
2. immutable, versioned protocol-performance evidence;
3. direct competency evidence and its transfer disposition;
4. evidence-only competency shadow state;
5. current lever state derived through the canonical competency-to-lever
   allocation.

Assessment v1.1 establishes lever baselines, not competency baselines. M6B
must not invent a neutral competency baseline or relabel a weighted
lever-derived estimate as direct competency observation. With no eligible
direct evidence, a competency shadow is `unknown`. A lever-derived competency
summary may later be used as clearly labeled routing context, but it cannot
seed direct competency state or feed back into lever scoring.

`GG-COMPETENCY-EVIDENCE-SHADOW-1.0` aggregates only replay-verified typed
evidence for one parent competency and one assessment epoch. It preserves
evidence success/failure mass, observed contexts, transfer status, and
withholding reasons. It does not claim mastery, psychometric validity, or a
production score.

Each typed event may produce at most one designated direct-competency
contribution. `GG-COMPETENCY-LEVER-SHADOW-1.0` may allocate that contribution
once through the parent's complete canonical mapping. Recommendation-target
levers are routing metadata and never replace that mapping. Protocol
performance and direct competency evidence may be two views of the same
immutable event, but they may not both be applied as separate lever
contributions.

Evidence remains pinned to the assessment epoch under which it was collected.
A newer assessment creates a new immutable lever baseline. Older evidence
remains replayable but is not silently carried forward; any future transfer
requires a separately reviewed, deduplicated contract.

Production eligibility is a separate result under
`GG-PRODUCTION-SCORE-ELIGIBILITY-1.0`. M6B shadow output cannot write
`LeverBaseline`, `LeverState`, `ScoreSnapshot`, recommendation order, or
activation state.

## Consequences

Completion cannot masquerade as mastery or broad competency change. An
assessment baseline cannot masquerade as direct competency evidence.
Recommendation-target levers remain a routing subset and are not confused
with the full canonical scoring allocation.

M6B can prove deterministic software behavior without establishing that the
evidence model is clinically, psychometrically, culturally, or
longitudinally valid. The pending measurement, accessibility, and
privacy/safety review in `ER-M6A-003` continues to block M6B acceptance and
mass authoring.
