# ADR 0005 — Canonical practice content and exact runtime projection

## Status

Accepted by the owner for M6A implementation.

## Context

The first five reviewed protocols lived as a large Python tuple in the
canonical importer. That was workable for a vertical slice but cannot support
383 individually authored packages, claim-level sources, risk review,
originality review, editorial state, or deterministic release governance.

Moving content must not silently change the five protocol IDs, fifteen
actions, user-facing behavior, or the frozen post-M4 configuration
fingerprint.

## Decision

`data/practices/release_manifest.yaml` is the canonical practice-content
release root. It explicitly enumerates versioned YAML packages, registries,
and offline JSON Schemas. The importer:

- validates the entire practice release before model writes;
- rejects unknown versions, unknown fields, unlisted packages, unsafe paths,
  duplicate IDs, and broken references;
- validates each parent competency, domain, and recommendation-target subset
  against the existing canonical curriculum and structured mapping;
- projects only the reviewed ORM fields into the runtime;
- requires the projection to retain fingerprint
  `274f7244630ed56d56a443a6a699399edade6c67fcf964237559e05b72368e35`.

Rich editorial, research, safety, adaptation, and future evidence-design
metadata remains source-only in M6A. No ORM migration or new protocol is
introduced.

## Consequences

Future authoring can be reviewed as data rather than application code, while
the current runtime remains exactly compatible. The release has a separate
content hash; `CurriculumVersion.source_hash` continues to identify only the
curriculum, model, and mapping inputs and therefore remains unchanged.

The five migrated packages are labeled `projected_legacy`, not falsely
presented as source-complete or full-library release candidates. The remaining
378 competencies remain explicit unauthored ledger rows.
