# Backup, upgrade, restore, and rollback

## What the backup contains

Grounded Growth uses SQLite's online backup API instead of copying a live WAL
database file. A database snapshot includes account, assessment, profile,
context, Personal OS, practice, draft/submitted check-in, evidence, score,
review, weekly-execution, assessment-calibration consent, and optional
pilot-feedback data. Treat the database and every copy as sensitive private
data.

The downloadable owner archive is not a restorable database backup. The
minimized evidence, pilot-feedback, and consent-filtered assessment calibration
JSON files are analysis exports and also cannot restore the application. The
calibration file contains linkable item responses and timing and remains
sensitive even without account identity.

## Create and verify a pre-upgrade backup

Choose a stable path so the restore command cannot select the wrong file:

```bash
docker compose exec app python manage.py backup_database \
  --output /data/backups/pre-upgrade.sqlite3
docker compose exec app python manage.py verify_database_backup \
  /data/backups/pre-upgrade.sqlite3 --compare-live
```

The command writes both files atomically with mode `0600`:

```text
/data/backups/pre-upgrade.sqlite3
/data/backups/pre-upgrade.sqlite3.manifest.json
```

It refuses to overwrite either an existing snapshot or sidecar. Move the
previous pair to its dated archive location or choose a new explicit filename.

The sidecar manifest contains no row values or database identifiers. It records
only the backup byte length and hash, SQLite integrity result, applied-migration
count/hash, and counts/hashes for critical owner state. `--compare-live`
requires the snapshot migrations and critical-state fingerprint to match the
live database exactly.

For a timestamped snapshot under `/data/backups`, use `make backup`. Keep an
independent encrypted copy outside the Docker host. Future files under
`/data/uploads` are not part of the SQLite snapshot.

## Upgrade and verify

Do not continue if backup verification fails.

```bash
git rev-parse HEAD
docker compose exec app python manage.py verify_m6h_operations_readiness
docker compose exec app python manage.py verify_assessment_calibration_collection
git pull --ff-only
docker compose up -d --build --wait
docker compose exec app python manage.py migrate --check
docker compose exec app python manage.py verify_evidence_events
docker compose exec app python manage.py rebuild_score_state --verify-only
docker compose exec app python manage.py verify_weekly_execution_readiness
docker compose exec app python manage.py verify_m6h_operations_readiness
docker compose exec app python manage.py verify_assessment_calibration_collection
curl --fail http://127.0.0.1:${APP_PORT:-3000}/health/
```

Also sign in and verify the profile, a current practice, evidence history,
Personal OS, weekly execution, and **Account** data management.

## Roll back a failed upgrade

Use the exact pre-upgrade source revision printed before the upgrade. Stop all
containers before replacing SQLite, and never copy over a running WAL database.

```bash
docker compose down
git switch --detach <pre-upgrade-commit>
docker compose build app
docker compose run --rm --no-deps --entrypoint python app -c \
  'from pathlib import Path; import shutil; source=Path("/data/backups/pre-upgrade.sqlite3"); target=Path("/data/grounded_growth.sqlite3"); shutil.copy2(source, target); target.chmod(0o600); target.with_name(target.name + "-wal").unlink(missing_ok=True); target.with_name(target.name + "-shm").unlink(missing_ok=True)'
docker compose up -d --wait
docker compose exec app python manage.py verify_database_backup \
  /data/backups/pre-upgrade.sqlite3 --compare-live
docker compose exec app python manage.py migrate --check
docker compose exec app python manage.py verify_evidence_events
docker compose exec app python manage.py rebuild_score_state --verify-only
docker compose exec app python manage.py verify_weekly_execution_readiness
docker compose exec app python manage.py verify_m6h_operations_readiness
docker compose exec app python manage.py verify_assessment_calibration_collection
curl --fail http://127.0.0.1:${APP_PORT:-3000}/health/
```

If `--compare-live` fails after restoration, keep the application stopped and
do not waive the mismatch. Preserve both files and investigate which source,
volume, or backup path was selected.

## Isolated restore drill

`make compose-smoke` uses a throwaway Compose project and named volume. It
creates synthetic owner state, verifies a pre-upgrade backup, changes account
state across recreation, restores while stopped, and proves exact critical-
state replay plus every established readiness contract.

## Deletion and retention copies

Live account deletion and retention do not edit existing backups. A backup may
still contain a deleted account, drafts, feedback, and private narrative. Apply
the operator's agreed lifecycle separately to backup and encrypted off-host
copies; never claim erasure until that lifecycle is completed and documented.

`APP_OWNER_RETENTION_ENABLED=false` is the default. Enabling it creates no
timer, startup mutation, or background task. The authenticated owner must still
preview and confirm each application. Only old draft check-ins and optional
pilot feedback are eligible; immutable developmental history is never targeted.

## Volume deletion warning

`docker compose down` preserves data. `docker compose down --volumes` deletes
the named volume and should be treated as permanent destruction unless an
independent, verified backup exists.
