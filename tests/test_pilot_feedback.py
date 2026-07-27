import json
from datetime import date
from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.urls import reverse

from growth.models import (
    ArchetypeResult,
    AssessmentRun,
    EvidenceEvent,
    LeverBaseline,
    LeverState,
    OrientationResult,
    PilotFeedback,
    PracticeCheckIn,
    PracticeReview,
    PracticeSprint,
    ScoreSnapshot,
)
from growth.services.pilot_feedback import (
    PILOT_EXPORT_SCHEMA_VERSION,
    PilotFeedbackError,
    build_privacy_safe_pilot_export,
    submit_pilot_feedback,
)
from growth.services.profile import build_profile_summary


def _feedback_data(protocol, **overrides):
    data = {
        "journey_stage": PilotFeedback.JourneyStage.REVIEW,
        "protocol": protocol,
        "applicability": PilotFeedback.Applicability.PARTLY,
        "time_to_start": PilotFeedback.StartTimeBand.TWO_TO_FIVE,
        "time_to_check_in": PilotFeedback.CheckInTimeBand.ONE_TO_TWO,
        "confusing_step": PilotFeedback.ConfusingStep.SETUP,
        "accessibility_friction": PilotFeedback.Friction.NONE,
        "safety_friction": PilotFeedback.Friction.NONE,
        "comment": "PRIVATE-PILOT-COMMENT-TOKEN",
    }
    data.update(overrides)
    return data


def _developmental_state_snapshot(user):
    summary = build_profile_summary(user)
    return {
        "assessment": list(
            AssessmentRun.objects.filter(user=user)
            .order_by("stable_id")
            .values(
                "stable_id",
                "assessment_version",
                "source",
                "answers",
                "clarifier_answers",
                "timing_data",
                "response_quality_result",
                "orientation_outputs",
                "archetype_outputs",
                "raw_lever_scores",
                "calibrated_lever_estimates",
                "lever_confidence",
                "original_share_code",
                "created_at",
            )
        ),
        "orientations": list(
            OrientationResult.objects.filter(assessment_run__user=user)
            .order_by("assessment_run_id", "stable_id")
            .values()
        ),
        "archetypes": list(
            ArchetypeResult.objects.filter(assessment_run__user=user)
            .order_by("assessment_run_id", "stable_id")
            .values()
        ),
        "baselines": list(
            LeverBaseline.objects.filter(user=user)
            .order_by("assessment_run_id", "lever_id")
            .values()
        ),
        "states": list(
            LeverState.objects.filter(user=user).order_by("assessment_run_id", "lever_id").values()
        ),
        "sprints": list(PracticeSprint.objects.filter(user=user).order_by("stable_id").values()),
        "check_ins": list(
            PracticeCheckIn.objects.filter(sprint__user=user).order_by("stable_id").values()
        ),
        "evidence": list(
            EvidenceEvent.objects.filter(check_in__sprint__user=user).order_by("stable_id").values()
        ),
        "snapshots": list(
            ScoreSnapshot.objects.filter(assessment_run__user=user)
            .order_by("assessment_run_id", "sequence")
            .values()
        ),
        "reviews": list(
            PracticeReview.objects.filter(sprint__user=user).order_by("stable_id").values()
        ),
        "recommendations": [protocol.stable_id for protocol in summary.recommendations],
        "priorities": summary.recommendation_priorities,
    }


@pytest.mark.django_db
def test_pilot_feedback_pages_require_login(client):
    for name in ("growth:pilot-feedback", "growth:pilot-feedback-export"):
        response = client.get(reverse(name))
        assert response.status_code == 302
        assert response.url.startswith("/accounts/login/")


@pytest.mark.django_db
def test_feedback_page_explains_optional_isolated_local_collection(client, user, seeded):
    client.force_login(user)

    response = client.get(reverse("growth:pilot-feedback"))
    content = response.content.decode()
    normalized = " ".join(content.split())

    assert response.status_code == 200
    assert "This is usability feedback, not developmental evidence." in content
    assert "No automatic timing or remote telemetry" in content
    assert "does not time, record, or send your activity anywhere" in normalized
    assert "This form is not monitored for urgent support." in content
    assert "Skipping this form has no effect." in content


@pytest.mark.django_db
def test_feedback_requires_one_optional_signal(client, user, seeded):
    protocol = (
        user.assessment_runs.get()
        .curriculum_version.levers.get(stable_id="L26")
        .practice_protocols.get(stable_id="PRACTICE-FRIENDSHIP-01")
    )
    client.force_login(user)

    response = client.post(
        reverse("growth:pilot-feedback"),
        {
            "journey_stage": PilotFeedback.JourneyStage.SETUP,
            "protocol": protocol.pk,
        },
    )

    assert response.status_code == 200
    assert "Answer at least one optional feedback question" in response.content.decode()
    assert PilotFeedback.objects.count() == 0


@pytest.mark.django_db
def test_feedback_questions_are_scoped_to_the_selected_journey_stage(client, user, seeded):
    protocol = (
        user.assessment_runs.get()
        .curriculum_version.levers.get(stable_id="L26")
        .practice_protocols.get(stable_id="PRACTICE-FRIENDSHIP-01")
    )
    client.force_login(user)

    page = client.get(reverse("growth:pilot-feedback"))
    content = page.content.decode()
    assert "contextual_forms.js" in content
    assert "data-feedback-stage-control" in content
    assert "data-feedback-stages" in content

    invalid = {
        "journey_stage": PilotFeedback.JourneyStage.ASSESSMENT,
        "protocol": protocol.pk,
        "applicability": PilotFeedback.Applicability.YES,
        "time_to_start": PilotFeedback.StartTimeBand.UNDER_TWO,
        "time_to_check_in": PilotFeedback.CheckInTimeBand.UNDER_ONE,
        "confusing_step": PilotFeedback.ConfusingStep.NONE,
        "accessibility_friction": PilotFeedback.Friction.NONE,
        "safety_friction": PilotFeedback.Friction.NONE,
        "comment": "",
    }
    response = client.post(reverse("growth:pilot-feedback"), invalid)

    assert response.status_code == 200
    assert (
        response.content.decode().count(
            "This question does not apply to the selected part of the experience."
        )
        == 4
    )
    assert not PilotFeedback.objects.exists()

    with pytest.raises(PilotFeedbackError, match="does not apply"):
        submit_pilot_feedback(
            user=user,
            cleaned_data={
                **invalid,
                "protocol": protocol,
            },
        )

    valid = {
        "journey_stage": PilotFeedback.JourneyStage.ASSESSMENT,
        "protocol": "",
        "applicability": "",
        "time_to_start": "",
        "time_to_check_in": "",
        "confusing_step": PilotFeedback.ConfusingStep.NONE,
        "accessibility_friction": PilotFeedback.Friction.NONE,
        "safety_friction": PilotFeedback.Friction.NONE,
        "comment": "",
    }
    saved = client.post(reverse("growth:pilot-feedback"), valid)
    assert saved.status_code == 302
    assert PilotFeedback.objects.get().journey_stage == PilotFeedback.JourneyStage.ASSESSMENT


@pytest.mark.django_db
def test_pre_m5b_ambiguous_feedback_remains_unchanged_and_exportable(user, seeded):
    protocol = (
        user.assessment_runs.get()
        .curriculum_version.levers.get(stable_id="L26")
        .practice_protocols.get(stable_id="PRACTICE-FRIENDSHIP-01")
    )
    historical = PilotFeedback.objects.create(
        user=user,
        journey_stage=PilotFeedback.JourneyStage.ASSESSMENT,
        protocol=protocol,
        applicability=PilotFeedback.Applicability.YES,
        time_to_start=PilotFeedback.StartTimeBand.UNDER_TWO,
        time_to_check_in=PilotFeedback.CheckInTimeBand.UNDER_ONE,
        confusing_step=PilotFeedback.ConfusingStep.NONE,
        accessibility_friction=PilotFeedback.Friction.NONE,
        safety_friction=PilotFeedback.Friction.NONE,
    )

    payload = build_privacy_safe_pilot_export(user)
    historical.refresh_from_db()

    assert payload["record_count"] == 1
    assert payload["records"][0] == {
        "sequence": 1,
        "contract_version": historical.contract_version,
        "journey_stage": "assessment",
        "protocol_stable_id": "PRACTICE-FRIENDSHIP-01",
        "applicability": "yes",
        "time_to_start_band": "under_2_minutes",
        "time_to_check_in_band": "under_1_minute",
        "confusing_step": "none",
        "accessibility_friction": "none",
        "safety_friction": "none",
        "optional_comment_present": False,
    }
    assert historical.journey_stage == PilotFeedback.JourneyStage.ASSESSMENT
    assert historical.protocol_id == "PRACTICE-FRIENDSHIP-01"


@pytest.mark.django_db
def test_feedback_submission_and_export_cannot_mutate_developmental_state(
    client,
    user,
    seeded,
):
    run = AssessmentRun.objects.get(user=user)
    protocol = run.curriculum_version.levers.get(stable_id="L26").practice_protocols.get(
        stable_id="PRACTICE-FRIENDSHIP-01"
    )
    PracticeSprint.objects.create(
        user=user,
        protocol=protocol,
        assessment_run=run,
        person_or_context="PRIVATE-PRACTICE-CONTEXT-TOKEN",
        start_date=date.today(),
    )
    before = _developmental_state_snapshot(user)
    client.force_login(user)

    response = client.post(
        reverse("growth:pilot-feedback"),
        {
            **_feedback_data(protocol),
            "protocol": protocol.pk,
        },
    )

    assert response.status_code == 302
    assert response.url == reverse("growth:pilot-feedback")
    record = PilotFeedback.objects.get(user=user)
    assert record.contract_version == "GG-PILOT-FEEDBACK-1.0"
    assert record.protocol_id == protocol.pk
    assert record.comment == "PRIVATE-PILOT-COMMENT-TOKEN"
    assert _developmental_state_snapshot(user) == before

    exported = client.get(reverse("growth:pilot-feedback-export"))

    assert exported.status_code == 200
    assert _developmental_state_snapshot(user) == before
    assert PracticeCheckIn.objects.filter(sprint__user=user).count() == 0
    assert EvidenceEvent.objects.filter(check_in__sprint__user=user).count() == 0


@pytest.mark.django_db
def test_submitted_feedback_is_append_only(user, seeded):
    protocol = (
        user.assessment_runs.get()
        .curriculum_version.levers.get(stable_id="L26")
        .practice_protocols.get(stable_id="PRACTICE-FRIENDSHIP-01")
    )
    record = submit_pilot_feedback(user=user, cleaned_data=_feedback_data(protocol))

    record.comment = "changed"
    with pytest.raises(ValidationError, match="immutable"):
        record.save()
    with pytest.raises(ValidationError, match="immutable"):
        PilotFeedback.objects.filter(pk=record.pk).update(comment="changed")
    with pytest.raises(ValidationError, match="immutable"):
        PilotFeedback.objects.bulk_update([record], ["comment"])


@pytest.mark.django_db
def test_pilot_export_is_deterministic_allowlisted_and_user_scoped(client, user, seeded):
    user.username = "PRIVATE-PILOT-USERNAME-TOKEN"
    user.save(update_fields=["username"])
    run = AssessmentRun.objects.get(user=user)
    protocol = run.curriculum_version.levers.get(stable_id="L26").practice_protocols.get(
        stable_id="PRACTICE-FRIENDSHIP-01"
    )
    first_record = submit_pilot_feedback(
        user=user,
        cleaned_data=_feedback_data(protocol),
    )
    second_record = submit_pilot_feedback(
        user=user,
        cleaned_data=_feedback_data(
            None,
            journey_stage=PilotFeedback.JourneyStage.PROFILE,
            applicability="",
            time_to_start="",
            time_to_check_in="",
            confusing_step=PilotFeedback.ConfusingStep.PROFILE,
            accessibility_friction=PilotFeedback.Friction.PRESENT,
            safety_friction=PilotFeedback.Friction.PREFER_NOT,
            comment="SECOND-PRIVATE-COMMENT-TOKEN",
        ),
    )

    other_user = get_user_model().objects.create_user(
        username="OTHER-PRIVATE-PILOT-USER-TOKEN",
        password="local-test-password-47!",
    )
    other_record = submit_pilot_feedback(
        user=other_user,
        cleaned_data=_feedback_data(
            protocol,
            comment="OTHER-PRIVATE-PILOT-COMMENT-TOKEN",
        ),
    )
    client.force_login(user)

    first = client.get(reverse("growth:pilot-feedback-export"))
    second = client.get(reverse("growth:pilot-feedback-export"))
    body = first.content.decode()
    payload = json.loads(body)

    assert first.status_code == 200
    assert first.content == second.content
    assert first["Content-Type"].startswith("application/json")
    assert first["Content-Disposition"] == (
        'attachment; filename="grounded-growth-private-pilot-feedback.json"'
    )
    assert "no-store" in first["Cache-Control"]
    assert "private" in first["Cache-Control"]
    assert payload["schema_version"] == PILOT_EXPORT_SCHEMA_VERSION
    assert payload["feedback_contract_version"] == "GG-PILOT-FEEDBACK-1.0"
    assert payload["collection_method"] == "participant_selected_categories"
    assert payload["remote_telemetry_used"] is False
    assert payload["developmental_state_modified_by_feedback"] is False
    assert payload["record_count"] == 2
    assert payload["records"][0]["protocol_stable_id"] == protocol.pk
    assert payload["records"][1]["protocol_stable_id"] is None
    assert payload["records"][1]["accessibility_friction"] == "present"
    assert payload["privacy"]["contains_free_text"] is False
    assert payload["privacy"]["contains_assessment_or_evidence_values"] is False

    forbidden_values = {
        "PRIVATE-PILOT-USERNAME-TOKEN",
        "PRIVATE-PILOT-COMMENT-TOKEN",
        "SECOND-PRIVATE-COMMENT-TOKEN",
        "OTHER-PRIVATE-PILOT-USER-TOKEN",
        "OTHER-PRIVATE-PILOT-COMMENT-TOKEN",
        str(first_record.pk),
        str(second_record.pk),
        str(other_record.pk),
        first_record.submitted_at.isoformat(),
        second_record.submitted_at.isoformat(),
        run.stable_id,
    }
    assert all(value not in body for value in forbidden_values)
    assert '"comment":' not in body
    assert "original_share_code" not in body
    assert '"answers"' not in body
    assert '"evidence"' not in body
    assert '"score"' not in body


@pytest.mark.django_db
def test_pilot_export_fails_closed_without_partial_data(client, user, seeded):
    protocol = (
        user.assessment_runs.get()
        .curriculum_version.levers.get(stable_id="L26")
        .practice_protocols.get(stable_id="PRACTICE-FRIENDSHIP-01")
    )
    record = submit_pilot_feedback(user=user, cleaned_data=_feedback_data(protocol))
    PilotFeedback._base_manager.filter(pk=record.pk).update(journey_stage="broken")
    client.force_login(user)

    response = client.get(reverse("growth:pilot-feedback-export"))

    assert response.status_code == 409
    assert response.content == (
        b"Pilot feedback export stopped because stored feedback failed validation."
    )
    assert str(record.pk).encode() not in response.content


@pytest.mark.django_db
def test_feedback_purge_is_scoped_explicit_and_developmentally_inert(user, seeded):
    protocol = (
        user.assessment_runs.get()
        .curriculum_version.levers.get(stable_id="L26")
        .practice_protocols.get(stable_id="PRACTICE-FRIENDSHIP-01")
    )
    submit_pilot_feedback(user=user, cleaned_data=_feedback_data(protocol))
    other_user = get_user_model().objects.create_user(
        username="other-pilot",
        password="local-test-password-47!",
    )
    submit_pilot_feedback(user=other_user, cleaned_data=_feedback_data(protocol))
    before = _developmental_state_snapshot(user)

    preview = StringIO()
    call_command("purge_pilot_feedback", username=user.username, stdout=preview)
    assert "Dry run: 1" in preview.getvalue()
    assert PilotFeedback.objects.filter(user=user).count() == 1

    deleted = StringIO()
    call_command(
        "purge_pilot_feedback",
        username=user.username,
        confirm=True,
        stdout=deleted,
    )
    assert "Deleted 1 optional pilot-feedback record" in deleted.getvalue()
    assert not PilotFeedback.objects.filter(user=user).exists()
    assert PilotFeedback.objects.filter(user=other_user).count() == 1
    assert _developmental_state_snapshot(user) == before

    with pytest.raises(CommandError, match="local user was not found"):
        call_command("purge_pilot_feedback", username="missing-pilot")
