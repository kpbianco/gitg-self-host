# Context and Personal OS foundation

## Scope

M6C-01 establishes `GG-CONTEXT-1.0` persistence and pure services. M6C-02 adds
the separate `GG-PERSONAL-OS-1.0` identity and Truth/Autopilot Audit
foundation. Neither batch adds a form, changes ordinary UI, ranks
recommendations, alters an assessment or score, authors a protocol, or
activates production scoring. Later M6C batches own priority, alternatives,
and the concise browser experience.

The additive, read-only readiness contract is
`GG-CONTEXT-READINESS-1.0`.

## Personal OS identity and audit contract

One `PersonalOSRevision` belongs to one authenticated user and one immutable
`AssessmentRun`. Reads and writes require that exact assessment epoch. A new
assessment has no Personal OS revision unless the user authors one; values are
never copied from an earlier epoch or derived from assessment answers,
orientations, archetypes, context, evidence, current lever state, or practice
history.

The five identity sections are `mission`, `principles`, `anti_goals`,
`twelve_month_direction`, and `priority_stack`. The four audit prompts are
`current_truth`, `autopilot_pattern`, `misalignment_or_fragmentation`, and
`deliberate_next_step`.

Each section uses the same four explicit states as context: `unknown`,
`not_applicable`, `deferred`, or `provided`. A non-provided state contains no
hidden value. Provided mission, direction, and audit responses are nonblank
text of at most 500 characters. Provided principles, anti-goals, and priority
stack are ordered lists of one to five unique nonblank items, each at most 160
characters. Ordering is authored meaning and is preserved.

Prompt and help definitions ask for minimal private detail and describe the
audit as provisional, descriptive, and user-authored. They do not diagnose,
assign personality destiny, shame, or rank morality. A mismatch is explicitly
not evidence of failure, deficient character, or diminished worth. The
contract computes no alignment, autopilot, personality, virtue, diagnostic,
or worth score.

## Personal OS snapshots and append-only writes

The pure builder rejects unknown versions, missing or extra sections, wrong
types, blank or over-bound values, duplicate list items, and hidden values
before persistence. Canonical UTF-8 JSON uses fixed section order plus sorted
object keys and compact separators; SHA-256 identifies unchanged semantic
input. The 64 KiB resource ceiling admits the complete legal UTF-8 payload,
including the worst-case JSON escaping permitted by the character/count bounds.

The snapshot contains only its contract/scope, assessment epoch stable ID,
and the nine private authored state/value entries. It excludes user identity,
Personal OS record UUIDs, timestamps, assessment answers, orientations,
archetypes, context, evidence, scores, practice history, feedback, and
unrelated narrative.

An unchanged retry returns the latest revision. Changed input appends the next
contiguous revision. Existing rows reject model save, queryset update,
bulk-update, and direct instance or queryset deletion; bulk creation is also
disabled so validation cannot be bypassed. The database protects user and
assessment foreign keys while revisions exist. A concurrent SQLite write
either commits a valid contiguous revision or returns an explicit retryable
conflict; it cannot leave a partial row.

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

Run the separate Personal OS readiness drill:

```bash
make personal-os-check
```

For a running instance, use the read-only verifier:

```bash
python manage.py verify_context_readiness
```

The verifier checks supported versions, ownership, scope, field/snapshot/hash
agreement, bounds, and contiguous revisions. Empty tables pass because context
is optional in this foundation.

`GG-PERSONAL-OS-READINESS-1.0` applies the same fail-closed approach to every
Personal OS row and accepts an empty optional table. Its summaries contain
only contract metadata, field IDs, counts, limits, and non-mutation flags; its
diagnostics do not print private authored values, snapshots, record IDs, or
user identity.

## Privacy and validation boundary

Context is private participant data stored in the local database and included
in normal database backups. M6C-01 adds no remote telemetry and does not add it
to existing minimized evidence or pilot-feedback exports. Context-specific UI,
export, deletion, retention, and participant consent behavior remain for later
reviewed batches.

Personal OS values are also private local reflection data and enter normal
database backups. M6C-02 does not add real participant or runtime-authored
values to evidence, pilot-feedback exports, logs, generated reports, telemetry,
recommendation inputs, score snapshots, or activation decisions. Synthetic
golden test fixtures are the deliberate exception. It adds no Personal OS export,
purge, deletion, or retention policy. Reverse migration requires a verified
backup and a separate retention decision if any participant Personal OS data
exists.

Automated checks establish schema, migration, deterministic snapshot, hashing,
transaction, isolation, and regression behavior. They do not establish that
the factor language or scales are accessible, culturally appropriate,
longitudinally useful, psychometric, clinical, specialist-approved, or
production-validated.

The same validation boundary applies to the Personal OS wording and audit.
Owner review of exact prompts and privacy, and later participant,
accessibility, cultural, safety, burden, longitudinal, clinical, and
psychometric review remain manual and unperformed by M6C-02 software checks.
