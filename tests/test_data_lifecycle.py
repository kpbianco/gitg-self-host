from __future__ import annotations

import json
from datetime import date, datetime
from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import models
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from growth.domain.context import ContextFactorValue
from growth.domain.personal_os import AUDIT_PROMPT_IDS, IDENTITY_SECTION_IDS
from growth.models import (
    AssessmentRun,
    Competency,
    CompletionCreditEvent,
    CompositeAssessmentSnapshot,
    CompositeScoreSnapshot,
    CompositeScoreState,
    EvidenceEvent,
    Lever,
    LeverBaseline,
    LeverState,
    PersonalOSRevision,
    PilotFeedback,
    PracticeCheckIn,
    PracticeContext,
    PracticeProtocol,
    PracticeSprint,
    ScoreSnapshot,
    WeeklyExecutionPlan,
    WeeklyExecutionReview,
)
from growth.services.context import PracticeContextInput, record_context_bundle
from growth.services.data_lifecycle import (
    DataLifecycleError,
    apply_retention,
    build_deletion_preview,
    build_retention_preview,
    delete_owner_account,
    render_owner_archive,
)
from growth.services.evidence import build_privacy_safe_evidence_export
from growth.services.operations_readiness import verify_operations_readiness
from growth.services.personal_os import record_personal_os_revision
from growth.services.pilot_feedback import build_privacy_safe_pilot_export, submit_pilot_feedback
from growth.services.practice import complete_with_review, save_check_in, start_practice
from growth.services.weekly_execution import (
    current_window,
    record_weekly_plan,
    record_weekly_review,
)

PRIVATE_CONTEXT = "Private context only for Kian"
PRIVATE_DRAFT = "Private draft narrative only for Kian"
PRIVATE_FEEDBACK = "Private feedback narrative only for Kian"
PRIVATE_MISSION = "Private mission narrative only for Kian"


def _personal_values():
    values = {
        section_id: {"state": "unknown", "value": None}
        for section_id in (*IDENTITY_SECTION_IDS, *AUDIT_PROMPT_IDS)
    }
    values["mission"] = {"state": "provided", "value": PRIVATE_MISSION}
    return {
        "identity_sections": {
            section_id: values[section_id] for section_id in IDENTITY_SECTION_IDS
        },
        "audit_responses": {section_id: values[section_id] for section_id in AUDIT_PROMPT_IDS},
    }


def _create_private_state(user):
    run = AssessmentRun.objects.get(user=user)
    protocol = PracticeProtocol.objects.get(stable_id="PRACTICE-FRIENDSHIP-01")
    sprint = start_practice(
        user=user,
        protocol=protocol,
        person_or_context=PRIVATE_CONTEXT,
        start_date=timezone.localdate(),
    )
    action = protocol.actions.order_by("sequence").first()
    draft = save_check_in(
        sprint=sprint, cleaned_data={"action": action, "note": PRIVATE_DRAFT}, submit=False
    )
    week_start, _ = current_window()
    plan = record_weekly_plan(
        user=user,
        assessment_run=run,
        sprint=sprint,
        action=action,
        week_start=week_start,
        intended_on=week_start,
    ).plan
    submitted = save_check_in(
        sprint=sprint,
        cleaned_data={
            "action": action,
            "action_attempted": True,
            "action_completed": True,
            "support_level": PracticeCheckIn.SupportLevel.INDEPENDENT,
            "context_comparison": PracticeCheckIn.ContextComparison.FIRST_RECORD,
            "evidence_direction": PracticeCheckIn.EvidenceDirection.SUPPORTS,
        },
        submit=True,
    )
    review = record_weekly_review(
        user=user, plan=plan, next_step="continue_current", adjustment="none"
    ).review
    feedback = submit_pilot_feedback(
        user=user,
        cleaned_data={
            "journey_stage": PilotFeedback.JourneyStage.ACCOUNT,
            "confusing_step": PilotFeedback.ConfusingStep.ACCOUNT,
            "accessibility_friction": PilotFeedback.Friction.NONE,
            "safety_friction": PilotFeedback.Friction.NONE,
            "comment": PRIVATE_FEEDBACK,
        },
    )
    provided = lambda value: ContextFactorValue("provided", value)  # noqa: E731
    record_context_bundle(
        user=user,
        assessment_run=run,
        assessment_factors={"season": provided("foundation"), "capacity": provided(3)},
        practice_inputs=(
            PracticeContextInput(
                protocol=protocol,
                factors={
                    key: provided(value)
                    for key, value in (
                        ("applicability", 4),
                        ("importance", 3),
                        ("readiness", 3),
                        ("urgency", 2),
                        ("opportunity_resources", 3),
                        ("burden", 1),
                    )
                },
            ),
        ),
    )
    personal = record_personal_os_revision(user=user, assessment_run=run, **_personal_values())
    return {
        "run": run,
        "sprint": sprint,
        "draft": draft,
        "submitted": submitted,
        "evidence": submitted.evidence_event,
        "plan": plan,
        "review": review,
        "feedback": feedback,
        "personal": personal.revision,
    }


def _close_private_sprint(records):
    sprint = records["sprint"]
    actions = list(sprint.protocol.actions.order_by("sequence"))
    save_check_in(
        sprint=sprint,
        cleaned_data={
            "action": actions[0],
            "action_attempted": True,
            "action_completed": True,
            "user_initiated": True,
            "moved_beyond_transactional": True,
            "meaningful_information_shared": True,
            "support_level": PracticeCheckIn.SupportLevel.INDEPENDENT,
            "context_comparison": PracticeCheckIn.ContextComparison.SAME_CONTEXT,
            "evidence_direction": PracticeCheckIn.EvidenceDirection.SUPPORTS,
        },
        submit=True,
    )
    save_check_in(
        sprint=sprint,
        cleaned_data={
            "action": actions[1],
            "action_attempted": True,
            "action_completed": True,
            "future_interaction_scheduled": True,
            "support_level": PracticeCheckIn.SupportLevel.INDEPENDENT,
            "context_comparison": PracticeCheckIn.ContextComparison.SAME_CONTEXT,
            "evidence_direction": PracticeCheckIn.EvidenceDirection.SUPPORTS,
        },
        submit=True,
    )
    review = complete_with_review(
        sprint=sprint,
        reflection="Private final reflection for the owner archive.",
        contradictory_evidence="",
    )
    records["practice_review"] = review
    records["completion_credit"] = CompletionCreditEvent.objects.get(sprint=sprint)
    return records


@pytest.mark.django_db
def test_owner_archive_is_complete_deterministic_private_and_cross_user_isolated(user, seeded):
    user.email = "kian-private@example.test"
    user.first_name = "Kian"
    user.save(update_fields=["email", "first_name"])
    records = _close_private_sprint(_create_private_state(user))
    other = get_user_model().objects.create_user(
        username="other-owner", email="other-private@example.test", password="other-password-47!"
    )
    submit_pilot_feedback(
        user=other,
        cleaned_data={
            "journey_stage": PilotFeedback.JourneyStage.OTHER,
            "comment": "Other owner's private narrative",
        },
    )
    first = render_owner_archive(user)
    assert first == render_owner_archive(user)
    archive = json.loads(first)
    assert archive["privacy_class"] == "owner-private"
    assert archive["privacy"]["safe_for_sharing"] is False
    assert set(archive["records"]) == {
        "archetype_results",
        "assessment_calibration_consents",
        "assessment_context",
        "assessment_runs",
        "composite_assessment_snapshots",
        "composite_score_snapshots",
        "composite_score_states",
        "completion_credit_events",
        "evidence_events",
        "lever_baselines",
        "lever_states",
        "orientation_results",
        "personal_os_revisions",
        "pilot_feedback",
        "practice_check_ins",
        "practice_context",
        "practice_reviews",
        "practice_sprints",
        "score_snapshots",
        "weekly_execution_plans",
        "weekly_execution_reviews",
    }
    text = first.decode()
    for private_value in (PRIVATE_CONTEXT, PRIVATE_DRAFT, PRIVATE_FEEDBACK, PRIVATE_MISSION):
        assert private_value in text
    for forbidden in (
        user.password,
        other.username,
        other.email,
        "Other owner's private narrative",
        str(records["run"].pk),
        str(records["sprint"].pk),
        str(records["draft"].pk),
        str(records["submitted"].pk),
        str(records["evidence"].pk),
        str(records["plan"].pk),
        str(records["review"].pk),
        str(records["feedback"].pk),
        str(records["personal"].pk),
        str(records["practice_review"].pk),
        str(records["completion_credit"].pk),
    ):
        assert forbidden not in text
    minimized = json.dumps(build_privacy_safe_evidence_export(user), sort_keys=True)
    pilot_minimized = json.dumps(build_privacy_safe_pilot_export(user), sort_keys=True)
    for private_value in (PRIVATE_CONTEXT, PRIVATE_DRAFT, PRIVATE_FEEDBACK, PRIVATE_MISSION):
        assert private_value not in minimized
        assert private_value not in pilot_minimized


@pytest.mark.django_db
def test_owner_archive_download_and_deletion_groups_include_composite_state(client, user, seeded):
    client.force_login(user)
    _close_private_sprint(_create_private_state(user))

    archive = client.get(reverse("growth:owner-archive"))
    assert archive.status_code == 200
    assert archive["Content-Disposition"] == (
        'attachment; filename="grounded-growth-owner-private-archive-v3.json"'
    )
    assert json.loads(archive.content)["schema_version"] == (
        "grounded-growth-owner-private-archive-v3"
    )

    management = client.get(reverse("growth:data-management"))
    assert management.status_code == 200
    assert sum(count for _label, count in management.context["deletion_groups"]) == (
        management.context["deletion_preview"].total_records
    )


@pytest.mark.django_db
def test_operations_readiness_is_deterministic_read_only_and_privacy_safe(user, seeded):
    _create_private_state(user)
    before = build_deletion_preview(user)
    first = verify_operations_readiness().as_dict()
    assert first == verify_operations_readiness().as_dict()
    assert first["software_ready"] is True
    assert first["requires_human_gate"] is True
    output = StringIO()
    call_command("verify_m6h_operations_readiness", "--json", stdout=output)
    rendered = output.getvalue()
    for private_value in (PRIVATE_CONTEXT, PRIVATE_DRAFT, PRIVATE_FEEDBACK, PRIVATE_MISSION):
        assert private_value not in rendered
    assert build_deletion_preview(user) == before


@pytest.mark.django_db
def test_archive_and_data_management_require_authentication(client):
    for name in (
        "growth:data-management",
        "growth:owner-archive",
        "growth:assessment-calibration-preview",
    ):
        response = client.get(reverse(name))
        assert response.status_code == 302
        assert response.url.startswith("/accounts/login/")


@pytest.mark.django_db
def test_deletion_form_requires_password_phrase_and_current_preview(client, user, seeded):
    client.force_login(user)
    _create_private_state(user)
    response = client.get(reverse("growth:data-management"))
    token = response.context["deletion_form"]["preview_token"].value()
    before = build_deletion_preview(user)
    wrong = client.post(
        reverse("growth:data-management"),
        {
            "action": "delete_account",
            "preview_token": token,
            "current_password": "wrong-password",
            "confirmation": "DELETE MY ACCOUNT",
        },
    )
    assert wrong.status_code == 200
    assert get_user_model().objects.filter(pk=user.pk).exists()
    assert build_deletion_preview(user).total_records == before.total_records
    submit_pilot_feedback(
        user=user,
        cleaned_data={
            "journey_stage": PilotFeedback.JourneyStage.OTHER,
            "comment": "A new record invalidates the old preview.",
        },
    )
    stale = client.post(
        reverse("growth:data-management"),
        {
            "action": "delete_account",
            "preview_token": token,
            "current_password": "local-test-password-47!",
            "confirmation": "DELETE MY ACCOUNT",
        },
    )
    assert stale.status_code == 200
    assert b"preview changed" in stale.content.lower()
    assert get_user_model().objects.filter(pk=user.pk).exists()


@pytest.mark.django_db
def test_deletion_form_executes_exact_preview_and_signs_owner_out(client, user, seeded):
    client.force_login(user)
    _create_private_state(user)
    response = client.get(reverse("growth:data-management"))
    token = response.context["deletion_form"]["preview_token"].value()
    deleted = client.post(
        reverse("growth:data-management"),
        {
            "action": "delete_account",
            "preview_token": token,
            "current_password": "local-test-password-47!",
            "confirmation": "DELETE MY ACCOUNT",
        },
    )
    assert deleted.status_code == 302
    assert deleted.url == reverse("login")
    assert not get_user_model().objects.filter(pk=user.pk).exists()
    assert "_auth_user_id" not in client.session


@pytest.mark.django_db
def test_account_deletion_removes_exact_owner_and_preserves_canonical_and_other_user(user, seeded):
    _close_private_sprint(_create_private_state(user))
    other = get_user_model().objects.create_user(username="preserved-owner")
    other_feedback = submit_pilot_feedback(
        user=other,
        cleaned_data={
            "journey_stage": PilotFeedback.JourneyStage.OTHER,
            "comment": "Preserved owner feedback.",
        },
    )
    canonical_before = (
        Lever.objects.count(),
        Competency.objects.count(),
        PracticeProtocol.objects.count(),
    )
    preview = build_deletion_preview(user)
    assert (
        delete_owner_account(user=user, expected_preview_hash=preview.content_hash)
        == preview.total_records
    )
    assert not get_user_model().objects.filter(pk=user.pk).exists()
    assert get_user_model().objects.filter(pk=other.pk).exists()
    assert PilotFeedback.objects.filter(pk=other_feedback.pk).exists()
    assert (
        Lever.objects.count(),
        Competency.objects.count(),
        PracticeProtocol.objects.count(),
    ) == canonical_before
    for queryset in (
        AssessmentRun.objects.filter(user_id=user.pk),
        LeverBaseline.objects.filter(user_id=user.pk),
        LeverState.objects.filter(user_id=user.pk),
        PracticeSprint.objects.filter(user_id=user.pk),
        PilotFeedback.objects.filter(user_id=user.pk),
        PersonalOSRevision.objects.filter(user_id=user.pk),
        WeeklyExecutionPlan.objects.filter(user_id=user.pk),
        WeeklyExecutionReview.objects.filter(user_id=user.pk),
        CompositeAssessmentSnapshot.objects.filter(assessment_run__user_id=user.pk),
        CompletionCreditEvent.objects.filter(assessment_run__user_id=user.pk),
        CompositeScoreState.objects.filter(user_id=user.pk),
        CompositeScoreSnapshot.objects.filter(assessment_run__user_id=user.pk),
    ):
        assert not queryset.exists()


@pytest.mark.django_db
def test_account_deletion_rolls_back_every_change_on_failure(user, seeded, monkeypatch):
    _create_private_state(user)
    preview = build_deletion_preview(user)
    module = __import__("growth.services.data_lifecycle", fromlist=["_force_delete"])
    original = module._force_delete
    calls = 0

    def fail_after_first(queryset):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("synthetic deletion failure")
        return original(queryset)

    monkeypatch.setattr("growth.services.data_lifecycle._force_delete", fail_after_first)
    with pytest.raises(RuntimeError, match="synthetic deletion failure"):
        delete_owner_account(user=user, expected_preview_hash=preview.content_hash)
    assert get_user_model().objects.filter(pk=user.pk).exists()
    assert build_deletion_preview(user) == preview


@pytest.mark.django_db
def test_retention_is_disabled_by_default_and_never_changes_records(user, seeded):
    _create_private_state(user)
    preview = build_retention_preview(user, as_of=date(2030, 1, 1))
    assert preview.enabled is False
    assert preview.total_records == 0
    with pytest.raises(DataLifecycleError, match="disabled"):
        apply_retention(user=user, expected_preview_hash=preview.content_hash, as_of=preview.as_of)


@pytest.mark.django_db
@override_settings(OWNER_RETENTION_ENABLED=True, OWNER_RETENTION_DAYS=30)
def test_retention_deletes_only_old_drafts_and_feedback(user, seeded):
    records = _create_private_state(user)
    old = datetime(2025, 1, 1, tzinfo=timezone.get_current_timezone())
    models.QuerySet.update(PracticeCheckIn.objects.filter(pk=records["draft"].pk), updated_at=old)
    models.QuerySet.update(
        PracticeCheckIn.objects.filter(pk=records["submitted"].pk), updated_at=old
    )
    models.QuerySet.update(
        PilotFeedback.objects.filter(pk=records["feedback"].pk), submitted_at=old
    )
    state_before = {
        "evidence": EvidenceEvent.objects.count(),
        "scores": ScoreSnapshot.objects.count(),
        "context": PracticeContext.objects.count(),
        "personal": PersonalOSRevision.objects.count(),
        "plans": WeeklyExecutionPlan.objects.count(),
        "reviews": WeeklyExecutionReview.objects.count(),
    }
    preview = build_retention_preview(user, as_of=date(2026, 8, 31))
    assert preview.record_counts == {"draft_check_ins": 1, "pilot_feedback": 1}
    result = apply_retention(
        user=user, expected_preview_hash=preview.content_hash, as_of=preview.as_of
    )
    assert result.total_deleted == 2
    assert not PracticeCheckIn.objects.filter(pk=records["draft"].pk).exists()
    assert PracticeCheckIn.objects.filter(pk=records["submitted"].pk).exists()
    assert not PilotFeedback.objects.filter(pk=records["feedback"].pk).exists()
    assert {
        "evidence": EvidenceEvent.objects.count(),
        "scores": ScoreSnapshot.objects.count(),
        "context": PracticeContext.objects.count(),
        "personal": PersonalOSRevision.objects.count(),
        "plans": WeeklyExecutionPlan.objects.count(),
        "reviews": WeeklyExecutionReview.objects.count(),
    } == state_before
