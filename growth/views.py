from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache

from growth.models import PracticeCheckIn, WeeklyExecutionPlan, WeeklyExecutionReview
from growth.services.personal_os_browser import build_browser_priority_presentation
from growth.services.practice import completion_evidence, current_sprint_for
from growth.services.profile import build_profile_summary
from growth.services.weekly_execution import (
    current_window,
    latest_unreviewed_plan,
    latest_weekly_plan,
)


@never_cache
def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        return JsonResponse({"status": "unhealthy"}, status=503)
    return JsonResponse({"status": "ok"})


def home(request):
    summary = build_profile_summary(request.user)
    priority = build_browser_priority_presentation(user=request.user, summary=summary)
    active_sprint = current_sprint_for(request.user)
    recent_check_ins = (
        PracticeCheckIn.objects.filter(
            sprint__user=request.user,
            status=PracticeCheckIn.Status.SUBMITTED,
        )
        .select_related("action", "sprint__protocol", "evidence_event")
        .order_by("-submitted_at")[:5]
    )
    next_action = None
    practice_evidence = None
    weekly_plan = None
    weekly_review_pending = None
    if summary.assessment_run is not None:
        window_start, _ = current_window()
        weekly_plan = latest_weekly_plan(
            user=request.user,
            assessment_run=summary.assessment_run,
            week_start=window_start,
        )
        weekly_review_pending = latest_unreviewed_plan(
            user=request.user,
            assessment_run=summary.assessment_run,
        )
    if active_sprint is not None:
        practice_evidence = completion_evidence(active_sprint)
        completed_action_ids = set(
            active_sprint.check_ins.filter(
                status=PracticeCheckIn.Status.SUBMITTED,
                action_completed=True,
            ).values_list("action_id", flat=True)
        )
        next_action = active_sprint.protocol.actions.exclude(
            stable_id__in=completed_action_ids
        ).first()
    return render(
        request,
        "growth/home.html",
        {
            "summary": summary,
            "priority": priority,
            "active_sprint": active_sprint,
            "next_action": next_action,
            "practice_evidence": practice_evidence,
            "recent_check_ins": recent_check_ins,
            "weekly_plan": weekly_plan,
            "weekly_review_pending": weekly_review_pending,
        },
    )


def profile(request):
    summary = build_profile_summary(request.user)
    return render(
        request,
        "growth/profile.html",
        {
            "summary": summary,
            "weekly_plan_count": WeeklyExecutionPlan.objects.filter(user=request.user).count(),
            "weekly_review_count": WeeklyExecutionReview.objects.filter(user=request.user).count(),
        },
    )
