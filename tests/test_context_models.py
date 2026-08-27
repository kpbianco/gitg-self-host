from __future__ import annotations

import hashlib
import json

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor

from growth.domain.context import ContextFactorValue, ContextValueState
from growth.models import AssessmentContext, AssessmentRun, PracticeContext, PracticeProtocol
from growth.services.canonical_import import seed_canonical_data
from growth.services.context import PracticeContextInput, record_context_bundle
from growth.services.score_state import synchronize_all_score_states
from tests.test_context_services import assessment_factors, practice_factors


def _clone_assessment(run, *, user, stable_id):
    return AssessmentRun.objects.create(
        stable_id=stable_id,
        user=user,
        curriculum_version=run.curriculum_version,
        assessment_version=run.assessment_version,
        source=AssessmentRun.Source.APPLICATION,
        answers={},
        clarifier_answers={},
        timing_data={},
        response_quality_result={},
        orientation_outputs={},
        archetype_outputs=[],
        raw_lever_scores={},
        calibrated_lever_estimates={},
        lever_confidence={},
    )


@pytest.mark.django_db
def test_context_models_are_immutable_and_validate_cross_user_ownership(user, seeded):
    run = AssessmentRun.objects.get(user=user)
    result = record_context_bundle(
        user=user,
        assessment_run=run,
        assessment_factors=assessment_factors(),
    )
    result.assessment_context.capacity_value = 4
    with pytest.raises(ValidationError, match="immutable"):
        result.assessment_context.save()
    with pytest.raises(ValidationError, match="immutable"):
        AssessmentContext.objects.filter(pk=result.assessment_context.pk).update(revision=9)

    other = get_user_model().objects.create_user(username="context-owner-mismatch")
    snapshot = result.assessment_context.canonical_snapshot
    mismatched = AssessmentContext(
        user=other,
        assessment_run=run,
        revision=2,
        season_state="provided",
        season_value="maintenance",
        capacity_state="provided",
        capacity_value=2,
        canonical_snapshot=snapshot,
        content_hash=result.assessment_context.content_hash,
    )
    with pytest.raises(ValidationError, match="must own"):
        mismatched.full_clean()


@pytest.mark.django_db
def test_context_revisions_cannot_be_deleted(user, seeded):
    run = AssessmentRun.objects.get(user=user)
    protocol = PracticeProtocol.objects.get(stable_id="PRACTICE-FRIENDSHIP-01")
    result = record_context_bundle(
        user=user,
        assessment_run=run,
        assessment_factors=assessment_factors(),
        practice_inputs=(PracticeContextInput(protocol=protocol, factors=practice_factors()),),
    )

    with pytest.raises(ValidationError, match="immutable"):
        result.assessment_context.delete()
    with pytest.raises(ValidationError, match="immutable"):
        PracticeContext.objects.filter(pk=result.practice_contexts[0].pk).delete()

    assert AssessmentContext.objects.filter(pk=result.assessment_context.pk).exists()
    assert PracticeContext.objects.filter(pk=result.practice_contexts[0].pk).exists()


@pytest.mark.django_db
def test_database_constraints_reject_invalid_states_values_and_defer_metadata(user, seeded):
    run = AssessmentRun.objects.get(user=user)
    protocol = PracticeProtocol.objects.get(stable_id="PRACTICE-FRIENDSHIP-01")
    result = record_context_bundle(
        user=user,
        assessment_run=run,
        assessment_factors=assessment_factors(),
        practice_inputs=(PracticeContextInput(protocol=protocol, factors=practice_factors()),),
    )
    assessment = result.assessment_context
    with pytest.raises(IntegrityError), transaction.atomic():
        AssessmentContext.objects.create(
            user=user,
            assessment_run=run,
            revision=2,
            season_state="invented",
            season_value="",
            capacity_state="provided",
            capacity_value=2,
            canonical_snapshot=assessment.canonical_snapshot,
            content_hash=assessment.content_hash,
        )
    with pytest.raises(IntegrityError), transaction.atomic():
        AssessmentContext.objects.create(
            user=user,
            assessment_run=run,
            revision=2,
            season_state="unknown",
            season_value="",
            capacity_state="provided",
            capacity_value=5,
            canonical_snapshot=assessment.canonical_snapshot,
            content_hash=assessment.content_hash,
        )

    practice = result.practice_contexts[0]
    values = {
        field: getattr(practice, field)
        for factor in (
            "applicability",
            "importance",
            "readiness",
            "urgency",
            "opportunity_resources",
            "burden",
        )
        for field in (f"{factor}_state", f"{factor}_value")
    }
    with pytest.raises(IntegrityError), transaction.atomic():
        PracticeContext.objects.create(
            user=user,
            assessment_run=run,
            protocol=protocol,
            revision=2,
            disposition="deferred",
            defer_reason="",
            canonical_snapshot=practice.canonical_snapshot,
            content_hash=practice.content_hash,
            **values,
        )


@pytest.mark.django_db
def test_all_four_states_are_persisted_without_hidden_values(user, seeded):
    run = AssessmentRun.objects.get(user=user)
    for revision, state in enumerate(ContextValueState, start=1):
        factors = assessment_factors()
        factors["capacity"] = ContextFactorValue(
            state,
            0 if state is ContextValueState.PROVIDED else None,
        )
        result = record_context_bundle(
            user=user,
            assessment_run=run,
            assessment_factors=factors,
        )
        assert result.assessment_context.revision == revision
        assert result.assessment_context.capacity_state == state.value
        assert result.assessment_context.capacity_value == (
            0 if state is ContextValueState.PROVIDED else None
        )


def _growth_row_digest(excluded_tables=(), excluded_columns=()):
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
            retained_indexes = sorted(
                (
                    index
                    for index, column in enumerate(columns)
                    if (table, column) not in excluded_columns
                ),
                key=columns.__getitem__,
            )
            retained_columns = [columns[index] for index in retained_indexes]
            rows = sorted(
                repr(tuple(row[index] for index in retained_indexes)) for row in cursor.fetchall()
            )
            payload.append((table, retained_columns, rows))
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


@pytest.mark.django_db(transaction=True)
def test_migration_round_trip_preserves_all_preexisting_growth_rows():
    seed_canonical_data()
    synchronize_all_score_states()
    executor = MigrationExecutor(connection)
    original_leaves = executor.loader.graph.leaf_nodes()
    excluded = {"growth_assessmentcontext", "growth_practicecontext"}
    added_columns = {("growth_practicecheckin", "typed_observations")}
    before = _growth_row_digest(excluded, added_columns)
    try:
        executor.migrate([("growth", "0007_pilotfeedback")])
        assert _growth_row_digest(excluded, added_columns) == before
        executor = MigrationExecutor(connection)
        executor.migrate([("growth", "0008_assessmentcontext_practicecontext")])
        assert _growth_row_digest(excluded, added_columns) == before
        executor = MigrationExecutor(connection)
        executor.migrate([("growth", "0007_pilotfeedback")])
        assert _growth_row_digest(excluded, added_columns) == before
    finally:
        MigrationExecutor(connection).migrate(original_leaves)
