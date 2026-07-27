from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache

from growth.models import PracticeCheckIn
from growth.services.practice import completion_evidence, current_sprint_for
from growth.services.profile import build_profile_summary
from growth.services.scoring import build_user_shadow_projection


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
    if active_sprint is not None:
        practice_evidence = completion_evidence(active_sprint)
        attempted_action_ids = set(
            active_sprint.check_ins.filter(
                status=PracticeCheckIn.Status.SUBMITTED,
                action_attempted=True,
            ).values_list("action_id", flat=True)
        )
        next_action = active_sprint.protocol.actions.exclude(
            stable_id__in=attempted_action_ids
        ).first()
    return render(
        request,
        "growth/home.html",
        {
            "summary": summary,
            "active_sprint": active_sprint,
            "next_action": next_action,
            "practice_evidence": practice_evidence,
            "recent_check_ins": recent_check_ins,
        },
    )


def profile(request):
    return render(
        request,
        "growth/profile.html",
        {
            "summary": build_profile_summary(request.user),
            "shadow": build_user_shadow_projection(request.user),
        },
    )
