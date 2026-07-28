# Grounded Growth — Project Handoff

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
Baseline mastery, confidence, evidence mass, and eventually current posterior state.

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
- The GitHub Pilot readiness gate combines quality, ten Playwright journeys,
  and Compose. Its retained artifact supports, but does not replace, human
  desktop/mobile review.
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
