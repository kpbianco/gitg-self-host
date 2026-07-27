from datetime import date
from decimal import Decimal

import pytest
from django.urls import reverse

from growth.domain.evidence import EvidenceInput, evaluate_evidence, replay_evidence
from growth.forms import PracticeCheckInForm
from growth.models import EvidenceEvent, PracticeCheckIn, PracticeProtocol, ScoreSnapshot
from growth.services.practice import PracticeWorkflowError, save_check_in, start_practice


def _start_friendship(user):
    return start_practice(
        user=user,
        protocol=PracticeProtocol.objects.get(stable_id="PRACTICE-FRIENDSHIP-01"),
        person_or_context="private label",
        start_date=date.today(),
    )


def _submitted_data(action, **overrides):
    data = {
        "action": action,
        "action_attempted": True,
        "action_completed": False,
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
        "context_comparison": PracticeCheckIn.ContextComparison.FIRST_RECORD,
        "evidence_direction": PracticeCheckIn.EvidenceDirection.SUPPORTS,
        "contradictory_evidence": "",
        "note": "",
    }
    data.update(overrides)
    return data


@pytest.mark.django_db
def test_check_in_form_exposes_action_specific_observation_map(user, seeded):
    sprint = _start_friendship(user)
    actions = list(sprint.protocol.actions.all())
    form = PracticeCheckInForm(sprint=sprint)

    assert form.fields["action"].widget.attrs["data-check-in-action-control"] == "true"
    assert form.action_observation_map[str(actions[0].pk)] == [
        "follow_up_question_asked",
        "meaningful_information_shared",
        "moved_beyond_transactional",
        "user_initiated",
    ]
    assert form.action_observation_map[str(actions[1].pk)] == [
        "future_interaction_scheduled",
        "user_initiated",
    ]
    assert form.action_observation_map[str(actions[2].pk)] == [
        "follow_up_question_asked",
        "follow_up_within_seven_days",
        "meaningful_information_shared",
        "user_initiated",
    ]


@pytest.mark.django_db
def test_submitted_check_in_requires_attempt_and_rejects_other_action_markers(
    user,
    seeded,
):
    sprint = _start_friendship(user)
    action = sprint.protocol.actions.get(sequence=1)
    snapshots_before = ScoreSnapshot.objects.count()

    with pytest.raises(PracticeWorkflowError, match="only after a real attempt"):
        save_check_in(
            sprint=sprint,
            cleaned_data=_submitted_data(
                action,
                action_attempted=False,
                meaningful_information_shared=True,
            ),
            submit=True,
        )

    with pytest.raises(PracticeWorkflowError, match="belong to another action"):
        save_check_in(
            sprint=sprint,
            cleaned_data=_submitted_data(
                action,
                follow_up_within_seven_days=True,
            ),
            submit=True,
        )

    assert not PracticeCheckIn.objects.exists()
    assert not EvidenceEvent.objects.exists()
    assert ScoreSnapshot.objects.count() == snapshots_before


@pytest.mark.django_db
def test_no_attempt_can_remain_a_draft_without_evidence(user, seeded):
    sprint = _start_friendship(user)
    action = sprint.protocol.actions.get(sequence=1)

    draft = save_check_in(
        sprint=sprint,
        cleaned_data=_submitted_data(
            action,
            action_attempted=False,
            support_level="",
            context_comparison="",
            evidence_direction="",
        ),
        submit=False,
    )

    assert draft.status == PracticeCheckIn.Status.DRAFT
    assert draft.action_attempted is False
    assert not EvidenceEvent.objects.exists()


def test_historical_no_attempt_evidence_still_replays_exactly():
    rules = {
        "schema_version": "practice-observation-v1",
        "primary_markers": [
            "moved_beyond_transactional",
            "meaningful_information_shared",
        ],
        "supporting_markers": ["user_initiated", "follow_up_question_asked"],
    }
    historical = evaluate_evidence(
        EvidenceInput(
            protocol_stable_id="PRACTICE-FRIENDSHIP-01",
            action_stable_id="PRACTICE-FRIENDSHIP-01-A1",
            action_attempted=False,
            action_completed=False,
            observations={
                "moved_beyond_transactional": True,
                "meaningful_information_shared": True,
                "user_initiated": True,
                "follow_up_question_asked": False,
            },
            internal_resistance=2,
            expected_reciprocity=3,
            observed_reciprocity=3,
            support_level="independent",
            context_comparison="first_record",
            evidence_direction="supports",
            contradiction_text_present=False,
            repetition_index=1,
        ),
        rules,
    )

    assert historical.performance == Decimal("0.2500")
    assert replay_evidence(historical.input_snapshot) == historical


@pytest.mark.django_db
def test_rendered_check_in_rejects_no_attempt_without_creating_evidence(
    client,
    user,
    seeded,
):
    sprint = _start_friendship(user)
    action = sprint.protocol.actions.get(sequence=1)
    client.force_login(user)
    url = reverse("growth:practice-check-in-new", kwargs={"sprint_id": sprint.pk})

    page = client.get(f"{url}?action={action.pk}")
    content = page.content.decode()
    assert page.status_code == 200
    assert "contextual_forms.js" in content
    assert "check-in-action-observations" in content
    assert f'value="{action.pk}" selected' in content

    response = client.post(
        url,
        {
            "action": action.pk,
            "action_attempted": "",
            "action_completed": "",
            "user_initiated": "on",
            "moved_beyond_transactional": "on",
            "follow_up_question_asked": "",
            "meaningful_information_shared": "on",
            "future_interaction_scheduled": "",
            "follow_up_within_seven_days": "",
            "internal_resistance": "1",
            "expected_reciprocity": "2",
            "observed_reciprocity": "3",
            "support_level": PracticeCheckIn.SupportLevel.INDEPENDENT,
            "context_comparison": PracticeCheckIn.ContextComparison.FIRST_RECORD,
            "evidence_direction": PracticeCheckIn.EvidenceDirection.SUPPORTS,
            "contradictory_evidence": "",
            "note": "",
            "intent": "submit",
        },
    )

    assert response.status_code == 200
    assert "Submit evidence only after a real attempt." in response.content.decode()
    assert not PracticeCheckIn.objects.exists()
    assert not EvidenceEvent.objects.exists()
