from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache

from growth.models import PracticeCheckIn, PracticeSprint
from growth.services.profile import build_profile_summary


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
    active_sprint = (
        PracticeSprint.objects.filter(user=request.user, status=PracticeSprint.Status.ACTIVE)
        .select_related("protocol")
        .first()
    )
    recent_check_ins = (
        PracticeCheckIn.objects.filter(
            sprint__user=request.user,
            status=PracticeCheckIn.Status.SUBMITTED,
        )
        .select_related("action", "sprint__protocol")
        .order_by("-submitted_at")[:5]
    )
    return render(
        request,
        "growth/home.html",
        {
            "summary": summary,
            "active_sprint": active_sprint,
            "recent_check_ins": recent_check_ins,
        },
    )


def profile(request):
    return render(
        request,
        "growth/profile.html",
        {"summary": build_profile_summary(request.user)},
    )
