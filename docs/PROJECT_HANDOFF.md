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

## Milestone sequence
### M1 — Guided UX, static scores
Build the app shell and full friendship protocol. Import profile and curriculum. Do not mutate scores.

### M2 — Evidence engine
Add structured evidence events, drafts/submission, quality, independence, context breadth, repetition, and contradiction.

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
