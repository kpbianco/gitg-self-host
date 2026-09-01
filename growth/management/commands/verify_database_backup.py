from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from growth.services.database_backup import (
    DatabaseBackupError,
    inspect_sqlite_database,
    verify_backup_manifest,
)


class Command(BaseCommand):
    help = "Verify a SQLite backup manifest, integrity, and critical logical state."

    def add_arguments(self, parser):
        parser.add_argument("backup", type=Path)
        parser.add_argument(
            "--compare-live",
            action="store_true",
            help="Require the backup's critical state and migrations to match the live database.",
        )

    def handle(self, *args, **options):
        if connection.vendor != "sqlite":
            raise CommandError("verify_database_backup currently supports SQLite only.")
        backup_path = options["backup"].expanduser().resolve()
        try:
            backup = verify_backup_manifest(backup_path)
            if options["compare_live"]:
                live_path = Path(connection.settings_dict["NAME"]).expanduser().resolve()
                live = inspect_sqlite_database(live_path)
                if backup.migration_sha256 != live.migration_sha256:
                    raise DatabaseBackupError(
                        "Backup migrations do not match the live database migrations."
                    )
                if backup.critical_state_sha256 != live.critical_state_sha256:
                    raise DatabaseBackupError(
                        "Backup critical state does not match the live database."
                    )
        except (OSError, DatabaseBackupError) as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            self.style.SUCCESS(
                "backup_verified=true "
                f"migrations={backup.applied_migrations} "
                f"critical_state_sha256={backup.critical_state_sha256}"
            )
        )
