import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection


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
        output = output.expanduser().resolve()
        database_path = Path(connection.settings_dict["NAME"]).resolve()
        if output == database_path:
            raise CommandError("Backup output must not replace the live database.")
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(output.suffix + ".tmp")
        if temporary.exists():
            temporary.unlink()

        connection.ensure_connection()
        source = connection.connection
        destination = sqlite3.connect(temporary)
        try:
            source.backup(destination)
        finally:
            destination.close()
        os.replace(temporary, output)
        self.stdout.write(self.style.SUCCESS(str(output)))
