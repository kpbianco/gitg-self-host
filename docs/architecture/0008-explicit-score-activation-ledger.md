# ADR 0008 — Score activation is an explicit release decision

## Status

Accepted by the owner for M6A implementation.

## Context

Protocol availability, editorial completeness, evidence capture, shadow
testing, and production score mutation are different decisions. A content
author should not be able to activate scoring by changing one field inside a
protocol package.

The existing reviewed boundary permits score mutation only for
`PRACTICE-FRIENDSHIP-01`.

## Decision

`data/practices/registries/activation_ledger.yaml` is the canonical activation
join. Each protocol has one entry identifying its scoring policy, activation
status, approved contract, decision reference, and shadow-test status.

The runtime `score_active` Boolean is derived from that ledger. Validation
requires exact ledger coverage and refuses a second score-active protocol
under the M6A contract. The protocol package records its scoring disposition
but cannot independently authorize mutation.

`GG-CURRICULUM-EXPANSION-READINESS-1.0` is additive: it invokes the unchanged
`GG-PILOT-READINESS-1.0` verifier, validates the content release and generated
reports, and compares the seeded runtime with the frozen projection.

## Consequences

Availability no longer implies scoring, and an activation change produces a
small, explicit, reviewable diff. New activation still requires reviewed
evidence semantics, deterministic replay, exact fixtures, safety approval,
and a separately authorized contract.

M6A leaves friendship active and the other four protocols shadow-only and
score-inactive.
