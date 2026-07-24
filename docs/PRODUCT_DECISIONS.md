# Product Decisions

## Decision 001 — Self-hosted consumer app
**Status:** Accepted

Notion remains the content studio. A dedicated web application is the consumer runtime.

## Decision 002 — Protocols, not competencies
**Status:** Accepted

The app recommends executable Practice Protocols. Competencies remain the curriculum ontology and recommendation target.

## Decision 003 — Static scores for Milestone 1
**Status:** Accepted

M1 may show a score-impact preview but must not mutate mastery or confidence.

## Decision 004 — Evidence before algorithm
**Status:** Accepted

Do not integrate the posterior update algorithm until structured evidence capture passes user testing.

## Decision 005 — Stable IDs over display text
**Status:** Accepted

All joins and imports must use canonical IDs. Display labels are editable and not authoritative.

## Decision 006 — Orientation is not mastery
**Status:** Accepted

Orientation/archetype data influences language, framing, and tie-breaking only.

## Decision 007 — No universal worth score
**Status:** Accepted

No aggregate score may be presented as human value, virtue, or a complete measure of flourishing.

## Decision 008 — Django monolith
**Status:** Accepted

M1 uses a single Python/Django application with server-rendered templates,
local assets, Gunicorn, and one Docker Compose service. The earlier suggested
Next.js architecture is superseded. A separate frontend, API service, and
Node.js runtime would add deployment and state boundaries without helping the
single-user local-instance validation.

## Decision 009 — SQLite for the local single instance
**Status:** Accepted

M1 stores application state at `/data/grounded_growth.sqlite3`, uses Django
migrations, a busy timeout, and WAL where supported. The data directory is a
persistent Docker volume. ORM usage should remain portable, but no PostgreSQL
service is added until deployment needs demonstrate that concurrency or
operational complexity is justified.

## Decision 010 — Browser scoring remains the M1 reference
**Status:** Accepted

Assessment v1.1's canonical JavaScript scoring engine remains the reference
implementation. Golden tests lock its known input/output behavior. Django
serves that exact engine to the authenticated assessment page and validates
the complete persisted result, but does not rewrite its mathematics or enable
its dormant evidence-update functions.

## Decision 011 — M1A before guided workflow
**Status:** Accepted

M1A establishes deployment, authentication, schema, canonical import, and the
Pilot 002 profile. Assessment-taking/import and the practice workflow are M1B
and begin only after M1A review.

## Decision 012 — Submitted evidence is distinct from working state
**Status:** Accepted

Practice check-ins may be saved as drafts. Only explicitly submitted,
timestamped, immutable check-ins appear in evidence history or count toward
completion. Submitted evidence is not converted into a score in M1.

## Decision 013 — Bounded completion without mastery
**Status:** Accepted

The first practice completes only after all three actions have been attempted,
at least two completed, a substantive interaction recorded, and a final review
submitted. Completion records protocol participation only. Every review and
completion screen states that completion does not establish mastery.

## Decision 014 — One current practice
**Status:** Accepted

A user may have one active or paused practice at a time. Pausing is reversible;
stopping is terminal. This keeps the home page and next action unambiguous
while M1 validates the guided experience.

## Decision 015 — Versioned evidence events before score updates
**Status:** Accepted

Each submitted check-in creates one immutable `GG-EVIDENCE-1.0` event in the
same transaction. The event records protocol adherence, structured quality,
independence, bounded context breadth, action-specific repetition,
contradiction, and base evidence mass. It snapshots exact structured inputs
and action rules for deterministic replay without copying private note text.
Drafts create no event.

## Decision 016 — M2 event mass is not lever state
**Status:** Accepted

M2A stops at `e = q × i × b × r`. It does not calculate task-to-lever
coefficients, success/failure contributions, posterior mastery, confidence,
need, task priority, or dynamic recommendations. Existing M1 submissions are
backfilled conservatively: missing context/support stay explicitly unknown,
and absence of contradiction text is not converted into supportive evidence.
