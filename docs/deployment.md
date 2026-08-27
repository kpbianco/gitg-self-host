# Deployment

## Supported single-instance topology

M1 runs one `app` service. Gunicorn listens on `0.0.0.0:8000` in the
container, and Docker Compose maps the configured host port. SQLite and future
uploaded application data live under `/data` in a named volume.

There is no reverse proxy, database service, cache, queue, or Node.js runtime.

## First installation

```bash
cp .env.example .env
```

Edit `.env` before starting:

| Variable | Required behavior |
|---|---|
| `APP_PORT` | Host port; defaults to `3000`. |
| `DJANGO_SECRET_KEY` | Long random value unique to this instance. |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated hostnames/LAN IPs used to open the app. |
| `APP_BOOTSTRAP_USERNAME` | First username, used only if no user exists. |
| `APP_BOOTSTRAP_PASSWORD` | First password, used only if no user exists. |
| `APP_TIME_ZONE` | IANA zone such as `America/Los_Angeles`; defaults to `UTC`. |
| `APP_DEBUG` | Keep `false` in deployment. |
| `APP_SECURE_COOKIES` | Keep `false` for direct HTTP; set `true` behind HTTPS. |

Generate a secret key:

```bash
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

Start:

```bash
docker compose up -d --build
docker compose ps
```

Open:

```text
http://<server-local-ip>:<APP_PORT>
```

For example, with server IP `192.168.1.20` and the default port:
`http://192.168.1.20:3000`. Ensure `192.168.1.20` appears in
`DJANGO_ALLOWED_HOSTS`.

## Startup contract

The non-root container user runs these steps on every start:

1. `manage.py migrate --noinput`
2. `manage.py bootstrap_user`
3. `manage.py seed_canonical`
4. `manage.py backfill_evidence_events`
5. `manage.py rebuild_score_state`
6. `manage.py collectstatic --noinput`
7. `gunicorn grounded_growth.wsgi:application`

Migrations, seeding, evidence backfill, and score-state reconciliation are
idempotent. Score-state startup initializes missing current rows, processes
pending versioned events once, verifies replay, and appends a rebuild snapshot
only if current state actually drifted. Bootstrap creation occurs only when
the auth user table is empty. An existing user prevents password creation or
reset, even if bootstrap environment values change.

## Authentication hardening

After confirming the first login:

1. Open **Account** and change the password, or run:

   ```bash
   docker compose exec app python manage.py changepassword <username>
   ```

2. Remove `APP_BOOTSTRAP_PASSWORD` from `.env`.
3. Restart:

   ```bash
   docker compose up -d
   ```

Django stores only its salted password hash in SQLite. Sessions use HttpOnly,
SameSite=Lax cookies. CSRF middleware protects state-changing requests.

## Health, logs, and shutdown

The unauthenticated health endpoint is:

```bash
curl --fail http://127.0.0.1:${APP_PORT:-3000}/health/
```

Expected response:

```json
{"status": "ok"}
```

Inspect stdout/stderr logs:

```bash
docker compose logs -f app
```

Gunicorn receives the container stop signal because the entrypoint uses
`exec`. Compose allows a 30-second graceful-stop window.

```bash
docker compose down
```

`down` removes the container and network but preserves the named volume. Do
not add `--volumes` unless permanent data deletion is intended.

## Persistence

Compose mounts:

```text
grounded_growth_data:/data
```

The database is:

```text
/data/grounded_growth.sqlite3
```

Future uploads use `/data/uploads`; backups use `/data/backups`.

Assessment runs, share codes, practice setup records, draft/submitted
check-ins, immutable evidence events, exact assessment baseline mass, and final
reviews all live in the same SQLite database and survive container replacement
with the named volume. M3B current lever state and immutable hashed score
snapshots live in that same database; assessment baselines remain separate.
Optional M5A pilot-feedback records also persist in SQLite, but remain in a
separate table and never enter assessment, evidence, score, recommendation, or
completion services. Optional M6C assessment/practice context and Personal OS
revisions are append-only, assessment-epoch-scoped private local data in the
same database and backups. Context priority results are reproducible and are
not stored. Authored Personal OS text is not a ranking, evidence, score,
activation, telemetry, or existing-export input.
M6H weekly plans and proof reviews also persist in SQLite and backups. They
contain stable linkage, schedule, categorical review state, and replayable
proof references, but no Personal OS prose. They do not create evidence or
score state.

## Updating

Back up first, then rebuild:

```bash
make backup
git pull --ff-only
docker compose up -d --build
docker compose ps
```

Startup applies new migrations and reconciles canonical seed data by stable
ID. Review `docs/data-import.md` before changing canonical files.

After an update, sign in and verify:

1. `/assessment/` loads the locally served scorer;
2. `/practices/` shows the friendship protocol;
3. any current practice and draft check-ins remain present;
4. a submitted check-in opens its evidence-reading page;
5. `/evidence/` shows only the signed-in user's submitted events;
6. `make evidence-verify` reports complete replay coverage;
7. `make score-verify` reports deterministic score-state coverage;
8. `/profile/` distinguishes the assessment baseline from current
   evidence-updated estimates;
9. `/health/` returns `{"status":"ok"}`.
10. `docker compose exec app python manage.py verify_pilot_readiness` reports
    the exact 383-protocol runtime boundary and replay state.
11. **Account → Open feedback form** explains that pilot feedback is optional,
    local, and separate from developmental state.
12. `/personal-os/` and
    `/personal-os/practices/<slug>/context/` require authentication, use the
    signed-in user's latest assessment, show no carried-forward values after
    reassessment, and state the local-backup and
    no-dedicated-export/purge/retention boundaries before collection.
13. `docker compose exec app python manage.py
    verify_m6c_pilot_readiness` reports all six prerequisite readiness
    contracts, the exact 383-protocol projection, registered authenticated
    browser routes, and all-catalog activation without writing data.
14. `/weekly/` shows one current-practice action and an explicit proof state;
    `docker compose exec app python manage.py
    verify_weekly_execution_readiness` replays plans and reviews without
    writing data or printing private values.

The evidence verifier is intentionally not an automatic repair step. Startup
backfill reconciles missing legacy events and verifies existing ones;
`evidence-verify` is the strict read-only operational audit. See
`docs/evidence-audit.md`.

Score-state operations are:

```bash
docker compose exec app python manage.py rebuild_score_state --verify-only
docker compose exec app python manage.py rebuild_score_state
```

The first command is read-only. The second initializes pending state and
repairs drift from immutable baselines/events with an audit snapshot. To
permanently exclude one processed event from current state without deleting
it from the evidence ledger:

```bash
docker compose exec app python manage.py rebuild_score_state \
  --reverse-event <event-uuid> \
  --reason "Documented correction reason"
```

Reversal is idempotent and has no M3B undo command. Back up first and use it
only for a documented correction. See `docs/scoring-state.md`.

Optional pilot feedback has a separate participant-data lifecycle. Preview
the exact user-scoped deletion first:

```bash
docker compose exec app python manage.py purge_pilot_feedback \
  --username <username>
```

After confirming the count and the participant agreement:

```bash
docker compose exec app python manage.py purge_pilot_feedback \
  --username <username> \
  --confirm
```

This command does not touch developmental state. It also does not remove rows
from existing backups; apply the same retention decision to backup copies.

## HTTPS or remote access later

M1 intentionally has no reverse proxy. For remote access, first establish an
appropriate threat model, place Caddy or another maintained proxy in front of
the app, use HTTPS, restrict network exposure, and set:

```text
APP_SECURE_COOKIES=true
```

Do not expose the direct HTTP port to the public internet.

## Repeatable deployment verification

Run the complete deployment drill from a Docker-capable host:

```bash
make compose-smoke
```

The drill builds the production image and uses an isolated Compose project,
temporary environment files, a free host port, and a throwaway named volume.
It verifies:

- the Compose health check and public `/health/` response;
- anonymous redirect plus a real CSRF-protected login over the mapped port;
- the non-root runtime, applied migrations, exact canonical counts, repeated
  seed idempotency, evidence replay, score-state replay, and the read-only
  `GG-PILOT-READINESS-1.0` and additive
  `GG-M6C-PILOT-READINESS-1.0` contracts;
- conspicuously synthetic Personal OS and context revisions created through
  public services, a deterministic context-priority result, and authenticated
  HTTP access to the Personal OS surface;
- database and bootstrap-password persistence after forced container
  recreation, including synthetic revision/result hashes and unchanged
  friendship-only activation;
- an online SQLite backup, `PRAGMA integrity_check`, and restore that preserve
  those synthetic hashes and the activation boundary;
- clean Gunicorn shutdown.

The script removes its isolated containers and volume on exit. It does not
read or modify the deployment `.env` or `grounded_growth_data` volume.
`APP_ENV_FILE` is an internal Compose override used by this drill; normal
deployment continues to default to `.env`.

GitHub Actions runs the same command in
`.github/workflows/verification.yml`, alongside Ruff, Django, pytest,
the isolated `make pilot-check`, and Playwright. The aggregate **Pilot
readiness gate** succeeds only when quality, browser, and Compose all pass.

The drill is isolated deployment-drill evidence. It does not release or deploy
the application, approve a participant pilot, or establish recommendation
usefulness, specialist review, accessibility-population, cultural-safety,
clinical, psychometric, longitudinal, or production validity.

## Private-pilot feedback data

M5A adds no analytics host or outbound feedback integration. Participant
feedback stays in `/data/grounded_growth.sqlite3` and is covered by the normal
backup/restore procedure. The authenticated minimized download is available at
`/account/pilot-feedback/export.json`.

The download excludes free text and direct identifiers, but remains sensitive
pilot data. Review it before sharing, avoid participant names in filenames,
and retain it only where access is appropriate. Local free-text comments stay
inside the database and backup; they are never included in the minimized
export.
