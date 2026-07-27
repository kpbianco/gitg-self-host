import json

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache

from growth.forms import PilotFeedbackForm
from growth.services.pilot_feedback import (
    PilotFeedbackError,
    build_pilot_feedback_summary,
    build_privacy_safe_pilot_export,
    submit_pilot_feedback,
)


@never_cache
def pilot_feedback(request):
    form = PilotFeedbackForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            submit_pilot_feedback(user=request.user, cleaned_data=form.cleaned_data)
        except PilotFeedbackError as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(
                request,
                "Optional product feedback submitted. It did not change your profile or practice.",
            )
            return redirect("growth:pilot-feedback")

    return render(
        request,
        "growth/pilot_feedback.html",
        {
            "form": form,
            "summary": build_pilot_feedback_summary(request.user),
        },
    )


@never_cache
def pilot_feedback_export(request):
    try:
        payload = build_privacy_safe_pilot_export(request.user)
    except PilotFeedbackError:
        return HttpResponse(
            "Pilot feedback export stopped because stored feedback failed validation.",
            status=409,
            content_type="text/plain; charset=utf-8",
        )

    response = HttpResponse(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        content_type="application/json; charset=utf-8",
    )
    response["Content-Disposition"] = (
        'attachment; filename="grounded-growth-private-pilot-feedback.json"'
    )
    response["Cache-Control"] = "no-store, private"
    return response
