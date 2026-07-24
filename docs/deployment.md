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
5. `manage.py collectstatic --noinput`
6. `gunicorn grounded_growth.wsgi:application`

Migrations, seeding, and evidence backfill are idempotent. Bootstrap creation
occurs only when the auth user table is empty. An existing user prevents
password creation or reset, even if bootstrap environment values change.

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
check-ins, immutable evidence events, and final reviews all live in the same
SQLite database and survive container replacement with the named volume.

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
5. `/health/` returns `{"status":"ok"}`.

## HTTPS or remote access later

M1 intentionally has no reverse proxy. For remote access, first establish an
appropriate threat model, place Caddy or another maintained proxy in front of
the app, use HTTPS, restrict network exposure, and set:

```text
APP_SECURE_COOKIES=true
```

Do not expose the direct HTTP port to the public internet.
