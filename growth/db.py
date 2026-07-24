import logging

from django.db.backends.signals import connection_created
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(connection_created)
def configure_sqlite(sender, connection, **kwargs) -> None:
    if connection.vendor != "sqlite":
        return

    with connection.cursor() as cursor:
        cursor.execute("PRAGMA busy_timeout = 20000")
        if connection.settings_dict["NAME"] != ":memory:":
            mode = cursor.execute("PRAGMA journal_mode = WAL").fetchone()[0]
            if str(mode).lower() != "wal":
                logger.warning("SQLite journal mode is %s instead of WAL.", mode)
        cursor.execute("PRAGMA foreign_keys = ON")
