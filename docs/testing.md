# Testing

## Development setup

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
PLAYWRIGHT_BROWSERS_PATH="$PWD/.playwright-browsers" \
  .venv/bin/python -m playwright install chromium
```

Node.js is used only to execute the canonical assessment JavaScript in golden
tests. It is not a deployed server or runtime dependency.

Each pytest invocation uses a unique SQLite database under the system
temporary directory. This prevents a completed WAL-enabled process from
leaving sidecars that can collide with a subsequent unit or browser run.

## Commands

```bash
make format
make lint
make test
make e2e
```

`make lint` runs Ruff format/lint checks and Django's system check.

`make test` covers:

- canonical counts, IDs, mapping coverage, and weights;
- malformed mapping rejection;
- idempotent curriculum, protocol, and Pilot 002 seeding;
- one-time bootstrap user behavior and password-hash preservation;
- login enforcement, CSRF-bearing login, and public health;
- authenticated home/profile/assessment/practice rendering;
- immutable and idempotent assessment-run persistence;
- exact 6-orientation, 15-archetype, and 37-lever golden-result persistence;
- GGA11 answer/code agreement and malformed assessment rejection;
- the seven-step practice setup and not-applicable exit;
- one-current-practice and per-user authorization boundaries;
- draft/submitted check-in separation and submitted immutability;
- required M2 evidence metadata on submission;
- deterministic `GG-EVIDENCE-1.0` output and exact replay;
- action-specific repetition and bounded context semantics;
- structured and legacy contradiction handling;
- atomic event creation, event immutability, and privacy-minimized snapshots;
- conservative, idempotent M1 evidence backfill;
- pause/resume/stop transitions and completion criteria;
- static raw/calibrated/confidence/need values after final review;
- SQLite foreign keys, busy timeout, and WAL;
- consistent backup and SQLite integrity;
- assessment v1.1 complete golden output, GGA11, and GGA1.

`make e2e` uses Playwright Chromium for four browser journeys:

1. login, Pilot 002 home, and developmental profile;
2. all 50 required assessment questions, result save, and 6/15/37 persistence;
3. GGA11 import and supported GGA1 import;
4. recommendation explanation, seven-step setup, start, pause/resume, draft,
   M2 evidence submission/detail, all three actions, final review, completion,
   and mastery disclaimer.

The server-side golden test and browser flow complement each other: the first
deep-compares every canonical output, while the second proves that the mounted
UI reaches and persists that engine.

## Docker acceptance

Before release:

```bash
cp .env.example .env
# Set real test values in .env.
docker compose build
docker compose up -d
docker compose ps
curl --fail http://127.0.0.1:${APP_PORT:-3000}/health/
```

Verify login from the mapped host port. Then record database identity, recreate
the application container, and compare:

```bash
docker compose exec app python manage.py shell -c \
  'from django.contrib.auth import get_user_model; from growth.models import Competency; print(get_user_model().objects.count(), Competency.objects.count())'
docker compose up -d --force-recreate
docker compose exec app python manage.py shell -c \
  'from django.contrib.auth import get_user_model; from growth.models import Competency; print(get_user_model().objects.count(), Competency.objects.count())'
```

Both checks must retain the user count and report 383 competencies. Also
confirm assessment/practice rows survive when present. Run `seed_canonical`
twice and confirm counts do not change. Inspect logs for migration, seed,
permission, or shutdown errors.

## Current scoring boundary

M1 proves guided UX and static persistence. M2A tests event-level evidence
classification and base mass. It deliberately has no task-to-lever
allocation, success/failure contribution, score snapshot, posterior update, or
dynamic recommendation test because those paths do not exist.
