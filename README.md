# Grounded Growth

## Install

```bash
cp .env.example .env
# Edit .env: set DJANGO_SECRET_KEY, DJANGO_ALLOWED_HOSTS,
# APP_BOOTSTRAP_USERNAME, and APP_BOOTSTRAP_PASSWORD.
docker compose up -d --build
```

Open `http://<server-local-ip>:<APP_PORT>`; the default port is
`3000`. Sign in with the bootstrap credentials from `.env`.

Grounded Growth is a self-hosted, evidence-oriented guided-development
application. M1 provides a secure Django runtime, the canonical v1.1
assessment, an immediately usable Pilot 002 demonstration profile, and one
complete guided practice workflow. Scores remain static.
M2A adds immutable, versioned evidence readings for submitted check-ins while
leaving every developmental profile value unchanged.
M2B adds a private evidence ledger, deterministic minimized export, strict
replay verification, and calibration fixtures around those same static events.

## Deployment essentials

- Add the server's LAN IP to `DJANGO_ALLOWED_HOSTS`.
- Application data persists in the `grounded_growth_data` named volume.
- The SQLite database is `/data/grounded_growth.sqlite3` inside the container.
- Startup applies migrations, creates the bootstrap user only when no user
  exists, idempotently seeds canonical data, and backfills missing evidence
  events.
- Health is available without authentication at `/health/`.
- Every other application page requires login; static assets are bundled
  locally.
- Gunicorn listens on `0.0.0.0:8000` inside the container. Compose maps
  `${APP_PORT:-3000}` on the host.

After the first successful login, change the password under **Account** or run:

```bash
docker compose exec app python manage.py changepassword <username>
```

Then remove `APP_BOOTSTRAP_PASSWORD` from `.env`. Restarts never reset an
existing password.

See [deployment](docs/deployment.md) for environment options, updates,
local-network access, shutdown behavior, and the future HTTPS boundary.

## What M1 contains

- Django 6.0 monolith with server-rendered responsive pages.
- Built-in Django authentication, sessions, CSRF protection, and HttpOnly
  session cookies.
- In-application assessment with 50 required questions, optional targeted
  clarifiers, full-question timing, canonical browser scoring, and GGA11 share
  codes.
- GGA11 profile import with supported GGA1 backward decoding.
- Complete M1 schema for assessments, baselines, curriculum links, protocols,
  sprints, actions, check-ins, and reviews.
- Validated import of 27 domains, 383 competencies, 37 levers, and 1,403
  structured competency-to-lever links.
- Idempotent Pilot 002 seed: 37 baselines, six orientations, and the three
  archetypes published in the canonical profile.
- The complete `Deepen One Existing Friendship` protocol data plus four
  inactive structured placeholders.
- The complete 14-day **Deepen One Existing Friendship** experience: reason,
  applicability, context, boundaries, start date, defined actions, activation,
  compact draft/submitted check-ins, pause/resume/stop, completion, and review.
- Assessment v1.1 golden and browser coverage for all scoring outputs, GGA11
  generation/import, and supported GGA1 decoding.
- SQLite WAL/busy-timeout configuration and consistent online backup command.
- Ruff, pytest, and Playwright coverage.

## What M2A adds

- Three compact submission choices for support used, context variation, and
  evidence direction.
- Stable action-specific observation rules.
- Pure `GG-EVIDENCE-1.0` classification of protocol performance, structured
  quality, independence, bounded context breadth, repetition, contradiction,
  and base event mass.
- One immutable evidence event per submitted check-in, with exact replay from
  a privacy-minimized input snapshot.
- Conservative, idempotent backfill of existing M1 submissions.
- Plain-language evidence detail with optional collapsed technical audit
  values.
- No lever allocation, baseline mutation, or dynamic recommendation.

## What M2B adds

- One authenticated evidence ledger across practices, newest first and
  filterable by evidence direction.
- A deterministic `grounded-growth-evidence-export-v1` download that excludes
  identity, database IDs, timestamps, private labels, free text, assessment
  answers, and share codes.
- A strict read-only verifier for event coverage, order, stable IDs, and exact
  replay.
- Synthetic golden cases for supportive, inconclusive, mixed,
  contradictory, and legacy-unknown evidence.
- No new evidence algorithm, lever allocation, baseline mutation, or dynamic
  recommendation.

## Product flow

1. Sign in with the bootstrap account.
2. Use the Pilot 002 profile immediately, take assessment v1.1, or import an
   existing GGA11/GGA1 share code.
3. Review the provisional profile and why a practice was selected.
4. Complete the seven-step guided setup; the three actions are already defined.
5. Save check-ins as drafts or submit them with a versioned evidence reading.
6. Review submitted observations in the evidence ledger or download the
   minimized calibration export.
7. Pause/resume when needed, or stop the practice.
8. Submit a final review after the bounded completion criteria are met.

Draft check-ins never appear as submitted evidence. Completing a practice does
not establish mastery. Event-level evidence mass does not change any profile
score.

## Common commands

Create a local development environment:

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
```

Then use:

```bash
make format
make lint
make test
make e2e
make migrate
make seed
make evidence-backfill
make evidence-verify
make run
make compose-up
make compose-down
make backup
```

The local `migrate`, `seed`, and `run` targets use `./var`; the deployed
container always uses `/data`.

## Canonical data

- `data/curriculum/` — 27 domains and 383 competencies.
- `data/model/` — 37 levers, six orientations, 15 archetypes, and weighted
  mappings.
- `data/assessment/` — canonical assessment v1.1 spec, browser engine,
  standalone UI, compatibility code, and fixtures.
- `data/notion/initial_mvp/` — Pilot 002 baselines, static task ranking, and
  starting profile.

The importer uses stable IDs and the structured mapping CSV. It never parses
human-readable `Lever Mapping` text. See
[data import](docs/data-import.md).

`legacy/` is provenance and design archaeology only. Canonical structured data
wins when they disagree.

## Backup, restore, and updates

Create an online database snapshot:

```bash
make backup
```

Backups are stored under `/data/backups` in the persistent volume. Follow the
[backup and restore procedure](docs/backup-and-restore.md) before replacing a
database.

For updates:

```bash
make backup
git pull --ff-only
docker compose up -d --build
```

Migrations and canonical seeding run safely on startup.

## Current limitations

- Pilot 002 source files publish only the top three archetypes and do not
  include original answers or a share code; the seed does not invent them.
- Profile scores are deliberately static. A submitted check-in creates base
  event evidence mass, but no practice action, check-in, completion, or review
  changes lever mastery, lever confidence, need, task priority, archetype,
  orientation, or recommendation values.
- The minimized JSON export omits direct identity and free text, but its
  structured behavioral values can still be sensitive and should be reviewed
  before sharing.
- Only **Deepen One Existing Friendship** is active. Four additional protocols
  are structured inactive placeholders, not generic generated exercises.
- The canonical JavaScript scorer remains the browser reference. Node.js is
  used by a development golden test only; no Node.js server exists at runtime.
- Direct local-network HTTP is supported. Add Caddy or another proxy later for
  HTTPS or remote access; no proxy is included in M1.
- The product and assessment are not psychometrically validated and do not
  score dignity, virtue, perfection, or human worth.

## Documentation

- [Architecture decisions](docs/architecture/README.md)
- [Deployment](docs/deployment.md)
- [Canonical data import](docs/data-import.md)
- [Assessment integration](docs/assessment-integration.md)
- [Practice workflow](docs/practice-workflow.md)
- [M2 evidence contract](docs/evidence-contract.md)
- [M2B evidence audit and calibration](docs/evidence-audit.md)
- [Backup and restore](docs/backup-and-restore.md)
- [Testing](docs/testing.md)
- [Project handoff](docs/PROJECT_HANDOFF.md)
- [Product decisions](docs/PRODUCT_DECISIONS.md)
