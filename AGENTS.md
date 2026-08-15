# AGENTS.md — Grounded Growth

## Mission
Build a self-hosted, evidence-oriented guided-development application. The product converts an assessment-derived developmental need into a bounded, concrete real-world practice without exposing internal curriculum databases to the user.

## Product boundary
- Notion is an internal curriculum/content studio, not the consumer runtime.
- The application recommends executable **Practice Protocols**, not abstract competencies.
- Completion is never equivalent to mastery.
- Human dignity is never scored.
- Personality/orientation changes framing and tie-breaking only; it does not determine worth or obligation.
- Dynamic score updates are limited to the reviewed M3A contract and the one
  explicitly activated friendship protocol. Do not generalize scoring to
  unreviewed protocols or invent missing priority inputs.
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
- Only `PRACTICE-FRIENDSHIP-01` is score-activated. A required baseline with
  unavailable mass fails closed and requires reassessment.
- `GG-PILOT-FEEDBACK-1.0` is product-usability data only. Never route it into
  assessment, evidence, scoring, ranking, completion, orientation, or
  archetype logic.
- Do not add automatic timing, browser analytics, session recording, tracking
  pixels, or remote telemetry under the pilot-feedback contract.
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
- `GG-TYPED-EVIDENCE-1.0` and `typed-evidence-rules-v1` are a parallel,
  pure, shadow-only M6B path. Version dispatch must fail closed, typed values
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
   exact five-protocol projection, deterministic generated reports, and
   explicit 378-row unauthored baseline.
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
9. Do not claim dynamic scoring works until score mutation is deliberately enabled and tested.

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

M4A activates **Schedule Non-Instrumental Play** as the second complete
protocol and establishes protocol-configured setup, check-in, and completion
copy. It records immutable evidence but remains explicitly score-inactive.
M4B activates **Practice Emotional Cue Detection** as the third complete
protocol. It is anchored to canonical nonverbal communication competency
`16.03`, treats cues as uncertain hypotheses, requires direct clarification,
and remains score-inactive.
M4C activates **State and Maintain One Boundary** as the fourth complete
protocol. It is anchored to canonical competency `11.10`, limits the
intervention to a safely stateable low-stakes situation, distinguishes a
boundary from coercion or punishment, requires both a direct statement and
proportionate follow-through, and remains score-inactive.
M4D activates **Complete an Attention-Presence Experiment** as the fifth
complete protocol. It is anchored to canonical competency `08.02`, compares
one usual and one changed condition without productivity scoring or
surveillance, preserves accessibility supports, requires a repeat within seven
days, and remains score-inactive.
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
`RG-M6A-002` open and do not claim M6B acceptance or begin mass authoring
until that recorded review is truthfully complete. The owner-directed sequence
permits later non-scored foundations while this governance remains pending;
that sequence does not accept M6B or authorize typed production scoring.

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

M6C-04 is the current implementation batch. It exposes those unchanged M6C
contracts through one authenticated, concise Personal OS journey, explicit
assessment and per-practice context forms, deterministic partial-cohort
recommendations and alternatives, and additive
`GG-M6C-PILOT-READINESS-1.0` browser/deployment verification. Personal OS text
remains private to its owner-facing surface; recommendation inputs and
explanations use only structured context. The batch adds no model, migration,
priority persistence, protocol/action, Personal OS analysis, evidence/scoring
write, activation, dedicated export/purge/retention automation, remote
telemetry, weekly execution, release, or deployment.

The representative 10–12 competency vertical slices begin only after M6C as
Phase B.

<!-- BEGIN PORTFOLIO-CONTROL MANAGED -->
## Governed agentic delivery

- Product: `gitg-self-host`; delivery profile: `product-data`.
- Control revision: `f55e9ab7e854bc0aef895edd1cc944607accc312`; harness version: `2`.
- Read `contracts/profile-requirements.yaml` and the approved
  `contracts/active-batch.yaml` before implementation.
- Stay inside active-batch allowed paths and preserve every forbidden path.
- Run the repository-local verification contract before claiming completion.
- Record exact evidence and distinguish static, simulated, protocol, bench,
  field, playtest, staging, and production validation.
- Do not claim physical, release, deployment, or production evidence that was
  not actually produced.
<!-- END PORTFOLIO-CONTROL MANAGED -->
