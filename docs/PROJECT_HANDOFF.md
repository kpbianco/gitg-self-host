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

Only submitted check-ins count toward completion. A database constraint limits
each user to one active or paused practice. Services—not templates—own state
transitions, evidence aggregation, and completion rules.

The stored-profile boundary is tested before and after practice completion,
event creation, ledger viewing, export, replay verification, and M3A
projection. M2 stores event-level base evidence mass. M3A computes posterior
values in memory but writes no current mastery, confidence, need/priority,
archetype, orientation, recommendation, or score snapshot.

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

Status: implemented; pending pull-request review.

The binding proposed contract is in `docs/scoring-shadow.md`. M3A is a
software-review and calibration gate, not psychometric validation.

#### M3B — State activation and dynamic ranking
- immutable before/after score snapshots;
- atomic, idempotent state application;
- rebuild and reversal from versioned events;
- current mastery/confidence state separated from assessment baseline;
- recalculated need and dynamic practice ranking;
- migration policy for baselines whose exact mass is unavailable.

Status: not started. Do not begin until M3A is reviewed and explicitly
approved.

### M4 — Protocol library expansion
Create reusable protocol patterns and convert more of the 383 competencies into executable interventions.

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
