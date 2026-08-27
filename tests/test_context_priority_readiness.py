from __future__ import annotations

import json
import traceback
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import connection, transaction

from growth.domain.context import ContextFactorValue
from growth.domain.context_priority import AlternativeRequest
from growth.models import (
    ArchetypeResult,
    AssessmentContext,
    AssessmentRun,
    EvidenceEvent,
    LeverBaseline,
    LeverState,
    OrientationResult,
    PersonalOSRevision,
    PilotFeedback,
    PracticeAction,
    PracticeCheckIn,
    PracticeContext,
    PracticeProtocol,
    PracticeReview,
    PracticeSprint,
    ScoreSnapshot,
)
from growth.services.context import PracticeContextInput, record_context_bundle
from growth.services.context_priority import (
    ContextPriorityReadinessError,
    ContextPriorityServiceError,
    build_context_priority_for_epoch,
    verify_context_priority_readiness,
)
from growth.services.evidence import build_privacy_safe_evidence_export
from growth.services.personal_os import record_personal_os_revision
from growth.services.pilot_feedback import build_privacy_safe_pilot_export
from growth.services.profile import build_profile_summary
from tests.test_context_services import assessment_factors, practice_factors
from tests.test_personal_os_services import audit_values, identity_values

PRIVATE_SENTINEL = "PRIVATE-M6C03-SENTINEL-DO-NOT-PRINT"


def _protected_state():
    models = (
        AssessmentRun,
        LeverBaseline,
        LeverState,
        OrientationResult,
        ArchetypeResult,
        EvidenceEvent,
        ScoreSnapshot,
        PracticeProtocol,
        PracticeAction,
        PracticeSprint,
        PracticeCheckIn,
        PracticeReview,
        PilotFeedback,
        AssessmentContext,
        PracticeContext,
        PersonalOSRevision,
    )
    return {
        model._meta.label: list(model.objects.order_by(model._meta.pk.name).values())
        for model in models
    }


def _active_protocols():
    return tuple(
        PracticeProtocol.objects.filter(availability=PracticeProtocol.Availability.ACTIVE).order_by(
            "stable_id"
        )
    )


def _record_complete_context(user, run, *, capacity=2, overrides=None):
    overrides = overrides or {}
    inputs = []
    for protocol in _active_protocols():
        factors = practice_factors()
        disposition = "considering"
        defer_reason = None
        if protocol.stable_id in overrides:
            factors, disposition, defer_reason = overrides[protocol.stable_id]
        inputs.append(
            PracticeContextInput(
                protocol=protocol,
                factors=factors,
                disposition=disposition,
                defer_reason=defer_reason,
            )
        )
    return record_context_bundle(
        user=user,
        assessment_run=run,
        assessment_factors=assessment_factors(capacity=capacity),
        practice_inputs=tuple(inputs),
    )


def _profile_priorities(user):
    summary = build_profile_summary(user)
    return {
        protocol_id: str(priority)
        for protocol_id, priority in summary.recommendation_priorities.items()
    }


@pytest.mark.django_db
def test_service_uses_exact_legacy_base_priorities_and_does_not_mutate_or_replace_profile_path(
    user, seeded
):
    run = AssessmentRun.objects.get(user=user)
    _record_complete_context(user, run)
    protocol_ids = tuple(protocol.stable_id for protocol in reversed(_active_protocols()))
    before_state = _protected_state()
    before_profile = _profile_priorities(user)
    before_activation = tuple(
        PracticeProtocol.objects.filter(score_active=True)
        .order_by("stable_id")
        .values_list("stable_id", flat=True)
    )
    before_evidence_export = json.dumps(
        build_privacy_safe_evidence_export(user), sort_keys=True
    ).encode()
    before_feedback_export = json.dumps(
        build_privacy_safe_pilot_export(user), sort_keys=True
    ).encode()

    result = build_context_priority_for_epoch(
        user=user,
        assessment_run=run,
        protocol_stable_ids=protocol_ids,
    )

    assert _protected_state() == before_state
    assert _profile_priorities(user) == before_profile
    assert {
        item.protocol_stable_id: format(item.base_priority, ".4f") for item in result.candidates
    } == before_profile
    assert json.dumps(build_privacy_safe_evidence_export(user), sort_keys=True).encode() == (
        before_evidence_export
    )
    assert json.dumps(build_privacy_safe_pilot_export(user), sort_keys=True).encode() == (
        before_feedback_export
    )
    assert (
        tuple(
            PracticeProtocol.objects.filter(score_active=True)
            .order_by("stable_id")
            .values_list("stable_id", flat=True)
        )
        == before_activation
    )
    assert "PRACTICE-FRIENDSHIP-01" in before_activation


@pytest.mark.django_db
def test_service_is_database_and_candidate_order_independent(user, seeded):
    run = AssessmentRun.objects.get(user=user)
    _record_complete_context(user, run)
    ids = tuple(protocol.stable_id for protocol in _active_protocols())
    forward = build_context_priority_for_epoch(
        user=user,
        assessment_run=run,
        protocol_stable_ids=ids,
    )
    reverse = build_context_priority_for_epoch(
        user=user,
        assessment_run=run,
        protocol_stable_ids=tuple(reversed(ids)),
    )
    assert forward.canonical_json == reverse.canonical_json
    assert forward.content_hash == reverse.content_hash


@pytest.mark.django_db
def test_service_holds_one_locked_epoch_transaction_for_all_mutable_inputs(user, seeded):
    run = AssessmentRun.objects.get(user=user)
    _record_complete_context(user, run)
    original_select_for_update = AssessmentRun.objects.select_for_update
    from growth.services.context_priority import _needs_for_epoch

    transaction_depth = len(connection.savepoint_ids)
    observed_transaction = []

    def observe_transaction(*args, **kwargs):
        observed_transaction.append(
            (transaction.get_connection().in_atomic_block, len(connection.savepoint_ids))
        )
        return _needs_for_epoch(*args, **kwargs)

    with (
        patch.object(
            AssessmentRun.objects,
            "select_for_update",
            wraps=original_select_for_update,
        ) as select_for_update,
        patch(
            "growth.services.context_priority._needs_for_epoch",
            side_effect=observe_transaction,
        ),
    ):
        result = build_context_priority_for_epoch(
            user=user,
            assessment_run=run,
            protocol_stable_ids=("PRACTICE-FRIENDSHIP-01",),
        )

    select_for_update.assert_called_once_with()
    assert observed_transaction == [(True, transaction_depth + 1)]
    assert result.assessment_epoch_id == run.pk


@pytest.mark.django_db
def test_service_supports_partial_cohort_and_distinct_alternative(user, seeded):
    run = AssessmentRun.objects.get(user=user)
    play_factors = practice_factors()
    play_factors["applicability"] = ContextFactorValue("not_applicable")
    _record_complete_context(
        user,
        run,
        overrides={"PRACTICE-PLAY-01": (play_factors, "considering", None)},
    )
    result = build_context_priority_for_epoch(
        user=user,
        assessment_run=run,
        protocol_stable_ids=("PRACTICE-PLAY-01", "PRACTICE-PRESENCE-01"),
        alternative_request=AlternativeRequest("PRACTICE-PLAY-01", "not_applicable"),
    )
    assert result.alternative.status.value == "selected"
    assert result.alternative.target_protocol_stable_id == "PRACTICE-PRESENCE-01"
    assert set(result.as_dict()["supplied_candidate_ids"]) == {
        "PRACTICE-PLAY-01",
        "PRACTICE-PRESENCE-01",
    }


@pytest.mark.django_db
def test_missing_row_differs_from_verified_nonprovided_capacity(user, seeded):
    run = AssessmentRun.objects.get(user=user)
    protocol = PracticeProtocol.objects.get(stable_id="PRACTICE-FRIENDSHIP-01")
    with pytest.raises(ContextPriorityServiceError, match="persisted assessment-context"):
        build_context_priority_for_epoch(
            user=user,
            assessment_run=run,
            protocol_stable_ids=(protocol.stable_id,),
        )

    record_context_bundle(
        user=user,
        assessment_run=run,
        assessment_factors={
            "season": ContextFactorValue("unknown"),
            "capacity": ContextFactorValue("unknown"),
        },
        practice_inputs=(PracticeContextInput(protocol=protocol, factors=practice_factors()),),
    )
    result = build_context_priority_for_epoch(
        user=user,
        assessment_run=run,
        protocol_stable_ids=(protocol.stable_id,),
    )
    assert result.ranking_disposition.value == "missing_context"
    assert result.primary_protocol_stable_id is None
    assert result.candidates[0].disposition.value == "missing_context"


@pytest.mark.django_db
def test_cross_user_inactive_noncanonical_and_duplicate_candidates_fail_closed(user, seeded):
    run = AssessmentRun.objects.get(user=user)
    _record_complete_context(user, run)
    other = get_user_model().objects.create_user(username="context-priority-other")
    with pytest.raises(ContextPriorityServiceError, match="user-owned"):
        build_context_priority_for_epoch(
            user=other,
            assessment_run=run,
            protocol_stable_ids=("PRACTICE-FRIENDSHIP-01",),
        )
    with pytest.raises(ContextPriorityServiceError, match="unique"):
        build_context_priority_for_epoch(
            user=user,
            assessment_run=run,
            protocol_stable_ids=("PRACTICE-FRIENDSHIP-01", "PRACTICE-FRIENDSHIP-01"),
        )
    with pytest.raises(ContextPriorityServiceError, match="manifest-projected"):
        build_context_priority_for_epoch(
            user=user,
            assessment_run=run,
            protocol_stable_ids=("PRACTICE-NONCANONICAL",),
        )
    PracticeProtocol.objects.filter(stable_id="PRACTICE-FRIENDSHIP-01").update(
        availability=PracticeProtocol.Availability.INACTIVE
    )
    with pytest.raises(ContextPriorityServiceError, match="active in the runtime"):
        build_context_priority_for_epoch(
            user=user,
            assessment_run=run,
            protocol_stable_ids=("PRACTICE-FRIENDSHIP-01",),
        )


def _raw_context_update(table, stable_id, assignment, parameters):
    with connection.cursor() as cursor:
        cursor.execute(
            f'UPDATE "{table}" SET {assignment} WHERE stable_id = %s',
            [*parameters, stable_id.hex],
        )


@pytest.mark.django_db
def test_hash_and_revision_tampering_fail_with_sanitized_error_chains(user, seeded):
    run = AssessmentRun.objects.get(user=user)
    record = _record_complete_context(user, run).practice_contexts[0]
    _raw_context_update(
        "growth_practicecontext",
        record.pk,
        "content_hash = %s",
        ["0" * 64],
    )
    with pytest.raises(ContextPriorityServiceError) as exc_info:
        build_context_priority_for_epoch(
            user=user,
            assessment_run=run,
            protocol_stable_ids=(record.protocol_id,),
        )
    error_chain = "".join(traceback.format_exception(exc_info.value))
    assert str(record.pk) not in error_chain
    assert user.username not in error_chain
    assert PRIVATE_SENTINEL not in error_chain


@pytest.mark.django_db
def test_cross_owned_current_state_fails_closed_instead_of_falling_back_to_baselines(user, seeded):
    run = AssessmentRun.objects.get(user=user)
    _record_complete_context(user, run)
    other = get_user_model().objects.create_user(username="context-priority-state-other")
    with connection.cursor() as cursor:
        cursor.execute(
            'UPDATE "growth_leverstate" SET user_id = %s WHERE assessment_run_id = %s',
            [other.pk, run.pk],
        )

    with pytest.raises(ContextPriorityServiceError, match="user-owned current lever state"):
        build_context_priority_for_epoch(
            user=user,
            assessment_run=run,
            protocol_stable_ids=("PRACTICE-FRIENDSHIP-01",),
        )


@pytest.mark.django_db
def test_noncontiguous_latest_revision_fails_closed(user, seeded):
    run = AssessmentRun.objects.get(user=user)
    _record_complete_context(user, run, capacity=2)
    changed = record_context_bundle(
        user=user,
        assessment_run=run,
        assessment_factors=assessment_factors(capacity=3),
    ).assessment_context
    _raw_context_update(
        "growth_assessmentcontext",
        changed.pk,
        "revision = %s",
        [3],
    )
    with pytest.raises(ContextPriorityServiceError, match="latest and contiguous"):
        build_context_priority_for_epoch(
            user=user,
            assessment_run=run,
            protocol_stable_ids=("PRACTICE-FRIENDSHIP-01",),
        )


@pytest.mark.django_db
def test_personal_os_orientation_and_archetype_values_never_enter_priority_or_hash(user, seeded):
    run = AssessmentRun.objects.get(user=user)
    _record_complete_context(user, run)
    ids = tuple(protocol.stable_id for protocol in _active_protocols())
    before = build_context_priority_for_epoch(
        user=user,
        assessment_run=run,
        protocol_stable_ids=ids,
    )
    record_personal_os_revision(
        user=user,
        assessment_run=run,
        identity_sections=identity_values(mission=PRIVATE_SENTINEL),
        audit_responses=audit_values(text=PRIVATE_SENTINEL),
    )
    OrientationResult.objects.filter(assessment_run=run).update(name=PRIVATE_SENTINEL)
    ArchetypeResult.objects.filter(assessment_run=run).update(name=PRIVATE_SENTINEL)
    after = build_context_priority_for_epoch(
        user=user,
        assessment_run=run,
        protocol_stable_ids=ids,
    )
    assert after.canonical_json == before.canonical_json
    assert after.content_hash == before.content_hash
    assert PRIVATE_SENTINEL not in after.canonical_json


@pytest.mark.django_db
def test_readiness_is_deterministic_empty_state_read_only_and_source_derived(seeded, capsys):
    before = _protected_state()
    first = verify_context_priority_readiness()
    second = verify_context_priority_readiness()
    assert first == second
    assert _protected_state() == before
    assert first.contract_version == "GG-CONTEXT-PRIORITY-READINESS-1.0"
    assert first.algorithm_version == "GG-CONTEXT-PRIORITY-1.0"
    assert first.projected_protocols == 383
    assert first.m6c03_baseline_protocols_present == 5
    assert first.score_active_protocols == 383
    assert first.friendship_score_active is True
    assert first.assessment_context_records == 0
    assert first.practice_context_records == 0
    assert first.changes_recommendations is False
    assert first.changes_score_state is False
    assert first.changes_production_activation is False
    assert first.ordinary_ui_changes is False

    call_command("verify_context_priority_readiness", "--json")
    first_output = capsys.readouterr().out
    call_command("verify_context_priority_readiness", "--json")
    second_output = capsys.readouterr().out
    assert first_output == second_output
    payload = json.loads(first_output)
    assert payload["synthetic_result_hash"] == first.synthetic_result_hash
    for forbidden in ("username", "record_id", "snapshot", PRIVATE_SENTINEL.lower()):
        assert forbidden not in first_output.lower()


@pytest.mark.django_db
def test_readiness_fails_closed_on_persisted_context_drift_without_private_values(user, seeded):
    run = AssessmentRun.objects.get(user=user)
    record = _record_complete_context(user, run).assessment_context
    _raw_context_update(
        "growth_assessmentcontext",
        record.pk,
        "content_hash = %s",
        ["0" * 64],
    )
    with pytest.raises(ContextPriorityReadinessError) as exc_info:
        verify_context_priority_readiness()
    error_chain = "".join(traceback.format_exception(exc_info.value))
    assert str(record.pk) not in error_chain
    assert user.username not in error_chain
    assert PRIVATE_SENTINEL not in error_chain
