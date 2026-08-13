# Context and defer-state foundation

## Scope

M6C-01 establishes `GG-CONTEXT-1.0` persistence and pure services. It does not
add a form, change ordinary UI, rank recommendations, alter an assessment or
score, author a protocol, or activate production scoring. Later M6C batches
own the concise Personal OS experience and the separately versioned priority
formula.

The additive, read-only readiness contract is
`GG-CONTEXT-READINESS-1.0`.

## Ownership and revisions

`AssessmentContext` stores season and capacity for one user and one immutable
`AssessmentRun`. `PracticeContext` stores candidate factors for one user, the
same assessment epoch, and one stable `PracticeProtocol`. A protocol must have
a canonical parent in that assessment epoch's curriculum.

Records are append-only revisions. Repeating an unchanged canonical input is
idempotent and returns the existing latest revision. Changed input appends the
next contiguous revision. Every lookup requires the user and an explicit
assessment run; there is no fallback that copies context from an older run to
a reassessment.

## Value states

Every factor uses one explicit state:

| State | Meaning | Stored value |
| --- | --- | --- |
| `unknown` | Not known or not collected | None |
| `not_applicable` | The factor does not apply here | None |
| `deferred` | The answer or candidate is intentionally postponed | None |
| `provided` | The user supplied the bounded value | Required |

Unknown, not applicable, and deferred are never encoded as zero. A missing
factor is malformed input rather than an implicit neutral or favorable value.

## Factor contracts

Ordinal values are integers from 0 through 4. They are storage inputs only in
M6C-01; no numeric priority meaning or favorable direction is assigned yet.

| Factor | Scope | Type | Plain-language meaning |
| --- | --- | --- | --- |
| Season | Assessment epoch | Category | The broad kind of season the person says they are in; context, not worth or performance |
| Capacity | Assessment epoch | Ordinal 0–4 | Self-reported room for an additional bounded practice, without judging effort, character, or potential |
| Applicability | Practice candidate | Ordinal 0–4 | Fit with the present role and situation; N/A creates no deficit |
| Importance | Practice candidate | Ordinal 0–4 | Current importance among competing goods; not moral worth |
| Readiness | Practice candidate | Ordinal 0–4 | Present readiness to attempt the bounded practice; low readiness is not failure |
| Urgency | Practice candidate | Ordinal 0–4 | User-reported time sensitivity; not crisis, obligation, or worth |
| Opportunity/resources | Practice candidate | Ordinal 0–4 | Available opportunity, support, access, and material resources |
| Burden | Practice candidate | Ordinal 0–4 | Expected time, access, effort, emotional, relational, or material load |

Season categories are `foundation`, `expansion`, `maintenance`, `transition`,
`recovery`, `caregiving`, `constraint`, and `other`. They are descriptive and
have no ordering. These definitions and categories require later
accessibility, cultural, and participant-language review.

## Defer / not now

A practice candidate has a separate `considering` or `deferred` disposition.
A deferred disposition requires at least one candidate factor in the
`deferred` state and one reason category: capacity, resources, timing, safety
or access, role or fit, competing priority, needs support, or user choice. An
optional review horizon is an integer from 1 through 366 days. A horizon is a
review prompt input, not an automatic timer, expiration, score event, or
negative observation.

Defer metadata is invalid on a considering candidate. Deferral does not write
or reduce a baseline, current estimate, confidence, evidence mass, need score,
need rank, completion state, or worth-related value.

## Canonical snapshots and hashes

Pure builders require the exact factor set and reject missing, extra,
unsupported, mismatched, Boolean-as-integer, or out-of-bound input. The
canonical snapshot contains:

- contract version and scope;
- assessment stable ID;
- protocol stable ID for candidate context;
- every factor in fixed contract order with explicit state and value;
- candidate disposition, reason, and review horizon.

It excludes database UUIDs, user identity, timestamps, private narrative,
assessment answers, evidence, and score state. UTF-8 JSON with sorted keys and
compact separators is hashed with SHA-256. Unchanged semantic input therefore
has an unchanged snapshot and hash; a different assessment epoch has a
different hash.

Snapshots are limited to 4,096 encoded bytes. The service validates all bundle
inputs before writing and uses one database transaction. A malformed candidate
rolls back the whole bundle.

## Migration, readiness, and rollback

Migration `0008_assessmentcontext_practicecontext` creates only the two context
tables, constraints, indexes, and foreign keys. It has no data migration,
backfill, canonical seed, or alteration of existing tables. Normal reverse
migration drops these M6C-01 records; back up the database first and do not
reverse after a later migration depends on them.

Run the isolated readiness drill:

```bash
make context-check
```

For a running instance, use the read-only verifier:

```bash
python manage.py verify_context_readiness
```

The verifier checks supported versions, ownership, scope, field/snapshot/hash
agreement, bounds, and contiguous revisions. Empty tables pass because context
is optional in this foundation.

## Privacy and validation boundary

Context is private participant data stored in the local database and included
in normal database backups. M6C-01 adds no remote telemetry and does not add it
to existing minimized evidence or pilot-feedback exports. Context-specific UI,
export, deletion, retention, and participant consent behavior remain for later
reviewed batches.

Automated checks establish schema, migration, deterministic snapshot, hashing,
transaction, isolation, and regression behavior. They do not establish that
the factor language or scales are accessible, culturally appropriate,
longitudinally useful, psychometric, clinical, specialist-approved, or
production-validated.
