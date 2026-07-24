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

Only submitted check-ins count toward completion. A database constraint limits
each user to one active or paused practice. Services—not templates—own state
transitions, evidence aggregation, and completion rules.

The static-score boundary is tested before and after practice completion. No
M1 workflow writes lever mastery, confidence, evidence mass, need/priority,
archetype, or orientation scores.

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

Status: implemented; pending pull-request review.

### M2 — Evidence engine
Extend submitted check-ins with versioned evidence quality, independence,
context breadth, repetition, and contradiction semantics. Draft/submitted
state already exists in M1.

Do not begin M2 until the M1B pull request is reviewed and a separate M2
contract resolves evidence semantics, migration strategy, and scoring
boundaries.

### M3 — Dynamic scoring
Implement versioned posterior updates and dynamic recommendation ranking in a pure domain package with exhaustive tests and immutable snapshots.

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
