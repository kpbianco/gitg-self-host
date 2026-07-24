from dataclasses import dataclass

from django.contrib.auth import get_user_model

from growth.models import AssessmentRun, LeverBaseline, PracticeProtocol


@dataclass(frozen=True)
class ProfileSummary:
    assessment_run: AssessmentRun | None
    highest_needs: list[LeverBaseline]
    strongest_capacities: list[LeverBaseline]
    recommendations: list[PracticeProtocol]


def build_profile_summary(user: get_user_model()) -> ProfileSummary:
    run = (
        AssessmentRun.objects.filter(user=user)
        .prefetch_related("orientation_results", "archetype_results")
        .first()
    )
    if run is None:
        return ProfileSummary(None, [], [], [])

    baselines = LeverBaseline.objects.filter(user=user, assessment_run=run).select_related("lever")
    highest_needs = list(baselines.order_by("need_rank")[:5])
    strongest_capacities = list(
        baselines.order_by("-calibrated_estimate", "-evidence_confidence")[:5]
    )
    need_lever_ids = [baseline.lever_id for baseline in highest_needs]
    recommendations = list(
        PracticeProtocol.objects.filter(
            availability=PracticeProtocol.Availability.ACTIVE,
            target_levers__stable_id__in=need_lever_ids,
        )
        .distinct()
        .order_by("display_order")[:3]
    )
    return ProfileSummary(
        assessment_run=run,
        highest_needs=highest_needs,
        strongest_capacities=strongest_capacities,
        recommendations=recommendations,
    )
