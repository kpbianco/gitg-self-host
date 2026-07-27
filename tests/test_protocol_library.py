from datetime import date

import pytest
from django.urls import reverse

from growth.forms import PracticeCheckInForm
from growth.models import (
    EvidenceEvent,
    LeverState,
    PracticeProtocol,
    PracticeSprint,
    ScoreSnapshot,
)
from growth.services.practice import (
    complete_with_review,
    completion_evidence,
    save_check_in,
    start_practice,
)


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


@pytest.mark.django_db
def test_emotional_cues_protocol_is_specific_and_rejects_mind_reading(client, user, seeded):
    client.force_login(user)
    protocol = PracticeProtocol.objects.get(stable_id="PRACTICE-EMOTIONAL-CUES-01")
    recommendation = client.get(
        reverse("growth:practice-recommendation", kwargs={"slug": protocol.slug})
    )
    setup = client.get(reverse("growth:practice-setup", kwargs={"slug": protocol.slug, "step": 1}))
    sprint = start_practice(
        user=user,
        protocol=protocol,
        person_or_context="weekly project sync",
        start_date=date.today(),
    )
    form = PracticeCheckInForm(sprint=sprint)

    assert protocol.parent_competency_id == "16.03"
    assert protocol.score_active is False
    assert protocol.actions.count() == 3
    assert "Observation is not mind-reading" in protocol.setup_copy["boundary_heading"]
    assert "Culture, disability, neurotype" in protocol.privacy_and_boundaries
    assert "A checkable interaction, not a personality judgment" in (
        recommendation.content.decode()
    )
    assert "Notice before interpreting" in recommendation.content.decode()
    assert "will not change your profile or recommendation" in setup.content.decode()
    assert form.fields["follow_up_question_asked"].label == (
        "I asked a neutral question to check my impression"
    )
    assert "expected_reciprocity" not in form.fields
    assert "future_interaction_scheduled" not in form.fields


@pytest.mark.django_db
def test_emotional_cues_evidence_completes_without_score_mutation(user, seeded):
    protocol = PracticeProtocol.objects.get(stable_id="PRACTICE-EMOTIONAL-CUES-01")
    sprint = start_practice(
        user=user,
        protocol=protocol,
        person_or_context="weekly project sync",
        start_date=date.today(),
    )
    before = _state(user)
    snapshots_before = ScoreSnapshot.objects.filter(assessment_run=sprint.assessment_run).count()
    actions = list(protocol.actions.all())

    save_check_in(
        sprint=sprint,
        cleaned_data=_data(
            actions[0],
            user_initiated=True,
            moved_beyond_transactional=True,
        ),
        submit=True,
    )
    save_check_in(
        sprint=sprint,
        cleaned_data=_data(
            actions[1],
            context_comparison="same_context",
            user_initiated=True,
        ),
        submit=True,
    )
    save_check_in(
        sprint=sprint,
        cleaned_data=_data(
            actions[2],
            action_completed=False,
            context_comparison="varied_context",
            meaningful_information_shared=True,
            follow_up_within_seven_days=True,
        ),
        submit=True,
    )
    assert not completion_evidence(sprint).ready_for_review
    save_check_in(
        sprint=sprint,
        cleaned_data=_data(
            actions[2],
            action_completed=False,
            context_comparison="same_context",
            follow_up_question_asked=True,
        ),
        submit=True,
    )

    completion = completion_evidence(sprint)
    assert completion.ready_for_review
    review = complete_with_review(
        sprint=sprint,
        reflection="Direct clarification corrected part of my first impression.",
        contradictory_evidence="Tone alone was not enough to infer emotion.",
    )
    sprint.refresh_from_db()
    assert EvidenceEvent.objects.filter(check_in__sprint=sprint).count() == 4
    assert sprint.status == PracticeSprint.Status.COMPLETED
    assert review.static_score_impact_preview == {}
    assert review.sprint.protocol.mastery_disclaimer == (
        "Completing this practice does not establish mastery."
    )
    assert ScoreSnapshot.objects.filter(assessment_run=sprint.assessment_run).count() == (
        snapshots_before
    )
    assert _state(user) == before
