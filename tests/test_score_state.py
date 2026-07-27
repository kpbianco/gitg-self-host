from datetime import date
from decimal import Decimal
from io import StringIO

import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.models.deletion import ProtectedError
from django.utils import timezone

from growth.domain.ranking import (
    ProtocolWeight,
    RankingContractError,
    protocol_priority,
    provisional_need_score,
)
from growth.models import (
    Competency,
    EvidenceEvent,
    LeverBaseline,
    LeverState,
    PracticeCheckIn,
    PracticeProtocol,
    ScoreSnapshot,
)
from growth.services.canonical_import import seed_canonical_data
from growth.services.evidence import create_evidence_event
from growth.services.practice import (
    PracticeWorkflowError,
    save_check_in,
    start_practice,
)
from growth.services.profile import build_profile_summary
from growth.services.score_state import (
    ScoreStateError,
    apply_evidence_event,
    reverse_evidence_event,
    synchronize_score_state_for_run,
    verify_score_state_for_run,
)


def _check_in_data(action, **overrides):
    data = {
        "action": action,
        "action_attempted": True,
        "action_completed": True,
        "user_initiated": True,
        "moved_beyond_transactional": True,
        "follow_up_question_asked": True,
        "meaningful_information_shared": True,
        "future_interaction_scheduled": False,
        "follow_up_within_seven_days": False,
        "internal_resistance": 2,
        "expected_reciprocity": 2,
        "observed_reciprocity": 3,
        "support_level": PracticeCheckIn.SupportLevel.INDEPENDENT,
        "context_comparison": PracticeCheckIn.ContextComparison.FIRST_RECORD,
        "evidence_direction": PracticeCheckIn.EvidenceDirection.SUPPORTS,
        "contradictory_evidence": "",
        "note": "",
    }
    data.update(overrides)
    return data


def _sprint(user):
    protocol = PracticeProtocol.objects.get(stable_id="PRACTICE-FRIENDSHIP-01")
    return start_practice(
        user=user,
        protocol=protocol,
        person_or_context="Private context",
        start_date=date.today(),
    )


def _state_values(user):
    return list(
        LeverState.objects.filter(user=user)
        .order_by("assessment_run_id", "lever_id")
        .values_list(
            "assessment_run_id",
            "lever_id",
            "status",
            "current_alpha",
            "current_beta",
            "current_estimate",
            "current_confidence",
            "cumulative_evidence_mass",
            "included_evidence_events",
            "current_need_score",
            "current_need_rank",
        )
    )


@pytest.mark.django_db
def test_v11_provisional_need_reproduces_seeded_scores_and_ranks(user, seeded):
    baselines = list(LeverBaseline.objects.filter(user=user).select_related("current_state"))

    assert len(baselines) == 37
    for baseline in baselines:
        state = baseline.current_state
        assert (
            provisional_need_score(
                baseline.calibrated_estimate,
                baseline.evidence_confidence,
            )
            == baseline.need_score
        )
        assert state.current_need_score == baseline.need_score
        assert state.current_need_rank == baseline.need_rank


@pytest.mark.django_db
def test_initialization_is_separate_idempotent_and_marks_unavailable_mass(user, seeded):
    run = user.assessment_runs.get()
    states = LeverState.objects.filter(assessment_run=run)
    unavailable = set(
        states.filter(status=LeverState.Status.BASELINE_ONLY).values_list(
            "lever_id",
            flat=True,
        )
    )
    initialization = ScoreSnapshot.objects.get(
        assessment_run=run,
        operation=ScoreSnapshot.Operation.INITIALIZE,
    )
    before = _state_values(user)

    result = synchronize_score_state_for_run(run)

    assert states.count() == 37
    assert unavailable == {"L06", "L15", "L32", "L37"}
    assert initialization.before_state == []
    assert len(initialization.after_state) == 37
    assert initialization.contribution_snapshot["baseline_only_levers"] == sorted(unavailable)
    assert result.initialized is False
    assert result.events_processed == 0
    assert result.rebuilt is False
    assert ScoreSnapshot.objects.filter(assessment_run=run).count() == 1
    assert _state_values(user) == before


@pytest.mark.django_db
def test_submitted_event_applies_atomically_once_and_keeps_baseline_immutable(user, seeded):
    sprint = _sprint(user)
    action = sprint.protocol.actions.get(sequence=1)
    baseline_before = list(
        LeverBaseline.objects.filter(user=user)
        .order_by("lever_id")
        .values_list(
            "lever_id",
            "calibrated_estimate",
            "evidence_confidence",
            "need_score",
            "need_rank",
        )
    )
    orientations_before = list(
        sprint.assessment_run.orientation_results.order_by("stable_id").values_list(
            "stable_id",
            "score",
            "confidence",
        )
    )
    archetypes_before = list(
        sprint.assessment_run.archetype_results.order_by("stable_id").values_list(
            "stable_id",
            "fit_index",
            "fit_confidence",
            "rank",
        )
    )
    state_before = LeverState.objects.get(user=user, lever_id="L26")

    check_in = save_check_in(
        sprint=sprint,
        cleaned_data=_check_in_data(action),
        submit=True,
    )
    event = check_in.evidence_event
    snapshot = ScoreSnapshot.objects.get(
        evidence_event=event,
        operation=ScoreSnapshot.Operation.PROCESS,
    )
    state_after = LeverState.objects.get(user=user, lever_id="L26")
    count_before_repeat = ScoreSnapshot.objects.count()

    repeated = apply_evidence_event(event)

    assert repeated.pk == snapshot.pk
    assert ScoreSnapshot.objects.count() == count_before_repeat
    assert snapshot.sequence == 2
    assert snapshot.before_state != snapshot.after_state
    assert snapshot.contribution_snapshot["direction"] == "supports"
    assert all(row["included"] is True for row in snapshot.contribution_snapshot["levers"])
    assert state_after.current_estimate > state_before.current_estimate
    assert state_after.current_confidence >= state_before.current_confidence
    assert state_after.cumulative_evidence_mass > 0
    assert state_after.included_evidence_events == 1
    assert (
        list(
            LeverBaseline.objects.filter(user=user)
            .order_by("lever_id")
            .values_list(
                "lever_id",
                "calibrated_estimate",
                "evidence_confidence",
                "need_score",
                "need_rank",
            )
        )
        == baseline_before
    )
    assert (
        list(
            sprint.assessment_run.orientation_results.order_by("stable_id").values_list(
                "stable_id",
                "score",
                "confidence",
            )
        )
        == orientations_before
    )
    assert (
        list(
            sprint.assessment_run.archetype_results.order_by("stable_id").values_list(
                "stable_id",
                "fit_index",
                "fit_confidence",
                "rank",
            )
        )
        == archetypes_before
    )
    verify_score_state_for_run(sprint.assessment_run)


@pytest.mark.django_db
def test_inconclusive_event_is_processed_but_withheld_from_current_state(user, seeded):
    sprint = _sprint(user)
    action = sprint.protocol.actions.get(sequence=1)
    before = _state_values(user)

    check_in = save_check_in(
        sprint=sprint,
        cleaned_data=_check_in_data(
            action,
            evidence_direction=PracticeCheckIn.EvidenceDirection.INCONCLUSIVE,
        ),
        submit=True,
    )
    snapshot = ScoreSnapshot.objects.get(
        evidence_event=check_in.evidence_event,
        operation=ScoreSnapshot.Operation.PROCESS,
    )

    assert snapshot.before_state == snapshot.after_state
    assert snapshot.active_event_count == 1
    assert all(row["included"] is False for row in snapshot.contribution_snapshot["levers"])
    assert _state_values(user) == before


@pytest.mark.django_db
def test_reversal_is_audited_idempotent_and_rebuild_repairs_drift(user, seeded):
    sprint = _sprint(user)
    action = sprint.protocol.actions.get(sequence=1)
    baseline_state = _state_values(user)
    check_in = save_check_in(
        sprint=sprint,
        cleaned_data=_check_in_data(action),
        submit=True,
    )
    event = check_in.evidence_event

    reversal = reverse_evidence_event(
        event,
        reason="Synthetic test correction.",
    )
    repeated = reverse_evidence_event(
        event,
        reason="A repeated command does not rewrite the audit reason.",
    )

    assert repeated.pk == reversal.pk
    assert reversal.reason == "Synthetic test correction."
    assert reversal.before_state != reversal.after_state
    assert _state_values(user) == baseline_state
    assert (
        ScoreSnapshot.objects.filter(
            evidence_event=event,
            operation=ScoreSnapshot.Operation.REVERSE,
        ).count()
        == 1
    )

    LeverState.objects.filter(
        assessment_run=sprint.assessment_run,
        lever_id="L26",
    ).update(current_estimate=Decimal("0.9999"))
    with pytest.raises(ScoreStateError, match="deterministic event replay"):
        verify_score_state_for_run(sprint.assessment_run)

    repaired = synchronize_score_state_for_run(sprint.assessment_run)

    assert repaired.rebuilt is True
    assert (
        ScoreSnapshot.objects.filter(
            assessment_run=sprint.assessment_run,
            operation=ScoreSnapshot.Operation.REBUILD,
        ).count()
        == 1
    )
    assert _state_values(user) == baseline_state
    verify_score_state_for_run(sprint.assessment_run)


@pytest.mark.django_db
def test_snapshots_and_applied_events_are_protected_from_mutation(user, seeded):
    sprint = _sprint(user)
    check_in = save_check_in(
        sprint=sprint,
        cleaned_data=_check_in_data(sprint.protocol.actions.get(sequence=1)),
        submit=True,
    )
    event = check_in.evidence_event
    snapshot = event.score_snapshots.get(operation=ScoreSnapshot.Operation.PROCESS)

    snapshot.reason = "changed"
    with pytest.raises(ValidationError, match="immutable"):
        snapshot.save()
    with pytest.raises(ValidationError, match="immutable"):
        ScoreSnapshot.objects.filter(pk=snapshot.pk).update(reason="changed")
    with pytest.raises(ValidationError, match="immutable"):
        ScoreSnapshot.objects.filter(pk=snapshot.pk).delete()
    with pytest.raises(ProtectedError):
        event.delete()


@pytest.mark.django_db
def test_unidentifiable_required_baseline_rolls_back_submission(user, seeded):
    run = user.assessment_runs.get()
    baseline = LeverBaseline.objects.get(assessment_run=run, lever_id="L26")
    LeverBaseline.objects.filter(pk=baseline.pk).update(
        raw_self_report=Decimal("0.5000"),
        calibrated_estimate=Decimal("0.5000"),
        baseline_alpha=None,
        baseline_beta=None,
        baseline_mass_source="",
    )
    LeverState.objects.filter(assessment_run=run, lever_id="L26").update(
        status=LeverState.Status.BASELINE_ONLY,
        current_alpha=None,
        current_beta=None,
        current_estimate=Decimal("0.5000"),
    )
    sprint = _sprint(user)

    with pytest.raises(PracticeWorkflowError, match="baseline mass is unavailable"):
        save_check_in(
            sprint=sprint,
            cleaned_data=_check_in_data(
                sprint.protocol.actions.get(sequence=1),
            ),
            submit=True,
        )

    assert PracticeCheckIn.objects.filter(sprint=sprint).count() == 0
    assert EvidenceEvent.objects.filter(check_in__sprint=sprint).count() == 0
    assert ScoreSnapshot.objects.filter(assessment_run=run).count() == 1


def test_protocol_priority_is_weighted_versioned_and_fails_closed():
    needs = {
        "L01": Decimal("0.8000"),
        "L02": Decimal("0.2000"),
    }

    assert protocol_priority(
        needs,
        (
            ProtocolWeight("L01", Decimal("0.7500")),
            ProtocolWeight("L02", Decimal("0.2500")),
        ),
    ) == Decimal("0.6500")

    with pytest.raises(RankingContractError, match="sum to"):
        protocol_priority(
            needs,
            (ProtocolWeight("L01", Decimal("0.9000")),),
        )
    with pytest.raises(RankingContractError, match="unavailable"):
        protocol_priority(
            needs,
            (ProtocolWeight("L03", Decimal("1.0000")),),
        )


@pytest.mark.django_db
def test_active_protocol_order_tracks_current_need_and_reversal(user, seeded):
    PracticeProtocol.objects.filter(stable_id="PRACTICE-PLAY-01").update(
        availability=PracticeProtocol.Availability.INACTIVE
    )

    def needs():
        return {
            state.lever_id: state.current_need_score
            for state in LeverState.objects.filter(user=user)
        }

    def competency_priority(competency, current_needs):
        return protocol_priority(
            current_needs,
            (ProtocolWeight(link.lever_id, link.weight) for link in competency.lever_links.all()),
        )

    friendship = PracticeProtocol.objects.get(stable_id="PRACTICE-FRIENDSHIP-01")
    friendship_competency = friendship.parent_competency
    baseline_needs = needs()
    friendship_before = competency_priority(friendship_competency, baseline_needs)
    sprint = _sprint(user)
    check_in = save_check_in(
        sprint=sprint,
        cleaned_data=_check_in_data(sprint.protocol.actions.get(sequence=1)),
        submit=True,
    )
    updated_needs = needs()
    friendship_after = competency_priority(friendship_competency, updated_needs)

    competitor = None
    for competency in Competency.objects.exclude(
        stable_id=friendship_competency.pk
    ).prefetch_related("lever_links"):
        before = competency_priority(competency, baseline_needs)
        after = competency_priority(competency, updated_needs)
        if friendship_before > before and friendship_after < after:
            competitor = competency
            break
    assert competitor is not None, "Synthetic ranking fixture requires a priority crossover."

    protocol = PracticeProtocol.objects.create(
        stable_id="TEST-DYNAMIC-RANK-PROTOCOL",
        slug="test-dynamic-rank-protocol",
        name="Synthetic Dynamic Ranking Protocol",
        parent_competency=competitor,
        availability=PracticeProtocol.Availability.ACTIVE,
        duration_days=7,
        recommendation_reason="Synthetic ranking verification.",
        applicability_prompt="Synthetic ranking verification.",
        setup_prompt="Synthetic ranking verification.",
        privacy_and_boundaries="Synthetic ranking verification.",
        completion_criteria=[],
        display_order=99,
    )
    protocol.target_levers.add(competitor.lever_links.first().lever)

    after_summary = build_profile_summary(user)
    assert after_summary.recommendations[0] == protocol
    assert (
        after_summary.recommendation_priorities[protocol.stable_id]
        > after_summary.recommendation_priorities[friendship.stable_id]
    )

    reverse_evidence_event(
        check_in.evidence_event,
        reason="Return synthetic ranking test to its baseline.",
    )
    baseline_summary = build_profile_summary(user)
    assert baseline_summary.recommendations[0] == friendship
    assert (
        baseline_summary.recommendation_priorities[friendship.stable_id]
        > baseline_summary.recommendation_priorities[protocol.stable_id]
    )


@pytest.mark.django_db
def test_score_state_management_command_verifies_and_repairs(user, seeded):
    verified = StringIO()
    call_command("rebuild_score_state", verify_only=True, stdout=verified)
    assert "verification passed for 1 assessment runs" in verified.getvalue()

    LeverState.objects.filter(user=user, lever_id="L26").update(
        current_confidence=Decimal("0.9999")
    )
    with pytest.raises(CommandError, match="deterministic event replay"):
        call_command("rebuild_score_state", verify_only=True)

    repaired = StringIO()
    call_command("rebuild_score_state", stdout=repaired)
    assert "1 repairs" in repaired.getvalue()
    call_command("rebuild_score_state", verify_only=True)


@pytest.mark.django_db
def test_upgrade_rebuild_initializes_and_processes_existing_event(user):
    seed_canonical_data()
    run = user.assessment_runs.get()
    protocol = PracticeProtocol.objects.get(stable_id="PRACTICE-FRIENDSHIP-01")
    sprint = start_practice(
        user=user,
        protocol=protocol,
        person_or_context="Pre-M3B context",
        start_date=date.today(),
    )
    check_in = PracticeCheckIn.objects.create(
        sprint=sprint,
        action=protocol.actions.get(sequence=1),
        status=PracticeCheckIn.Status.SUBMITTED,
        action_attempted=True,
        action_completed=True,
        moved_beyond_transactional=True,
        meaningful_information_shared=True,
        support_level=PracticeCheckIn.SupportLevel.INDEPENDENT,
        context_comparison=PracticeCheckIn.ContextComparison.FIRST_RECORD,
        evidence_direction=PracticeCheckIn.EvidenceDirection.SUPPORTS,
        submitted_at=timezone.now(),
    )
    event = create_evidence_event(check_in)
    assert not LeverState.objects.filter(assessment_run=run).exists()

    result = synchronize_score_state_for_run(run)

    assert result.initialized is True
    assert result.events_processed == 1
    assert LeverState.objects.filter(assessment_run=run).count() == 37
    assert ScoreSnapshot.objects.filter(assessment_run=run).count() == 2
    assert ScoreSnapshot.objects.filter(
        evidence_event=event,
        operation=ScoreSnapshot.Operation.PROCESS,
    ).exists()
    assert (
        LeverState.objects.get(
            assessment_run=run,
            lever_id="L26",
        ).cumulative_evidence_mass
        > 0
    )
