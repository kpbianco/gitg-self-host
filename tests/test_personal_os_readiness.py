from __future__ import annotations

import json
import traceback

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection

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
from growth.services.context import verify_context_readiness
from growth.services.evidence import build_privacy_safe_evidence_export
from growth.services.personal_os import (
    PersonalOSReadinessError,
    record_personal_os_revision,
    verify_personal_os_readiness,
)
from growth.services.pilot_feedback import build_privacy_safe_pilot_export
from growth.services.profile import build_profile_summary
from tests.test_personal_os_services import audit_values, identity_values

PRIVATE_SENTINEL = "PRIVATE-M6C02-SENTINEL-DO-NOT-PRINT"


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
    )
    return {
        model._meta.label: list(model.objects.order_by(model._meta.pk.name).values())
        for model in models
    }


def _recommendations(user):
    summary = build_profile_summary(user)
    return [
        (protocol.stable_id, str(summary.recommendation_priorities[protocol.stable_id]))
        for protocol in summary.recommendations
    ]


def _record_with_sentinel(user, run):
    identity = identity_values(mission=PRIVATE_SENTINEL)
    identity["principles"] = {
        "state": "provided",
        "value": [f"{PRIVATE_SENTINEL}-principle"],
    }
    identity["anti_goals"] = {
        "state": "provided",
        "value": [f"{PRIVATE_SENTINEL}-anti-goal"],
    }
    identity["priority_stack"] = {
        "state": "provided",
        "value": [f"{PRIVATE_SENTINEL}-priority"],
    }
    return record_personal_os_revision(
        user=user,
        assessment_run=run,
        identity_sections=identity,
        audit_responses=audit_values(text=PRIVATE_SENTINEL),
    ).revision


@pytest.mark.django_db
def test_empty_optional_readiness_command_is_deterministic_and_private(seeded, capsys):
    call_command("verify_personal_os_readiness", "--json")
    first = capsys.readouterr().out
    call_command("verify_personal_os_readiness", "--json")
    second = capsys.readouterr().out
    assert first == second
    payload = json.loads(first)
    assert payload["contract_version"] == "GG-PERSONAL-OS-READINESS-1.0"
    assert payload["personal_os_contract_version"] == "GG-PERSONAL-OS-1.0"
    assert payload["records"] == 0
    assert payload["assessment_epochs_with_personal_os"] == 0
    assert payload["software_ready"] is True
    for forbidden in (
        "canonical_snapshot",
        "content_hash",
        "authored_value",
        "username",
        "assessment_answers",
    ):
        assert forbidden not in first.lower()


@pytest.mark.django_db
def test_capture_and_readiness_preserve_context_exports_and_every_existing_domain(user, seeded):
    run = AssessmentRun.objects.get(user=user)
    before_state = _protected_state()
    before_recommendations = _recommendations(user)
    before_evidence_export = json.dumps(
        build_privacy_safe_evidence_export(user), sort_keys=True
    ).encode()
    before_feedback_export = json.dumps(
        build_privacy_safe_pilot_export(user), sort_keys=True
    ).encode()
    before_context = verify_context_readiness().as_dict()

    record = _record_with_sentinel(user, run)
    summary = verify_personal_os_readiness()

    after_evidence_export = json.dumps(
        build_privacy_safe_evidence_export(user), sort_keys=True
    ).encode()
    after_feedback_export = json.dumps(
        build_privacy_safe_pilot_export(user), sort_keys=True
    ).encode()
    assert _protected_state() == before_state
    assert _recommendations(user) == before_recommendations
    assert after_evidence_export == before_evidence_export
    assert after_feedback_export == before_feedback_export
    assert verify_context_readiness().as_dict() == before_context
    assert summary.records == 1
    assert summary.assessment_epochs_with_personal_os == 1
    assert summary.changes_recommendations is False
    assert summary.changes_score_state is False
    assert summary.changes_production_activation is False
    assert summary.ordinary_ui_changes is False
    assert PracticeProtocol.objects.filter(score_active=True).count() == 383
    assert not PracticeProtocol.objects.filter(score_active=False).exists()
    exported = after_evidence_export + after_feedback_export
    assert PRIVATE_SENTINEL.encode() not in exported
    assert str(record.pk).encode() not in exported
    assert user.username.encode() not in exported
    assert b"personal_os" not in exported


def _raw_update(record, assignment, parameters):
    with connection.cursor() as cursor:
        cursor.execute(
            f'UPDATE "personal_os_revision" SET {assignment} WHERE stable_id = %s',
            [*parameters, record.pk.hex],
        )


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("corruption", "assignment", "parameters"),
    [
        ("hash", "content_hash = %s", ["0" * 64]),
        (
            "field-bound",
            "mission_value = %s",
            [PRIVATE_SENTINEL + "x" * 600],
        ),
        (
            "resource-bound",
            "canonical_snapshot = %s",
            [json.dumps({"oversized": "x" * 65537})],
        ),
    ],
)
def test_readiness_fails_closed_without_private_diagnostics(
    user, seeded, corruption, assignment, parameters
):
    run = AssessmentRun.objects.get(user=user)
    record = _record_with_sentinel(user, run)
    _raw_update(record, assignment, parameters)
    with pytest.raises(PersonalOSReadinessError) as exc_info:
        verify_personal_os_readiness()
    message = str(exc_info.value)
    assert corruption not in message.lower()
    assert PRIVATE_SENTINEL not in message
    assert str(record.pk) not in message
    assert user.username not in message


@pytest.mark.django_db
def test_readiness_rejects_snapshot_epoch_and_private_payload_tampering(user, seeded):
    run = AssessmentRun.objects.get(user=user)
    record = _record_with_sentinel(user, run)
    corrupted = dict(record.canonical_snapshot)
    corrupted["assessment_epoch_id"] = "ASSESSMENT-WRONG-EPOCH"
    corrupted["unrelated_narrative"] = PRIVATE_SENTINEL
    _raw_update(record, "canonical_snapshot = %s", [json.dumps(corrupted)])
    with pytest.raises(PersonalOSReadinessError) as exc_info:
        verify_personal_os_readiness()
    assert PRIVATE_SENTINEL not in str(exc_info.value)
    with pytest.raises(CommandError) as command_exc:
        call_command("verify_personal_os_readiness")
    assert PRIVATE_SENTINEL not in str(command_exc.value)


@pytest.mark.django_db
def test_readiness_exception_tracebacks_do_not_retain_private_validation_values(user, seeded):
    run = AssessmentRun.objects.get(user=user)
    record = _record_with_sentinel(user, run)
    with connection.cursor() as cursor:
        cursor.execute("PRAGMA ignore_check_constraints = ON")
        try:
            _raw_update(record, "mission_state = %s", [PRIVATE_SENTINEL])
        finally:
            cursor.execute("PRAGMA ignore_check_constraints = OFF")

    with pytest.raises(PersonalOSReadinessError) as service_exc:
        verify_personal_os_readiness()
    service_traceback = "".join(traceback.format_exception(service_exc.value))
    assert PRIVATE_SENTINEL not in service_traceback

    with pytest.raises(CommandError) as command_exc:
        call_command("verify_personal_os_readiness")
    command_traceback = "".join(traceback.format_exception(command_exc.value))
    assert PRIVATE_SENTINEL not in command_traceback


@pytest.mark.django_db
def test_readiness_rejects_ownership_version_and_revision_drift_without_values(user, seeded):
    run = AssessmentRun.objects.get(user=user)
    first = _record_with_sentinel(user, run)
    record_personal_os_revision(
        user=user,
        assessment_run=run,
        identity_sections=identity_values(mission="Synthetic changed"),
        audit_responses=audit_values(),
    )
    other = get_user_model().objects.create_user(username="private-owner-sentinel")

    _raw_update(first, "user_id = %s", [other.pk])
    with pytest.raises(PersonalOSReadinessError) as owner_exc:
        verify_personal_os_readiness()
    assert PRIVATE_SENTINEL not in str(owner_exc.value)
    _raw_update(first, "user_id = %s", [user.pk])

    with connection.cursor() as cursor:
        cursor.execute("PRAGMA ignore_check_constraints = ON")
        try:
            _raw_update(first, "contract_version = %s", ["GG-PERSONAL-OS-UNKNOWN"])
        finally:
            cursor.execute("PRAGMA ignore_check_constraints = OFF")
    with pytest.raises(PersonalOSReadinessError) as version_exc:
        verify_personal_os_readiness()
    assert PRIVATE_SENTINEL not in str(version_exc.value)

    with connection.cursor() as cursor:
        cursor.execute("PRAGMA ignore_check_constraints = ON")
        try:
            _raw_update(first, "contract_version = %s", ["GG-PERSONAL-OS-1.0"])
        finally:
            cursor.execute("PRAGMA ignore_check_constraints = OFF")
    second = PersonalOSRevision.objects.get(assessment_run=run, revision=2)
    _raw_update(second, "revision = %s", [3])
    with pytest.raises(PersonalOSReadinessError, match="not contiguous") as revision_exc:
        verify_personal_os_readiness()
    assert PRIVATE_SENTINEL not in str(revision_exc.value)
