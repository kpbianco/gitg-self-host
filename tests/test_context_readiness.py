from __future__ import annotations

import json

import pytest
from django.core.management import call_command
from django.db import connection

from growth.models import (
    ArchetypeResult,
    AssessmentRun,
    EvidenceEvent,
    LeverBaseline,
    LeverState,
    OrientationResult,
    PilotFeedback,
    PracticeAction,
    PracticeCheckIn,
    PracticeProtocol,
    PracticeReview,
    PracticeSprint,
    ScoreSnapshot,
)
from growth.services.context import (
    ContextReadinessError,
    PracticeContextInput,
    record_context_bundle,
    verify_context_readiness,
)
from growth.services.profile import build_profile_summary
from tests.test_context_services import assessment_factors, practice_factors


def _stored_state():
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


@pytest.mark.django_db
def test_context_capture_and_readiness_do_not_mutate_existing_domains(user, seeded):
    run = AssessmentRun.objects.get(user=user)
    protocol = PracticeProtocol.objects.get(stable_id="PRACTICE-FRIENDSHIP-01")
    before_state = _stored_state()
    before_recommendations = _recommendations(user)

    record_context_bundle(
        user=user,
        assessment_run=run,
        assessment_factors=assessment_factors(),
        practice_inputs=(PracticeContextInput(protocol=protocol, factors=practice_factors()),),
    )
    summary = verify_context_readiness()

    assert _stored_state() == before_state
    assert _recommendations(user) == before_recommendations
    assert summary.contract_version == "GG-CONTEXT-READINESS-1.0"
    assert summary.context_contract_version == "GG-CONTEXT-1.0"
    assert summary.assessment_records == 1
    assert summary.practice_records == 1
    assert summary.changes_recommendations is False
    assert summary.changes_score_state is False
    assert summary.ordinary_ui_changes is False
    assert list(
        PracticeProtocol.objects.filter(score_active=True).values_list("stable_id", flat=True)
    ) == ["PRACTICE-FRIENDSHIP-01"]


@pytest.mark.django_db
def test_readiness_command_is_deterministic_and_empty_optional_context_passes(seeded, capsys):
    call_command("verify_context_readiness", "--json")
    first = capsys.readouterr().out
    call_command("verify_context_readiness", "--json")
    second = capsys.readouterr().out
    assert first == second
    payload = json.loads(first)
    assert payload["assessment_records"] == 0
    assert payload["practice_records"] == 0
    assert payload["software_ready"] is True


@pytest.mark.django_db
def test_readiness_fails_closed_on_hash_tampering(user, seeded):
    run = AssessmentRun.objects.get(user=user)
    record = record_context_bundle(
        user=user,
        assessment_run=run,
        assessment_factors=assessment_factors(),
    ).assessment_context
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE growth_assessmentcontext SET content_hash = %s WHERE stable_id = %s",
            ["0" * 64, record.pk.hex],
        )
    with pytest.raises(ContextReadinessError, match="content hash"):
        verify_context_readiness()
