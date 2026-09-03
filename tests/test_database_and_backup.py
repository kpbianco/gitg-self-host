import json
import sqlite3
import stat
from io import StringIO

import pytest
from django.core.management import CommandError, call_command
from django.db import connection

from growth.services.database_backup import manifest_path_for


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
    assert stat.S_IMODE(output.stat().st_mode) == 0o600

    backup = sqlite3.connect(output)
    try:
        user_count = backup.execute("SELECT COUNT(*) FROM auth_user").fetchone()[0]
        integrity = backup.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        backup.close()
    assert user_count == 1
    assert integrity == "ok"
    manifest_path = manifest_path_for(output)
    manifest = json.loads(manifest_path.read_text())
    assert stat.S_IMODE(manifest_path.stat().st_mode) == 0o600
    assert manifest["privacy"] == {
        "contains_database_identifiers": False,
        "contains_only_counts_and_hashes": True,
        "contains_row_values": False,
    }
    assert set(manifest["inspection"]["critical_tables"]["auth_user"]) == {"rows", "sha256"}
    assert {
        "growth_assessmentrun",
        "growth_assessmentcalibrationconsent",
        "growth_orientationresult",
        "growth_archetyperesult",
        "growth_leverbaseline",
        "growth_leverstate",
    } <= set(manifest["inspection"]["critical_tables"])
    stdout = StringIO()
    call_command("verify_database_backup", output, "--compare-live", stdout=stdout)
    assert "backup_verified=true" in stdout.getvalue()
    assert "kian" not in manifest_path.read_text()


@pytest.mark.django_db
def test_backup_refuses_to_replace_live_database():
    with pytest.raises(CommandError, match="must not replace"):
        call_command("backup_database", output=connection.settings_dict["NAME"])


@pytest.mark.django_db(transaction=True)
def test_backup_refuses_to_overwrite_an_existing_snapshot(tmp_path, user):
    output = tmp_path / "snapshot.sqlite3"
    call_command("backup_database", output=output)
    original = output.read_bytes()
    with pytest.raises(CommandError, match="already exists"):
        call_command("backup_database", output=output)
    assert output.read_bytes() == original


@pytest.mark.django_db(transaction=True)
def test_backup_verifier_rejects_file_tampering(tmp_path, user):
    output = tmp_path / "snapshot.sqlite3"
    call_command("backup_database", output=output)
    with output.open("ab") as target:
        target.write(b"tampered")
    with pytest.raises(CommandError, match="byte length"):
        call_command("verify_database_backup", output)


@pytest.mark.django_db(transaction=True)
def test_backup_live_comparison_rejects_critical_state_drift(tmp_path, user):
    output = tmp_path / "snapshot.sqlite3"
    call_command("backup_database", output=output)
    user.email = "changed-after-backup@example.test"
    user.save(update_fields=["email"])
    with pytest.raises(CommandError, match="critical state"):
        call_command("verify_database_backup", output, "--compare-live")
