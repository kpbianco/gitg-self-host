from datetime import date

import pytest
from django.urls import reverse

from growth.forms import PracticeCheckInForm
from growth.models import EvidenceEvent, LeverState, PracticeProtocol, ScoreSnapshot
from growth.services.practice import completion_evidence, save_check_in, start_practice


def _state(user):
    return list(
        LeverState.objects.filter(user=user)
        .order_by("lever_id")
        .values_list(
            "lever_id",
            "current_estimate",
            "current_confidence",
            "cumulative_evidence_mass",
        )
    )


def _data(action, **overrides):
    data = {
        "action": action,
        "action_attempted": True,
        "action_completed": True,
        "user_initiated": False,
        "moved_beyond_transactional": False,
        "follow_up_question_asked": False,
        "meaningful_information_shared": False,
        "future_interaction_scheduled": False,
        "follow_up_within_seven_days": False,
        "internal_resistance": None,
        "expected_reciprocity": None,
        "observed_reciprocity": None,
        "support_level": "independent",
        "context_comparison": "first_record",
        "evidence_direction": "supports",
        "contradictory_evidence": "",
        "note": "",
    }
    data.update(overrides)
    return data


@pytest.mark.django_db
def test_play_protocol_has_specific_setup_and_compact_check_in(user, seeded):
    protocol = PracticeProtocol.objects.get(stable_id="PRACTICE-PLAY-01")
    sprint = start_practice(
        user=user,
        protocol=protocol,
        person_or_context="tabletop game",
        start_date=date.today(),
    )
    form = PracticeCheckInForm(sprint=sprint)

    assert protocol.parent_competency_id == "26.01"
    assert protocol.actions.count() == 3
    assert form.fields["future_interaction_scheduled"].label == (
        "A specific play window was reserved"
    )
    assert "expected_reciprocity" not in form.fields
    assert "Personally meaningful" not in str(form)


@pytest.mark.django_db
def test_play_pages_render_specific_score_inactive_guidance(client, user, seeded):
    client.force_login(user)
    protocol = PracticeProtocol.objects.get(stable_id="PRACTICE-PLAY-01")

    recommendation = client.get(
        reverse("growth:practice-recommendation", kwargs={"slug": protocol.slug})
    )
    setup = client.get(reverse("growth:practice-setup", kwargs={"slug": protocol.slug, "step": 1}))

    assert recommendation.status_code == 200
    assert "A real activity, not an abstract intention" in recommendation.content.decode()
    assert "Reserve a play window" in recommendation.content.decode()
    assert setup.status_code == 200
    assert "will not change your profile or recommendation" in setup.content.decode()


@pytest.mark.django_db
def test_play_evidence_and_completion_never_change_score_state(user, seeded):
    protocol = PracticeProtocol.objects.get(stable_id="PRACTICE-PLAY-01")
    sprint = start_practice(
        user=user,
        protocol=protocol,
        person_or_context="improvised music",
        start_date=date.today(),
    )
    before = _state(user)
    snapshots_before = ScoreSnapshot.objects.filter(assessment_run=sprint.assessment_run).count()
    actions = list(protocol.actions.all())

    save_check_in(
        sprint=sprint,
        cleaned_data=_data(actions[0], future_interaction_scheduled=True),
        submit=True,
    )
    save_check_in(
        sprint=sprint,
        cleaned_data=_data(
            actions[1],
            context_comparison="same_context",
            moved_beyond_transactional=True,
            meaningful_information_shared=True,
        ),
        submit=True,
    )
    save_check_in(
        sprint=sprint,
        cleaned_data=_data(
            actions[2],
            action_completed=False,
            context_comparison="same_context",
            follow_up_within_seven_days=True,
        ),
        submit=True,
    )

    completion = completion_evidence(sprint)
    assert completion.ready_for_review
    assert EvidenceEvent.objects.filter(check_in__sprint=sprint).count() == 3
    assert ScoreSnapshot.objects.filter(assessment_run=sprint.assessment_run).count() == (
        snapshots_before
    )
    assert _state(user) == before
