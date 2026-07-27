import json

from django.core.paginator import Paginator
from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache

from growth.services.evidence import (
    EVIDENCE_DIRECTION_LABELS,
    EvidenceWorkflowError,
    build_evidence_ledger,
    build_privacy_safe_evidence_export,
)


@never_cache
def evidence_ledger(request):
    direction = request.GET.get("direction", "all")
    if direction != "all" and direction not in EVIDENCE_DIRECTION_LABELS:
        raise Http404("That evidence direction filter is not available.")
    try:
        ledger = build_evidence_ledger(request.user, direction=direction)
    except EvidenceWorkflowError:
        return render(
            request,
            "growth/evidence_audit_error.html",
            status=409,
        )

    paginator = Paginator(ledger.rows, 20)
    page = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "growth/evidence_ledger.html",
        {
            "ledger": ledger,
            "page": page,
            "direction_options": (
                ("all", "All directions"),
                *EVIDENCE_DIRECTION_LABELS.items(),
            ),
        },
    )


@never_cache
def evidence_export(request):
    try:
        payload = build_privacy_safe_evidence_export(request.user)
    except EvidenceWorkflowError:
        return HttpResponse(
            "Evidence export stopped because replay verification failed.",
            status=409,
            content_type="text/plain; charset=utf-8",
        )

    response = HttpResponse(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        content_type="application/json; charset=utf-8",
    )
    response["Content-Disposition"] = 'attachment; filename="grounded-growth-evidence.json"'
    response["Cache-Control"] = "no-store"
    return response
