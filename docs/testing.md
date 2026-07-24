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
- authenticated home/profile rendering;
- immutable assessment runs;
- static mastery/confidence after a completed practice review;
- SQLite foreign keys, busy timeout, and WAL;
- consistent backup and SQLite integrity;
- assessment v1.1 complete golden output, GGA11, and GGA1.

`make e2e` uses Playwright Chromium for:

1. unauthenticated redirect;
2. login;
3. Pilot 002 home;
4. first recommendation visibility;
5. developmental profile and mastery boundary.

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

Both checks must retain the user count and report 383 competencies. Run
`seed_canonical` twice and confirm counts do not change. Inspect logs for
migration, seed, permission, or shutdown errors.

## Current M1A test boundary

M1A does not claim browser coverage for assessment completion/import or the
practice workflow. Those become applicable in M1B. Dynamic scoring tests are
deliberately absent because dynamic scoring is disabled.
