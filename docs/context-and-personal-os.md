# Context and Personal OS foundation

## Scope

M6C-01 establishes `GG-CONTEXT-1.0` persistence and pure services. M6C-02 adds
the separate `GG-PERSONAL-OS-1.0` identity and Truth/Autopilot Audit
foundation. M6C-03 adds backend-only `GG-CONTEXT-PRIORITY-1.0` ranking and
alternatives. M6C-04 exposes those unchanged contracts through one concise
authenticated browser journey and an additive deployment/pilot-readiness gate.
It alters no assessment or score, authors no protocol, persists no ranking
result, analyzes no Personal OS text, and does not expand production scoring.

The additive, read-only readiness contract is
`GG-CONTEXT-READINESS-1.0`.

## Context-priority contract

One result belongs to one explicit user-owned assessment epoch, its latest
verified assessment-context revision, and exactly one latest verified
practice-context revision for every supplied active canonical candidate. The
service validates contiguous revisions, snapshot hashes, supported versions,
canonical parents and full weights, recommendation-target subsets, active
manifest projection, stable-ID uniqueness, and the unchanged
`GG-NEED-RANKING-1.0` base priority before calling the pure engine.
It reads mutable epoch inputs in one transaction, using the assessment-run row
lock where supported and one SQLite read snapshot, so a concurrent context or
score-state transition cannot create a mixed-time result.

No assessment-context row means that a context-aware result cannot be built. A
verified row with non-provided capacity instead yields a structured
`missing_context` ranking. Season remains descriptive and appears in the
structured result, but it has no multiplier, ordering, or tie effect.

A candidate is numeric only when its disposition is `considering` and all six
practice factors plus assessment capacity are explicitly `provided`. The
precedence is `not_applicable`, then `deferred`, then `missing_context`, then
eligible: applicability N/A therefore remains distinct even if another factor
is deferred. N/A on another required factor is missing context. Withheld
candidates have no context-priority value and are never treated as zero.

For every provided ordinal `x`, the multiplier is exactly `Decimal(x) / 4`.
Burden is inverted as `1 - Decimal(burden) / 4`. The final calculation is:

```text
context priority = base priority
  × applicability × importance × readiness × urgency
  × opportunity/resources × capacity × inverse burden
```

The product is quantized half-up once to four decimal places. Explicit zero is
a valid supplied value and may produce an eligible zero priority. There is no
floor, imputation, rescaling, learned weight, Personal OS/free-text analysis,
or personality/orientation modifier. Eligible candidates sort by descending
context priority, descending unchanged base priority, then stable protocol ID.

An alternative request must identify one supplied N/A or deferred candidate
and a matching reason. It returns the highest-ranked distinct eligible member
of that supplied cohort, or `no_eligible_alternative`; it never expands the
cohort or returns the withheld source.

Canonical compact UTF-8 JSON contains algorithm and dependency versions,
assessment/protocol stable IDs, base and context priorities, factor-state and
multiplier breakdowns, dispositions, allowlisted explanation codes,
alternative source/target IDs, and exact context hashes. It excludes identity,
database record IDs, timestamps, Personal OS/audit text, assessment answers,
private narrative, evidence payloads, and unrelated participant data.

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

Run the context-priority readiness drill:

```bash
make context-priority-check
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

`GG-CONTEXT-PRIORITY-READINESS-1.0` replays a committed synthetic cohort,
derives the current active projection and activation state from canonical
source, verifies the M6C-03 five-protocol baseline remains represented with
the reviewed friendship activation still present, and accepts empty optional
context tables. When persisted context exists, drift fails with diagnostics
that do not print values, snapshots, identity, or record IDs.

M6C-04 adds the read-only aggregate `GG-M6C-PILOT-READINESS-1.0`. It invokes
the six existing pilot, curriculum-expansion, competency-evidence, context,
Personal OS, and context-priority readiness contracts; verifies exact
definition IDs, five active canonical protocols, friendship-only activation,
and registered authenticated browser routes; accepts empty or valid optional
state; and writes nothing. Its summaries and failures never print authored
values, private snapshots, user identity, or record IDs. This aggregate is
additive and does not replace `GG-PILOT-READINESS-1.0` or any governance or
human review gate.

## Concise authenticated browser journey

The `/personal-os/` entry point and
`/personal-os/practices/<slug>/context/` practice-review route are
authenticated and use only the signed-in owner's latest assessment run. A user
without an assessment is redirected to the assessment journey. A new
assessment epoch displays no copied or inferred Personal OS, season, capacity,
or practice-context values from an earlier run.

The page progressively discloses the exact five identity sections, exact four
descriptive audit prompts, assessment season/capacity, and one active
manifest-projected practice's context at a time. Each value can remain
unknown, N/A, or deferred. Ordinal inputs have no preselected numeric default,
and the page adds no completion percentage, alignment/autopilot score,
diagnosis, moral rank, shame, streak, or pressure language.

Personal OS and assessment-context submissions use the unchanged append-only
services. Valid changes append one revision, unchanged retries are idempotent,
and malformed or stale-epoch requests write nothing. POSTs use CSRF and
POST-redirect-GET. A retryable SQLite contention response is bounded and does
not echo a private value.

Practice context has three explicit modes:

1. provide all six 0–4 applicability, importance, readiness, urgency,
   opportunity/resources, and burden factors;
2. mark applicability not applicable; or
3. defer by naming the deferred factor, categorical reason, and optional
   1–366-day review horizon.

Unknown values remain visibly unknown. No factor is inferred from Personal OS
text, assessment answers, personality, orientation, archetype, pilot feedback,
setup/check-in data, or another factor.

The presenter calls `GG-CONTEXT-PRIORITY-1.0` with only active canonical
practices that have a latest verified revision in the current assessment
epoch. Any result is labeled as a ranking among those explicitly reviewed
practices; an unreviewed practice is not treated as unfavorable and the cohort
is never expanded silently. The reproducible result is not persisted.

With no current-epoch context, the existing profile recommendation IDs, base
priorities, display order, reasons, and practice behavior remain exact. Missing
capacity or no eligible reviewed candidate is described as missing structured
context, not presented as context-aware fallback, and never converted to zero.
With complete capacity and at least one eligible reviewed candidate, home,
practice-list, and recommendation surfaces display a small set in exact engine
order. Fixed allowlisted plain-language explanations distinguish provisional
need from current context fit without raw backend names or false precision.

An explicitly N/A or deferred reviewed candidate may request an alternative
through the unchanged M6C-03 contract. The response is the highest-ranked
distinct eligible practice from only that reviewed cohort, or an explicit
no-eligible-alternative state. It does not return the source practice, invent
context, start a practice, author a protocol, or mutate evidence, completion,
score, or activation state.

## Privacy and validation boundary

Context is private participant data stored in the local database and included
in normal database backups. M6C-04 adds authenticated collection and
privacy-minimized recommendation presentation, but no remote telemetry and no
context data in existing minimized evidence or pilot-feedback exports. It adds
no dedicated context export, purge, retention automation, urgent-support
monitoring, participant-release approval, or new account/assessment deletion
guarantee.

Personal OS values are also private local reflection data and enter normal
database backups. M6C-04 renders authored values only on the authenticated
Personal OS surface for their owner. They do not enter context-priority inputs
or explanations, other recommendation surfaces, messages, logs, URL/query
data, generated reports, telemetry, existing exports, evidence/score
snapshots, or activation decisions. Conspicuously synthetic fixtures and the
Personal OS surface's own synthetic browser artifact are the deliberate test
exceptions. The page asks for minimal detail and explains these boundaries
before collection. The batch adds no Personal OS export, purge, deletion, or
retention policy. Reverse migration still requires a verified backup and a
separate retention decision if participant Personal OS data exists.

Automated checks establish schema, migration, deterministic snapshot, hashing,
transaction, isolation, and regression behavior. They do not establish that
the factor language or scales are accessible, culturally appropriate,
longitudinally useful, psychometric, clinical, specialist-approved, or
production-validated.

The same validation boundary applies to the Personal OS wording, audit,
context factors, explanations, and browser flow. Owner review of exact prompts,
privacy, partial-cohort language, and retained synthetic desktop/mobile
artifacts remains required. Participant usefulness and accessibility-population,
cultural, safety, burden, longitudinal, clinical, and psychometric validation
are not established by M6C software, browser, hosted-CI, or Compose checks.
