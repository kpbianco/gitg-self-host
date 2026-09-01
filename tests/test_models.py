from datetime import date

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from growth.models import (
    AssessmentRun,
    LeverBaseline,
    PracticeReview,
    PracticeSprint,
)


@pytest.mark.django_db
def test_assessment_run_is_immutable(user, seeded):
    run = AssessmentRun.objects.get(user=user)
    run.original_share_code = "GGA11.changed"
    with pytest.raises(ValidationError, match="immutable"):
        run.save()
    with pytest.raises(ValidationError, match="immutable"):
        AssessmentRun.objects.filter(pk=run.pk).update(original_share_code="GGA11.changed")


@pytest.mark.django_db
def test_completing_practice_and_review_does_not_mutate_mastery(user, seeded):
    run = AssessmentRun.objects.get(user=user)
    protocol = run.curriculum_version.levers.get(stable_id="L26").practice_protocols.get(
        stable_id="PRACTICE-FRIENDSHIP-01"
    )
    before = {
        baseline.lever_id: (
            baseline.calibrated_estimate,
            baseline.evidence_confidence,
        )
        for baseline in LeverBaseline.objects.filter(user=user)
    }
    sprint = PracticeSprint.objects.create(
        user=user,
        protocol=protocol,
        assessment_run=run,
        scoring_contract_version=PracticeSprint.ScoringContract.LEGACY,
        person_or_context="Private context",
        start_date=date.today(),
        status=PracticeSprint.Status.COMPLETED,
        completed_at=timezone.now(),
    )
    review = PracticeReview.objects.create(
        sprint=sprint,
        actions_attempted=3,
        actions_completed=2,
        substantive_interaction_occurred=True,
        reflection="A bounded review.",
        submitted_at=timezone.now(),
    )
    after = {
        baseline.lever_id: (
            baseline.calibrated_estimate,
            baseline.evidence_confidence,
        )
        for baseline in LeverBaseline.objects.filter(user=user)
    }
    assert before == after
    assert review.static_score_impact_preview == {}
    assert review.mastery_disclaimer == "Completing this practice does not establish mastery."


@pytest.mark.django_db
def test_sprint_scoring_contract_fails_closed_on_an_unknown_version(user, seeded):
    run = AssessmentRun.objects.get(user=user)
    protocol = run.curriculum_version.levers.get(stable_id="L26").practice_protocols.get(
        stable_id="PRACTICE-FRIENDSHIP-01"
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        PracticeSprint.objects.create(
            user=user,
            protocol=protocol,
            assessment_run=run,
            scoring_contract_version="GG-UNKNOWN-SCORING-1.0",
            person_or_context="Private context",
            start_date=date.today(),
            status=PracticeSprint.Status.STOPPED,
        )
