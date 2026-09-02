from datetime import date, timedelta

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import IntegrityError, OperationalError
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from growth.domain.context_priority import AlternativeRequest
from growth.domain.practice_content import PracticeContentError
from growth.forms import (
    PracticeApplicabilityForm,
    PracticeBoundaryForm,
    PracticeCheckInForm,
    PracticeContextForm,
    PracticePriorityContextForm,
    PracticeReviewForm,
    PracticeStartDateForm,
)
from growth.models import (
    AssessmentContext,
    AssessmentRun,
    CompletionCreditEvent,
    EvidenceEvent,
    PracticeCheckIn,
    PracticeContext,
    PracticeProtocol,
    PracticeReview,
    PracticeSprint,
)
from growth.services.context import ContextServiceError, PracticeContextInput, record_context_bundle
from growth.services.personal_os_browser import (
    active_projected_protocol_ids,
    assessment_factors_from_record,
    build_browser_priority_presentation,
    practice_context_initial,
)
from growth.services.practice import (
    PracticeWorkflowError,
    complete_with_review,
    completion_evidence,
    current_sprint_for,
    save_check_in,
    start_practice,
    transition_sprint,
)
from growth.services.profile import build_profile_summary


def _protocol(slug: str) -> PracticeProtocol:
    return get_object_or_404(
        PracticeProtocol.objects.prefetch_related("actions", "target_levers"),
        slug=slug,
    )


def _sprint(user, sprint_id) -> PracticeSprint:
    return get_object_or_404(
        PracticeSprint.objects.select_related("protocol", "assessment_run").prefetch_related(
            "protocol__actions"
        ),
        pk=sprint_id,
        user=user,
    )


def practice_list(request):
    summary = build_profile_summary(request.user)
    priority = build_browser_priority_presentation(user=request.user, summary=summary)
    recommended_ids = {protocol.pk for protocol in priority.recommendations}
    protocols = list(
        PracticeProtocol.objects.prefetch_related("target_levers").order_by("display_order")
    )
    ranked_protocols = list(priority.recommendations) if priority.context_aware else protocols
    ranked_ids = {protocol.pk for protocol in ranked_protocols}
    not_context_ranked = (
        [protocol for protocol in protocols if protocol.pk not in ranked_ids]
        if priority.context_aware
        else []
    )
    return render(
        request,
        "growth/practice_list.html",
        {
            "protocols": protocols,
            "ranked_protocols": ranked_protocols,
            "not_context_ranked": not_context_ranked,
            "recommended_ids": recommended_ids,
            "current_sprint": current_sprint_for(request.user),
            "priority": priority,
        },
    )


def practice_recommendation(request, slug):
    protocol = _protocol(slug)
    current = current_sprint_for(request.user)
    summary = build_profile_summary(request.user)
    priority = build_browser_priority_presentation(user=request.user, summary=summary)
    is_recommended = protocol.pk in {item.pk for item in priority.recommendations}
    context_candidate = next(
        (item for item in priority.candidates if item.protocol.pk == protocol.pk),
        None,
    )
    return render(
        request,
        "growth/practice_recommendation.html",
        {
            "protocol": protocol,
            "current_sprint": current,
            "is_recommended": is_recommended,
            "has_profile": summary.assessment_run is not None,
            "assessment_run": summary.assessment_run,
            "priority": priority,
            "context_candidate": context_candidate,
        },
    )


def _practice_context_record(run, protocol):
    rows = tuple(
        PracticeContext.objects.filter(assessment_run=run, protocol=protocol).order_by("revision")
    )
    for record in rows:
        record.full_clean()
    if [record.revision for record in rows] != list(range(1, len(rows) + 1)):
        raise ValidationError("Practice context revision sequence is invalid.")
    return rows[-1] if rows else None


def _assessment_context_record(run):
    rows = tuple(AssessmentContext.objects.filter(assessment_run=run).order_by("revision"))
    for record in rows:
        record.full_clean()
    if [record.revision for record in rows] != list(range(1, len(rows) + 1)):
        raise ValidationError("Assessment context revision sequence is invalid.")
    return rows[-1] if rows else None


def _render_practice_context(
    request,
    *,
    protocol,
    summary,
    form,
    status=200,
    alternative_request=None,
):
    priority = build_browser_priority_presentation(
        user=request.user,
        summary=summary,
        alternative_request=alternative_request,
    )
    current = _practice_context_record(summary.assessment_run, protocol)
    return render(
        request,
        "growth/practice_context.html",
        {
            "protocol": protocol,
            "assessment_run": summary.assessment_run,
            "form": form,
            "current_context": current,
            "priority": priority,
        },
        status=status,
    )


@require_http_methods(["GET", "POST"])
def practice_priority_context(request, slug):
    summary = build_profile_summary(request.user)
    run = summary.assessment_run
    if run is None:
        messages.info(
            request, "Complete or import an assessment before reviewing practice context."
        )
        return redirect("growth:assessment")
    protocol = _protocol(slug)
    try:
        projected_ids = active_projected_protocol_ids()
    except (PracticeContentError, ValueError):
        raise Http404 from None
    if (
        protocol.stable_id not in projected_ids
        or protocol.availability != PracticeProtocol.Availability.ACTIVE
    ):
        raise Http404
    try:
        current = _practice_context_record(run, protocol)
    except (ValidationError, ValueError, TypeError):
        return HttpResponse(
            "Saved practice context could not be verified. No value is displayed.",
            status=409,
        )
    form = PracticePriorityContextForm(
        request.POST or None,
        initial=practice_context_initial(current, assessment_epoch=run.pk),
    )
    if request.method == "POST" and request.POST.get("intent") == "request_alternative":
        form = PracticePriorityContextForm(
            initial=practice_context_initial(current, assessment_epoch=run.pk)
        )
        if current is None or (
            current.applicability_state != "not_applicable" and current.disposition != "deferred"
        ):
            return HttpResponse(
                "An alternative requires a saved not-applicable or deferred review.",
                status=400,
            )
        reason = "not_applicable" if current.applicability_state == "not_applicable" else "deferred"
        return _render_practice_context(
            request,
            protocol=protocol,
            summary=summary,
            form=form,
            alternative_request=AlternativeRequest(protocol.stable_id, reason),
        )
    if request.method == "POST" and form.is_valid():
        if form.cleaned_data["assessment_epoch"] != run.pk:
            return HttpResponse(
                "The assessment epoch changed. Reload before saving; no value is displayed.",
                status=409,
            )
        if (
            request.POST.get("intent") == "save_and_request_alternative"
            and form.cleaned_data["mode"] != "not_applicable"
        ):
            form.add_error(
                "mode",
                "The direct alternative action requires an explicit not-applicable response.",
            )
            return _render_practice_context(
                request,
                protocol=protocol,
                summary=summary,
                form=form,
                status=400,
            )
        try:
            assessment_context = _assessment_context_record(run)
        except (ValidationError, ValueError, TypeError):
            return HttpResponse(
                "Saved season and capacity context could not be verified. No value is displayed.",
                status=409,
            )
        factors, disposition, defer_reason, review_horizon_days = form.context_input(protocol)
        try:
            result = record_context_bundle(
                user=request.user,
                assessment_run=run,
                assessment_factors=assessment_factors_from_record(assessment_context),
                practice_inputs=(
                    PracticeContextInput(
                        protocol=protocol,
                        factors=factors,
                        disposition=disposition,
                        defer_reason=defer_reason,
                        review_horizon_days=review_horizon_days,
                    ),
                ),
            )
        except (OperationalError, IntegrityError):
            return HttpResponse(
                "The local store is busy. Reload and retry; no value is displayed.",
                status=409,
            )
        except (ContextServiceError, ValidationError, ValueError, TypeError):
            form.add_error(None, "The practice context response could not be validated.")
            return _render_practice_context(
                request,
                protocol=protocol,
                summary=summary,
                form=form,
                status=400,
            )
        created = result.practice_created[0]
        messages.success(
            request,
            "Practice context revision saved." if created else "Practice context was unchanged.",
        )
        if request.POST.get("intent") == "save_and_request_alternative":
            current = _practice_context_record(run, protocol)
            refreshed_form = PracticePriorityContextForm(
                initial=practice_context_initial(current, assessment_epoch=run.pk)
            )
            return _render_practice_context(
                request,
                protocol=protocol,
                summary=summary,
                form=refreshed_form,
                alternative_request=AlternativeRequest(protocol.stable_id, "not_applicable"),
            )
        return redirect("growth:practice-context", slug=protocol.slug)
    return _render_practice_context(
        request,
        protocol=protocol,
        summary=summary,
        form=form,
        status=400 if request.method == "POST" else 200,
    )


def _setup_session_key(request, protocol):
    return f"practice_setup:{request.user.pk}:{protocol.pk}"


def _setup_data(request, protocol):
    return dict(request.session.get(_setup_session_key(request, protocol), {}))


def _save_setup_data(request, protocol, setup):
    request.session[_setup_session_key(request, protocol)] = setup
    request.session.modified = True


def _first_incomplete_setup_step(setup):
    requirements = (
        (1, "reason_reviewed"),
        (2, "applicable"),
        (3, "person_or_context"),
        (4, "boundaries_acknowledged"),
        (5, "start_date"),
        (6, "actions_reviewed"),
    )
    for step, key in requirements:
        if not setup.get(key):
            return step
    return 7


@require_http_methods(["GET", "POST"])
def practice_setup(request, slug, step):
    if step not in range(1, 8):
        raise Http404
    protocol = _protocol(slug)
    if protocol.availability != PracticeProtocol.Availability.ACTIVE:
        messages.info(request, "This structured protocol is not active yet.")
        return redirect("growth:practice-recommendation", slug=slug)
    if not AssessmentRun.objects.filter(user=request.user).exists():
        messages.info(request, "Complete or import an assessment before setting up a practice.")
        return redirect("growth:assessment")
    current = current_sprint_for(request.user)
    if current is not None:
        messages.info(request, "You already have a current practice.")
        return redirect("growth:practice-sprint", sprint_id=current.pk)

    setup = _setup_data(request, protocol)
    first_incomplete = _first_incomplete_setup_step(setup)
    if step > first_incomplete:
        return redirect("growth:practice-setup", slug=slug, step=first_incomplete)

    form = None
    if step == 1:
        if request.method == "POST":
            setup["reason_reviewed"] = True
            _save_setup_data(request, protocol, setup)
            return redirect("growth:practice-setup", slug=slug, step=2)
    elif step == 2:
        form = PracticeApplicabilityForm(request.POST or None, protocol=protocol)
        if request.method == "POST" and form.is_valid():
            if form.cleaned_data["applicable"] == "no":
                request.session.pop(_setup_session_key(request, protocol), None)
                messages.info(
                    request,
                    "That is useful information. This practice can wait until it fits.",
                )
                return redirect("growth:practice-recommendation", slug=slug)
            setup["applicable"] = True
            _save_setup_data(request, protocol, setup)
            return redirect("growth:practice-setup", slug=slug, step=3)
    elif step == 3:
        form = PracticeContextForm(
            request.POST or None,
            protocol=protocol,
            initial={"person_or_context": setup.get("person_or_context", "")},
        )
        if request.method == "POST" and form.is_valid():
            setup["person_or_context"] = form.cleaned_data["person_or_context"]
            _save_setup_data(request, protocol, setup)
            return redirect("growth:practice-setup", slug=slug, step=4)
    elif step == 4:
        form = PracticeBoundaryForm(request.POST or None, protocol=protocol)
        if request.method == "POST" and form.is_valid():
            setup["boundaries_acknowledged"] = True
            _save_setup_data(request, protocol, setup)
            return redirect("growth:practice-setup", slug=slug, step=5)
    elif step == 5:
        form = PracticeStartDateForm(
            request.POST or None,
            initial={"start_date": setup.get("start_date", timezone.localdate().isoformat())},
        )
        if request.method == "POST" and form.is_valid():
            setup["start_date"] = form.cleaned_data["start_date"].isoformat()
            _save_setup_data(request, protocol, setup)
            return redirect("growth:practice-setup", slug=slug, step=6)
    elif step == 6:
        if request.method == "POST":
            setup["actions_reviewed"] = True
            _save_setup_data(request, protocol, setup)
            return redirect("growth:practice-setup", slug=slug, step=7)
    elif request.method == "POST":
        try:
            sprint = start_practice(
                user=request.user,
                protocol=protocol,
                person_or_context=setup["person_or_context"],
                start_date=date.fromisoformat(setup["start_date"]),
            )
        except (KeyError, ValueError, PracticeWorkflowError) as exc:
            messages.error(request, str(exc))
            return redirect("growth:practice-recommendation", slug=slug)
        request.session.pop(_setup_session_key(request, protocol), None)
        messages.success(request, "Practice started. The intervention is ready when you are.")
        return redirect("growth:practice-sprint", sprint_id=sprint.pk)

    return render(
        request,
        "growth/practice_setup.html",
        {
            "protocol": protocol,
            "step": step,
            "form": form,
            "setup": setup,
            "start_date": setup.get("start_date"),
        },
    )


def practice_sprint(request, sprint_id):
    sprint = _sprint(request.user, sprint_id)
    submitted = list(
        sprint.check_ins.filter(status=PracticeCheckIn.Status.SUBMITTED)
        .select_related("action", "evidence_event")
        .order_by("-submitted_at")
    )
    drafts = list(
        sprint.check_ins.filter(status=PracticeCheckIn.Status.DRAFT)
        .select_related("action")
        .order_by("-updated_at")
    )
    evidence = completion_evidence(sprint)
    attempted_ids = {item.action_id for item in submitted if item.action_attempted}
    completed_ids = {item.action_id for item in submitted if item.action_completed}
    action_rows = [
        {
            "action": action,
            "attempted": action.pk in attempted_ids,
            "completed": action.pk in completed_ids,
        }
        for action in sprint.protocol.actions.all()
    ]
    next_action = next(
        (row["action"] for row in action_rows if not row["completed"]),
        None,
    )
    return render(
        request,
        "growth/practice_sprint.html",
        {
            "sprint": sprint,
            "submitted_check_ins": submitted,
            "draft_check_ins": drafts,
            "evidence": evidence,
            "action_rows": action_rows,
            "next_action": next_action,
            "end_date": sprint.start_date + timedelta(days=sprint.protocol.duration_days - 1),
        },
    )


@require_POST
def practice_state(request, sprint_id):
    sprint = _sprint(request.user, sprint_id)
    target = request.POST.get("status", "")
    if target not in (
        PracticeSprint.Status.ACTIVE,
        PracticeSprint.Status.PAUSED,
        PracticeSprint.Status.STOPPED,
    ):
        messages.error(request, "That practice status is not available.")
        return redirect("growth:practice-sprint", sprint_id=sprint.pk)
    try:
        transition_sprint(sprint, target)
    except PracticeWorkflowError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f"Practice {PracticeSprint.Status(target).label.lower()}.")
    return redirect("growth:practice-sprint", sprint_id=sprint.pk)


@require_http_methods(["GET", "POST"])
def practice_check_in(request, sprint_id, check_in_id=None):
    sprint = _sprint(request.user, sprint_id)
    if check_in_id is None:
        check_in = None
    else:
        check_in = get_object_or_404(
            PracticeCheckIn,
            pk=check_in_id,
            sprint=sprint,
            status=PracticeCheckIn.Status.DRAFT,
        )
    initial = None
    if check_in is None and request.method == "GET":
        requested_action = request.GET.get("action")
        if requested_action and sprint.protocol.actions.filter(pk=requested_action).exists():
            initial = {"action": requested_action}
    submit = request.method == "POST" and request.POST.get("intent") == "submit"
    form = PracticeCheckInForm(
        request.POST or None,
        instance=check_in,
        sprint=sprint,
        require_evidence_metadata=submit,
        initial=initial,
    )
    if request.method == "POST" and form.is_valid():
        try:
            saved = save_check_in(
                sprint=sprint,
                cleaned_data=form.cleaned_data,
                existing=check_in,
                submit=submit,
            )
        except PracticeWorkflowError as exc:
            form.add_error(None, str(exc))
        else:
            if saved.status == PracticeCheckIn.Status.DRAFT:
                messages.success(request, "Draft saved. It is not submitted evidence.")
            else:
                messages.success(request, "Check-in submitted and added to evidence history.")
            return redirect("growth:practice-sprint", sprint_id=sprint.pk)
    return render(
        request,
        "growth/practice_check_in.html",
        {
            "sprint": sprint,
            "form": form,
            "check_in": check_in,
        },
    )


def practice_check_in_detail(request, sprint_id, check_in_id):
    sprint = _sprint(request.user, sprint_id)
    check_in = get_object_or_404(
        PracticeCheckIn.objects.select_related("action"),
        pk=check_in_id,
        sprint=sprint,
        status=PracticeCheckIn.Status.SUBMITTED,
    )
    event = get_object_or_404(EvidenceEvent, check_in=check_in)
    return render(
        request,
        "growth/practice_check_in_detail.html",
        {
            "sprint": sprint,
            "check_in": check_in,
            "event": event,
        },
    )


@require_http_methods(["GET", "POST"])
def practice_review(request, sprint_id):
    sprint = _sprint(request.user, sprint_id)
    if PracticeReview.objects.filter(sprint=sprint).exists():
        return redirect("growth:practice-review-complete", sprint_id=sprint.pk)
    if sprint.status == PracticeSprint.Status.STOPPED:
        messages.info(request, "A stopped practice cannot be completed.")
        return redirect("growth:practice-sprint", sprint_id=sprint.pk)
    evidence = completion_evidence(sprint)
    form = PracticeReviewForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            complete_with_review(
                sprint=sprint,
                reflection=form.cleaned_data["reflection"],
                contradictory_evidence=form.cleaned_data["contradictory_evidence"],
            )
        except PracticeWorkflowError as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "Final review submitted. Practice complete.")
            return redirect("growth:practice-review-complete", sprint_id=sprint.pk)
    return render(
        request,
        "growth/practice_review.html",
        {
            "sprint": sprint,
            "evidence": evidence,
            "form": form,
        },
    )


def practice_review_complete(request, sprint_id):
    sprint = _sprint(request.user, sprint_id)
    try:
        review = PracticeReview.objects.get(sprint=sprint)
    except PracticeReview.DoesNotExist:
        return redirect("growth:practice-review", sprint_id=sprint.pk)
    credit_event = CompletionCreditEvent.objects.filter(review=review).first()
    return render(
        request,
        "growth/practice_review_complete.html",
        {
            "sprint": sprint,
            "review": review,
            "credit_event": credit_event,
        },
    )
