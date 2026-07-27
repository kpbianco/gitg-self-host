from datetime import date

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.urls import reverse

from growth.models import (
    LeverBaseline,
    PracticeCheckIn,
    PracticeProtocol,
    PracticeSprint,
)
from growth.services.practice import (
    PracticeWorkflowError,
    completion_evidence,
    start_practice,
    transition_sprint,
)
from growth.services.scoring import build_user_shadow_projection


def friendship_protocol():
    return PracticeProtocol.objects.get(stable_id="PRACTICE-FRIENDSHIP-01")


def create_sprint(user):
    return start_practice(
        user=user,
        protocol=friendship_protocol(),
        person_or_context="R.",
        start_date=date.today(),
    )


def check_in_post(action, **overrides):
    data = {
        "action": action.pk,
        "action_attempted": "on",
        "action_completed": "",
        "user_initiated": "",
        "moved_beyond_transactional": "",
        "follow_up_question_asked": "",
        "meaningful_information_shared": "",
        "future_interaction_scheduled": "",
        "follow_up_within_seven_days": "",
        "internal_resistance": "",
        "expected_reciprocity": "",
        "observed_reciprocity": "",
        "support_level": "independent",
        "context_comparison": "first_record",
        "evidence_direction": "supports",
        "contradictory_evidence": "",
        "note": "",
    }
    data.update(overrides)
    return data


@pytest.mark.django_db
def test_first_practice_explains_recommendation_and_defines_intervention(client, user, seeded):
    client.force_login(user)
    protocol = friendship_protocol()

    response = client.get(reverse("growth:practice-recommendation", kwargs={"slug": protocol.slug}))
    assert response.status_code == 200
    assert b"Why this was selected" in response.content
    assert b"friendship, belonging, and hospitality" in response.content
    assert b"You will not need to invent the practice" in response.content
    assert b"Spend at least ten minutes primarily listening" in response.content
    assert b"Propose a specific shared activity and date" in response.content
    assert b"Within seven days" in response.content


@pytest.mark.django_db
def test_seven_step_setup_starts_practice_without_inventing_intervention(client, user, seeded):
    client.force_login(user)
    protocol = friendship_protocol()
    setup_url = lambda step: reverse(  # noqa: E731
        "growth:practice-setup",
        kwargs={"slug": protocol.slug, "step": step},
    )

    first = client.get(setup_url(1))
    assert first.status_code == 200
    assert b"Why this practice" in first.content
    assert b"Static-score boundary" in first.content
    assert client.post(setup_url(1)).status_code == 302

    applicable = client.get(setup_url(2))
    assert b"Is this applicable now" in applicable.content
    assert client.post(setup_url(2), {"applicable": "yes"}).status_code == 302

    context = client.get(setup_url(3))
    assert b"Choose one existing relationship" in context.content
    assert client.post(setup_url(3), {"person_or_context": "Initials only"}).status_code == 302

    boundaries = client.get(setup_url(4))
    assert b"Privacy and interpersonal boundaries" in boundaries.content
    assert client.post(setup_url(4), {"boundaries_acknowledged": "on"}).status_code == 302

    assert client.post(setup_url(5), {"start_date": date.today().isoformat()}).status_code == 302
    actions = client.get(setup_url(6))
    assert b"Three actions, already defined" in actions.content
    assert b"Spend at least ten minutes primarily listening" in actions.content
    assert client.post(setup_url(6)).status_code == 302

    ready = client.get(setup_url(7))
    assert b"Your 14-day practice is prepared" in ready.content
    started = client.post(setup_url(7))
    sprint = PracticeSprint.objects.get(user=user)
    assert started.status_code == 302
    assert started.url == reverse("growth:practice-sprint", kwargs={"sprint_id": sprint.pk})
    assert sprint.status == PracticeSprint.Status.ACTIVE
    assert sprint.person_or_context == "Initials only"
    assert sprint.boundaries_acknowledged_at is not None


@pytest.mark.django_db
def test_not_applicable_setup_exits_without_creating_sprint(client, user, seeded):
    client.force_login(user)
    protocol = friendship_protocol()
    setup_url = lambda step: reverse(  # noqa: E731
        "growth:practice-setup",
        kwargs={"slug": protocol.slug, "step": step},
    )
    client.post(setup_url(1))
    response = client.post(setup_url(2), {"applicable": "no"}, follow=True)
    assert response.status_code == 200
    assert b"This practice can wait until it fits" in response.content
    assert not PracticeSprint.objects.exists()


@pytest.mark.django_db
def test_draft_remains_outside_evidence_and_submission_appears_in_history(client, user, seeded):
    client.force_login(user)
    sprint = create_sprint(user)
    actions = list(sprint.protocol.actions.all())
    new_url = reverse("growth:practice-check-in-new", kwargs={"sprint_id": sprint.pk})

    draft_data = check_in_post(actions[0], note="private draft")
    draft_data["intent"] = "draft"
    response = client.post(new_url, draft_data)
    assert response.status_code == 302
    draft = PracticeCheckIn.objects.get()
    assert draft.status == PracticeCheckIn.Status.DRAFT
    assert draft.submitted_at is None
    assert completion_evidence(sprint).actions_attempted == 0

    sprint_page = client.get(reverse("growth:practice-sprint", kwargs={"sprint_id": sprint.pk}))
    assert b"Draft check-ins" in sprint_page.content
    assert b"Drafts are not submitted evidence" in sprint_page.content

    submitted_data = check_in_post(
        actions[1],
        action_completed="on",
        future_interaction_scheduled="on",
    )
    submitted_data["intent"] = "submit"
    response = client.post(new_url, submitted_data)
    assert response.status_code == 302
    submitted = PracticeCheckIn.objects.get(status=PracticeCheckIn.Status.SUBMITTED)
    assert submitted.submitted_at is not None

    home = client.get(reverse("growth:home"))
    assert actions[1].title.encode() in home.content
    assert b"Recent submitted check-ins" in home.content

    submitted.note = "cannot edit"
    with pytest.raises(ValidationError, match="immutable"):
        submitted.save()


@pytest.mark.django_db
def test_practice_can_pause_resume_and_stop(client, user, seeded):
    client.force_login(user)
    sprint = create_sprint(user)
    state_url = reverse("growth:practice-state", kwargs={"sprint_id": sprint.pk})

    assert client.post(state_url, {"status": "paused"}).status_code == 302
    sprint.refresh_from_db()
    assert sprint.status == PracticeSprint.Status.PAUSED
    assert sprint.paused_at is not None

    assert client.post(state_url, {"status": "active"}).status_code == 302
    sprint.refresh_from_db()
    assert sprint.status == PracticeSprint.Status.ACTIVE
    assert sprint.paused_at is None

    assert client.post(state_url, {"status": "stopped"}).status_code == 302
    sprint.refresh_from_db()
    assert sprint.status == PracticeSprint.Status.STOPPED
    assert sprint.stopped_at is not None
    with pytest.raises(PracticeWorkflowError):
        transition_sprint(sprint, PracticeSprint.Status.ACTIVE)


@pytest.mark.django_db
def test_completion_and_review_do_not_mutate_static_scores(client, user, seeded):
    client.force_login(user)
    sprint = create_sprint(user)
    actions = list(sprint.protocol.actions.all())
    new_url = reverse("growth:practice-check-in-new", kwargs={"sprint_id": sprint.pk})
    before = list(
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

    evidence_rows = (
        check_in_post(
            actions[0],
            action_completed="on",
            user_initiated="on",
            moved_beyond_transactional="on",
            meaningful_information_shared="on",
        ),
        check_in_post(
            actions[1],
            action_completed="on",
            future_interaction_scheduled="on",
            context_comparison="same_context",
        ),
        check_in_post(
            actions[2],
            follow_up_question_asked="on",
            follow_up_within_seven_days="on",
            context_comparison="same_context",
        ),
    )
    for row in evidence_rows:
        row["intent"] = "submit"
        assert client.post(new_url, row).status_code == 302

    evidence = completion_evidence(sprint)
    assert evidence.ready_for_review is True
    projection_before_review = build_user_shadow_projection(user).projection
    assert projection_before_review.event_count == 3
    review_url = reverse("growth:practice-review", kwargs={"sprint_id": sprint.pk})
    review_page = client.get(review_url)
    assert review_page.status_code == 200
    assert b"Completing this practice does not establish mastery." in review_page.content
    assert b"All three actions attempted" in review_page.content

    completed = client.post(
        review_url,
        {
            "reflection": "The invitation became more specific and mutual.",
            "contradictory_evidence": "Timing was harder than expected.",
        },
        follow=True,
    )
    assert completed.status_code == 200
    assert b"The experiment is closed" in completed.content
    assert b"Completing this practice does not establish mastery." in completed.content
    assert b"Saved score impact" in completed.content
    assert b"None" in completed.content

    sprint.refresh_from_db()
    assert sprint.status == PracticeSprint.Status.COMPLETED
    assert sprint.completed_at is not None
    assert sprint.review.actions_attempted == 3
    assert sprint.review.actions_completed == 2
    assert sprint.review.substantive_interaction_occurred is True
    assert sprint.review.static_score_impact_preview == {}
    after = list(
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
    assert after == before
    assert build_user_shadow_projection(user).projection == projection_before_review


@pytest.mark.django_db
def test_sprints_are_private_and_only_one_can_be_current(client, user, seeded):
    sprint = create_sprint(user)
    other_user = get_user_model().objects.create_user("other", password="different password 47!")
    client.force_login(other_user)
    assert (
        client.get(reverse("growth:practice-sprint", kwargs={"sprint_id": sprint.pk})).status_code
        == 404
    )

    with pytest.raises(PracticeWorkflowError, match="current practice"):
        create_sprint(user)
