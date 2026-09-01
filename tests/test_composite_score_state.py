from datetime import date
from decimal import Decimal
from io import StringIO

import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from growth.domain.composite_scoring import ALGORITHM_VERSION
from growth.models import (
    AssessmentRun,
    CompletionCreditEvent,
    CompositeAssessmentSnapshot,
    CompositeScoreSnapshot,
    CompositeScoreState,
    EvidenceEvent,
    LeverBaseline,
    PracticeCheckIn,
    PracticeProtocol,
    ScoreSnapshot,
)
from growth.services.composite_score_state import (
    CompositeScoreStateError,
    create_completion_credit_event,
    reverse_completion_credit_event,
    synchronize_composite_score_state_for_run,
    verify_composite_score_state_for_run,
)
from growth.services.practice import complete_with_review, save_check_in, start_practice
from growth.services.profile import build_profile_summary
from growth.services.score_state import (
    synchronize_score_state_for_run,
    verify_score_state_for_run,
)


def _friendship():
    return PracticeProtocol.objects.get(stable_id="PRACTICE-FRIENDSHIP-01")


def _start(user):
    return start_practice(
        user=user,
        protocol=_friendship(),
        person_or_context="R.",
        start_date=date.today(),
    )


def _submit(sprint, action, *, first, completed, **observations):
    data = {
        "action": action,
        "action_attempted": True,
        "action_completed": completed,
        "user_initiated": False,
        "moved_beyond_transactional": False,
        "follow_up_question_asked": False,
        "meaningful_information_shared": False,
        "future_interaction_scheduled": False,
        "follow_up_within_seven_days": False,
        "internal_resistance": None,
        "expected_reciprocity": None,
        "observed_reciprocity": None,
        "support_level": PracticeCheckIn.SupportLevel.INDEPENDENT,
        "context_comparison": (
            PracticeCheckIn.ContextComparison.FIRST_RECORD
            if first
            else PracticeCheckIn.ContextComparison.SAME_CONTEXT
        ),
        "evidence_direction": PracticeCheckIn.EvidenceDirection.SUPPORTS,
        "contradictory_evidence": "",
        "note": "",
    }
    data.update(observations)
    return save_check_in(sprint=sprint, cleaned_data=data, submit=True)


def _partial_closeout(user):
    sprint = _start(user)
    actions = list(sprint.protocol.actions.order_by("sequence"))
    _submit(
        sprint,
        actions[0],
        first=True,
        completed=True,
        user_initiated=True,
        moved_beyond_transactional=True,
        meaningful_information_shared=True,
    )
    _submit(
        sprint,
        actions[1],
        first=False,
        completed=True,
        future_interaction_scheduled=True,
    )
    review = complete_with_review(
        sprint=sprint,
        reflection="Two actions were sufficient for this closeout.",
        contradictory_evidence="",
    )
    return sprint, review


def _full_closeout(user):
    sprint = _start(user)
    actions = list(sprint.protocol.actions.order_by("sequence"))
    _submit(
        sprint,
        actions[0],
        first=True,
        completed=True,
        user_initiated=True,
        moved_beyond_transactional=True,
        meaningful_information_shared=True,
    )
    _submit(
        sprint,
        actions[1],
        first=False,
        completed=True,
        future_interaction_scheduled=True,
    )
    _submit(
        sprint,
        actions[2],
        first=False,
        completed=True,
        follow_up_question_asked=True,
        follow_up_within_seven_days=True,
    )
    review = complete_with_review(
        sprint=sprint,
        reflection="All three actions were completed.",
        contradictory_evidence="",
    )
    return sprint, review


def _clone_epoch_with_baselines(run, *, stable_id):
    clone = AssessmentRun.objects.create(
        stable_id=stable_id,
        user=run.user,
        curriculum_version=run.curriculum_version,
        assessment_version=run.assessment_version,
        source=run.source,
        answers=run.answers,
        clarifier_answers=run.clarifier_answers,
        timing_data=run.timing_data,
        response_quality_result=run.response_quality_result,
        orientation_outputs=run.orientation_outputs,
        archetype_outputs=run.archetype_outputs,
        raw_lever_scores=run.raw_lever_scores,
        calibrated_lever_estimates=run.calibrated_lever_estimates,
        lever_confidence=run.lever_confidence,
        original_share_code=run.original_share_code,
    )
    LeverBaseline.objects.bulk_create(
        [
            LeverBaseline(
                user=run.user,
                assessment_run=clone,
                lever=baseline.lever,
                raw_self_report=baseline.raw_self_report,
                calibrated_estimate=baseline.calibrated_estimate,
                evidence_confidence=baseline.evidence_confidence,
                baseline_alpha=baseline.baseline_alpha,
                baseline_beta=baseline.baseline_beta,
                baseline_mass_source=baseline.baseline_mass_source,
                need_score=baseline.need_score,
                need_rank=baseline.need_rank,
                notes=baseline.notes,
            )
            for baseline in LeverBaseline.objects.filter(assessment_run=run).select_related("lever")
        ]
    )
    return clone


@pytest.mark.django_db
def test_seed_projects_every_family_lever_domain_and_competency(user, seeded):
    run = user.assessment_runs.get()
    snapshot = CompositeAssessmentSnapshot.objects.get(assessment_run=run)
    state = CompositeScoreState.objects.get(assessment_run=run)

    assert snapshot.projection["counts"] == {
        "families": 7,
        "levers": 37,
        "domains": 27,
        "competencies": 383,
    }
    assert len(state.state["families"]) == 7
    assert len(state.state["levers"]) == 37
    assert len(state.state["domains"]) == 27
    assert len(state.state["competencies"]) == 383
    assert state.state["canonical_coverage"] == "0.000000000000"
    for row in snapshot.projection["competencies"].values():
        assert sum(Decimal(weight) for weight in row["relationships"].values()) == Decimal("1")
        assert Decimal(row["estimate"]) >= 0
        assert Decimal(row["estimate"]) <= 1
    verify_composite_score_state_for_run(run)


@pytest.mark.django_db
def test_check_ins_do_not_score_and_human_partial_closeout_awards_075(user, seeded):
    run = user.assessment_runs.get()
    before_composite = CompositeScoreState.objects.get(assessment_run=run)
    before_hash = before_composite.state_hash
    before_state = before_composite.state
    before_snapshot_count = CompositeScoreSnapshot.objects.filter(assessment_run=run).count()
    before_legacy = list(
        LeverBaseline.objects.filter(assessment_run=run).values_list(
            "lever_id", "calibrated_estimate", "need_score"
        )
    )
    legacy_snapshot_count = ScoreSnapshot.objects.filter(assessment_run=run).count()
    sprint = _start(user)
    assert sprint.scoring_contract_version == ALGORITHM_VERSION
    actions = list(sprint.protocol.actions.order_by("sequence"))
    _submit(
        sprint,
        actions[0],
        first=True,
        completed=True,
        user_initiated=True,
        moved_beyond_transactional=True,
        meaningful_information_shared=True,
    )
    _submit(
        sprint,
        actions[1],
        first=False,
        completed=True,
        future_interaction_scheduled=True,
    )

    before_composite.refresh_from_db()
    assert before_composite.state_hash == before_hash
    assert before_composite.state == before_state
    assert CompositeScoreSnapshot.objects.filter(assessment_run=run).count() == (
        before_snapshot_count
    )
    assert CompletionCreditEvent.objects.count() == 0
    assert EvidenceEvent.objects.filter(check_in__sprint=sprint).count() == 2
    synchronize_score_state_for_run(run)
    verify_score_state_for_run(run)
    assert ScoreSnapshot.objects.filter(assessment_run=run).count() == legacy_snapshot_count

    complete_with_review(
        sprint=sprint,
        reflection="The minimum bounded actions were enough for this run.",
        contradictory_evidence="",
    )
    event = CompletionCreditEvent.objects.get(sprint=sprint)
    state = CompositeScoreState.objects.get(assessment_run=run)
    competency_id = sprint.protocol.parent_competency_id
    assert event.completion_credit == Decimal("0.7500")
    assert state.state["competencies"][competency_id]["completion_credit"] == ("0.750000000000")
    assert state.state_hash != before_hash
    assert (
        list(
            LeverBaseline.objects.filter(assessment_run=run).values_list(
                "lever_id", "calibrated_estimate", "need_score"
            )
        )
        == before_legacy
    )
    verify_composite_score_state_for_run(run)


@pytest.mark.django_db
def test_repeated_closeouts_take_maximum_and_reversal_falls_back(user, seeded):
    partial_sprint, _review = _partial_closeout(user)
    partial_event = CompletionCreditEvent.objects.get(sprint=partial_sprint)
    run = partial_sprint.assessment_run
    competency_id = partial_sprint.protocol.parent_competency_id
    state = CompositeScoreState.objects.get(assessment_run=run)
    partial_priority = Decimal(state.state["competencies"][competency_id]["remaining_priority"])

    full_sprint, _review = _full_closeout(user)
    full_event = CompletionCreditEvent.objects.get(sprint=full_sprint)
    state.refresh_from_db()
    assert full_event.completion_credit == Decimal("1.0000")
    assert state.state["competencies"][competency_id]["completion_credit"] == ("1.000000000000")
    assert Decimal(state.state["competencies"][competency_id]["remaining_priority"]) == 0
    assert state.active_event_count == 2

    weaker_sprint, weaker_review = _partial_closeout(user)
    weaker_event = CompletionCreditEvent.objects.get(sprint=weaker_sprint)
    state.refresh_from_db()
    assert weaker_event.completion_credit == Decimal("0.7500")
    assert state.state["competencies"][competency_id]["completion_credit"] == ("1.000000000000")
    assert Decimal(state.state["competencies"][competency_id]["remaining_priority"]) == 0
    process_count = CompositeScoreSnapshot.objects.filter(
        completion_credit_event=weaker_event,
        operation=CompositeScoreSnapshot.Operation.PROCESS,
    ).count()
    assert create_completion_credit_event(weaker_review).pk == weaker_event.pk
    assert (
        CompositeScoreSnapshot.objects.filter(
            completion_credit_event=weaker_event,
            operation=CompositeScoreSnapshot.Operation.PROCESS,
        ).count()
        == process_count
        == 1
    )

    reverse_completion_credit_event(full_event, reason="Synthetic replay fallback test.")
    state.refresh_from_db()
    assert state.state["competencies"][competency_id]["completion_credit"] == ("0.750000000000")
    assert (
        Decimal(state.state["competencies"][competency_id]["remaining_priority"])
        == partial_priority
    )
    assert state.active_event_count == 2
    assert CompositeScoreSnapshot.objects.filter(
        completion_credit_event=partial_event,
        operation=CompositeScoreSnapshot.Operation.PROCESS,
    ).exists()
    verify_composite_score_state_for_run(run)
    synchronized = synchronize_composite_score_state_for_run(run)
    assert synchronized.events_processed == 0
    assert not synchronized.rebuilt


@pytest.mark.django_db
def test_completion_credit_is_isolated_to_its_assessment_epoch(user, seeded):
    sprint, _review = _partial_closeout(user)
    original = sprint.assessment_run
    other = _clone_epoch_with_baselines(original, stable_id="assessment-epoch-isolation")

    synchronize_composite_score_state_for_run(other)

    competency_id = sprint.protocol.parent_competency_id
    original_state = CompositeScoreState.objects.get(assessment_run=original)
    other_state = CompositeScoreState.objects.get(assessment_run=other)
    assert original_state.state["competencies"][competency_id]["completion_credit"] == (
        "0.750000000000"
    )
    assert other_state.state["competencies"][competency_id]["completion_credit"] == (
        "0.000000000000"
    )
    assert other_state.active_event_count == 0


@pytest.mark.django_db
def test_composite_score_state_management_command_verifies(user, seeded):
    output = StringIO()

    call_command("rebuild_composite_score_state", verify_only=True, stdout=output)

    assert "verification passed for 1 assessment runs" in output.getvalue()


@pytest.mark.django_db
def test_composite_closeout_history_is_immutable_and_tamper_evident(user, seeded):
    sprint, _review = _partial_closeout(user)
    event = CompletionCreditEvent.objects.get(sprint=sprint)
    snapshot = event.score_snapshots.get(operation=CompositeScoreSnapshot.Operation.PROCESS)

    event.completion_credit = Decimal("0.5000")
    with pytest.raises(ValidationError, match="immutable"):
        event.save()
    with pytest.raises(ValidationError, match="immutable"):
        CompletionCreditEvent.objects.filter(pk=event.pk).update(
            completion_credit=Decimal("0.5000")
        )
    with pytest.raises(ValidationError, match="immutable"):
        snapshot.delete()

    CompletionCreditEvent._base_manager.filter(pk=event.pk).update(
        completion_credit=Decimal("0.5000")
    )
    with pytest.raises(CompositeScoreStateError, match="value does not verify"):
        verify_composite_score_state_for_run(sprint.assessment_run)


@pytest.mark.django_db
def test_composite_metadata_repair_is_audited(user, seeded):
    run = user.assessment_runs.get()
    state = CompositeScoreState.objects.get(assessment_run=run)
    before_count = CompositeScoreSnapshot.objects.filter(assessment_run=run).count()
    CompositeScoreState.objects.filter(pk=state.pk).update(state_hash="0" * 64)

    result = synchronize_composite_score_state_for_run(run)

    assert result.rebuilt is True
    assert CompositeScoreSnapshot.objects.filter(assessment_run=run).count() == before_count + 1
    repair = CompositeScoreSnapshot.objects.filter(assessment_run=run).latest("sequence")
    assert repair.operation == CompositeScoreSnapshot.Operation.REBUILD
    assert repair.reason == "Deterministic composite-state metadata repair."
    verify_composite_score_state_for_run(run)


@pytest.mark.django_db
def test_profile_fails_closed_when_composite_state_does_not_verify(user, seeded):
    run = user.assessment_runs.get()
    CompositeScoreState.objects.filter(assessment_run=run).update(state_hash="0" * 64)

    summary = build_profile_summary(user)

    assert summary.composite_state_active is False
    assert summary.dynamic_state_active is False
    assert summary.recommendations == []
    assert summary.recommendation_priorities == {}
    assert "verification must pass" in summary.state_verification_error


@pytest.mark.django_db(transaction=True)
def test_migration_preserves_existing_sprints_as_legacy_and_defaults_new_sprints_to_composite(
    user, seeded
):
    run = user.assessment_runs.get()
    executor = MigrationExecutor(connection)
    original_leaves = executor.loader.graph.leaf_nodes()
    try:
        executor.migrate([("growth", "0011_weeklyexecutionplan_weeklyexecutionreview_and_more")])
        old_apps = executor.loader.project_state(
            [("growth", "0011_weeklyexecutionplan_weeklyexecutionreview_and_more")]
        ).apps
        old_sprint_model = old_apps.get_model("growth", "PracticeSprint")
        old_sprint = old_sprint_model.objects.create(
            user_id=user.pk,
            protocol_id="PRACTICE-FRIENDSHIP-01",
            assessment_run_id=run.pk,
            person_or_context="Pre-migration sprint",
            start_date=date.today(),
            status="stopped",
        )

        executor = MigrationExecutor(connection)
        executor.migrate([("growth", "0012_composite_closeout_scoring")])
        new_apps = executor.loader.project_state(
            [("growth", "0012_composite_closeout_scoring")]
        ).apps
        new_sprint_model = new_apps.get_model("growth", "PracticeSprint")
        assert new_sprint_model.objects.get(pk=old_sprint.pk).scoring_contract_version == (
            "GG-SCORE-STATE-1.0"
        )
        new_sprint = new_sprint_model.objects.create(
            user_id=user.pk,
            protocol_id="PRACTICE-FRIENDSHIP-01",
            assessment_run_id=run.pk,
            person_or_context="Post-migration sprint",
            start_date=date.today(),
            status="stopped",
        )
        assert new_sprint.scoring_contract_version == ALGORITHM_VERSION
    finally:
        MigrationExecutor(connection).migrate(original_leaves)
