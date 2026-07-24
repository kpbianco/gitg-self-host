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
application. M1A provides the secure Django foundation, canonical curriculum
import, Pilot 002 profile, and static-score boundary. The guided assessment and
practice workflow follows in M1B after review.

## Deployment essentials

- Add the server's LAN IP to `DJANGO_ALLOWED_HOSTS`.
- Application data persists in the `grounded_growth_data` named volume.
- The SQLite database is `/data/grounded_growth.sqlite3` inside the container.
- Startup applies migrations, creates the bootstrap user only when no user
  exists, and idempotently seeds canonical data.
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

## What M1A contains

- Django 6.0 monolith with server-rendered responsive pages.
- Built-in Django authentication, sessions, CSRF protection, and HttpOnly
  session cookies.
- Complete M1 schema for assessments, baselines, curriculum links, protocols,
  sprints, actions, check-ins, and reviews.
- Validated import of 27 domains, 383 competencies, 37 levers, and 1,403
  structured competency-to-lever links.
- Idempotent Pilot 002 seed: 37 baselines, six orientations, and the three
  archetypes published in the canonical profile.
- The complete `Deepen One Existing Friendship` protocol data plus four
  inactive structured placeholders.
- Assessment v1.1 golden coverage for all scoring outputs, GGA11 generation,
  and supported GGA1 decoding.
- SQLite WAL/busy-timeout configuration and consistent online backup command.
- Ruff, pytest, and Playwright coverage.

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

## M1 limitations

- Assessment taking and GGA11 import are planned for M1B; M1A only establishes
  their immutable storage model and golden integration boundary.
- Practice setup, check-ins, pause/resume, completion, and review UI are M1B.
- Pilot 002 source files publish only the top three archetypes and do not
  include original answers or a share code; the seed does not invent them.
- Scores are static. No practice action, check-in, completion, or review
  changes lever mastery, confidence, need, archetype, or orientation values.
- Direct local-network HTTP is supported. Add Caddy or another proxy later for
  HTTPS or remote access; no proxy is included in M1.
- The product and assessment are not psychometrically validated and do not
  score dignity, virtue, perfection, or human worth.

## Documentation

- [Architecture decisions](docs/architecture/README.md)
- [Deployment](docs/deployment.md)
- [Canonical data import](docs/data-import.md)
- [Assessment integration](docs/assessment-integration.md)
- [Backup and restore](docs/backup-and-restore.md)
- [Testing](docs/testing.md)
- [Project handoff](docs/PROJECT_HANDOFF.md)
- [Product decisions](docs/PRODUCT_DECISIONS.md)
