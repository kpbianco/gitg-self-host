# ADR 0010 — Representative typed protocols remain source-only

## Status

Accepted for M6D-01 implementation; content and source review remain pending.

## Context

The first representative Phase B cohort must prove that behavioral, artifact,
skill-rehearsal, and audit/redesign packages can carry exact typed evidence
rules without changing the five-protocol runtime or treating software replay as
measurement validation. The existing `typed-evidence-rules-v1` materializer is
pure and has no ORM or browser integration.

## Decision

M6D-01 adds exactly four individually authored draft packages for competencies
`08.06`, `09.12`, `10.02`, and `13.02`. Each package is inactive,
`runtime_projection: none`, `SP-SHADOW-ONLY`, and score-inactive in the
activation ledger.

An action may use `typed-evidence-rules-v1` only when:

- every action in its package uses that same rule version;
- the package observation version matches the action rules;
- an adjacent immutable identity names the exact protocol, action, parent
  competency, and scoring policy;
- the package is inactive and cannot enter the ORM runtime projection; and
- the existing typed materializer accepts every explicit normalization rule.

The identity wrapper belongs to canonical source content, not the typed
algorithm. This keeps `GG-TYPED-EVIDENCE-1.0` and historical materialized
snapshots unchanged while preventing a source rule from being replayed under a
different package identity.

Generated reports and readiness distinguish the expanding source catalog from
the frozen runtime. Synthetic fixture replay is static and shadow-only; it does
not persist a typed event or authorize production scoring.

## Consequences

The canonical catalog contains nine packages and twenty-nine source actions,
while seeding still creates exactly five runtime protocols and fifteen runtime
actions. The legacy projection hash and friendship-only score activation stay
unchanged. The four drafts remain blocked from release-candidate, source-
complete, M6B-accepted, participant, specialist, mastery, or production claims.
