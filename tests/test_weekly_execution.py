from __future__ import annotations

import hashlib
import json
from datetime import date

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.urls import reverse
from django.utils import timezone

from growth.domain.personal_os import AUDIT_PROMPT_IDS, IDENTITY_SECTION_IDS
from growth.domain.weekly_execution import (
    WeeklyExecutionContractError,
    WeeklyProofOutcome,
    build_weekly_plan_snapshot,
    build_weekly_review_snapshot,
    current_week_start,
    week_end,
)
from growth.models import (
    AssessmentRun,
    EvidenceEvent,
    LeverState,
    PilotFeedback,
    PracticeCheckIn,
    PracticeProtocol,
    PracticeReview,
    PracticeSprint,
    ScoreSnapshot,
    WeeklyExecutionPlan,
    WeeklyExecutionReview,
)
from growth.services.practice import save_check_in, start_practice
from growth.services.profile import build_profile_summary
from growth.services.weekly_execution import (
    WeeklyExecutionReadinessError,
    WeeklyExecutionServiceError,
    WeeklyExecutionWriteConflictError,
    current_window,
    latest_unreviewed_plan,
    proof_events_for_plan,
    record_weekly_plan,
    record_weekly_review,
    verify_weekly_execution_readiness,
)


def _friendship_protocol():
    return PracticeProtocol.objects.get(stable_id="PRACTICE-FRIENDSHIP-01")


def _sprint(user):
    return start_practice(
        user=user,
        protocol=_friendship_protocol(),
        person_or_context="Synthetic weekly context",
        start_date=timezone.localdate(),
    )


def _plan(user, sprint, *, intended_on=None):
    start, _ = current_window()
    action = sprint.protocol.actions.order_by("sequence").first()
    return record_weekly_plan(
        user=user,
        assessment_run=sprint.assessment_run,
        sprint=sprint,
        action=action,
        week_start=start,
        intended_on=intended_on or start,
    ).plan


def _submitted_evidence(sprint, action, *, completed=False, direction="supports"):
    return save_check_in(
        sprint=sprint,
        cleaned_data={
            "action": action,
            "action_attempted": True,
            "action_completed": completed,
            "support_level": PracticeCheckIn.SupportLevel.INDEPENDENT,
            "context_comparison": PracticeCheckIn.ContextComparison.FIRST_RECORD,
            "evidence_direction": direction,
            "contradictory_evidence": (
                "Synthetic contradictory observation."
                if direction in {"mixed", "contradicts"}
                else ""
            ),
        },
        submit=True,
    )


def _recommendation_signature(user):
    summary = build_profile_summary(user)
    return (
        tuple(item.stable_id for item in summary.recommendations),
        tuple(sorted(summary.recommendation_priorities.items())),
    )


def _nonweekly_state(user, sprint):
    return {
        "evidence": list(EvidenceEvent.objects.order_by("stable_id").values()),
        "score": list(ScoreSnapshot.objects.order_by("stable_id").values()),
        "lever": list(LeverState.objects.order_by("lever_id").values()),
        "check_ins": list(PracticeCheckIn.objects.order_by("stable_id").values()),
        "practice_reviews": list(PracticeReview.objects.order_by("stable_id").values()),
        "pilot_feedback": list(PilotFeedback.objects.order_by("stable_id").values()),
        "recommendations": _recommendation_signature(user),
        "sprint_status": PracticeSprint.objects.get(pk=sprint.pk).status,
    }


def _personal_os_post(*, epoch, direction, priority):
    data = {"form_type": "personal_os", "assessment_epoch": epoch}
    for section_id in (*IDENTITY_SECTION_IDS, *AUDIT_PROMPT_IDS):
        data[f"{section_id}_state"] = "unknown"
        data[f"{section_id}_value"] = ""
    data.update(
        {
            "twelve_month_direction_state": "provided",
            "twelve_month_direction_value": direction,
            "priority_stack_state": "provided",
            "priority_stack_value": priority,
        }
    )
    return data


def test_week_window_and_canonical_snapshots_are_strict_and_deterministic():
    monday = date(2026, 8, 24)
    assert current_week_start(date(2026, 8, 27)) == monday
    assert week_end(monday) == date(2026, 8, 30)
    first = build_weekly_plan_snapshot(
        assessment_epoch_id="ASSESSMENT-WEEKLY",
        sprint_id="00000000-0000-0000-0000-000000000001",
        protocol_stable_id="PRACTICE-WEEKLY",
        action_stable_id="ACTION-WEEKLY-01",
        week_start=monday,
        intended_on=date(2026, 8, 30),
    )
    second = build_weekly_plan_snapshot(
        assessment_epoch_id="ASSESSMENT-WEEKLY",
        sprint_id="00000000-0000-0000-0000-000000000001",
        protocol_stable_id="PRACTICE-WEEKLY",
        action_stable_id="ACTION-WEEKLY-01",
        week_start="2026-08-24",
        intended_on="2026-08-30",
    )
    assert first == second
    assert set(first.payload) == {
        "action_stable_id",
        "assessment_epoch_id",
        "contract_version",
        "intended_on",
        "protocol_stable_id",
        "scope",
        "sprint_id",
        "week_start",
    }
    with pytest.raises(WeeklyExecutionContractError, match="Monday"):
        build_weekly_plan_snapshot(
            assessment_epoch_id="ASSESSMENT-WEEKLY",
            sprint_id="SPRINT-WEEKLY",
            protocol_stable_id="PRACTICE-WEEKLY",
            action_stable_id="ACTION-WEEKLY-01",
            week_start=date(2026, 8, 25),
            intended_on=date(2026, 8, 25),
        )
    with pytest.raises(WeeklyExecutionContractError, match="seven-day window"):
        build_weekly_plan_snapshot(
            assessment_epoch_id="ASSESSMENT-WEEKLY",
            sprint_id="SPRINT-WEEKLY",
            protocol_stable_id="PRACTICE-WEEKLY",
            action_stable_id="ACTION-WEEKLY-01",
            week_start=monday,
            intended_on=date(2026, 8, 31),
        )

    proof = {
        "action_completed": False,
        "action_attempted": True,
        "adverse": False,
        "algorithm_version": "GG-EVIDENCE-1.0",
        "direction": "supports",
        "event_id": "00000000-0000-0000-0000-000000000002",
        "submitted_at": "2026-08-27T10:00:00+00:00",
        "withholding_reasons": [],
    }
    review = build_weekly_review_snapshot(
        plan_stable_id="00000000-0000-0000-0000-000000000003",
        plan_content_hash="a" * 64,
        proof_events=(proof,),
        reviewed_at="2026-08-27T11:00:00+00:00",
        next_step="continue_current",
        adjustment="none",
    )
    assert review.payload["outcome"] == WeeklyProofOutcome.ATTEMPTED
    assert (
        build_weekly_review_snapshot(
            plan_stable_id="00000000-0000-0000-0000-000000000003",
            plan_content_hash="a" * 64,
            proof_events=(),
            reviewed_at="2026-08-27T11:00:00+00:00",
            next_step="continue_current",
            adjustment="none",
        ).payload["outcome"]
        == WeeklyProofOutcome.NO_SUBMITTED_EVIDENCE
    )


@pytest.mark.django_db
def test_weekly_plan_is_append_only_idempotent_owned_and_latest_revision_only(user, seeded):
    sprint = _sprint(user)
    start, end = current_window()
    action = sprint.protocol.actions.order_by("sequence").first()
    first = record_weekly_plan(
        user=user,
        assessment_run=sprint.assessment_run,
        sprint=sprint,
        action=action,
        week_start=start,
        intended_on=start,
    )
    retry = record_weekly_plan(
        user=user,
        assessment_run=sprint.assessment_run,
        sprint=sprint,
        action=action,
        week_start=start,
        intended_on=start,
    )
    changed = record_weekly_plan(
        user=user,
        assessment_run=sprint.assessment_run,
        sprint=sprint,
        action=action,
        week_start=start,
        intended_on=end,
    )
    assert (first.created, retry.created, changed.created) == (True, False, True)
    assert retry.plan.pk == first.plan.pk
    assert changed.plan.revision == 2
    assert (
        latest_unreviewed_plan(user=user, assessment_run=sprint.assessment_run).pk
        == changed.plan.pk
    )
    with pytest.raises(WeeklyExecutionServiceError, match="latest"):
        record_weekly_review(
            user=user,
            plan=first.plan,
            next_step="continue_current",
            adjustment="none",
        )
    review = record_weekly_review(
        user=user,
        plan=changed.plan,
        next_step="continue_current",
        adjustment="none",
    )
    assert review.created is True
    assert latest_unreviewed_plan(user=user, assessment_run=sprint.assessment_run) is None
    with pytest.raises(WeeklyExecutionWriteConflictError, match="immutable"):
        record_weekly_review(
            user=user,
            plan=changed.plan,
            next_step="pause_reconsider",
            adjustment="timing",
        )

    other = get_user_model().objects.create_user(username="weekly-other")
    with pytest.raises(WeeklyExecutionServiceError, match="own"):
        record_weekly_plan(
            user=other,
            assessment_run=sprint.assessment_run,
            sprint=sprint,
            action=action,
            week_start=start,
            intended_on=start,
        )
    changed.plan.intended_on = start
    with pytest.raises(ValidationError, match="immutable"):
        changed.plan.save()
    with pytest.raises(ValidationError, match="immutable"):
        WeeklyExecutionReview.objects.filter(pk=review.review.pk).delete()


@pytest.mark.django_db
def test_weekly_review_replays_exact_post_plan_proof_without_side_effects(user, seeded):
    sprint = _sprint(user)
    action = sprint.protocol.actions.order_by("sequence").first()
    before_plan_event = _submitted_evidence(sprint, action)
    plan = _plan(user, sprint)
    assert proof_events_for_plan(plan) == ()

    second = save_check_in(
        sprint=sprint,
        cleaned_data={
            "action": action,
            "action_attempted": True,
            "action_completed": True,
            "support_level": PracticeCheckIn.SupportLevel.INDEPENDENT,
            "context_comparison": PracticeCheckIn.ContextComparison.SAME_CONTEXT,
            "evidence_direction": PracticeCheckIn.EvidenceDirection.SUPPORTS,
        },
        submit=True,
    )
    proof = proof_events_for_plan(plan)
    assert len(proof) == 1
    assert proof[0]["event_id"] == str(second.evidence_event.pk)
    assert proof[0]["event_id"] != str(before_plan_event.evidence_event.pk)
    assert proof[0]["action_completed"] is True

    protected = _nonweekly_state(user, sprint)
    result = record_weekly_review(
        user=user,
        plan=plan,
        next_step="plan_next_action",
        adjustment="scope",
    )
    assert result.review.outcome == WeeklyProofOutcome.COMPLETED
    assert result.review.canonical_snapshot["proof_events"] == list(proof)
    assert _nonweekly_state(user, sprint) == protected
    retry = record_weekly_review(
        user=user,
        plan=plan,
        next_step="plan_next_action",
        adjustment="scope",
    )
    assert retry.created is False
    assert retry.review.pk == result.review.pk
    later = save_check_in(
        sprint=sprint,
        cleaned_data={
            "action": action,
            "action_attempted": True,
            "action_completed": False,
            "support_level": PracticeCheckIn.SupportLevel.PLANNING_AID,
            "context_comparison": PracticeCheckIn.ContextComparison.SAME_CONTEXT,
            "evidence_direction": PracticeCheckIn.EvidenceDirection.MIXED,
            "contradictory_evidence": "Synthetic later mixed observation.",
        },
        submit=True,
    )
    assert str(later.evidence_event.pk) not in json.dumps(result.review.canonical_snapshot)
    assert verify_weekly_execution_readiness().exact_replayed_proof_events == 1


@pytest.mark.django_db
def test_weekly_browser_loop_is_authenticated_private_and_no_proof_is_explicit(
    client, user, seeded
):
    url = reverse("growth:weekly-execution")
    assert client.get(url).status_code == 302
    client.force_login(user)
    run = AssessmentRun.objects.get(user=user)
    no_sprint = client.get(url)
    assert no_sprint.status_code == 200
    assert b"No active practice" in no_sprint.content

    direction = "PRIVATE-WEEKLY-DIRECTION-SENTINEL"
    priority = "PRIVATE-WEEKLY-PRIORITY-SENTINEL"
    response = client.post(
        reverse("growth:personal-os"),
        _personal_os_post(epoch=run.pk, direction=direction, priority=priority),
    )
    assert response.status_code == 302
    sprint = _sprint(user)
    action = sprint.protocol.actions.order_by("sequence").first()
    page = client.get(url)
    assert page.status_code == 200
    assert direction.encode() in page.content
    assert priority.encode() in page.content
    assert action.title.encode() in page.content
    for private_free_url in (reverse("growth:home"), reverse("growth:profile")):
        body = client.get(private_free_url).content
        assert direction.encode() not in body
        assert priority.encode() not in body

    week_start, _ = current_window()
    saved = client.post(
        url,
        {
            "form_type": "weekly_plan",
            "assessment_epoch": run.pk,
            "sprint_id": sprint.pk,
            "week_start": week_start.isoformat(),
            "action": action.pk,
            "intended_on": week_start.isoformat(),
        },
    )
    assert saved.status_code == 302
    assert saved.url == url
    review_page = client.get(url)
    assert b"No submitted proof for this plan" in review_page.content
    reviewed = client.post(
        url,
        {
            "form_type": "weekly_review",
            "plan_id": WeeklyExecutionPlan.objects.get().pk,
            "next_step": "continue_current",
            "adjustment": "none",
        },
    )
    assert reviewed.status_code == 302
    completed = client.get(url)
    assert b"No submitted evidence" in completed.content
    assert b"The review created no new evidence or score contribution" in completed.content

    stale = client.post(
        url,
        {
            "form_type": "weekly_plan",
            "assessment_epoch": "ASSESSMENT-STALE",
            "sprint_id": sprint.pk,
            "week_start": week_start.isoformat(),
            "action": action.pk,
            "intended_on": week_start.isoformat(),
        },
    )
    assert stale.status_code == 409
    assert direction.encode() not in stale.content
    assert priority.encode() not in stale.content


@pytest.mark.django_db
def test_weekly_readiness_is_private_deterministic_and_fails_closed(user, seeded, capsys):
    empty = verify_weekly_execution_readiness()
    assert empty.plans == 0
    assert empty.reviews == 0
    assert empty.software_ready is True
    assert empty.requires_human_gate is False

    sprint = _sprint(user)
    plan = _plan(user, sprint)
    record_weekly_review(
        user=user,
        plan=plan,
        next_step="continue_current",
        adjustment="none",
    )
    first = verify_weekly_execution_readiness().as_dict()
    second = verify_weekly_execution_readiness().as_dict()
    assert first == second
    assert first["plans"] == 1
    assert first["reviews"] == 1
    assert first["changes_evidence"] is False
    assert first["changes_score_state"] is False
    assert first["changes_recommendation_order"] is False
    assert first["changes_practice_completion"] is False
    call_command("verify_weekly_execution_readiness", "--json")
    command_payload = capsys.readouterr().out
    assert json.loads(command_payload) == first
    serialized = json.dumps(first, sort_keys=True)
    for forbidden in ("canonical_snapshot", "content_hash", user.username, "person_or_context"):
        assert forbidden not in serialized

    with connection.cursor() as cursor:
        cursor.execute(
            'UPDATE "growth_weeklyexecutionplan" SET "content_hash" = %s WHERE "stable_id" = %s',
            ["0" * 64, plan.pk.hex],
        )
    with pytest.raises(WeeklyExecutionReadinessError, match="failed"):
        verify_weekly_execution_readiness()


def _growth_digest(excluded_tables=(), excluded_columns=()):
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
def test_weekly_migration_round_trip_preserves_preexisting_growth_state(seeded):
    executor = MigrationExecutor(connection)
    original_leaves = executor.loader.graph.leaf_nodes()
    excluded = {
        "growth_assessmentcalibrationconsent",
        "growth_completioncreditevent",
        "growth_compositeassessmentsnapshot",
        "growth_compositescoresnapshot",
        "growth_compositescorestate",
        "growth_weeklyexecutionplan",
        "growth_weeklyexecutionreview",
    }
    added_columns = {("growth_practicesprint", "scoring_contract_version")}
    before = _growth_digest(excluded, added_columns)
    try:
        executor.migrate([("growth", "0010_practicecheckin_typed_observations")])
        assert _growth_digest(excluded, added_columns) == before
        executor = MigrationExecutor(connection)
        executor.migrate([("growth", "0011_weeklyexecutionplan_weeklyexecutionreview_and_more")])
        assert _growth_digest(excluded, added_columns) == before
        executor = MigrationExecutor(connection)
        executor.migrate([("growth", "0010_practicecheckin_typed_observations")])
        assert _growth_digest(excluded, added_columns) == before
    finally:
        MigrationExecutor(connection).migrate(original_leaves)
