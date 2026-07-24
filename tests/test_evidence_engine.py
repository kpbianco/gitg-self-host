import json
from datetime import date
from decimal import Decimal
from io import StringIO

import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from growth.domain.evidence import (
    EVIDENCE_ALGORITHM_VERSION,
    EvidenceContractError,
    EvidenceInput,
    evaluate_evidence,
    repetition_multiplier,
    replay_evidence,
    validate_evidence_rules,
)
from growth.models import (
    EvidenceEvent,
    LeverBaseline,
    PracticeCheckIn,
    PracticeProtocol,
)
from growth.services.canonical_import import seed_canonical_data
from growth.services.evidence import backfill_evidence_events, verify_evidence_event
from growth.services.practice import PracticeWorkflowError, save_check_in, start_practice


def friendship_protocol():
    return PracticeProtocol.objects.get(stable_id="PRACTICE-FRIENDSHIP-01")


def create_sprint(user):
    return start_practice(
        user=user,
        protocol=friendship_protocol(),
        person_or_context="R.",
        start_date=date.today(),
    )


def evidence_data(action, **overrides):
    data = {
        "action": action,
        "action_attempted": True,
        "action_completed": True,
        "user_initiated": True,
        "moved_beyond_transactional": False,
        "follow_up_question_asked": False,
        "meaningful_information_shared": False,
        "future_interaction_scheduled": False,
        "follow_up_within_seven_days": False,
        "internal_resistance": None,
        "expected_reciprocity": None,
        "observed_reciprocity": None,
        "support_level": PracticeCheckIn.SupportLevel.INDEPENDENT,
        "context_comparison": PracticeCheckIn.ContextComparison.FIRST_RECORD,
        "evidence_direction": PracticeCheckIn.EvidenceDirection.SUPPORTS,
        "contradictory_evidence": "",
        "note": "",
    }
    data.update(overrides)
    return data


def baseline_snapshot(user):
    return list(
        LeverBaseline.objects.filter(user=user)
        .order_by("lever_id")
        .values_list(
            "lever_id",
            "raw_self_report",
            "calibrated_estimate",
            "evidence_confidence",
            "need_score",
            "need_rank",
        )
    )


def test_pure_evidence_contract_is_deterministic_and_versioned():
    rules = {
        "schema_version": "practice-observation-v1",
        "primary_markers": ["future_interaction_scheduled"],
        "supporting_markers": ["user_initiated"],
    }
    evidence = EvidenceInput(
        protocol_stable_id="PRACTICE-FRIENDSHIP-01",
        action_stable_id="PRACTICE-FRIENDSHIP-01-A2",
        action_attempted=True,
        action_completed=True,
        observations={
            "future_interaction_scheduled": True,
            "user_initiated": True,
        },
        internal_resistance=2,
        expected_reciprocity=3,
        observed_reciprocity=3,
        support_level="independent",
        context_comparison="first_record",
        evidence_direction="supports",
        contradiction_text_present=False,
        repetition_index=1,
    )

    first = evaluate_evidence(evidence, rules)
    second = evaluate_evidence(evidence, rules)

    assert first == second
    assert first.algorithm_version == EVIDENCE_ALGORITHM_VERSION
    assert first.performance == Decimal("1.0000")
    assert first.quality == Decimal("0.8500")
    assert first.independence == Decimal("1.0000")
    assert first.context_breadth == Decimal("0.5500")
    assert first.repetition_multiplier == Decimal("1.0000")
    assert first.contradiction_level == Decimal("0.0000")
    assert first.base_evidence_mass == Decimal("0.4675")
    assert first.explanation["base_evidence"]["label"] == "Moderate event evidence"
    assert replay_evidence(first.input_snapshot) == first


def test_contract_validates_rules_and_repeat_multipliers():
    assert [repetition_multiplier(index) for index in range(1, 6)] == [
        Decimal("1.00"),
        Decimal("0.65"),
        Decimal("0.40"),
        Decimal("0.25"),
        Decimal("0.25"),
    ]
    with pytest.raises(EvidenceContractError, match="at least one"):
        repetition_multiplier(0)
    with pytest.raises(EvidenceContractError, match="unknown observation"):
        validate_evidence_rules(
            {
                "schema_version": "practice-observation-v1",
                "primary_markers": ["invented_field"],
                "supporting_markers": ["user_initiated"],
            }
        )
    with pytest.raises(EvidenceContractError, match="overlap"):
        validate_evidence_rules(
            {
                "schema_version": "practice-observation-v1",
                "primary_markers": ["user_initiated"],
                "supporting_markers": ["user_initiated"],
            }
        )


def test_clear_contradictory_attempt_can_be_high_quality_without_completion():
    result = evaluate_evidence(
        EvidenceInput(
            protocol_stable_id="PRACTICE-FRIENDSHIP-01",
            action_stable_id="PRACTICE-FRIENDSHIP-01-A2",
            action_attempted=True,
            action_completed=False,
            observations={},
            internal_resistance=3,
            expected_reciprocity=None,
            observed_reciprocity=None,
            support_level="independent",
            context_comparison="first_record",
            evidence_direction="contradicts",
            contradiction_text_present=True,
            repetition_index=1,
        ),
        {
            "schema_version": "practice-observation-v1",
            "primary_markers": ["future_interaction_scheduled"],
            "supporting_markers": ["user_initiated"],
        },
    )

    assert result.performance == Decimal("0.3500")
    assert result.quality == Decimal("0.8500")
    assert result.contradiction_level == Decimal("1.0000")


@pytest.mark.django_db
def test_draft_has_no_event_and_submission_creates_immutable_event(user, seeded):
    sprint = create_sprint(user)
    action = sprint.protocol.actions.get(sequence=1)
    before = baseline_snapshot(user)

    draft = save_check_in(
        sprint=sprint,
        cleaned_data=evidence_data(
            action,
            support_level="",
            context_comparison="",
            evidence_direction="",
            note="private details must not enter the event snapshot",
        ),
        submit=False,
    )
    assert draft.status == PracticeCheckIn.Status.DRAFT
    assert not EvidenceEvent.objects.exists()

    event_source = save_check_in(
        sprint=sprint,
        existing=draft,
        cleaned_data=evidence_data(
            action,
            moved_beyond_transactional=True,
            meaningful_information_shared=True,
            note="private details must not enter the event snapshot",
        ),
        submit=True,
    )
    event = event_source.evidence_event

    assert event.algorithm_version == EVIDENCE_ALGORITHM_VERSION
    assert event.repetition_index == 1
    assert event.protocol_stable_id == sprint.protocol_id
    assert event.action_stable_id == action.pk
    assert "note" not in event.input_snapshot
    assert "contradictory_evidence" not in event.input_snapshot
    assert "private details" not in json.dumps(event.input_snapshot)
    verify_evidence_event(event)
    assert baseline_snapshot(user) == before

    seed_canonical_data()
    event.refresh_from_db()
    assert EvidenceEvent.objects.count() == 1
    verify_evidence_event(event)

    event.quality = Decimal("0.1000")
    with pytest.raises(ValidationError, match="immutable"):
        event.save()
    with pytest.raises(ValidationError, match="immutable"):
        EvidenceEvent.objects.filter(pk=event.pk).update(quality=Decimal("0.1000"))
    with pytest.raises(ValidationError, match="immutable"):
        PracticeCheckIn.objects.filter(pk=event_source.pk).update(note="changed")


@pytest.mark.django_db
def test_submission_requires_metadata_and_preserves_contradiction(user, seeded):
    sprint = create_sprint(user)
    action = sprint.protocol.actions.get(sequence=1)

    with pytest.raises(PracticeWorkflowError, match="requires"):
        save_check_in(
            sprint=sprint,
            cleaned_data=evidence_data(
                action,
                support_level="",
                context_comparison="",
                evidence_direction="",
            ),
            submit=True,
        )
    with pytest.raises(PracticeWorkflowError, match="brief explanation"):
        save_check_in(
            sprint=sprint,
            cleaned_data=evidence_data(
                action,
                evidence_direction=PracticeCheckIn.EvidenceDirection.MIXED,
            ),
            submit=True,
        )

    check_in = save_check_in(
        sprint=sprint,
        cleaned_data=evidence_data(
            action,
            evidence_direction=PracticeCheckIn.EvidenceDirection.CONTRADICTS,
            contradictory_evidence="The invitation was clearly unwelcome.",
        ),
        submit=True,
    )
    assert check_in.evidence_event.contradiction_level == Decimal("1.0000")
    assert (
        check_in.evidence_event.explanation["direction"]["label"]
        == "Contradicted the expected pattern"
    )


@pytest.mark.django_db
def test_context_comparison_tracks_submission_order(user, seeded):
    sprint = create_sprint(user)
    first_action = sprint.protocol.actions.get(sequence=1)
    second_action = sprint.protocol.actions.get(sequence=2)

    with pytest.raises(PracticeWorkflowError, match="first submitted"):
        save_check_in(
            sprint=sprint,
            cleaned_data=evidence_data(
                first_action,
                context_comparison=PracticeCheckIn.ContextComparison.SAME_CONTEXT,
            ),
            submit=True,
        )
    save_check_in(
        sprint=sprint,
        cleaned_data=evidence_data(first_action),
        submit=True,
    )
    with pytest.raises(PracticeWorkflowError, match="only available"):
        save_check_in(
            sprint=sprint,
            cleaned_data=evidence_data(second_action),
            submit=True,
        )


@pytest.mark.django_db
def test_repetition_is_action_specific_and_context_is_bounded(user, seeded):
    sprint = create_sprint(user)
    first_action = sprint.protocol.actions.get(sequence=1)
    second_action = sprint.protocol.actions.get(sequence=2)

    first = save_check_in(
        sprint=sprint,
        cleaned_data=evidence_data(first_action),
        submit=True,
    )
    repeat = save_check_in(
        sprint=sprint,
        cleaned_data=evidence_data(
            first_action,
            context_comparison=PracticeCheckIn.ContextComparison.VARIED_CONTEXT,
        ),
        submit=True,
    )
    different_action = save_check_in(
        sprint=sprint,
        cleaned_data=evidence_data(
            second_action,
            context_comparison=PracticeCheckIn.ContextComparison.SAME_CONTEXT,
            future_interaction_scheduled=True,
        ),
        submit=True,
    )

    assert first.evidence_event.repetition_index == 1
    assert repeat.evidence_event.repetition_index == 2
    assert repeat.evidence_event.repetition_multiplier == Decimal("0.6500")
    assert repeat.evidence_event.context_breadth == Decimal("0.7500")
    assert different_action.evidence_event.repetition_index == 1


@pytest.mark.django_db
def test_existing_m1_submissions_backfill_conservatively_and_idempotently(user, seeded):
    sprint = create_sprint(user)
    action = sprint.protocol.actions.get(sequence=1)
    first = PracticeCheckIn.objects.create(
        sprint=sprint,
        action=action,
        status=PracticeCheckIn.Status.SUBMITTED,
        action_attempted=True,
        submitted_at=timezone.now(),
    )
    second = PracticeCheckIn.objects.create(
        sprint=sprint,
        action=action,
        status=PracticeCheckIn.Status.SUBMITTED,
        action_attempted=True,
        contradictory_evidence="Existing free-text contradiction.",
        submitted_at=timezone.now(),
    )

    dry_run_output = StringIO()
    call_command("backfill_evidence_events", dry_run=True, stdout=dry_run_output)
    assert "2 would be created" in dry_run_output.getvalue()
    assert not EvidenceEvent.objects.exists()

    first_run = backfill_evidence_events()
    second_run = backfill_evidence_events()

    assert first_run.events_created == 2
    assert second_run.events_created == 0
    assert second_run.events_already_present == 2
    assert first.evidence_event.independence == Decimal("0.7000")
    assert first.evidence_event.context_breadth == Decimal("0.5500")
    assert first.evidence_event.contradiction_level is None
    assert second.evidence_event.contradiction_level == Decimal("0.5000")
    assert second.evidence_event.repetition_index == 2

    output = StringIO()
    call_command("backfill_evidence_events", stdout=output)
    assert "0 created, 2 already present" in output.getvalue()


@pytest.mark.django_db
def test_evidence_detail_is_authenticated_private_and_plain_language(client, user, seeded):
    sprint = create_sprint(user)
    action = sprint.protocol.actions.get(sequence=2)
    check_in = save_check_in(
        sprint=sprint,
        cleaned_data=evidence_data(
            action,
            future_interaction_scheduled=True,
        ),
        submit=True,
    )
    url = reverse(
        "growth:practice-check-in-detail",
        kwargs={"sprint_id": sprint.pk, "check_in_id": check_in.pk},
    )

    anonymous = client.get(url)
    assert anonymous.status_code == 302

    client.force_login(user)
    page = client.get(url)
    assert page.status_code == 200
    assert "Your developmental profile is unchanged." in page.content.decode()
    assert "does not establish mastery" in page.content.decode()
    assert "GG-EVIDENCE-1.0" in page.content.decode()
    assert "does not allocate" in page.content.decode()
    assert "this event to levers" in page.content.decode()
