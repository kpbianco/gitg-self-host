import json

from django.http import FileResponse, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from growth.services.assessment import (
    AssessmentPayloadError,
    assessment_scorer_path,
    load_assessment_assets,
    persist_assessment_run,
)


@never_cache
@require_GET
def assessment(request):
    assets = load_assessment_assets()
    return render(
        request,
        "growth/assessment.html",
        {
            "assessment_spec": assets.spec,
            "assessment_model": assets.model,
            "assessment_storage_key": f"gga_v1_1_state_user_{request.user.pk}",
        },
    )


@require_GET
def assessment_scorer(request):
    return FileResponse(
        assessment_scorer_path().open("rb"),
        content_type="text/javascript; charset=utf-8",
    )


@require_POST
def save_assessment(request):
    if len(request.body) > 2_000_000:
        return JsonResponse({"error": "Assessment payload is too large."}, status=400)
    try:
        payload = json.loads(request.body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse({"error": "Request body must be valid JSON."}, status=400)
    try:
        run, created = persist_assessment_run(request.user, payload)
    except AssessmentPayloadError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    return JsonResponse(
        {
            "created": created,
            "run_id": run.stable_id,
            "profile_url": reverse("growth:profile"),
        },
        status=201 if created else 200,
    )
