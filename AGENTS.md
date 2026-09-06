# AGENTS.md — Grounded Growth

## Mission
Build a self-hosted, evidence-oriented guided-development application. The product converts an assessment-derived developmental need into a bounded, concrete real-world practice without exposing internal curriculum databases to the user.

## Product boundary
- Notion is an internal curriculum/content studio, not the consumer runtime.
- The application recommends executable **Practice Protocols**, not abstract competencies.
- Completion is never equivalent to mastery.
- Human dignity is never scored.
- Personality/orientation changes framing and tie-breaking only; it does not determine worth or obligation.
- Historical dynamic score updates use the reviewed M3A/M3B mathematics and
  remain immutable. Decision 053 prospectively replaces event-level mutation
  with assessment-composite priority and explicit human-closeout completion
  credit for new scoring-version sprints. The activation ledger still makes
  the complete 383-protocol catalog available.
- M6 is an owner-authorized, multi-PR expansion toward individually authored
  packages for all 383 competencies. Coverage does not authorize boilerplate,
  score activation, or a claim of universal, clinical, or psychometric
  validity.
- The product is becoming a guided life OS for people who may be highly
  driven yet misdirected, fragmented, or running on autopilot. Assessment,
  orientations, and archetypes are diagnostic and framing inputs—not the
  headline, destiny, or measure of worth.
- The intended path connects a concise Truth/Autopilot Audit with mission,
  principles, anti-goals, current season and capacity, a priority stack,
  twelve-month direction, weekly execution, and proof-based review. Ordinary
  users should see a small context-fit set of next practices, never a
  383-item encyclopedia or giant worksheet.

## Canonical source hierarchy
Use these files in priority order:
1. `docs/PROJECT_HANDOFF.md`
2. `docs/PRODUCT_DECISIONS.md`
3. `data/practices/release_manifest.yaml` and its explicitly listed content
4. `data/curriculum/ideal_person_curriculum_v2_pluralist_full_scope.yaml`
5. `data/model/grounded_growth_model_v1.json`
6. `data/model/competency_lever_mapping_v1.csv`
7. `data/assessment/v1.1_bundle/`
8. `docs/pilot/PILOT_002_FINDINGS.md`
9. `legacy/` only for provenance and design research; do not treat it as canonical implementation data.

## Implemented initial milestone
Milestone 1 validates the UX with static scores:
- import Pilot 002 profile;
- take assessment v1.1 or import a supported share code;
- show a concise working profile;
- recommend one bounded practice;
- provide a setup wizard;
- provide a compact evidence check-in;
- provide a final review;
- do **not** mutate mastery or confidence.

A review may show a clearly labeled hypothetical score-impact preview, but M1
currently saves no preview and no score impact.

M2A adds versioned, immutable event-level evidence classification under the
contract in `docs/evidence-contract.md`. It may calculate protocol performance,
quality, independence, context breadth, repetition, contradiction, and base
event mass. It must not allocate that mass to levers or mutate any profile
score.

M2B adds auditability around those unchanged events: an authenticated
per-user ledger, a privacy-minimized deterministic export, strict read-only
replay verification, and synthetic calibration fixtures. It does not add a
new evidence algorithm, task-to-lever allocation, or profile mutation.

M3A adds `GG-SCORING-SHADOW-1.0`: exact or conservatively reconstructed
assessment mass, an explicit stable practice-to-competency link, canonical
structured task weights, direction-aware posterior projection, and a clearly
labeled profile preview. It is read-only. It must not create current score
state, snapshots, or dynamic recommendations.

M3B activates that exact reviewed mathematics as `GG-SCORE-STATE-1.0`.
Assessment baselines remain immutable; current lever state and full
before/after snapshots are separate. Evidence processing is atomic,
idempotent, replay-verified, rebuildable, and reversible through an append-only
audit transition. `GG-NEED-RANKING-1.0` reproduces assessment v1.1's
provisional need function and ranks active protocols from canonical structured
weights. It does not invent applicability, importance, readiness, urgency, or
opportunity values that the product does not collect.

Implement one complete protocol first: `Deepen One Existing Friendship`.
Create inactive placeholders for four others:
- Schedule Non-Instrumental Play
- Practice Emotional Cue Detection
- State and Maintain One Boundary
- Complete an Attention-Presence Experiment

## Binding application stack
- Current supported stable Django and Python.
- Django templates with ordinary local CSS and small amounts of vanilla JavaScript.
- Locally bundled HTMX only when it materially improves an interaction.
- SQLite through the Django ORM.
- Gunicorn.
- pytest, Ruff, and Playwright.
- One application service in Docker Compose.

Do not introduce React, Next.js, a separate frontend or API service,
PostgreSQL/MariaDB, Redis, Celery, a message queue, Kubernetes, a reverse proxy,
externally hosted assets, live Notion synchronization, or microservices for M1.
There must be no Node.js server at runtime.

The accepted rationale is recorded in
`docs/architecture/0001-django-monolith-and-sqlite.md`.

## Engineering rules
- Keep domain, import, recommendation, and eventual scoring logic outside
  Django views and templates.
- Stable IDs are authoritative; never join canonical entities by display text.
- Store curriculum and algorithm version metadata.
- Every eventual scoring update must be deterministic, auditable, reversible, and explainable.
- M3A shadow projection must use only replay-verified submitted events tied to
  the same assessment run. Inconclusive and legacy direction-unknown events
  remain visible but are withheld from its posterior.
- M3B current state must reproduce the accepted M3A projection exactly.
  Every process, reversal, initialization, and repair must retain immutable
  hashed before/after state and a versioned active-event set.
- `LeverBaseline` remains the assessment record. Never overwrite it with
  current evidence-informed state.
- `GG-COMPOSITE-CLOSEOUT-SCORING-1.0` is additive and prospective. It derives
  family, domain, and competency starting estimates from immutable assessment
  data, but those projections award no completion credit and must be labeled
  assessment-derived rather than directly measured.
- New composite-version check-ins create replayable evidence but no production
  completion-credit update. Only an explicit human final closeout may create a
  closeout credit event and composite state transition.
- Composite relationship allocation is exactly 50 percent canonical mapping
  plus 50 percent equal mapped-lever share. Action units are equal in v1;
  minimum closeout earns 0.75 and all defined actions earn 1.00. Repeated
  attempts aggregate by maximum active credit, never by sum.
- Preserve `GG-SCORE-STATE-1.0`, historical `LeverState`, `EvidenceEvent`, and
  `ScoreSnapshot` replay exactly. Do not migrate old event mass into closeout
  credit or silently convert an in-flight legacy sprint.
- Every canonical protocol is score-activated by the M6F activation ledger. A
  required baseline with unavailable mass still fails closed and requires
  reassessment.
- `GG-PILOT-FEEDBACK-1.0` is product-usability data only. Never route it into
  assessment, evidence, scoring, ranking, completion, orientation, or
  archetype logic.
- Do not add automatic timing, browser analytics, session recording, tracking
  pixels, or remote telemetry under the pilot-feedback contract.
- Assessment calibration reuse requires the latest explicit per-run
  `GG-ASSESSMENT-CALIBRATION-CONSENT-1.0` revision. Ordinary assessment use and
  the Pilot 002 seed never imply participation. Withdrawal excludes a run from
  future exports without changing the owner's private assessment history.
- The calibration export is sensitive pseudonymous data, not anonymous data.
  Keep identity, exact timestamps, share codes, free text, private context,
  developmental history, and derived profile outputs outside its allowlist;
  never upload it automatically or silently overwrite an existing copy.
- Calibration analysis must consume only an exact, hash-verified M6I-04 export.
  It must not query the application database, use a network service, infer
  uncollected inputs, or emit participant rows, pseudonyms, raw responses, raw
  timing, exact timestamps, identity, share codes, free text, private context,
  developmental history, or derived profile outputs.
- Suppress nonzero aggregate cells below five. The 30-participant descriptive
  and linked-retest thresholds are software workflow thresholds, not evidence
  or validation thresholds. Every calibration evidence axis remains open and
  `completed_axes` remains zero until qualified analysis and separate human
  review truthfully establish it.
- Never infer missing task-to-lever links from display strings at runtime.
- Practice packages, registries, schemas, and the activation ledger under
  `data/practices/` are the canonical protocol source. Do not restore a
  competing Python-dictionary catalog.
- Validate a complete practice release and its curriculum mapping before
  database writes. Keep its content hash separate from
  `CurriculumVersion.source_hash`.
- Runtime score activation derives only from the explicit activation ledger.
  Availability, editorial completeness, evidence capture, and shadow testing
  do not imply score mutation.
- Preserve `practice-observation-v1` for historical replay. New Boolean,
  count, ordinal, duration, artifact, conceptual, observer, objective, or
  qualified evidence requires a new typed contract and exact fixtures.
- `GG-TYPED-EVIDENCE-1.0` and `typed-evidence-rules-v1` are the production
  typed evidence path for the M6F catalog. Version dispatch must fail closed, typed values
  require explicit normalization rules, and free text, artifact contents, and
  sensitive observer/qualified-review narrative are never opaque score input.
- Assessment v1.1 provides lever baselines, not competency baselines.
  `GG-COMPETENCY-EVIDENCE-SHADOW-1.0` is evidence-only and unknown when no
  eligible direct evidence exists. Never feed a lever-derived competency
  summary back into direct competency state.
- `GG-COMPETENCY-LEVER-SHADOW-1.0` may apply one designated competency
  contribution per immutable event through the full canonical parent mapping.
  Reject duplicate event keys; do not count protocol performance and direct
  competency evidence twice; do not substitute recommendation-target levers.
- `GG-PRODUCTION-SCORE-ELIGIBILITY-1.0` is separate from capture and shadow
  output. Passing typed evidence or shadow fixtures never changes production
  activation.
- Regenerate and review the 383-row coverage, domain/lever, risk, and
  originality reports, plus the research-gap registry, whenever canonical
  practice content changes.
- Validate all imported weight sums and IDs.
- Do not silently normalize malformed data; fail with actionable diagnostics.
- Add tests before enabling any score mutation.
- Every submitted M2 check-in must create its evidence event atomically.
  Event snapshots must contain enough structured input and versioned rules for
  exact replay without duplicating private free text.
- New submitted check-ins require a real attempted action. Observation fields
  must belong to the selected action's reviewed primary/supporting marker set.
  Drafts remain available before an action occurs; do not rewrite historical
  events to apply this prospective M5B gate.
- Use Django migrations; keep ORM code portable to PostgreSQL without adding a
  PostgreSQL service in M1.
- The deployed SQLite database is `/data/grounded_growth.sqlite3`; enable a
  busy timeout and WAL where supported.
- Require authentication for all application pages except login, health, and
  required static assets.
- Bundle every browser asset locally.

## UX rules
- Do not show 37 levers or 383 competencies on the home page.
- Do not show raw Notion/database property names to the user.
- Avoid giant tables, long bullet-form worksheets, gamified streak pressure, personality stereotypes, or self-help hype.
- A user should start a recommended practice in under five minutes without inventing the intervention.
- Evidence check-ins should take under two minutes.
- Clearly distinguish practice completion from mastery.

## Definition of done for each batch
Before asking for review:
1. Run Ruff formatting/linting, Django system checks, pytest, and relevant
   Playwright tests.
2. Run `make pilot-check` against an isolated fresh database.
3. Run `make curriculum-check`; it must preserve the independent pilot gate,
   exact 383-protocol/1,151-action projection, deterministic generated reports,
   and zero uncovered competencies.
4. For M6B and later, run `make competency-evidence-check`; it must preserve
   exact v1 replay, validate the additive typed/shadow software contracts, and
   report specialist acceptance separately from software readiness.
5. Run `make compose-smoke` in a Docker-capable environment. It must exercise
   the mapped host port, health check, login, migrations, idempotent seed,
   evidence/score/readiness replay, all applicable readiness contracts, container
   recreation, volume persistence, backup/restore, and clean shutdown.
6. Require the aggregate GitHub **Pilot readiness gate**, then review its
   desktop/mobile browser artifact for a pilot-bound merge.
7. Audit changed files against this document and `docs/PROJECT_HANDOFF.md`.
8. Report failed or unverified acceptance criteria plainly.
9. Do not claim all-catalog dynamic scoring works until legacy, typed, mixed,
   reversal, rebuild, withholding, and baseline-immutability paths pass.

## Current implementation boundary
M1A established the runtime, persistent schema, authentication, canonical
importer, golden assessment boundary, and Pilot 002 profile. M1B integrates the
canonical assessment and completes the friendship recommendation, setup,
sprint, draft/submitted check-in, pause/resume/stop, completion, and review
experience.

M1 through M3B and M4A through M4E are reviewed and merged; Decisions 023–038
are accepted.
M3B may update only separate current lever state from replay-verified
friendship evidence. Baselines, raw self-report, orientations, archetypes,
completion, and human worth remain unchanged.

M4A activated **Schedule Non-Instrumental Play** as the second complete
protocol and establishes protocol-configured setup, check-in, and completion
copy. It was score-inactive at that historical milestone.
M4B activated **Practice Emotional Cue Detection** as the third complete
protocol. It is anchored to canonical nonverbal communication competency
`16.03`, treats cues as uncertain hypotheses, requires direct clarification,
and was score-inactive at that historical milestone.
M4C activated **State and Maintain One Boundary** as the fourth complete
protocol. It is anchored to canonical competency `11.10`, limits the
intervention to a safely stateable low-stakes situation, distinguishes a
boundary from coercion or punishment, requires both a direct statement and
proportionate follow-through, and was score-inactive at that milestone.
M4D activated **Complete an Attention-Presence Experiment** as the fifth
complete protocol. It is anchored to canonical competency `08.02`, compares
one usual and one changed condition without productivity scoring or
surveillance, preserves accessibility supports, requires a repeat within seven
days, and was score-inactive at that milestone.
The initial five-protocol library is now complete. Further protocol-library
expansion must proceed in separately authorized, reviewable batches. Adding a protocol to the library
does not authorize score activation. Any newly score-active protocol requires
a stable canonical parent competency, validated structured weights, reviewed
evidence semantics, and golden coverage before it may affect current state or
recommendation order.

M4E is the post-M4 pilot-readiness closeout. It adds the read-only
`GG-PILOT-READINESS-1.0` inventory/replay contract, an isolated
`make pilot-check`, an aggregate GitHub gate over quality, Playwright, and
Compose, retained desktop/mobile walkthrough artifacts, and keyboard/mobile
hardening. It must not add protocols or expand score activation.

M5A adds a bounded operator guide and optional, authenticated, append-only
`GG-PILOT-FEEDBACK-1.0` product-usability records. Setup/check-in timing is
participant-selected in broad bands; no activity is timed automatically. The
`grounded-growth-private-pilot-export-v1` allowlist excludes identity, record
IDs, exact timestamps, free text, private context, assessment data, evidence,
and scores. Submission, viewing, and export must leave assessment, evidence,
score state, recommendation order, completion, orientations, and archetypes
unchanged.

M5A must not add remote telemetry, new protocols, new score activation, or any
path from pilot feedback into developmental state without separate
authorization.

M5B is a narrow closeout of the first owner-operated session. It scopes
feedback questions to the selected journey stage, scopes observation prompts
to the selected action, requires a real attempt before evidence submission,
and provides an explicit operator-only pilot-feedback purge. Existing
feedback, check-ins, evidence, and score transitions remain immutable and
replayable; no algorithm or activation boundary changes.

M6A establishes `GG-PRACTICE-CONTENT-1.0` and the additive
`GG-CURRICULUM-EXPANSION-READINESS-1.0` foundation. Five `projected_legacy`
packages reproduce the exact M4 runtime fingerprint from canonical YAML.
Generated control reports explicitly show 5/383 package coverage and 378
unauthored competencies. Risk, scoring-policy, source, protocol-family, expert
review, research-gap, and activation registries are source-only governance;
M6A adds no migration, protocol, action, UI, evidence mathematics, or score
activation.

M6B software introduces pure
`GG-TYPED-EVIDENCE-1.0` evaluation,
`GG-COMPETENCY-EVIDENCE-SHADOW-1.0`,
`GG-COMPETENCY-LEVER-SHADOW-1.0`, and
`GG-PRODUCTION-SCORE-ELIGIBILITY-1.0`, guarded by additive
`GG-COMPETENCY-EVIDENCE-READINESS-1.0`. It adds no migration, UI, protocol,
action, recommendation input, or score activation. Existing v1 evidence,
scoring, state, ranking, and five-protocol runtime behavior remain exact.

M6B implementation does not itself satisfy the pending measurement,
accessibility, and privacy/safety review in `ER-M6A-003`. Keep
`RG-M6A-002` open and do not claim M6B acceptance, runtime projection, score
activation, participant release, deployment, or production validation until
that review is truthfully complete. Under Decision 051, PFSPAM may continue
fixed, inactive, unprojected, source-only draft cohorts and merge only an exact
head with every required check green. This sequencing does not accept M6B or
authorize typed production scoring.

M6C-01 is reviewed and merged. It adds append-only `GG-CONTEXT-1.0`
assessment-epoch context and defer-state foundations plus additive readiness,
without changing ordinary UI or recommendations.

M6C-02 is reviewed and merged. It adds append-only
`GG-PERSONAL-OS-1.0` mission, principles, anti-goals, twelve-month direction,
priority-stack, and descriptive Truth/Autopilot Audit revisions plus additive
readiness. It adds no identity or audit score, ordinary UI, priority formula,
alternative recommendation, weekly execution, export, deletion/retention
policy, evidence/scoring path, protocol, or activation.

M6C-03 is reviewed and merged. It adds the pure backend-only
`GG-CONTEXT-PRIORITY-1.0` engine and read-only
`GG-CONTEXT-PRIORITY-READINESS-1.0`. It multiplies the unchanged
`GG-NEED-RANKING-1.0` protocol base priority only by explicitly provided
context factors and returns deterministic withheld, primary, and alternative
results. It adds no migration, persistence, ordinary UI, Personal OS text
analysis, evidence/scoring write, protocol, or activation.

M6C-04 is reviewed and merged. It exposes those unchanged M6C
contracts through one authenticated, concise Personal OS journey, explicit
assessment and per-practice context forms, deterministic partial-cohort
recommendations and alternatives, and additive
`GG-M6C-PILOT-READINESS-1.0` browser/deployment verification. Personal OS text
remains private to its owner-facing surface; recommendation inputs and
explanations use only structured context. The batch adds no model, migration,
priority persistence, protocol/action, Personal OS analysis, evidence/scoring
write, activation, dedicated export/purge/retention automation, remote
telemetry, weekly execution, release, or deployment.

M6D-01 is reviewed and merged. M6E-FULL-FRONTIER materialized the source-only
implementation batch. It preserves the nine previously authored packages and
deterministically materializes one package for every remaining competency: 383
packages and 1,151 source actions across all 27 domains, with zero uncovered
competencies and all 37 levers represented through valid parent mappings and
recommendation-target subsets.

M6E originally materialized all 374 additions as inactive editorial drafts.
M6F supersedes that source-only boundary: all 383 packages are runtime
projected and score active, while the five legacy protocols retain their v1
evidence snapshot compatibility and the other 378 use typed evidence.

Decision 051 historically permitted exact-head, required-CI-green source-only
draft delivery. Decision 052 supersedes its runtime and activation ceiling for
the current M6F batch. Human semantic/source/originality/accessibility/privacy/
safety review remains deferred, not passed, for the owner's consolidated
383/383 audit.
M6F-ALL-ACTIVE is the current owner-directed batch. It supersedes the prior
five-runtime/friendship-only activation boundary and projects all 383 canonical
protocols into runtime with score activation. Content and specialist review
remain explicitly pending for the owner's consolidated audit; activation must
not be described as clinical, psychometric, cultural, accessibility, or
intervention-effectiveness validation. Existing immutable baselines, exact
stable IDs, typed/legacy replay, structured provenance, adverse and
inconclusive withholding, append-only score snapshots, reversal, rebuild, and
the completion/mastery and human-dignity boundaries remain mandatory.

Decision 052 supplies the owner approval for this batch's runtime projection
and score activation. Participant exposure, release, deployment, and broader
production or validation claims still require separate human approval.

M6H-01 is reviewed and merged. It adds an authenticated
seven-day loop over the latest verified Personal OS direction, existing
context priority, one current-practice action, submitted evidence, and a
structured proof review. Plans and reviews are append-only and
assessment-epoch scoped. Planning, elapsed time, and review choices create no
evidence, score contribution, recommendation factor, practice completion, or
mastery claim. Proof freezes at the review timestamp so later evidence cannot
rewrite an immutable review. This slice intentionally performs no human,
specialist, participant, release, or deployment-gate work.

M6H-02 is reviewed and merged. It adds a deterministic
owner-private archive, preview-first account deletion, explicit retention that
is disabled by default, and verified pre-upgrade backup, restore, rollback, and
replay operations. It must not change curriculum, evidence eligibility,
scoring mathematics, activation, recommendation order, completion, mastery,
or human-worth boundaries. Existing backup copies remain separate private
artifacts and are never silently rewritten or claimed erased.

M6B-GOV-AUDIT is the current automated governance slice. It produces one
deterministic row for every one of the 383 packages and 1,151 actions, stable
finding IDs, complete inventory coverage, and a prioritized owner/specialist
review packet. Automated structural checks may pass or identify objective
defects, but semantic, source, originality, accessibility, safety,
measurement, cultural, legal, clinical, and intervention judgments remain
open for named humans. The audit must keep `ER-M6A-003` pending,
`RG-M6A-002` open, all 383 owner-directed activation records unchanged, and
M6B acceptance false until the separate manual `M6B-GOV` contract is
truthfully completed.

M6I-01-COMPOSITE-CLOSEOUT-SCORING is the current owner-directed software
slice. Decision 053 rejects Decisions 047–049 as the production scoring
architecture and prospectively supersedes Decision 052's event-level score
trigger without deactivating any protocol. It projects assessment-derived
scores across 7 families, 37 levers, 27 domains, and 383 competencies; uses a
50/50 canonical/equal relationship blend; and awards 0.75 or 1.00 completion
credit only at explicit human closeout. Completion is not mastery. The batch
must keep `ER-M6A-003` pending, `RG-M6A-002` open, and all historical scoring
history immutable and replayable.

M6I-02-APPLICABILITY-PERSONAL-COVERAGE is reviewed and merged. It adds a
direct explicit N/A route and a separately labeled personal-applicable
coverage denominator while preserving canonical coverage, score state,
recommendation mathematics, and reassessment isolation.

M6I-03-ASSESSMENT-CALIBRATION-READINESS is reviewed and merged. It is a source-only software
slice. It verifies the frozen assessment v1.1 item, clarifier, lever, family,
orientation, coverage, hash, and golden-replay inventory and enumerates eight
open participant evidence axes. It reads no application database or private
runtime data and changes no assessment, score, recommendation, UI, migration,
or production behavior. Structural readiness must not be described as
psychometric, fairness, participant, longitudinal, or effectiveness
validation.

M6I-04-CONSENTED-ASSESSMENT-CALIBRATION-DATA is reviewed and merged.
It adds explicit per-completed-run consent, withdrawal, reconsent, an
owner-inspectable contribution, and an acknowledged mode-0600 local operator
export. One random token links included retakes without exporting identity,
exact timestamps, assessment IDs, share codes, free text, developmental
history, or derived profile outputs. It adds no telemetry and changes no
assessment, recommendation, evidence, completion, score, or replay behavior.
Software collection capability completes zero participant evidence axes.

M6I-05-ASSESSMENT-CALIBRATION-ANALYSIS-READINESS is the current software
slice. It validates an exact M6I-04 export and writes a deterministic private
aggregate with small-cell suppression, fixed workflow thresholds, exploratory
linked-retest agreement, and explicit missing-input reasons. It reads no
database, uploads nothing, includes no participant rows or raw values, and
keeps all eight participant evidence axes open with zero completed. Aggregate
analysis readiness is not psychometric, fairness, participant, longitudinal,
or effectiveness validation.

## M6J tailored-content continuation

M6J-01 individually rewrites all 42 practices in domains 01, 02 and 13. M6J-02
adds all 12 self-knowledge practices in domain 05. M6J-03 adds all 23 practices
in domains 03 and 04. M6J-04 adds all 14 vulnerability/disability/care practices
in domain 06. M6J-05 adds all 14 emotional maturity/resilience practices in
domain 07, for 105 authored. The broader owner requirement covers all 383;
the remaining 278 must stay explicitly rewrite-pending. The owner
requires focus on the substantive content rewrite, with explicit canonical
scope maps and self-contained tasks; publication status is not content progress. Compiler inputs live in `docs/authoring/exercises/`, while
the canonical runtime source remains the manifest-listed practice YAML.
The compiler must reject missing competencies, duplicated instructions and
invalid observation checks; passing those checks is not human acceptance.
Preserve the existing home-upkeep evidence rules as well as the five frozen
legacy projections. An import must not replace instructions or rules for an
active or paused practice. See ADR 0018 and the current handoff before the next
cohort. Do not describe scoring completion, source links or 383 active records
as completion of this content rewrite.

<!-- BEGIN PORTFOLIO-CONTROL MANAGED -->
## Governed agentic delivery

- Product: `gitg-self-host`; delivery profile: `product-data`.
- Control revision: `2e6d817ee4e0db4e4efc82b21fa9ad1735fb96d9`; harness version: `2`.
- Read `contracts/profile-requirements.yaml` and the approved
  `contracts/active-batch.yaml` before implementation.
- Stay inside active-batch allowed paths and preserve every forbidden path.
- Run the repository-local verification contract before claiming completion.
- Record exact evidence and distinguish static, simulated, protocol, bench,
  field, playtest, staging, and production validation.
- Do not claim physical, release, deployment, or production evidence that was
  not actually produced.
<!-- END PORTFOLIO-CONTROL MANAGED -->
