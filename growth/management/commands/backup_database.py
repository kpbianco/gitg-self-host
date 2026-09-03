import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from growth.services.database_backup import (
    DatabaseBackupError,
    manifest_path_for,
    write_backup_manifest,
)


class Command(BaseCommand):
    help = "Create a consistent SQLite backup using SQLite's online backup API."

    def add_arguments(self, parser):
        parser.add_argument("--output", type=Path)

    def handle(self, *args, **options):
        if connection.vendor != "sqlite":
            raise CommandError("backup_database currently supports SQLite only.")

        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        output = options["output"] or settings.DATA_DIR / "backups" / (
            f"grounded_growth-{timestamp}.sqlite3"
        )
        output = Path(output).expanduser().resolve()
        database_path = Path(connection.settings_dict["NAME"]).resolve()
        if output == database_path:
            raise CommandError("Backup output must not replace the live database.")
        if output.exists() or manifest_path_for(output).exists():
            raise CommandError(
                "Backup output or its manifest already exists; choose a new explicit path."
            )
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(output.suffix + ".tmp")
        if temporary.exists():
            temporary.unlink()

        connection.ensure_connection()
        source = connection.connection
        try:
            destination = sqlite3.connect(temporary)
            try:
                source.backup(destination)
            finally:
                destination.close()
            os.chmod(temporary, 0o600)
            os.replace(temporary, output)
            manifest = write_backup_manifest(output)
        except (OSError, sqlite3.DatabaseError, DatabaseBackupError) as exc:
            raise CommandError(str(exc)) from exc
        finally:
            temporary.unlink(missing_ok=True)
        self.stdout.write(self.style.SUCCESS(f"backup={output}"))
        self.stdout.write(self.style.SUCCESS(f"manifest={manifest}"))
