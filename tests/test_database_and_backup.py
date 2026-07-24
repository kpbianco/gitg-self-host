import sqlite3

import pytest
from django.core.management import CommandError, call_command
from django.db import connection


@pytest.mark.django_db
def test_sqlite_safety_pragmas_are_enabled():
    with connection.cursor() as cursor:
        timeout = cursor.execute("PRAGMA busy_timeout").fetchone()[0]
        foreign_keys = cursor.execute("PRAGMA foreign_keys").fetchone()[0]
        journal_mode = cursor.execute("PRAGMA journal_mode").fetchone()[0]
    assert timeout == 20000
    assert foreign_keys == 1
    assert journal_mode.lower() == "wal"


@pytest.mark.django_db(transaction=True)
def test_backup_command_creates_consistent_database(tmp_path, user):
    output = tmp_path / "snapshot.sqlite3"
    call_command("backup_database", output=output)
    assert output.exists()

    backup = sqlite3.connect(output)
    try:
        user_count = backup.execute("SELECT COUNT(*) FROM auth_user").fetchone()[0]
        integrity = backup.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        backup.close()
    assert user_count == 1
    assert integrity == "ok"


@pytest.mark.django_db
def test_backup_refuses_to_replace_live_database():
    with pytest.raises(CommandError, match="must not replace"):
        call_command("backup_database", output=connection.settings_dict["NAME"])
