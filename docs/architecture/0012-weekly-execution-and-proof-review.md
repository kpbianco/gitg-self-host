# ADR 0012 — Weekly execution and proof review remain outside evidence creation

## Status

Accepted for implementation by owner direction on 2026-08-27.

## Context

Grounded Growth already stores a private Personal OS, computes context-aware
practice priority from explicit factors, runs one current practice, and
creates replayable evidence only from submitted check-ins. The missing
software link is a small weekly operating loop. Treating a plan or reflection
as proof would create a second, weaker scoring path; leaving proof open-ended
would make an immutable review change when later evidence arrives.

## Decision

Store weekly plans as append-only revisions scoped to one user, assessment
epoch, current sprint, stable action, and Monday-to-Sunday window. Store one
immutable review for a reviewable plan revision.

The review snapshot includes only verified evidence events for the exact
sprint and action, submitted after plan creation, inside the weekly window,
and at or before a frozen review timestamp. It derives a bounded outcome from
those events and records only categorical next-step and adjustment choices.

Personal OS text may render on authenticated owner-facing Personal OS and
weekly pages but is never analyzed, logged, exported through existing exports,
or copied into weekly snapshots.

## Consequences

- Replanning preserves history; identical retries are idempotent.
- Superseded plan revisions do not reappear as pending review targets.
- Later evidence cannot invalidate or rewrite a completed weekly review.
- No plan or review creates evidence, score state, a recommendation factor,
  practice completion, or mastery.
- Readiness output contains counts and versions only, never authored values,
  record hashes, user identity, or private context.
- M6H-01 needs automated software, browser, migration, and recovery
  verification only. Deferred human and specialist review stays separate.
