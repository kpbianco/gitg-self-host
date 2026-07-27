# ADR 0004 — Isolated private-pilot feedback

## Status

Proposed for M5A review.

## Context

The reviewed product can now be used in a private pilot, but product-friction
observations have a different meaning from developmental evidence. Reusing
check-ins or score inputs for usability feedback would contaminate evidence,
make recommendations respond to interface problems, and blur participant
consent.

Automatic analytics would also expand the deployment and privacy boundary.
The single-instance product does not need a remote event collector to learn
whether setup or check-in was understandable.

## Decision

M5A introduces `GG-PILOT-FEEDBACK-1.0` as a separate append-only model and
service:

- submission is optional and authenticated;
- timing uses participant-selected broad bands rather than automatic
  instrumentation;
- the service does not import or call assessment, evidence, scoring, ranking,
  completion, or recommendation services;
- records may identify a product surface by stable protocol ID but never
  create an evidence event or score snapshot;
- a deterministic allowlisted export excludes identity, IDs, exact
  timestamps, free text, private context, and all developmental data;
- no remote telemetry or external service is introduced.

The operator procedure is documentation rather than an administrative runtime
surface. Ordinary participants see only clear product-feedback language and
the local collection boundary.

## Consequences

Pilot usability can be reviewed without changing the developmental record.
The categorical export is easier to compare across sessions while carrying
less private material than raw comments.

The export is privacy-minimized, not anonymous. Free text remains in the local
database and requires normal backup/access protection. Append-only feedback
cannot be corrected in place through the UI; a later deletion/retention policy
would require a separate reviewed operational decision.

Feedback cannot become an applicability, ranking, evidence, or score input
without replacing this contract in a new milestone.
