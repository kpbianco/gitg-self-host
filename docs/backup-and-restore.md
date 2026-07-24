# Backup and restore

## Consistent database backup

Grounded Growth uses SQLite's online backup API rather than copying a live WAL
database file directly.

```bash
make backup
```

Equivalent command:

```bash
docker compose exec app python manage.py backup_database
```

The command writes a timestamped snapshot under:

```text
/data/backups/grounded_growth-YYYYMMDDTHHMMSSZ.sqlite3
```

Choose an explicit destination inside the volume when needed:

```bash
docker compose exec app python manage.py backup_database \
  --output /data/backups/before-update.sqlite3
```

Keep independent copies of important backups outside the Docker host. The
database backup does not include future files under `/data/uploads`; copy that
directory separately when uploads are introduced.

The SQLite snapshot includes users, assessment answers/results/share codes,
practice state, drafts, submitted check-ins, and reviews. Treat it as sensitive
personal data and protect both the file and any off-host copies accordingly.

## Verify a backup

```bash
docker compose exec app python -c \
  'import sqlite3; db=sqlite3.connect("/data/backups/before-update.sqlite3"); print(db.execute("PRAGMA integrity_check").fetchone()[0])'
```

Expected output is `ok`.

## Restore

1. Stop every application container that can access the volume:

   ```bash
   docker compose down
   ```

2. Preserve the current database as an additional recovery point:

   ```bash
   docker compose run --rm --no-deps --entrypoint sh app -c \
     'cp /data/grounded_growth.sqlite3 /data/backups/pre-restore.sqlite3'
   ```

3. Replace it with the selected verified snapshot:

   ```bash
   docker compose run --rm --no-deps --entrypoint sh app -c \
     'cp /data/backups/before-update.sqlite3 /data/grounded_growth.sqlite3'
   ```

4. Start and verify:

   ```bash
   docker compose up -d
   docker compose ps
   curl --fail http://127.0.0.1:${APP_PORT:-3000}/health/
   ```

Startup applies any migrations required by the currently checked-out
application version.

## Volume deletion warning

`docker compose down` preserves data. `docker compose down --volumes` deletes
the named volume and should be treated as permanent data destruction unless a
tested external backup exists.
