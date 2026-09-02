from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BACKUP_MANIFEST_SCHEMA_VERSION = "grounded-growth-sqlite-backup-v1"
CRITICAL_STATE_TABLES = (
    "auth_user",
    "growth_assessmentrun",
    "growth_assessmentcalibrationconsent",
    "growth_orientationresult",
    "growth_archetyperesult",
    "growth_leverbaseline",
    "growth_leverstate",
    "growth_practicesprint",
    "growth_practicecheckin",
    "growth_evidenceevent",
    "growth_scoresnapshot",
    "growth_practicereview",
    "growth_pilotfeedback",
    "growth_assessmentcontext",
    "growth_practicecontext",
    "personal_os_revision",
    "growth_weeklyexecutionplan",
    "growth_weeklyexecutionreview",
)


class DatabaseBackupError(ValueError):
    pass


@dataclass(frozen=True)
class TableFingerprint:
    rows: int
    sha256: str


@dataclass(frozen=True)
class DatabaseInspection:
    integrity: str
    applied_migrations: int
    migration_sha256: str
    critical_tables: dict[str, TableFingerprint]
    critical_state_sha256: str

    def as_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["critical_tables"] = {
            name: value["critical_tables"][name] for name in sorted(value["critical_tables"])
        }
        return value


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def manifest_path_for(database_path: Path) -> Path:
    return database_path.with_suffix(database_path.suffix + ".manifest.json")


def _quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _normalized_sqlite_value(value: Any) -> Any:
    if isinstance(value, bytes):
        return {"bytes_sha256": hashlib.sha256(value).hexdigest(), "length": len(value)}
    return value


def _table_fingerprint(database: sqlite3.Connection, table: str) -> TableFingerprint:
    columns = [
        row[1]
        for row in database.execute(f"PRAGMA table_info({_quote_identifier(table)})").fetchall()
    ]
    if not columns:
        raise DatabaseBackupError(f"Required backup table is missing: {table}.")
    select = ", ".join(_quote_identifier(column) for column in columns)
    rows = [
        [_normalized_sqlite_value(value) for value in row]
        for row in database.execute(f"SELECT {select} FROM {_quote_identifier(table)}").fetchall()
    ]
    canonical_rows = sorted(_canonical_json(row) for row in rows)
    return TableFingerprint(
        rows=len(rows),
        sha256=_sha256({"columns": columns, "rows": canonical_rows}),
    )


def inspect_sqlite_database(path: Path) -> DatabaseInspection:
    path = path.expanduser().resolve()
    if not path.is_file():
        raise DatabaseBackupError(f"Database file does not exist: {path}.")
    database = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        integrity_rows = database.execute("PRAGMA integrity_check").fetchall()
        integrity = "\n".join(str(row[0]) for row in integrity_rows)
        if integrity != "ok":
            raise DatabaseBackupError(f"SQLite integrity check failed: {integrity}.")
        migrations = [
            [row[0], row[1]]
            for row in database.execute(
                "SELECT app, name FROM django_migrations ORDER BY app, name"
            ).fetchall()
        ]
        tables = {table: _table_fingerprint(database, table) for table in CRITICAL_STATE_TABLES}
    except sqlite3.DatabaseError as exc:
        raise DatabaseBackupError(f"SQLite backup inspection failed: {exc}.") from exc
    finally:
        database.close()
    state = {
        "migrations": migrations,
        "critical_tables": {name: asdict(tables[name]) for name in sorted(tables)},
    }
    return DatabaseInspection(
        integrity=integrity,
        applied_migrations=len(migrations),
        migration_sha256=_sha256(migrations),
        critical_tables=tables,
        critical_state_sha256=_sha256(state),
    )


def build_backup_manifest(database_path: Path) -> dict[str, Any]:
    database_path = database_path.expanduser().resolve()
    inspection = inspect_sqlite_database(database_path)
    return {
        "schema_version": BACKUP_MANIFEST_SCHEMA_VERSION,
        "created_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "database": {"bytes": database_path.stat().st_size, "sha256": sha256_file(database_path)},
        "inspection": inspection.as_dict(),
        "privacy": {
            "contains_row_values": False,
            "contains_database_identifiers": False,
            "contains_only_counts_and_hashes": True,
        },
    }


def write_backup_manifest(database_path: Path) -> Path:
    database_path = database_path.expanduser().resolve()
    manifest_path = manifest_path_for(database_path)
    temporary = manifest_path.with_suffix(manifest_path.suffix + ".tmp")
    payload = (_canonical_json(build_backup_manifest(database_path)) + "\n").encode("utf-8")
    try:
        temporary.write_bytes(payload)
        os.chmod(temporary, 0o600)
        os.replace(temporary, manifest_path)
    finally:
        temporary.unlink(missing_ok=True)
    return manifest_path


def verify_backup_manifest(database_path: Path) -> DatabaseInspection:
    database_path = database_path.expanduser().resolve()
    manifest_path = manifest_path_for(database_path)
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DatabaseBackupError(
            f"Backup manifest is missing or invalid: {manifest_path}."
        ) from exc
    if manifest.get("schema_version") != BACKUP_MANIFEST_SCHEMA_VERSION:
        raise DatabaseBackupError("Backup manifest schema version is not supported.")
    expected = manifest.get("database")
    if not isinstance(expected, dict):
        raise DatabaseBackupError("Backup manifest database metadata is invalid.")
    if expected.get("bytes") != database_path.stat().st_size:
        raise DatabaseBackupError("Backup byte length does not match its manifest.")
    if expected.get("sha256") != sha256_file(database_path):
        raise DatabaseBackupError("Backup file hash does not match its manifest.")
    inspection = inspect_sqlite_database(database_path)
    if manifest.get("inspection") != inspection.as_dict():
        raise DatabaseBackupError("Backup logical state does not match its manifest.")
    if manifest.get("privacy") != {
        "contains_database_identifiers": False,
        "contains_only_counts_and_hashes": True,
        "contains_row_values": False,
    }:
        raise DatabaseBackupError("Backup manifest privacy declaration is invalid.")
    return inspection
