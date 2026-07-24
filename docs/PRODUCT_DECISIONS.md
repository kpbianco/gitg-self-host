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
implementation. M1A locks its known input/output behavior with a golden test.
Integration may wrap or mount it, but may not rewrite its mathematics or
enable its dormant evidence-update functions.

## Decision 011 — M1A before guided workflow
**Status:** Accepted

M1A establishes deployment, authentication, schema, canonical import, and the
Pilot 002 profile. Assessment-taking/import and the practice workflow are M1B
and begin only after M1A review.
