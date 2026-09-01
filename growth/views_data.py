from __future__ import annotations

from datetime import date

from django.contrib import messages
from django.contrib.auth import logout
from django.core import signing
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache

from growth.forms import AccountDeletionForm, RetentionConfirmationForm
from growth.services.data_lifecycle import (
    DataLifecycleError,
    apply_retention,
    build_deletion_preview,
    build_retention_preview,
    delete_owner_account,
    render_owner_archive,
)

PREVIEW_TOKEN_SALT = "growth.owner-data-lifecycle.v1"
PREVIEW_TOKEN_MAX_AGE_SECONDS = 15 * 60


def _signed_preview(kind: str, content_hash: str, **extra) -> str:
    return signing.dumps(
        {"kind": kind, "content_hash": content_hash, **extra},
        salt=PREVIEW_TOKEN_SALT,
        compress=True,
    )


def _load_preview(token: str, expected_kind: str, expected_owner: str) -> dict:
    try:
        payload = signing.loads(
            token,
            salt=PREVIEW_TOKEN_SALT,
            max_age=PREVIEW_TOKEN_MAX_AGE_SECONDS,
        )
    except signing.BadSignature as exc:
        raise DataLifecycleError("The preview expired or was changed. Review it again.") from exc
    if payload.get("kind") != expected_kind:
        raise DataLifecycleError("The confirmation does not match this operation.")
    if payload.get("owner") != expected_owner:
        raise DataLifecycleError("The confirmation does not match the signed-in owner.")
    return payload


def _deletion_groups(counts: dict[str, int]) -> tuple[tuple[str, int], ...]:
    groups = (
        ("Account and signed-in sessions", ("account", "sessions")),
        (
            "Assessment and profile",
            (
                "assessment_runs",
                "orientation_results",
                "archetype_results",
                "lever_baselines",
                "lever_states",
            ),
        ),
        (
            "Practice, check-ins, evidence, scores, and reviews",
            (
                "practice_sprints",
                "practice_check_ins",
                "evidence_events",
                "score_snapshots",
                "practice_reviews",
            ),
        ),
        (
            "Context, Personal OS, and weekly execution",
            (
                "assessment_context",
                "practice_context",
                "personal_os_revisions",
                "weekly_execution_plans",
                "weekly_execution_reviews",
            ),
        ),
        ("Optional pilot feedback", ("pilot_feedback",)),
    )
    return tuple((label, sum(counts.get(name, 0) for name in names)) for label, names in groups)


@never_cache
def owner_archive(request):
    try:
        content = render_owner_archive(request.user)
    except (DataLifecycleError, ValueError):
        return HttpResponse(
            "Owner archive stopped because stored records failed deterministic verification.",
            status=409,
            content_type="text/plain; charset=utf-8",
        )
    response = HttpResponse(content, content_type="application/json; charset=utf-8")
    response["Content-Disposition"] = (
        'attachment; filename="grounded-growth-owner-private-archive-v1.json"'
    )
    response["Cache-Control"] = "no-store, private"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@never_cache
def data_management(request):
    deletion_preview = build_deletion_preview(request.user)
    retention_preview = build_retention_preview(request.user)
    owner = str(request.user.pk)
    deletion_token = _signed_preview("delete", deletion_preview.content_hash, owner=owner)
    retention_token = _signed_preview(
        "retention",
        retention_preview.content_hash,
        owner=owner,
        as_of=retention_preview.as_of.isoformat(),
    )
    deletion_form = AccountDeletionForm(
        user=request.user, initial={"preview_token": deletion_token}
    )
    retention_form = RetentionConfirmationForm(initial={"preview_token": retention_token})

    if request.method == "POST" and request.POST.get("action") == "apply_retention":
        retention_form = RetentionConfirmationForm(request.POST)
        if retention_form.is_valid():
            try:
                payload = _load_preview(
                    retention_form.cleaned_data["preview_token"], "retention", owner
                )
                result = apply_retention(
                    user=request.user,
                    expected_preview_hash=payload["content_hash"],
                    as_of=date.fromisoformat(payload["as_of"]),
                )
            except (DataLifecycleError, KeyError, ValueError) as exc:
                retention_form.add_error(None, str(exc))
            else:
                messages.success(
                    request,
                    f"Retention applied to {result.total_deleted} eligible record(s). "
                    "Immutable developmental history was unchanged.",
                )
                return redirect("growth:data-management")

    if request.method == "POST" and request.POST.get("action") == "delete_account":
        deletion_form = AccountDeletionForm(request.POST, user=request.user)
        if deletion_form.is_valid():
            try:
                payload = _load_preview(
                    deletion_form.cleaned_data["preview_token"], "delete", owner
                )
                deleted = delete_owner_account(
                    user=request.user,
                    expected_preview_hash=payload["content_hash"],
                )
            except (DataLifecycleError, KeyError) as exc:
                deletion_form.add_error(None, str(exc))
            else:
                logout(request)
                messages.success(
                    request,
                    f"The account and {deleted - 1} owned record(s) were permanently deleted.",
                )
                return redirect("login")

    return render(
        request,
        "growth/data_management.html",
        {
            "deletion_preview": deletion_preview,
            "deletion_groups": _deletion_groups(deletion_preview.record_counts),
            "deletion_form": deletion_form,
            "retention_preview": retention_preview,
            "retention_form": retention_form,
        },
    )
