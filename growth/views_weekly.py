from __future__ import annotations

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import IntegrityError, OperationalError
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from growth.forms import WeeklyExecutionPlanForm, WeeklyExecutionReviewForm
from growth.models import PersonalOSRevision, PracticeCheckIn
from growth.services.personal_os_browser import build_browser_priority_presentation
from growth.services.practice import current_sprint_for
from growth.services.profile import build_profile_summary
from growth.services.weekly_execution import (
    WeeklyExecutionServiceError,
    WeeklyExecutionWriteConflictError,
    current_window,
    latest_unreviewed_plan,
    latest_weekly_plan,
    proof_events_for_plan,
    record_weekly_plan,
    record_weekly_review,
)


def _next_action(sprint):
    if sprint is None:
        return None
    attempted = set(
        sprint.check_ins.filter(
            status=PracticeCheckIn.Status.SUBMITTED,
            action_attempted=True,
        ).values_list("action_id", flat=True)
    )
    return sprint.protocol.actions.exclude(pk__in=attempted).order_by("sequence").first()


def _latest_personal_os(run):
    rows = tuple(PersonalOSRevision.objects.filter(assessment_run=run).order_by("revision"))
    for row in rows:
        row.full_clean()
    if [row.revision for row in rows] != list(range(1, len(rows) + 1)):
        raise ValidationError("Personal OS revision sequence is invalid.")
    return rows[-1] if rows else None


def _proof_rows(plan):
    if plan is None:
        return ()
    return tuple(
        {
            **event,
            "direction_label": event["direction"].replace("_", " ").capitalize(),
            "withholding_labels": tuple(
                item.replace("_", " ").capitalize() for item in event["withholding_reasons"]
            ),
        }
        for event in proof_events_for_plan(plan)
    )


def _render(
    request,
    *,
    summary,
    priority,
    week_start,
    week_end,
    active_sprint,
    current_plan,
    review_target,
    personal_os,
    plan_form,
    review_form,
    status=200,
):
    current_review = (
        current_plan.review
        if current_plan is not None and hasattr(current_plan, "review")
        else None
    )
    target_review = (
        review_target.review
        if review_target is not None and hasattr(review_target, "review")
        else None
    )
    proof_rows = (
        _proof_rows(review_target)
        if target_review is None
        else tuple(
            {
                **event,
                "direction_label": event["direction"].replace("_", " ").capitalize(),
                "withholding_labels": tuple(
                    item.replace("_", " ").capitalize() for item in event["withholding_reasons"]
                ),
            }
            for event in target_review.canonical_snapshot["proof_events"]
        )
    )
    return render(
        request,
        "growth/weekly_execution.html",
        {
            "summary": summary,
            "priority": priority,
            "week_start": week_start,
            "week_end": week_end,
            "active_sprint": active_sprint,
            "current_plan": current_plan,
            "current_review": current_review,
            "review_target": review_target,
            "target_review": target_review,
            "personal_os": personal_os,
            "plan_form": plan_form,
            "review_form": review_form,
            "proof_rows": proof_rows,
        },
        status=status,
    )


@require_http_methods(["GET", "POST"])
def weekly_execution(request):
    summary = build_profile_summary(request.user)
    run = summary.assessment_run
    if run is None:
        messages.info(request, "Complete or import an assessment before planning a week.")
        return redirect("growth:assessment")
    week_start, week_end = current_window()
    active_sprint = current_sprint_for(request.user)
    current_plan = latest_weekly_plan(
        user=request.user,
        assessment_run=run,
        week_start=week_start,
    )
    review_target = latest_unreviewed_plan(user=request.user, assessment_run=run)
    try:
        personal_os = _latest_personal_os(run)
        for row in (current_plan, review_target):
            if row is not None:
                row.full_clean()
        if current_plan is not None and current_plan.user_id != request.user.pk:
            raise ValidationError("Weekly plan ownership failed.")
    except (ValidationError, ValueError, TypeError, WeeklyExecutionServiceError):
        return HttpResponse(
            "Saved weekly or Personal OS state could not be verified. "
            "No private value is displayed.",
            status=409,
        )
    priority = build_browser_priority_presentation(user=request.user, summary=summary)
    form_type = request.POST.get("form_type") if request.method == "POST" else None

    next_action = _next_action(active_sprint)
    plan_initial = {}
    if active_sprint is not None:
        plan_initial = {
            "assessment_epoch": run.pk,
            "sprint_id": active_sprint.pk,
            "week_start": week_start,
            "action": (
                current_plan.action_id
                if current_plan is not None and current_plan.sprint_id == active_sprint.pk
                else getattr(next_action, "pk", None)
            ),
            "intended_on": (
                current_plan.intended_on
                if current_plan is not None and current_plan.sprint_id == active_sprint.pk
                else max(week_start, min(week_end, timezone.localdate()))
            ),
        }
    plan_form = (
        WeeklyExecutionPlanForm(
            request.POST if form_type == "weekly_plan" else None,
            sprint=active_sprint,
            initial=plan_initial,
        )
        if active_sprint is not None
        else None
    )
    review_form = (
        WeeklyExecutionReviewForm(
            request.POST if form_type == "weekly_review" else None,
            initial={
                "plan_id": review_target.pk,
                "next_step": "continue_current",
                "adjustment": "none",
            },
        )
        if review_target is not None
        else None
    )

    if request.method == "POST" and form_type not in {"weekly_plan", "weekly_review"}:
        return HttpResponse("Unsupported weekly action. Nothing was saved.", status=400)

    if form_type == "weekly_plan" and plan_form is not None and plan_form.is_valid():
        if plan_form.cleaned_data["assessment_epoch"] != run.pk:
            return HttpResponse(
                "The assessment epoch changed. Reload before saving the weekly plan.",
                status=409,
            )
        try:
            result = record_weekly_plan(
                user=request.user,
                assessment_run=run,
                sprint=active_sprint,
                action=plan_form.cleaned_data["action"],
                week_start=plan_form.cleaned_data["week_start"],
                intended_on=plan_form.cleaned_data["intended_on"],
            )
        except (WeeklyExecutionWriteConflictError, OperationalError, IntegrityError):
            return HttpResponse(
                "The weekly plan changed while saving. Reload and retry.", status=409
            )
        except (WeeklyExecutionServiceError, ValidationError, ValueError, TypeError):
            plan_form.add_error(None, "The weekly plan could not be validated.")
        else:
            messages.success(
                request,
                "Weekly plan revision saved."
                if result.created
                else "The weekly plan was unchanged.",
            )
            return redirect("growth:weekly-execution")

    if form_type == "weekly_review" and review_form is not None and review_form.is_valid():
        if review_form.cleaned_data["plan_id"] != review_target.pk:
            return HttpResponse(
                "The weekly review target changed. Reload before submitting.", status=409
            )
        try:
            result = record_weekly_review(
                user=request.user,
                plan=review_target,
                next_step=review_form.cleaned_data["next_step"],
                adjustment=review_form.cleaned_data["adjustment"],
            )
        except (WeeklyExecutionWriteConflictError, OperationalError, IntegrityError):
            return HttpResponse(
                "The weekly review changed while saving. Reload the completed review.",
                status=409,
            )
        except (WeeklyExecutionServiceError, ValidationError, ValueError, TypeError):
            review_form.add_error(None, "The weekly review could not be validated.")
        else:
            messages.success(
                request,
                "Weekly proof review saved."
                if result.created
                else "The weekly proof review was unchanged.",
            )
            return redirect("growth:weekly-execution")

    try:
        return _render(
            request,
            summary=summary,
            priority=priority,
            week_start=week_start,
            week_end=week_end,
            active_sprint=active_sprint,
            current_plan=current_plan,
            review_target=review_target,
            personal_os=personal_os,
            plan_form=plan_form,
            review_form=review_form,
            status=400 if request.method == "POST" else 200,
        )
    except (ValidationError, ValueError, TypeError, WeeklyExecutionServiceError):
        return HttpResponse(
            "Saved weekly proof could not be verified. No private value is displayed.",
            status=409,
        )
