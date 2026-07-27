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
- exact canonical alpha/beta baseline-mass persistence and drift rejection;
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
- direction-complete synthetic calibration fixtures and exact golden outputs;
- authenticated, filtered, per-user evidence-ledger isolation;
- deterministic allowlisted export with identity, IDs, timestamps, free text,
  and assessment data excluded;
- strict whole-database replay verification and nonzero failure on gaps/drift;
- unchanged lever baselines after ledger, export, and verification operations;
- stable `17.03` practice mapping and four task weights summing to 1.0;
- exact `GG-SCORING-SHADOW-1.0` coefficients, direction routing,
  success/failure mass, posterior, and confidence against a synthetic fixture;
- monotonic confidence for included evidence and unchanged confidence for
  withheld evidence;
- malformed task weights, duplicate events, and ambiguous baseline mass
  failing closed;
- draft exclusion and unchanged stored profile state after shadow projection;
- exact assessment v1.1 provisional-need reproduction across all 37 baseline
  rows;
- separate 37-row current-state initialization and four conservative Pilot
  baseline-only rows;
- atomic and idempotent submitted-event application with unchanged assessment
  baselines;
- withheld inconclusive state, immutable contribution snapshots, and
  protected scored events;
- full score-history hash/replay verification, audited event reversal, and
  deterministic drift repair;
- missing required baseline mass rolling back check-in, event, state, and
  snapshot together;
- dynamic active-protocol ordering from current need and canonical weights;
- score-state management-command verify and repair behavior;
- pause/resume/stop transitions and completion criteria;
- unchanged assessment baselines and no review-only current-state transition;
- SQLite foreign keys, busy timeout, and WAL;
- consistent backup and SQLite integrity;
- assessment v1.1 complete golden output, GGA11, and GGA1.

`make e2e` uses Playwright Chromium for four browser journeys:

1. login, Pilot 002 home, and developmental profile;
2. all 50 required assessment questions, result save, and 6/15/37 persistence;
3. GGA11 import and supported GGA1 import;
4. recommendation explanation, seven-step setup, start, pause/resume, draft,
   M2 evidence submission/detail, ledger, minimized JSON download, all three
   actions, M3B evidence-updated profile state, final review, completion, and
   mastery disclaimer.

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
twice and confirm counts do not change. Run `make evidence-verify` and
`make score-verify`. Inspect logs for migration, seed, score-state, permission,
or shutdown errors.

## Current scoring boundary

M1 proves guided UX and static assessment persistence. M2A tests event-level
evidence classification and base mass. M2B tests read-only audit, export,
replay, and calibration behavior. M3A tests task-to-lever allocation and the
accepted posterior contract. M3B tests its bounded activation for the
friendship protocol.

Current state, need rank, and active-practice order may now change after
eligible submitted evidence. Tests prove that assessment baselines, raw
self-report, orientations, archetypes, completion, and final review remain
separate. Dynamic context priority and additional score-activated protocols
remain outside M3B.
