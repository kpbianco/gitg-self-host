# ADR 0006 — Keep protocol evidence, competency evidence, and lever state distinct

## Status

Accepted architectural boundary for M6A; domain implementation is deferred to
M6B.

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

The architecture keeps four concepts separate:

1. immutable assessment baseline and its mass;
2. immutable, versioned protocol-performance evidence;
3. future direct competency evidence and transfer disposition;
4. current lever state derived through the canonical competency-to-lever
   allocation.

M6A records `canonical_lever_allocation: parent_competency_mapping` and an
explicit scoring policy for every migrated package, but adds no competency
state or new mathematics. M6B must define the pure domain types, accepted ADR
extensions, exact synthetic fixtures, replay, withholding, reversal, and
no-baseline-mutation tests before general activation.

## Consequences

Completion cannot masquerade as mastery or broad competency change.
Recommendation-target levers remain a routing subset and are not confused
with the full canonical scoring allocation.

M6A cannot claim full scoring coverage. It truthfully records which evidence
could become eligible, which remains shadow-only or non-scored, and which
questions still block implementation.
