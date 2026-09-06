# Grounded Growth — Project Handoff

## Current owner priority — rich competency content, 2026-09-06

The owner reiterated that the task is to make each competency rich,
representative of its underlying goal, self-contained and usable by different
individuals. The owner specifically redirected this continuation away from
PR/merge work and back to that content requirement.

M6J-01 through M6J-04 supplied 91 authored practices in domains 01 through 06
and 13. M6J-05 adds all 14 domain 07 practices for emotional maturity,
resilience and mental well-being: 42 distinct action instructions, 168 checks
and 56 worked outcome examples. Total authoring is 105/383, with exactly 278
rewrite-pending. This count is not human review or empirical acceptance.
See `docs/authoring/M6J-05-SCOPE-MAP.md` for every canonical facet and
`docs/authoring/M6J-05-PRACTICE-READER.md` for the full new text.

Each practice supplies a concrete default, materials, distinct ordered tasks,
observable checks, adaptations, scope limits and meaningful review. Emotional
labels remain hypotheses; pauses return to the issue; ordinary anxiety
experiments require real repeated attempts; grief has no prescribed timetable;
help plans distinguish preparation, contact and care received. Two new inspected
NHS/NIMH references and two rechecked existing references support narrow factual
claims, not the effectiveness of the original exercises or specialist acceptance.

Authoring inputs compile into the canonical runtime practice YAML. The other
369 packages must remain byte-identical to M6J-04 baseline
`0a3939a468dac1e9ffd9451c012968e88840930c`. All 383 protocol identities,
1,151 action identities, parent mappings, activation, assessment, ranking,
scoring mathematics and explicit human closeout remain unchanged. Ongoing
practice import protection and immutable historical replay remain mandatory.
See the M6J-05 evidence record for exact executed and unverified checks.

Continue with domain 08, Attention, Desire, Temperance, and Discipline, using
the same explicit scope maps and standalone content standard. Its 08.02
legacy runtime projection is frozen: enrich its source-only guide without
silently changing compatible runtime evidence or claiming the legacy package
has been rewritten. The earlier eight pre-frontier packages still need explicit
standards review. Do not substitute publication status for content progress.
The two original concerns are not collectively closed: scoring software exists,
content remediation is partial and specialist/source/empirical acceptance remains open.

## What this project is
Grounded Growth is a personalized human-development curriculum and adaptive practice system. It began as an 876-item list of traits/tasks, was reconstructed into a pluralist 383-competency curriculum, mapped to 37 trainable developmental levers, and paired with a 50-item assessment that initializes provisional lever states and task rankings.

The central product insight is that a competency is not yet an executable task. The consumer product must convert a ranked developmental need into a concrete, bounded **Practice Protocol** with observable actions, structured evidence, and a clear distinction between completion and mastery.

## Validated assets
- 383 master competencies across 27 domains.
- 37 developmental levers in 7 families.
- 6 non-evaluative orientations and 15 paired archetypes.
- Weighted competency-to-lever mapping.
- Assessment v1.1 with corrected timing, raw/calibrated/confidence display, backward-compatible share codes, and Notion export.
- Pilot 002 profile and static task ranking.
- A Notion content studio containing the full curriculum and baseline ranking.

## What the Notion pilot proved
The curriculum and ranking are coherent enough to produce a plausible first recommendation. However, Notion failed as a consumer runtime:
- users must understand pages, views, properties, templates, and database operations;
- broad competencies force the user to invent the intervention;
- long bullet-form reflection feels informal and unprofessional;
- evidence is vague and easy to spoof;
- navigation and activation are not intuitive for non-Notion users.

Therefore:
- retain Notion as internal curriculum authoring/editorial tooling;
- build a self-hosted web application for the guided user experience;
- delay dynamic score mutation until evidence capture is validated.

## Accepted runtime architecture
The consumer runtime is a deliberately simple Django monolith:

- Python and the current supported stable Django release;
- Django templates, local CSS, and only small amounts of local JavaScript;
- SQLite through the Django ORM, stored at
  `/data/grounded_growth.sqlite3`;
- Gunicorn bound to `0.0.0.0` in one Docker Compose application service;
- pytest, Ruff, and Playwright for verification.

M1 does not use React, Next.js, a separate API/frontend, PostgreSQL, Redis,
Celery, a queue, a reverse proxy, or externally hosted browser assets. SQLite
uses a 20-second busy timeout and WAL where supported. This is intentionally a
single-instance local-network deployment while keeping ordinary ORM code
portable to PostgreSQL later.

See `docs/architecture/0001-django-monolith-and-sqlite.md`.

## Canonical conceptual model
### Competency
A broad human capacity, such as Maintaining Friendship.

### Lever
A trainable developmental capacity, such as Friendship, Belonging, and Hospitality.

### Task–Lever Link
A weighted mapping between a competency and one or more levers.

### Practice Protocol
A bounded intervention with a duration, setup, concrete actions, evidence questions, contradictory evidence, completion criteria, and mastery disclaimer.

### Assessment Run
The initial self-report and response-quality result.

### Lever State
Immutable provisional assessment baseline plus separate evidence-updated
working state. It is not a direct competency or mastery observation.

### Direct Competency Evidence Shadow
An evidence-only, non-production projection from replay-verified typed events.
Assessment v1.1 supplies no competency baseline; zero eligible evidence is
explicitly unknown.

### Practice Sprint
An instantiated protocol for a user.

### Evidence Event
One structured observation/check-in tied to a practice action.

### Score Snapshot
An immutable audit record of score state before and after any future update.

## Product doctrine
- Human dignity is never scored.
- There is no single perfect-person score.
- Optional roles can be not applicable without penalty.
- Self-report initializes hypotheses; it does not prove mastery.
- Task completion is not mastery.
- Real-world transfer and contradiction matter.
- Personality affects presentation and tie-breaking only.
- Scores must be explainable, provisional, and evidence-sensitive.
- Grounded Growth is becoming a guided life OS for people who may be driven
  yet misdirected, fragmented, or operating on autopilot. Assessment,
  personality, orientations, and archetypes frame the work; they are not the
  headline, destiny, stereotype, or measure of worth.
- The longer path connects a concise Truth/Autopilot Audit with mission,
  principles, anti-goals, current season and capacity, priority stack,
  twelve-month direction, weekly execution, and proof-based review. The home
  experience should offer a small context-fit set of next practices—not a
  383-item checklist, content encyclopedia, or giant worksheet.

## Pilot 002 working profile
Primary archetype: The Seeker.
Supporting patterns: The Systems Steward and The Explorer; Strategist behavior is also evident but the assessment's agency construct emphasizes rapid/interpersonal decisiveness.

Working interpretation:
A meaning-driven systems thinker with high discernment, strong technical and intellectual independence, and a preference for coherence, durable systems, and purposeful exploration. Current balancing work emphasizes relationships, play, empathy/social perception, intimacy, communication, conflict repair, and boundaries.

See `docs/pilot/PILOT_002_FINDINGS.md` and `data/notion/initial_mvp/01_lever_baselines_import.csv` for exact baseline values.

## First complete protocol
### Deepen One Existing Friendship
Duration: 14 days.

Setup: choose one existing friend whom the user values and would realistically like to know more deeply.

Actions:
1. Initiate a substantive conversation about something currently meaningful in the friend's life; spend at least ten minutes primarily listening.
2. Propose a specific shared activity and date rather than a vague future intention.
3. Within seven days, reference something the person shared and ask how it developed.

Evidence fields:
- interaction occurred;
- user initiated;
- conversation moved beyond transactional content;
- user asked a follow-up question;
- friend voluntarily shared personally meaningful information;
- a specific future interaction was scheduled;
- follow-up occurred within seven days;
- internal resistance;
- expected reciprocity versus actual reciprocity;
- support used, context comparison, and evidence direction;
- contradictory evidence;
- optional note.

Completion criteria:
- all three actions attempted;
- at least two completed;
- at least one substantive interaction;
- final review submitted.

Completion does not imply mastery.

## Current implementation state

M1 is implemented as two reviewable batches:

- **M1A foundation:** one-service Docker deployment, non-root Gunicorn,
  persistent SQLite, bootstrap authentication, health, migrations, idempotent
  canonical import, Pilot 002 demonstration seed, and authenticated
  home/profile.
- **M1B guided workflow:** canonical assessment v1.1 taking and GGA11/GGA1
  import; profile persistence with all 6 orientation, 15 archetype, and 37
  lever outputs; recommendations; the seven-step friendship setup; active,
  paused, stopped, and completed practice states; compact draft/submitted
  check-ins; guarded completion; and immutable final review.
- **M2A evidence contract:** each submitted check-in atomically creates a
  replayable `GG-EVIDENCE-1.0` event with protocol performance, structured
  quality, independence, bounded context breadth, action-specific repetition,
  contradiction, and base event mass.
- **M2B evidence audit:** authenticated users can review all submitted events
  in one paginated ledger, filter by evidence direction, and download a
  deterministic privacy-minimized calibration export. A read-only management
  command verifies complete event coverage, submission order, and exact replay
  against direction-complete synthetic golden fixtures.
- **M3A shadow scoring:** a pure Decimal package applies an explicit
  direction-aware policy and canonical `17.03` task weights to replay-verified
  events. The profile displays the result only as an unsaved preview.
- **M3B score-state activation:** submitted friendship evidence atomically
  updates separate current lever state under the accepted M3A mathematics,
  with immutable hashed before/after snapshots, deterministic rebuild and
  reversal, recalculated provisional need, and dynamic active-protocol order.
- **M5A private-pilot operations:** optional participant-selected usability
  categories are stored as a separate append-only record and exported through
  a privacy-minimized allowlist. They never enter assessment, evidence,
  scoring, recommendation, completion, orientation, or archetype logic.
- **M5B pilot findings closeout:** the first owner-operated session is recorded
  without private content. Feedback questions are journey-scoped, check-in
  observations are action-scoped, evidence submission requires a real
  attempted action, and an explicit user-scoped feedback purge supports the
  agreed participant-data lifecycle. Historical records and all reviewed
  evidence/scoring mathematics remain unchanged.
- **M6A canonical protocol-content foundation:** five versioned YAML packages
  and their source, family, risk, scoring-policy, research-gap, expert-review,
  and activation registries replace the hard-coded Python catalog. Offline
  schemas, deterministic 383-row coverage/originality reports, and the
  additive expansion-readiness contract preserve the exact five-protocol
  runtime and friendship-only scoring boundary. No ORM, UI, evidence, scoring,
  or ranking change is included.
- **M6B competency-evidence architecture (software merged, governance
  pending):** pure
  `GG-TYPED-EVIDENCE-1.0`, evidence-only competency shadow, one-way lever
  shadow, production-eligibility gate, synthetic fixtures, deterministic
  reports, and additive software readiness. It adds no migration, UI,
  protocol/action, recommendation input, or activation. Pending
  `ER-M6A-003` review prevents an M6B-accepted claim. The newest
  owner-directed control contract defers governance while later software and
  content sequencing proceeds, without authorizing production scoring.
- **M6C-01 context/defer-state foundation:** append-only
  `GG-CONTEXT-1.0` records scope season/capacity to a user and assessment epoch
  and candidate factors to a user, epoch, and stable protocol. Explicit
  unknown, N/A, deferred, and provided states, bounded defer metadata,
  deterministic snapshots/hashes, schema-only migration, and additive
  readiness do not yet change recommendations or ordinary UI.
- **M6C-02 Personal OS identity foundation:** append-only
  `GG-PERSONAL-OS-1.0` revisions store exactly five identity sections and four
  descriptive Truth/Autopilot Audit responses for one authenticated user and
  assessment epoch. Explicit states, bounded authored values, deterministic
  private snapshots, conflict-safe idempotent writes, reversible schema, and
  additive readiness add no score, UI, recommendation, activation, export,
  deletion, or retention behavior.
- **M6C-03 context-priority backend:** pure `GG-CONTEXT-PRIORITY-1.0`
  multiplies unchanged protocol base need by seven explicitly provided context
  terms, withholds N/A/defer/missing context, returns deterministic distinct
  alternatives, and emits privacy-minimized canonical results. Additive
  readiness replays synthetic fixtures and validates current canonical mapping
  and activation without changing ordinary recommendations or stored state.
- **M6C-04 concise browser and pilot-readiness closeout:** one authenticated
  Personal OS entry point uses only the owner's latest assessment epoch,
  presents exact staged Personal OS, season/capacity, and per-practice context
  inputs, and applies the unchanged M6C-03 engine only to explicitly reviewed
  current-epoch practices. Home and practice surfaces show a small,
  honestly-labeled context-aware set or the unchanged legacy recommendation
  behavior; N/A/defer alternatives remain distinct and cohort-bounded. The
  additive `GG-M6C-PILOT-READINESS-1.0` contract and deployment drill verify
  the browser slice without storing priority results, analyzing authored text,
  changing scoring, or expanding friendship-only activation.

Only submitted check-ins count toward completion. A database constraint limits
each user to one active or paused practice. Services—not templates—own state
transitions, evidence aggregation, and completion rules.

The assessment baseline remains unchanged through practice completion, event
creation, ledger viewing, export, replay verification, and current-state
activation. M2 stores event-level base evidence mass. M3A established the
posterior contract in memory. M3B writes only separate `LeverState` rows and
append-only `ScoreSnapshot` transitions. It never rewrites raw self-report,
assessment baselines, orientations, or archetypes.

## Milestone sequence
### M1 — Guided UX, static scores
Build the app shell and full friendship protocol. Import profile and curriculum. Do not mutate scores.

#### M1A — Foundation
- Django project and complete M1 domain schema;
- one-service Docker deployment with persistent SQLite;
- bootstrap authentication and public health endpoint;
- validated, idempotent canonical import;
- assessment v1.1 golden-test boundary;
- Pilot 002-backed authenticated home and profile.

Status: implemented and merged.

#### M1B — Guided workflow
- take assessment v1.1 in the application or import GGA11;
- retain GGA1 decoding compatibility;
- practice recommendation explanation and setup;
- active practice, compact draft/submitted check-ins, pause/resume/stop;
- completion and final review with an explicit mastery disclaimer;
- browser coverage for the complete M1 path.

Status: implemented and merged.

### M2 — Evidence engine
Extend submitted check-ins with versioned evidence quality, independence,
context breadth, repetition, and contradiction semantics. Draft/submitted
state already exists in M1.

#### M2A — Evidence contract and events
- three compact structured metadata choices on submission;
- stable action-specific observation rules;
- pure deterministic `GG-EVIDENCE-1.0` evaluation;
- immutable, replayable evidence events;
- conservative idempotent backfill for submitted M1 rows;
- plain-language evidence detail with collapsed technical audit values;
- no lever allocation or profile mutation.

Status: implemented and merged.

The binding semantics, migration strategy, and exclusions are in
`docs/evidence-contract.md`. Base event mass alone was not treated as
authorization for scoring; M2B completed the required audit gate.

#### M2B — Evidence audit and calibration
- authenticated per-user ledger of submitted evidence events;
- plain-language direction filtering and event explanations;
- deterministic `grounded-growth-evidence-export-v1` JSON export built by
  allowlist, without identity, record IDs, timestamps, private labels, free
  text, assessment answers, or share codes;
- strict read-only whole-database replay verification;
- versioned synthetic golden fixtures for supportive, inconclusive, mixed,
  contradictory, and legacy-unknown events;
- no algorithm change, lever allocation, or profile mutation.

Status: implemented and merged.

The operational and privacy contract is in `docs/evidence-audit.md`.

### M3 — Dynamic scoring
Build and review a versioned projection before activating any stored state.

#### M3A — Shadow scoring contract
- persist exact canonical assessment alpha/beta mass for new runs;
- conservatively reconstruct published Pilot 002 mass only when identifiable;
- link `PRACTICE-FRIENDSHIP-01` to canonical competency `17.03`;
- validate the four structured weights and recommendation-target
  compatibility without changing recommendation eligibility;
- apply the reviewed `k_tl` coefficient once to M2 base event mass;
- route supportive, mixed, contradictory, inconclusive, and legacy-unknown
  direction explicitly;
- anchor confidence at the assessment value and add only a bounded monotonic
  gain from included evidence;
- render an authenticated, clearly labeled unsaved profile preview;
- lock exact behavior with synthetic golden fixtures;
- create no current score, score snapshot, need/rank, or recommendation write.

Status: implemented, reviewed, and merged.

The accepted contract is in `docs/scoring-shadow.md`. M3A is a
software-review and calibration gate, not psychometric validation.

#### M3B — State activation and dynamic ranking
- separate 37-lever current state for each immutable assessment baseline;
- immutable, hashed initialization/process/reversal/rebuild snapshots;
- atomic and idempotent evidence creation plus score application;
- strict replay of evidence, contributions, transition history, need ranks,
  active-event sets, and final current state;
- startup reconciliation and read-only verification command;
- audited permanent event reversal without deleting the evidence ledger;
- assessment v1.1 provisional-need recalculation from current estimate and
  confidence;
- active-practice priority from canonical parent-competency weights;
- `baseline_only` policy and reassessment path for unavailable mass;
- unchanged assessment baseline, completion state, orientations, archetypes,
  and human-worth boundary.

Status: implemented, reviewed, and merged. Decisions 023–026 are accepted.

The binding activation contract is in `docs/scoring-state.md`.

### M4 — Protocol library expansion
Create reusable protocol patterns and convert more of the 383 competencies into executable interventions.

#### M4A — Non-instrumental play
- activate `PRACTICE-PLAY-01` as a complete 10-day, three-action protocol;
- anchor it to canonical competency `26.01`, Play for its own sake;
- make setup, check-in labels, and completion evidence protocol-configurable;
- retain immutable `GG-EVIDENCE-1.0` events without altering historical replay;
- keep the protocol score-inactive and create no score snapshot.

Status: implemented, reviewed, and merged. Decisions 027–028 are accepted.

#### M4B — Emotional cue detection
- activate `PRACTICE-EMOTIONAL-CUES-01` as a complete 10-day, three-action protocol;
- anchor it to canonical competency `16.03`, Nonverbal communication;
- use only canonical target lever `L24` from that competency's structured mapping;
- require observable description, multiple tentative explanations, and neutral
  direct clarification;
- explicitly reject mind-reading, diagnosis, and cultural or neurotype
  stereotyping;
- retain immutable `GG-EVIDENCE-1.0` events while remaining score-inactive.

Status: implemented, reviewed, and merged. Decisions 029–030 are accepted.

#### M4C — State and maintain one boundary
- activate `PRACTICE-BOUNDARY-01` as a complete 10-day, three-action protocol;
- anchor it to canonical competency `11.10`, Saying no and ending responsibly;
- use only canonical target lever `L25` from that competency's structured mapping;
- distinguish a self-directed boundary from coercion, punishment, threats, or
  silent tests;
- exclude abuse, coercive control, stalking, unsafe dependency,
  discrimination, and likely-retaliation contexts from this guided practice;
- require both a direct boundary statement and one proportionate follow-through;
- retain immutable `GG-EVIDENCE-1.0` events while remaining score-inactive.

Status: implemented, reviewed, and merged. Decisions 031–032 are accepted.

#### M4D — Attention-presence experiment
- activate `PRACTICE-PRESENCE-01` as a complete 10-day, three-action protocol;
- anchor it to canonical competency `08.02`, Mindfulness and present attention;
- use only canonical target lever `L08` from that competency's structured mapping;
- compare one usual and one changed 15-minute condition around the same
  low-stakes activity;
- treat noticing and returning attention—not output or zero distraction—as the
  relevant observation;
- preserve movement, fidgets, assistive technology, reminders, and necessary
  alerts while excluding safety-critical activity and surveillance;
- require both a condition comparison and one repeat within seven days;
- retain immutable `GG-EVIDENCE-1.0` events while remaining score-inactive.

Status: implemented, reviewed, and merged. Decisions 033–034 are accepted.

The initial five-protocol library is complete after M4D. Further expansion
must use separately reviewed batches. A new executable protocol does not
become score-active until its stable canonical parent, structured weights,
evidence semantics, and golden tests are explicitly reviewed.

#### M4E — Post-M4 pilot-readiness closeout
- freeze the reviewed initial inventory under
  `GG-PILOT-READINESS-1.0`;
- verify exact canonical/source/database counts, stable protocol links,
  action inventory and configuration fingerprint, Pilot 002 completeness,
  draft/evidence separation, evidence replay, score-state replay, and
  friendship-only activation without writing state;
- provide an isolated `make pilot-check` from a fresh migrated database;
- require one aggregate GitHub gate over quality, nine Playwright journeys,
  and the production Docker Compose drill;
- retain desktop/mobile walkthrough screenshots and failure diagnostics;
- add a keyboard skip path, conspicuous focus, and stable mobile navigation;
- add no protocols and activate no additional scoring.

Status: implemented, reviewed, and merged. Decisions 035–036 are accepted.

The verification record and human sign-off checklist are in
`docs/pilot/PILOT_READINESS_CLOSEOUT.md`.

### M5 — Private pilot operations

#### M5A — Structured usability feedback
- add a bounded operator/session guide with consent, observation,
  accessibility/safety, data-handling, and stop criteria;
- collect optional applicability, participant-estimated setup/check-in time,
  confusing-step, and accessibility/safety-friction categories;
- store `GG-PILOT-FEEDBACK-1.0` separately and append-only;
- provide deterministic
  `grounded-growth-private-pilot-export-v1` JSON by allowlist;
- exclude identity, record IDs, exact timestamps, free text, private context,
  assessment data, evidence, scores, orientations, and archetypes from the
  export;
- prove submission, viewing, and export cannot mutate assessment, evidence,
  score state, recommendation order, completion, orientations, or archetypes;
- use no automatic timing, protocol addition, remote telemetry, or scoring
  expansion.

Status: implemented, reviewed, and merged. Decisions 037–038 are accepted.

The binding engineering/privacy contract is in `docs/pilot-feedback.md`; the
session checklist is in `docs/pilot/PRIVATE_PILOT_OPERATIONS.md`.

#### M5B — Pilot findings and form-coherence closeout
- run authorized private-pilot sessions using the reviewed M5A checklist;
- record aggregate, de-identified product findings under `docs/pilot/`;
- scope optional feedback questions to the selected journey stage;
- scope check-in observations to the selected action and require a real
  attempt before submission;
- preserve drafts before an action and every existing immutable event;
- provide a preview-first, exact-user operator command for feedback deletion;
- document that backups remain within the same retention agreement;
- do not infer developmental conclusions or expand scoring from usability
  feedback.

Status: implemented for review from the first owner-operated session.
Decisions 039–041 are proposed.

The de-identified record is in
`docs/pilot/PRIVATE_PILOT_001_FINDINGS.md`.

### M6 — Full-curriculum expansion

#### M6A — Canonical protocol-content foundation

- record the owner-authorized multi-PR expansion and its non-worth,
  pluralist, accessibility, safety, source, and anti-boilerplate boundaries;
- add a manifest-driven, versioned canonical package format under
  `data/practices/`;
- project the five existing protocols and fifteen actions exactly into the
  existing runtime;
- add source, risk, scoring-policy, protocol-family, and activation
  registries plus research gaps and expert review;
- generate the 383-row coverage ledger, domain/lever matrices, risk register,
  coverage summary, and originality report;
- preserve the old pilot verifier and add
  `GG-CURRICULUM-EXPANSION-READINESS-1.0`;
- add no new protocol, action, score activation, migration, UI, evidence
  execution, or scoring mathematics.

Status: implemented, reviewed, and merged. Decisions 042–045 are accepted as
the M6 program direction.

The program charter is in `docs/program/M6_CURRICULUM_EXPANSION.md`; package
and report mechanics are in `docs/practice-content.md`.

#### M6B — Competency evidence and scoring architecture

- keep assessment baseline, protocol evidence, direct competency evidence,
  transfer disposition, and lever state distinct;
- add pure `GG-TYPED-EVIDENCE-1.0` evaluation from materialized
  `typed-evidence-rules-v1` snapshots with fail-closed dispatch;
- establish evidence-only `GG-COMPETENCY-EVIDENCE-SHADOW-1.0`, with no
  invented competency baseline;
- add one-way `GG-COMPETENCY-LEVER-SHADOW-1.0`, duplicate-event protection,
  and no lever-derived feedback;
- separate `GG-PRODUCTION-SCORE-ELIGIBILITY-1.0` from capture and shadow
  execution;
- add proposed ADR/decision updates, exact synthetic fixtures, property
  tests, replay, reversal, no-double-counting, assessment-epoch isolation, and
  no-baseline-mutation proofs;
- add additive `GG-COMPETENCY-EVIDENCE-READINESS-1.0`;
- keep production score activation at friendship only.

Status: software implementation merged. Decisions 047–049 and ADR 0009 remain
proposed pending the required governance review. The batch added no migration,
UI, protocol/action, M6C context input, recommendation change, or production
activation.

`ER-M6A-003` remains pending and `RG-M6A-002` remains open. M6B is not
accepted. The latest owner-directed control sequence defers governance while
M6C and later non-scored content work proceed; it does not permit a specialist,
measurement, accessibility, privacy/safety, or production-score claim.

#### M6C — Context-aware priority and Personal OS foundation

- add applicability, importance, readiness, urgency, opportunity/resources,
  current season and capacity, and defer/not-now inputs;
- add the minimum mission, principles, anti-goals, priority-stack, and concise
  Truth/Autopilot Audit experience;
- keep personality as framing or a tie-break only;
- prove a useful alternative recommendation after “not now” without deficit
  language;
- preserve concise home and practice flows.

M6C-01 adds only the versioned storage and pure-service foundation:

- `AssessmentContext` stores append-only season/capacity revisions per user
  and immutable assessment epoch;
- `PracticeContext` stores append-only candidate factor/defer revisions per
  user, epoch, and stable protocol;
- every factor is explicitly unknown, N/A, deferred, or provided, and only a
  provided factor carries a value;
- deferred candidates require a categorical reason and may have a bounded
  1–366 day review horizon;
- canonical minimal snapshots and SHA-256 hashes are deterministic, retain the
  assessment-epoch and protocol stable IDs needed for scope, and exclude user
  identity, context-record UUIDs, timestamps, and narrative;
- `GG-CONTEXT-READINESS-1.0` validates all present records without writing
  state.

Status: M6C-01 is reviewed and merged at `8a1c937`. It adds no
ordinary UI, recommendation formula, Personal OS worksheet, protocol, evidence
or scoring path, activation, baseline/current-state mutation, or automatic
context carry-forward. Representative vertical slices remain later Phase B
work.

M6C-02 adds only the separate Personal OS identity/audit foundation:

- exact identity sections `mission`, `principles`, `anti_goals`,
  `twelve_month_direction`, and ordered `priority_stack`;
- exact audit prompts `current_truth`, `autopilot_pattern`,
  `misalignment_or_fragmentation`, and `deliberate_next_step`;
- explicit unknown, N/A, deferred, or provided states with no hidden value;
- private user-authored scalar/list bounds and no diagnostic, alignment,
  autopilot, personality, virtue, or worth score;
- immutable assessment-epoch revisions with deterministic UTF-8 snapshots,
  idempotent retries, explicit SQLite contention, and fail-closed privacy-safe
  readiness;
- no ordinary UI, priority formula, alternatives, weekly execution, existing
  export, deletion/retention policy, protocol, evidence, scoring, or activation
  change.

Status: M6C-02 is reviewed and merged at `9ee7542`.

M6C-03 adds the backend-only context-priority and alternative contract:

- an explicit assessment epoch, its latest verified assessment context, and
  one latest verified context revision per supplied active canonical protocol;
- the unchanged `GG-NEED-RANKING-1.0` protocol priority as base;
- exact `x / 4` factor normalization, `1 - burden / 4`, seven-term Decimal
  multiplication, and half-up four-place quantization;
- N/A, defer, missing-context, and explicit-zero semantics without imputation;
- deterministic ordering and distinct alternatives within the supplied
  cohort;
- compact allowlisted UTF-8 JSON, SHA-256, explanation codes, and context
  hashes with no identity, Personal OS text, assessment answers, private
  narrative, or evidence payload;
- additive `GG-CONTEXT-PRIORITY-READINESS-1.0` with synthetic golden replay,
  current canonical mapping/activation verification, optional empty context,
  and privacy-safe drift diagnostics.

Status: reviewed and merged at `c7b51c1`. M6C-03 adds no migration,
persistence, ordinary UI, protocol/content, evidence/scoring write, or
activation.

M6C-04 closes the concise browser and deployment-readiness slice:

- one authenticated Personal OS entry point is scoped to the owner's latest
  assessment run and redirects a user without an assessment to assessment;
- a new assessment epoch begins with no copied or inferred Personal OS or
  context values;
- the five identity sections, four descriptive audit prompts, season/capacity,
  and one active practice's context appear in short staged sections, with
  unknown, N/A, and defer preserved and no preselected ordinal values;
- Personal OS and assessment-context submissions call the unchanged append-only
  services; valid changes append once, unchanged retries are idempotent, stale
  or malformed input writes nothing, and SQLite contention is retryable without
  echoing private values;
- all six practice factors are either explicitly provided, applicability is
  explicitly N/A, or one factor is explicitly deferred with a categorical
  reason and optional 1–366-day horizon;
- the browser supplies the unchanged context-priority engine only the active
  canonical practices explicitly reviewed in that current epoch, never treats
  an unreviewed practice as unfavorable, and never persists a priority result;
- context-aware home, practice-list, and recommendation copy uses fixed
  allowlisted explanations, distinguishes provisional need from current
  context fit, and provides a distinct cohort-bounded alternative or an
  explicit no-alternative state;
- authored Personal OS text renders only on its owner's authenticated Personal
  OS surface and never enters ranking, explanations, exports, reports,
  evidence/score snapshots, logs, URLs, telemetry, or activation;
- `GG-M6C-PILOT-READINESS-1.0` is an additive read-only aggregate over all six
  prerequisite readiness contracts, exact definition IDs, registered
  authenticated routes, the five-protocol projection, and friendship-only
  activation; it does not replace `GG-PILOT-READINESS-1.0` or a human gate;
- the Compose drill uses only conspicuously synthetic values to prove public
  service creation, authenticated HTTP access, deterministic priority replay,
  recreation, backup/restore, and unchanged activation.

Status: reviewed and merged. M6C-04 adds no model, migration, backfill,
protocol/action, dependency, external service, remote telemetry, weekly
execution, dedicated Personal OS/context export or purge, score formula/write,
or activation change.

#### M6D-01 — First representative low-risk source cohort

- author exactly competencies `08.06`, `09.12`, `10.02`, and `13.02` as four
  individually authored, low-risk draft packages;
- use distinct behavioral-start, prospective decision-record,
  practice-feedback-retry, and bounded home-system audit/redesign families;
- add claim-level sources, explicit research gaps, and fourteen action-specific
  `typed-evidence-rules-v1` fixture replays;
- require exact adjacent protocol/action/competency/policy identity and reject
  mixed, unknown, malformed, or runtime-projected typed packages;
- expand the source catalog to nine packages and twenty-nine actions while the
  runtime remains five protocols and fifteen actions;
- keep all four new packages inactive, unprojected, shadow-only, and absent
  from persisted evidence, score state, recommendations, and activation.

Status: reviewed and merged. Under Decision 051, trained
content/source/originality/accessibility/privacy/safety, retained-evidence, and
owner review remain deferred to the final 383/383 M6B-GOV gate.
`ER-M6A-003` stays pending, `RG-M6A-002` stays open, and Decisions 047–049
stay proposed.

#### M6E-FULL-FRONTIER — Complete source-only competency catalog

- preserve the nine previously authored packages and their merged M6D-01
  cohort behavior;
- deterministically materialize one source-only package for each of the 374
  remaining canonical competencies, yielding 383 packages and 1,151 actions;
- cover all 27 domains and all 37 levers through canonical parent mappings and
  valid non-empty recommendation-target subsets;
- give every generated package three stable typed actions, scoped reflections,
  explicit applicability/N/A behavior, and privacy, safety, completion,
  transfer, and mastery boundaries;
- keep every generated package draft, inactive, unprojected, and without an
  approved production contract; high-risk packages are non-scored and all
  other generated packages are shadow-only;
- preserve the exact five-protocol/fifteen-action runtime, historical replay,
  M6C behavior, recommendation behavior, and friendship-only score activation.

Status: the complete 383/383 source frontier is materialized on the
M6E-FULL-FRONTIER candidate branch. Automated structure, mapping, schema,
originality, and regression checks do not close the consolidated trained
content/source/originality/accessibility/privacy/safety/cultural/specialist
review. `ER-M6A-003` remains pending, `RG-M6A-002` remains open, and Decisions
047–049 remain proposed.

## M1 acceptance criteria
1. User understands why a practice was recommended without seeing backend fields.
2. User starts within five minutes.
3. User does not have to invent the intervention.
4. User logs a check-in in under two minutes.
5. Draft evidence is not treated as submitted.
6. Practice can be paused/resumed.
7. Practice can be completed without changing mastery.
8. Review explicitly distinguishes completion from mastery.
9. App runs via Docker Compose.
10. Tests cover the core path.

## M3A acceptance criteria

1. The friendship protocol uses stable competency `17.03` and its structured
   four-lever mapping.
2. Task weights sum to approximately 1.0 and malformed mappings fail closed.
3. Only replay-verified submitted events tied to the current assessment enter
   the projection.
4. Supportive, mixed, contradictory, inconclusive, and direction-unknown cases
   have explicit golden-tested behavior.
5. Included evidence cannot lower confidence; withheld evidence cannot raise
   it.
6. Drafts, completion, and review alone do not affect the projection.
7. New assessment runs retain exact canonical alpha/beta mass.
8. Pilot reconstruction is labeled and ambiguous mass remains unavailable.
9. Profile rendering leaves every stored profile and recommendation value
   unchanged.
10. The UI states that the result is a preview and completion is not mastery.
11. M3B mutation and dynamic ranking remain absent.

## M3B acceptance criteria

1. M3A mathematics, direction semantics, weights, and rounding remain
   unchanged.
2. Every baseline has a separate current state; baseline values never mutate.
3. Check-in, evidence event, score update, and process snapshot commit or roll
   back together.
4. Reprocessing the same event is idempotent.
5. Each initialization, processed event, reversal, and repair retains a full
   immutable hashed before/after state.
6. Draft, completion, review, inconclusive, and direction-unknown cases do not
   move current estimates.
7. Reversal retains the evidence event, requires a reason, and is idempotent.
8. Rebuild reproduces current state and repairs drift with an audit snapshot.
9. Startup initializes and reconciles score state after evidence backfill.
10. Current need reproduces assessment v1.1 at baseline and recalculates after
    eligible evidence.
11. Active practice order uses stable canonical weights and current need.
12. Missing required baseline mass fails the submission transaction and
    directs the user toward reassessment.
13. Profile language distinguishes baseline, current estimate, confidence,
    completion, mastery, and worth.
14. Orientations and archetypes remain unchanged.

## M4E acceptance criteria

1. A fresh isolated database passes migrations, bootstrap, repeated seed,
   evidence reconciliation, score initialization, and
   `GG-PILOT-READINESS-1.0`.
2. The readiness verifier is read-only and exits nonzero on canonical,
   protocol, Pilot 002, evidence, or score-state drift.
3. Exactly five reviewed protocols and fifteen reviewed actions are active.
4. Friendship remains the only score-active protocol.
5. All protocol parents and recommendation targets use reviewed stable IDs
   and canonical structured mappings.
6. Draft check-ins remain outside the evidence ledger; score-inactive
   protocol events have no score snapshots.
7. The GitHub Pilot readiness gate requires quality, browser, and Compose
   success on the same commit.
8. The mobile walkthrough proves keyboard content access, five-protocol
   coverage, score-boundary copy, and no horizontal overflow.
9. Desktop/mobile screenshots and failure traces are retained for human
   review.
10. M4E creates no migration, protocol, evidence algorithm, scoring algorithm,
    current-state mutation path, or external telemetry.

## M5A acceptance criteria

1. Feedback submission and export require an authenticated session.
2. The UI says feedback is optional, local, not developmental evidence, and
   not monitored for urgent support.
3. Applicability, rough time-to-start/check-in, confusing-step, and
   accessibility/safety-friction categories are available without requiring
   free text.
4. Timing is participant-estimated in broad bands; the application adds no
   automatic timing, analytics, recording, or remote telemetry.
5. Submitted feedback is append-only and versioned as
   `GG-PILOT-FEEDBACK-1.0`.
6. The per-user export is deterministic, allowlisted, and versioned as
   `grounded-growth-private-pilot-export-v1`.
7. The export excludes identity, database IDs, exact timestamps, free text,
   private context, assessment data, evidence, score state, orientations, and
   archetypes.
8. Submission and export leave every assessment, baseline, current state,
   score snapshot, evidence event, sprint/check-in/review state, orientation,
   archetype, and recommendation priority unchanged.
9. The operator guide covers consent, neutral observation, non-fabricated
   evidence, accessibility/safety response, export review, and stop criteria.
10. M5A adds no protocol, score activation, scoring/ranking input, external
    service, or administrative surface for ordinary users.

## M5B acceptance criteria

1. A non-practice feedback stage does not display or accept a protocol,
   applicability, setup-time, or check-in-time response.
2. Practice feedback questions appear only for their documented journey
   stages, with server-side enforcement when JavaScript is absent or bypassed.
3. Existing `GG-PILOT-FEEDBACK-1.0` records remain unchanged and exportable.
4. A check-in displays only observation prompts from the selected action's
   reviewed primary/supporting marker set.
5. The next required action is preselected when entering its check-in from the
   active-practice page.
6. A new submitted check-in requires `action_attempted=true`; a draft remains
   available before the action occurs.
7. Truthy observations belonging to another action fail with an actionable
   error rather than being ignored or normalized.
8. The prospective submission gate changes no existing event, evidence
   output, score transition, replay result, completion rule, protocol, or
   activation boundary.
9. Pilot-feedback deletion is read-only by default, requires an exact local
   username and explicit confirmation, and cannot delete developmental state.
10. M5B adds no telemetry, automatic timing, evidence/scoring mathematics,
    protocol, recommendation input, or score activation.

## M6A acceptance criteria

1. The practice release manifest explicitly enumerates all packages, schemas,
   and registries and rejects unlisted, unsafe, unknown-version, or
   unknown-field inputs.
2. Canonical parent/domain IDs and recommendation-target subsets validate
   against the unchanged 383-competency, 37-lever mapping before writes.
3. Five `projected_legacy` packages and fifteen actions reproduce the exact
   reviewed runtime fingerprint and seed idempotently.
4. `CurriculumVersion.source_hash` remains unchanged; the practice release has
   a separate deterministic content hash.
5. The coverage ledger has exactly 383 rows: five projected packages and 378
   explicitly unauthored competencies across all 27 domains.
6. Domain, lever, risk, scoring-policy, source, activation, research-gap,
   expert-review, and originality state are explicit and deterministic.
7. The known 383-row Notion journal-prompt duplication, uniform five-package
   action/duration warnings, and two legacy evidence-rule duplicates are
   reported rather than silently normalized.
8. Friendship remains the only score-active protocol. The other four remain
   executable but shadow-only for scoring.
9. `GG-PILOT-READINESS-1.0` remains independently callable and unchanged;
   `GG-CURRICULUM-EXPANSION-READINESS-1.0` is additive and read-only.
10. M6A adds no migration, protocol, action, UI, typed evidence execution,
    scoring/ranking mathematics, or score activation.

## M6B acceptance criteria

Software implementation may satisfy criteria 1–13, but criterion 14 is an
external governance gate. Until it is satisfied, report the branch as
software-ready but not M6B-accepted.

1. `GG-EVIDENCE-1.0`, `practice-observation-v1`,
   `GG-SCORING-SHADOW-1.0`, `GG-SCORE-STATE-1.0`, and
   `GG-NEED-RANKING-1.0` retain exact independent replay and output.
2. `GG-TYPED-EVIDENCE-1.0` dispatches only
   `typed-evidence-rules-v1`, snapshots materialized rules and minimal
   structured provenance, and fails closed on missing, malformed, mismatched,
   or unknown versions.
3. Exact fixtures cover Boolean, count/frequency, ordinal, duration, artifact,
   conceptual/scenario, objective, consented-observer, qualified-attestation,
   unknown/not-observed, contradictory, and adverse input.
4. Typed values have rule-defined normalization; the engine never assumes
   that more, longer, or higher is better. Free text, artifact content, and
   unnecessary observer/qualified-review narrative cannot affect output.
5. Unknown, not observed, inconclusive, not applicable, deferred,
   contradictory, and adverse states remain distinct. N/A/defer never
   produces a deficit, and adversity does not silently become contradiction.
6. `GG-COMPETENCY-EVIDENCE-SHADOW-1.0` is evidence-only, returns unknown for
   zero eligible evidence, and does not invent or mutate a competency or
   assessment baseline.
7. `GG-COMPETENCY-LEVER-SHADOW-1.0` uses the complete canonical parent
   mapping, rejects duplicate event keys and malformed mappings, applies one
   designated competency contribution per event, and never feeds a
   lever-derived competency summary back to levers.
8. Replay is deterministic and input-order independent; reversal restores the
   exact starting projection; old evidence remains attached to its original
   assessment epoch after reassessment.
9. `GG-PRODUCTION-SCORE-ELIGIBILITY-1.0` enforces exact eligibility with
   explicit fail-closed diagnostics. Typed-shadow withholding reasons remain
   in their evidence contributions. Every new typed path is
   production-ineligible in M6B, and friendship remains the only
   score-active protocol.
10. Property/invariant tests prove bounds, idempotent replay, duplicate
    rejection, no double counting, explicit withholding, exact reversal, no
    baseline mutation, and fail-closed version behavior.
11. `typed_evidence_capability_v1.csv`,
    `scoring_policy_execution_v1.csv`, and
    `competency_evidence_readiness_v1.json` are deterministic and fresh. The
    readiness report records zero typed production protocols, zero typed
    score-active protocols, and does not equate software readiness with M6B
    acceptance.
12. The exact five-protocol/fifteen-action runtime projection, 5/383 content
    coverage, curriculum/model/mapping source hash, existing readiness gates,
    and recommendation behavior remain unchanged. M6B governance inputs use a
    new deterministic practice-catalog content hash without changing the
    legacy runtime projection hash.
13. M6B adds no migration, persistence model, UI, protocol, action, M6C
    context-priority input, recommendation/ranking change, or production
    state write.
14. `ER-M6A-003` is truthfully completed by the required measurement,
    accessibility, and privacy/safety roles with date and decision reference,
    and `RG-M6A-002` is resolved. Until then, M6B acceptance and production
    use of the new typed paths remain blocked even when software readiness
    passes. The later owner-directed sequencing of non-scored software/content
    work does not satisfy or waive this criterion.

## M6C-01 acceptance criteria

1. Season, capacity, applicability, importance, readiness, urgency,
   opportunity/resources, and burden use bounded typed definitions and
   explicit unknown, not-applicable, deferred, or provided states.
2. Missing factors and hidden values fail closed; unknown, N/A, and deferred
   are never replaced with zero or another invented default.
3. Candidate defer/not-now requires a reason category and permits only an
   optional 1–366 day review horizon; it creates no developmental deficit.
4. Every record belongs to one user and assessment epoch. Practice context
   also belongs to one stable protocol in that epoch's curriculum.
5. Reassessment never inherits context silently. All reads require the exact
   assessment run.
6. Pure canonical snapshots and SHA-256 hashes reproduce exactly for unchanged
   semantic input and differ by assessment epoch.
7. Changed context appends a revision; unchanged retry is idempotent; malformed
   bundle input writes nothing.
8. Migration 0008 creates only the two context tables and reverses without
   rewriting any existing assessment, evidence, score, feedback, practice, or
   review record.
9. Existing evidence, typed evidence, score-state, need-ranking, pilot,
   curriculum, and competency-evidence contracts remain independently exact.
10. Recommendations, ordinary UI, canonical practice data, and friendship-only
    production activation remain unchanged.
11. `GG-CONTEXT-READINESS-1.0` is additive, read-only, and fails closed on
    ownership, scope, version, bound, snapshot, hash, or revision drift.
12. Software evidence is not accessibility, cultural, longitudinal,
    specialist, clinical, psychometric, release, or production validation.

## M6C-02 acceptance criteria

1. Exactly five identity sections and four audit prompts are fixed under
   `GG-PERSONAL-OS-1.0`; no identity, audit, diagnostic, or worth score exists.
2. Every section is explicitly unknown, N/A, deferred, or provided, with
   scalar/list bounds and no hidden value.
3. Prompt/help definitions are user-authored, minimal-detail,
   non-diagnostic, non-shaming, and state that mismatch does not diminish
   worth.
4. Every revision belongs to one authenticated user and immutable assessment
   epoch; no source domain or older epoch supplies inferred values.
5. The pure builder rejects malformed input and produces deterministic compact
   UTF-8 JSON and SHA-256 from the exact private snapshot allowlist.
6. Changed input appends contiguously, unchanged retry is idempotent, direct
   mutation/deletion is blocked, and concurrent SQLite writes succeed safely
   or return a retryable conflict.
7. Schema-only migration 0009 reverses to 0008 without rewriting any
   pre-existing growth row.
8. Private values do not enter existing exports, logs, reports, telemetry,
   recommendations, score snapshots, or activation decisions.
9. `GG-PERSONAL-OS-READINESS-1.0` accepts empty state and fails closed on
   version, ownership, epoch, field, bound, snapshot, hash, or revision drift
   without printing private values.
10. Context and every existing assessment, evidence, scoring, recommendation,
    pilot, curriculum, and activation boundary remains exact.
11. M6C-02 adds no form, route, template, browser collection, ranking,
    alternative recommendation, weekly execution, export, deletion, or
    retention policy.
12. Focused and complete repository checks plus unchanged browser/Compose
    regressions are required before merge.
13. Software evidence is not M6B governance, accessibility, cultural,
    clinical, psychometric, longitudinal, participant, release, deployment,
    or production validation.

## M6C-03 acceptance criteria

1. `GG-CONTEXT-PRIORITY-1.0` is pure, deterministic, Decimal-based, and scoped
   to one explicit user-owned assessment epoch with verified latest context.
2. Supplied candidates are unique active manifest-projected protocols whose
   canonical parents, full weights, and recommendation-target subsets verify.
3. Applicability N/A, defer, missing context, and explicit zero remain
   distinct; withheld candidates never sort as numeric deficits.
4. Capacity must be explicitly provided for a numeric result; season is
   descriptive and has no ordering or multiplier effect.
5. Provided ordinals normalize as `x / 4`, burden as `1 - burden / 4`, and the
   seven-term product is quantized half-up once to four decimal places.
6. Eligible candidates order by context priority, unchanged base priority, and
   stable protocol ID; no personality, Personal OS, or free-text modifier is
   used.
7. N/A/defer alternatives are distinct eligible members of only the supplied
   cohort, or explicitly `no_eligible_alternative`.
8. The canonical result includes versions, stable IDs, priorities, factor
   states/contributions, explanations, exact context hashes, compact UTF-8 JSON,
   and SHA-256 while excluding private and unrelated domains.
9. `build_profile_summary`, forms, routes, views, templates, browser output,
   exports, assessments, evidence, score state, protocols, and activation
   remain exact and unchanged.
10. `GG-CONTEXT-PRIORITY-READINESS-1.0` replays the synthetic golden cohort,
    validates the canonical projection/activation and optional persisted
    context, accepts empty state, writes nothing, and sanitizes drift errors.
11. No model, migration, backfill, priority persistence, UI, telemetry,
    deletion/retention policy, canonical report/content, or production write is
    added.
12. Focused and full deterministic gates plus unchanged browser and Compose
    regressions are required before merge.
13. Software evidence does not establish recommendation usefulness, M6B
    governance, participant, specialist, accessibility, cultural, safety,
    clinical, psychometric, longitudinal, release, deployment, production, or
    mastery validation.

## M6C-04 acceptance criteria

1. The browser entry is authenticated, uses only the owner's latest
   `AssessmentRun`, redirects no-assessment users to assessment, and never
   carries Personal OS or context forward to a new assessment epoch.
2. Exactly five identity sections, four descriptive Truth/Autopilot prompts,
   season, and capacity are progressively disclosed. Every value may remain
   unknown, N/A, or deferred; no completion, alignment, autopilot, diagnostic,
   morality, or worth score is created.
3. Personal OS and assessment-context POSTs use the unchanged services, CSRF,
   and POST-redirect-GET. Changed input appends one revision, unchanged retries
   are idempotent, stale/malformed input writes nothing, and retryable database
   conflicts reveal no private value.
4. One active manifest-projected practice is reviewed at a time. The user must
   either provide all six explicit 0–4 factors, mark applicability N/A, or defer
   a named factor with a categorical reason and optional 1–366-day horizon.
   Ordinals have no preselected default and no factor is inferred.
5. The browser presenter supplies only current-epoch, explicitly reviewed,
   active canonical practices to the unchanged M6C-03 engine. Ranking is
   labeled as partial-cohort ranking and is never persisted.
6. No current-epoch context preserves exact legacy recommendation IDs,
   priorities, order, reasons, and practice behavior. Missing capacity or no
   eligible candidate is explicit and is not called context-aware fallback.
7. With explicit capacity and an eligible reviewed cohort, home, practice
   list, and recommendation surfaces use exact engine order plus fixed
   allowlisted explanations that distinguish provisional need from current fit
   without false precision or worth, obligation, diagnosis, or mastery claims.
8. N/A/deferred candidates may request the highest-ranked distinct eligible
   alternative from only that reviewed cohort, or receive an explicit
   no-eligible-alternative state. The request does not invent context or mutate
   practice, evidence, deficit, score, or activation state.
9. Authored Personal OS text appears only on its owner's authenticated Personal
   OS page and is excluded from ranking, other recommendation surfaces,
   messages, logs, URLs, retained non-Personal-OS artifacts, reports, telemetry,
   existing exports, evidence/score snapshots, and activation.
10. The page gives a pre-collection privacy notice: values are private local
    data included in normal backups, minimal detail is preferred, and this
    slice adds no dedicated export, purge, automated retention, telemetry,
    urgent-support monitoring, participant release, or new deletion guarantee.
11. Authentication, CSRF, ownership, stale-epoch isolation, labels, semantic
    headings, keyboard focus, 200-percent zoom, 390-by-844 layout, reduced
    motion, and no-horizontal-overflow behavior fail closed without an external
    asset or runtime service.
12. Read-only `GG-M6C-PILOT-READINESS-1.0` verifies all six prerequisite
    readiness contracts, exact Personal OS/context definition IDs, registered
    authenticated routes, five active protocols, friendship-only activation,
    and empty or valid optional state without writes or private output.
13. The isolated Compose drill creates only synthetic Personal OS/context
    revisions through public services, builds a deterministic priority result,
    exercises authenticated HTTP, and proves state hashes and activation
    survive recreation and verified backup/restore.
14. Focused and full deterministic checks, browser journeys, Compose, required
    hosted CI, retained-artifact review, and the aggregate Pilot readiness gate
    must pass on the exact candidate commit before owner merge review; every
    skipped, unavailable, or unperformed item is reported.
15. Canonical content, assessment, evidence, typed/shadow paths, score state,
    exports, practice workflow, five-protocol projection, and friendship-only
    activation remain exact. No persistence schema, protocol/action,
    dependency, external service, remote telemetry, weekly execution, or
    production-score change is added.
16. M6B governance remains pending. Software, browser, CI, or Compose evidence
    is not specialist, participant, accessibility-population, cultural-safety,
    clinical, psychometric, longitudinal, recommendation-usefulness, release,
    deployment, production, or mastery validation.

## M6D-01 acceptance criteria

1. Exactly competencies `08.06`, `09.12`, `10.02`, and `13.02` have new
   canonical packages under their contracted stable IDs, domains, families,
   target-lever subsets, and action counts.
2. Each package is low-risk, draft, inactive, unprojected, shadow-only, and
   score-inactive, with explicit applicability, adaptations, privacy, safety,
   completion, transfer, and mastery boundaries.
3. Claim-level sources and unresolved research gaps are explicit; source
   discovery is not represented as source completeness or validation.
4. The source-only typed loader validates exact sibling identities and rejects
   mixed, unknown, malformed, or runtime-projected typed rules without changing
   legacy `practice-observation-v1` behavior.
5. Fourteen conspicuously synthetic action fixtures replay deterministic
   supportive, contradictory, inconclusive, unavailable, adverse, recency,
   repetition, and duplicate-origin paths without private prose or artifacts.
6. Generated reports show the M6D-01 frontier of 383 competencies, nine source
   packages, twenty-nine source actions, and 374 uncovered competencies while
   distinguishing the frozen five-protocol/fifteen-action runtime.
7. `GG-M6D-01-AUTHORING-READINESS-1.0` verifies cohort identities, hashes,
   fixtures, inactive governance, prerequisite readiness, and no database
   writes. Persisted batch tests assert the owned cohort while shared tests
   derive any later catalog frontier from canonical state.
8. Historical evidence/score replay, M6C behavior, the frozen runtime
   projection hash, and friendship-only activation remain exact.
9. Hosted CI is required before the source-only merge. Trained content/source/
   originality/accessibility/privacy/safety, retained-evidence, and owner review
   are explicitly deferred to the final 383/383 M6B-GOV gate; software and
   synthetic evidence do not establish specialist, participant, clinical,
   psychometric, longitudinal, effectiveness, release, deployment, production,
   or mastery validation.

## Full competency source frontier acceptance criteria

1. The catalog contains exactly 383 packages with a one-to-one match to all
   383 canonical competency IDs across all 27 domains and no uncovered row.
2. The nine previously authored packages remain authoritative. The 374
   generated packages have deterministic stable IDs and exactly 1,122 unique
   generated action IDs, titles, and instructions.
3. Every generated action has typed evidence rules and a stable measurement
   identity; each package retains competency-specific scope, evidence target,
   applicability, N/A/defer behavior, adaptations, privacy, safety, completion,
   transfer, and mastery boundaries.
4. All 37 levers are covered through canonical parent mappings and through
   recommendation targets that are non-empty subsets of those mappings.
5. Every generated package is a draft, inactive, unprojected, and has no
   approved activation contract. High-risk generated packages use
   `SP-NON-SCORED-REFLECTION`; all others use `SP-SHADOW-ONLY`.
6. Originality reports contain zero exact duplicate action titles,
   instructions, or reflection sets. Bounded near-duplicate warnings remain
   retained for consolidated human disposition.
7. The source registry, activation ledger, release manifest, generated YAML,
   and deterministic reports agree on one catalog hash and fail closed on
   drift.
8. The runtime remains exactly five protocols and fifteen actions, with the
   frozen projection hash and friendship-only score activation unchanged.
9. No source package is represented as source-complete, release-ready,
   specialist-approved, participant-validated, or effective until the
   consolidated audit and separately authorized validation are complete.

## Handoff audit notes

- Canonical curriculum counts remain 27 domains, 383 competencies, 37 levers,
  6 orientations, 15 archetypes, and 1,403 weighted links.
- The M1B assessment view serves the canonical
  `assessment_scoring_v1_1.js` directly; it does not maintain a divergent copy.
- The standalone UI omitted the spec's optional orientation-clarifier stage.
  The integrated page exposes both canonical capability and orientation
  clarifiers without changing question wording or scoring.
- Valid all-N/A assessment outcomes can produce null raw/calibrated/need
  values, so M1B allows those baseline fields to be null.
- Pilot 002 remains available for immediate demonstration. Later in-app or
  imported assessments become the current profile without rewriting the seed.
- M2A preserves existing submitted check-ins byte-for-byte. Its startup
  backfill creates separate events with conservative unknowns and verifies
  existing events by replaying their input snapshots.
- M2B adds no migration and changes no stored event. Its export is minimized
  for calibration but remains sensitive behavioral data. Exact event and user
  identifiers, dates, private context, notes, contradiction detail, assessment
  answers, and share codes are deliberately absent.
- M3A does not parse the Notion `Lever Mapping` field. The friendship protocol
  references `17.03`, whose canonical structured weights are L26 `0.65`, L10
  `0.15`, L23 `0.10`, and L24 `0.10`.
- New assessment baselines store the canonical scorer's alpha/beta values.
  Pilot 002 reconstruction succeeds for all four friendship levers; neutral
  published pairs that do not identify mass remain null.
- `GG-SCORING-SHADOW-1.0` keeps inconclusive and legacy-unknown events in the
  audit ledger but withholds them from posterior and confidence.
- The dormant browser helper's mass-only confidence line was not adopted: it
  can lower the displayed assessment confidence after adding evidence. M3A
  uses an anchored monotonic gain and leaves assessment v1.1 unchanged.
- M3A review accepted Decisions 019–022 without a scoring-math change.
- M3B retains `GG-SCORING-SHADOW-1.0` as the exact accepted math version and
  versions persistence and ranking separately as `GG-SCORE-STATE-1.0` and
  `GG-NEED-RANKING-1.0`.
- Pilot 002 initializes 37 current rows: 33 evidence-active and L06, L15, L32,
  and L37 baseline-only. All four friendship-mapped rows are active.
- Dynamic need intentionally reproduces the assessment v1.1 provisional
  function. Context-aware applicability/importance/readiness/urgency ranking
  is not claimed because those inputs are not collected.
- The only score-active protocol remains Deepen One Existing Friendship.
  Play, emotional cue detection, boundary practice, and the attention-presence
  experiment are executable but score-inactive.
- M3B review accepted Decisions 023–026 without changing its scoring
  mathematics or activation boundary.
- `make compose-smoke` is the repeatable deployment gate. It uses an isolated
  Compose project and throwaway named volume to prove the image, mapped-port
  login, health, migrations, idempotent seeding, evidence/score/readiness
  replay, persistence, online backup, restore, and clean shutdown without
  touching a real `.env` or deployment volume.
- M4E adds no migration or state-changing startup step. Its readiness command
  is strictly read-only; `make pilot-check` constructs disposable state before
  calling it.
- The GitHub Pilot readiness gate combines quality, the ten established
  Playwright journeys plus the M6C-04 Personal OS/context journey, and Compose.
  Its retained artifact supports, but does not replace, human desktop/mobile
  review.
- M5A adds one migration for a separate optional `PilotFeedback` table. No
  existing canonical, assessment, evidence, score, sprint, or review table is
  changed.
- Pilot timing categories are participant estimates. There is no automatic
  measurement, external analytics endpoint, or remote telemetry.
- Pilot feedback free text remains local and is deliberately excluded from
  the deterministic minimized export. The export is still sensitive pilot
  data and is not claimed to be anonymous.
- Private Pilot 001 retained no direct identity or private content in the
  repository. Its minimized exports showed one stage/practice mismatch,
  action-irrelevant observation fields, and a no-attempt evidence submission.
- M5B responds prospectively at form and service boundaries. It does not
  migrate, rewrite, delete, reinterpret, or change replay of the original
  append-only feedback/check-in/evidence rows.
- Optional pilot feedback has no automatic retention timer. The
  preview-first `purge_pilot_feedback` command deletes only an explicitly
  named local user's feedback after `--confirm`; backups must be handled
  separately under the same participant agreement.
- M6A replaces the importer tuple with manifest-listed canonical packages.
  The release is fully validated before writes and projects only existing ORM
  fields.
- The canonical curriculum/model/mapping source hash remains
  `6958ccfbe0c0d80b7485ac866a8418578850284b58956f59168429819447dfc5`;
  the reviewed five-protocol projection remains
  `274f7244630ed56d56a443a6a699399edade6c67fcf964237559e05b72368e35`.
- The generated baseline is intentionally incomplete: 5/383 competencies,
  5/27 domains, 13/37 parent-mapped levers, six recommendation-target levers,
  three low-risk and two moderate-risk packages, one score-active protocol,
  and zero source-complete release candidates.
- All five migrated packages retain `practice-observation-v1` solely for
  compatibility. M6A metadata describing richer evidence does not execute;
  M6B must establish typed replay semantics before later authoring or
  activation.
- M6B's proposed direct competency state is evidence-only because assessment
  v1.1 provides lever baselines, not competency baselines. Zero eligible
  evidence is unknown, not a neutral score.
- Typed evidence remains pinned to its original assessment epoch. The proposed
  M6B contracts define no automatic carry-forward after reassessment.
- Passing `GG-COMPETENCY-EVIDENCE-READINESS-1.0` demonstrates software
  determinism only. `ER-M6A-003` and `RG-M6A-002` remain the explicit
  specialist-review blockers for M6B acceptance, runtime projection, score
  activation, participant release, deployment, and validation claims. Under
  Decision 051 they do not block CI-gated source-only draft authoring.
- M6C-01 context scales are explicit storage contracts only. No factor is read
  by profile, recommendation, evidence, scoring, or ordinary UI code in this
  batch. The context snapshot excludes identity and narrative, while the local
  database and its backups remain sensitive participant data.
# Current M6F override — 2026-08-26

Decision 052 and ADR 0011 supersede every five-runtime, friendship-only,
inactive, unprojected, source-only, or shadow-only activation ceiling in the
historical milestone record below. The current owner-directed contract is
exactly 383 runtime protocols, 1,151 actions, and 383 score-active protocols.
The five original protocols retain legacy v1 replay; 378 protocols use typed
structured evidence. Assessment baselines and completion/mastery and
human-worth boundaries remain unchanged. Deferred content and specialist audit
status remains visible and is not converted into a validation claim.

# Current M6H-01 integration — 2026-08-27

M6H-01 is the current software-only full-product integration slice. It adds an
authenticated weekly loop over the latest verified Personal OS direction, the
existing context-priority presentation, one current-practice action, and an
immutable proof review. Plan revisions are append-only. Review proof is
limited to exact submitted evidence after plan creation and before a frozen
review cutoff. The weekly layer creates no evidence, score state,
recommendation factor, practice completion, or mastery claim. Manual audit,
specialist review, participant work, release, and deployment approval remain
outside this slice.

# Current M6H-02 operations — 2026-08-31

M6H-02 adds an authenticated owner-data surface and deterministic operations
gate. The owner-private archive includes all and only the signed-in owner's
application records and explicitly includes private narrative; it is not a
sharing export. Password hashes, sessions, opaque database keys, other users,
secrets, and server metadata are excluded.

Deletion requires the current password, an exact phrase, and an unchanged
signed preview. It removes the selected account, sessions, and owned rows in
one transaction while preserving canonical content and other users. Retention
is disabled by default, has no scheduler, and can target only old drafts and
optional pilot feedback after a separate preview and confirmation. Existing
backup copies remain separate private artifacts.

`backup_database` now creates a `0600` SQLite snapshot and counts-and-hashes
sidecar. `verify_database_backup --compare-live` proves integrity, migrations,
and exact critical state before upgrade or after rollback. These operations do
not change evidence, scoring, recommendation, completion, or mastery semantics.

# Current M6B governance audit — 2026-09-01

M6B-GOV-AUDIT is the deterministic software precursor to the manual M6B-GOV
gate. It produces one schema-validated row for every canonical package and
stable action, retains every objective or pending-review finding under a
stable ID, and routes the resulting queue by role, risk, domain, protocol
family, evidence kind, and dependency.

The current packet records exactly 383 packages, 1,151 actions, five legacy
packages, 378 typed packages, 374 generated additions, 383 score-active
packages, and zero source-complete packages. This is a static catalog audit;
it reads no participant or owner-private data and writes no runtime state.

The audit is intentionally unable to accept M6B. `ER-M6A-003` remains pending
with no completed roles, date, or decision reference, `RG-M6A-002` remains
open, and the separate manual M6B-GOV specialist and owner records remain
required.

# Current M6I-01 composite closeout scoring — 2026-09-01

Decision 053 prospectively supersedes Decision 052's event-level production
score trigger while retaining all 383 runtime protocols and all historical
`GG-SCORE-STATE-1.0` history. A concise assessment now projects labeled
starting estimates across 7 families, 37 levers, 27 domains, and 383
competencies. Relationships blend canonical relevance and equal mapped-lever
share 50/50; competency and priority composites use 50% lever, 25% family,
and 25% parent domain components.

New check-ins remain immutable evidence and do not change global coverage.
The user must explicitly close the whole practice after its substantive and
minimum-action criteria are satisfied. The minimum earns 0.75 completion
credit and all defined actions earn 1.00; repeated practices use the
maximum active credit rather than a sum. Shared lever, family, and domain
coverage then reduces remaining priority and reranks the next-practice queue.
Completion is not mastery.

The deterministic catalog covers 383 practices and all 1,151 equal action
units. `ER-M6A-003` remains pending, `RG-M6A-002` remains open, and M6B
specialist acceptance remains false. This is owner-approved software
architecture, not psychometric, clinical, cultural, accessibility,
privacy/safety-specialist, participant, longitudinal, or intervention-
effectiveness validation.

# Current M6I-02 applicability and personal coverage — 2026-09-02

Decision 054 adds a direct explicit not-applicable route to an active
recommendation and derives a separately labeled personal-applicable coverage
denominator from latest verified current-epoch context revisions. Unknown,
deferred, provided, and zero remain distinct; an empty denominator is
unavailable. Applicability awards no credit and changes no canonical coverage,
score state, recommendation mathematics, baseline, or historical replay.

# Current M6I-03 assessment calibration readiness — 2026-09-02

Decision 055 adds the source-only
`GG-ASSESSMENT-CALIBRATION-READINESS-1.0` audit. It freezes the assessment v1.1
specification, model, scorer, and coverage hashes; verifies the exact 50 core,
43 clarifier, 37-lever, seven-family, and six-orientation inventory; and proves
one direct item and one adaptive clarifier per lever with complete frozen
coverage parity. The existing JavaScript golden replay remains mandatory.

All eight empirical calibration axes remain `data_collection_required` with
zero completed. The audit reads no database or private runtime data and changes
no assessment, scoring, recommendation, evidence, completion, UI, migration,
or replay behavior. It is not psychometric, fairness, accessibility-population,
participant, longitudinal, or effectiveness validation. `ER-M6A-003` remains
pending, `RG-M6A-002` remains open, and M6B specialist acceptance remains
false.

# Current M6I-04 consented assessment calibration data — 2026-09-02

ADR 0016 adds `GG-ASSESSMENT-CALIBRATION-CONSENT-1.0` as an explicit
secondary-use boundary around already-stored completed assessment runs.
Participant-created runs remain excluded by default; the Pilot 002 seed is
ineligible. Consent, withdrawal, and later reconsent are authenticated,
per-run, append-only, contiguous, idempotent, and snapshot/hash verified.

The deterministic dataset links explicitly included retakes with a random
pseudonymous participant token and exports item responses, clarifiers, timing,
allowlisted response-quality summaries, run sequence, and whole-day intervals.
It excludes identity, database and assessment IDs, exact timestamps, share
codes, free text, Personal OS/context, practice/evidence/completion/score
history, and derived profile outputs. The owner can inspect their contribution;
the acknowledged local operator command writes a new mode-0600 file and never
uploads or overwrites it.

Withdrawal affects future exports and does not delete or mutate the underlying
private assessment. Calibration consent is included in owner archive, account
deletion, backup, restore, and migration rollback and is not an automated
retention target. This software path contributes zero observations and closes
zero M6I-03 evidence axes. Completed runs do not measure abandonment, and all
qualified analysis and human validation gates remain open.

# Current M6I-05 assessment calibration analysis readiness — 2026-09-03

ADR 0017 adds `GG-ASSESSMENT-CALIBRATION-ANALYSIS-READINESS-1.0` as a deterministic,
local-only analysis boundary for an exact M6I-04 consented export. The
operator command requires explicit sensitive-input acknowledgement, verifies
the export and its hash, reads no database, performs no upload, refuses
overwrite, and creates a mode-0600 private aggregate.

The report contains only exact cohort/source totals, small-cell-suppressed item
distributions and timing summaries, allowlisted response-quality summaries,
threshold status, exploratory linked-retest agreement, and explicit per-axis
limitations. Participant rows, pseudonyms, raw responses and timing, exact
timestamps, identity, share codes, free text, Personal OS/context,
practice/evidence/completion/score history, and derived profile outputs remain
excluded. The aggregate remains sensitive and is not safe for public sharing.

Thirty consented participants and thirty linked-retest participants are fixed
software workflow thresholds. Meeting them makes a dataset only a candidate
for qualified analysis. The M6I-04 export lacks external reference measures,
population-group variables, abandoned attempts, fit judgments, and
longitudinal outcomes; completed-run timing cannot measure abandonment. All
eight participant evidence axes remain incomplete and not established with
`completed_axes` fixed at zero. All qualified-analysis, specialist,
psychometric, fairness, accessibility-population, cultural, participant,
clinical, longitudinal, release, deployment, mastery, and effectiveness gates
remain open.
