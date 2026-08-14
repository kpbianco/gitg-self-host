from __future__ import annotations

import hashlib
import importlib
import json

import pytest
from django.core.exceptions import ValidationError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.operations.models import CreateModel

from growth.models import AssessmentRun, PersonalOSRevision
from growth.services.personal_os import record_personal_os_revision
from tests.test_personal_os_services import audit_values, identity_values


def test_migration_0009_is_one_schema_only_create_model_operation():
    module = importlib.import_module("growth.migrations.0009_personalosrevision")
    assert module.Migration.dependencies[0] == (
        "growth",
        "0008_assessmentcontext_practicecontext",
    )
    assert len(module.Migration.operations) == 1
    assert isinstance(module.Migration.operations[0], CreateModel)


@pytest.mark.django_db
def test_direct_mutation_bulk_paths_and_deletion_are_blocked(user, seeded):
    run = AssessmentRun.objects.get(user=user)
    record = record_personal_os_revision(
        user=user,
        assessment_run=run,
        identity_sections=identity_values(),
        audit_responses=audit_values(),
    ).revision
    record.mission_value = "Synthetic rewrite"
    with pytest.raises(ValidationError, match="immutable"):
        record.save()
    with pytest.raises(ValidationError, match="immutable"):
        PersonalOSRevision.objects.filter(pk=record.pk).update(revision=2)
    with pytest.raises(ValidationError, match="immutable"):
        PersonalOSRevision.objects.bulk_update([record], ["revision"])
    with pytest.raises(ValidationError, match="validated individual"):
        PersonalOSRevision.objects.bulk_create([])
    with pytest.raises(ValidationError, match="immutable"):
        record.delete()
    with pytest.raises(ValidationError, match="immutable"):
        PersonalOSRevision.objects.filter(pk=record.pk).delete()
    with pytest.raises(ValidationError, match="immutable"):
        PersonalOSRevision._base_manager.filter(pk=record.pk).update(revision=2)
    assert PersonalOSRevision.objects.filter(pk=record.pk).exists()


@pytest.mark.django_db
def test_direct_create_runs_full_contract_validation(user, seeded):
    run = AssessmentRun.objects.get(user=user)
    valid = record_personal_os_revision(
        user=user,
        assessment_run=run,
        identity_sections=identity_values(),
        audit_responses=audit_values(),
    ).revision
    invalid = PersonalOSRevision(
        user=user,
        assessment_run=run,
        revision=2,
        canonical_snapshot=valid.canonical_snapshot,
        content_hash=valid.content_hash,
        **{
            field.name: getattr(valid, field.name)
            for field in PersonalOSRevision._meta.fields
            if field.name.endswith("_state") or field.name.endswith("_value")
        },
    )
    invalid.mission_value = ""
    with pytest.raises(ValidationError):
        invalid.save(force_insert=True)
    invalid.mission_value = valid.mission_value
    invalid.revision = 7
    with pytest.raises(ValidationError, match="next contiguous value"):
        invalid.save(force_insert=True)
    assert PersonalOSRevision.objects.count() == 1


def _growth_row_digest(excluded_tables=()):
    with connection.cursor() as cursor:
        tables = sorted(
            table
            for table in connection.introspection.table_names(cursor)
            if table.startswith("growth_") and table not in excluded_tables
        )
        payload = []
        for table in tables:
            cursor.execute(f'SELECT * FROM "{table}"')
            columns = [item[0] for item in cursor.description]
            rows = sorted(repr(tuple(row)) for row in cursor.fetchall())
            payload.append((table, columns, rows))
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


@pytest.mark.django_db(transaction=True)
def test_migration_0008_to_0009_to_0008_preserves_historical_preexisting_rows():
    executor = MigrationExecutor(connection)
    original_leaves = executor.loader.graph.leaf_nodes()
    excluded = {"personal_os_revision"}
    try:
        executor.migrate([("growth", "0008_assessmentcontext_practicecontext")])
        historical_apps = executor.loader.project_state(
            [("growth", "0008_assessmentcontext_practicecontext")]
        ).apps
        historical_apps.get_model("growth", "CurriculumVersion").objects.create(
            stable_id="M6C02-HISTORICAL-ROW",
            curriculum_version="synthetic",
            model_version="synthetic",
            assessment_version="synthetic",
            source_hash="0" * 64,
        )
        before = _growth_row_digest(excluded)

        executor = MigrationExecutor(connection)
        executor.migrate([("growth", "0009_personalosrevision")])
        assert _growth_row_digest(excluded) == before
        assert "personal_os_revision" in connection.introspection.table_names()
        with connection.cursor() as cursor:
            cursor.execute('SELECT COUNT(*) FROM "personal_os_revision"')
            assert cursor.fetchone()[0] == 0

        executor = MigrationExecutor(connection)
        executor.migrate([("growth", "0008_assessmentcontext_practicecontext")])
        assert _growth_row_digest(excluded) == before
        assert "personal_os_revision" not in connection.introspection.table_names()

        executor = MigrationExecutor(connection)
        executor.migrate([("growth", "0009_personalosrevision")])
        assert _growth_row_digest(excluded) == before
    finally:
        MigrationExecutor(connection).migrate(original_leaves)
