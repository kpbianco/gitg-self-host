# AGENTS.md — Grounded Growth

## Mission
Build a self-hosted, evidence-oriented guided-development application. The product converts an assessment-derived developmental need into a bounded, concrete real-world practice without exposing internal curriculum databases to the user.

## Product boundary
- Notion is an internal curriculum/content studio, not the consumer runtime.
- The application recommends executable **Practice Protocols**, not abstract competencies.
- Completion is never equivalent to mastery.
- Human dignity is never scored.
- Personality/orientation changes framing and tie-breaking only; it does not determine worth or obligation.
- Do not activate dynamic score updates until the guided workflow and evidence capture pass acceptance tests.

## Canonical source hierarchy
Use these files in priority order:
1. `docs/PROJECT_HANDOFF.md`
2. `docs/PRODUCT_DECISIONS.md`
3. `data/curriculum/ideal_person_curriculum_v2_pluralist_full_scope.yaml`
4. `data/model/grounded_growth_model_v1.json`
5. `data/model/competency_lever_mapping_v1.csv`
6. `data/assessment/v1.1_bundle/`
7. `docs/pilot/PILOT_002_FINDINGS.md`
8. `legacy/` only for provenance and design research; do not treat it as canonical implementation data.

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
- Never infer missing task-to-lever links from display strings at runtime.
- Validate all imported weight sums and IDs.
- Do not silently normalize malformed data; fail with actionable diagnostics.
- Add tests before enabling any score mutation.
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
2. Run the app through Docker Compose.
3. Audit changed files against this document and `docs/PROJECT_HANDOFF.md`.
4. Report failed or unverified acceptance criteria plainly.
5. Do not claim dynamic scoring works until score mutation is deliberately enabled and tested.

## Current implementation boundary
M1A established the runtime, persistent schema, authentication, canonical
importer, golden assessment boundary, and Pilot 002 profile. M1B integrates the
canonical assessment and completes the friendship recommendation, setup,
sprint, draft/submitted check-in, pause/resume/stop, completion, and review
experience.

M1 is a static-score product boundary. Do not implement M2 evidence weights,
M3 posterior updates, hidden score mutation, or dynamic recommendation changes
without a separately reviewed milestone. Practice completion remains separate
from competency mastery.
