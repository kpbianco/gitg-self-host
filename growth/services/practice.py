from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from growth.models import (
    AssessmentRun,
    PracticeCheckIn,
    PracticeProtocol,
    PracticeReview,
    PracticeSprint,
)
from growth.services.evidence import EvidenceWorkflowError, create_evidence_event


class PracticeWorkflowError(ValueError):
    pass


@dataclass(frozen=True)
class CompletionEvidence:
    actions_attempted: int
    actions_completed: int
    substantive_interaction_occurred: bool
    all_actions_attempted: bool
    enough_actions_completed: bool
    ready_for_review: bool


def current_sprint_for(user) -> PracticeSprint | None:
    return (
        PracticeSprint.objects.filter(
            user=user,
            status__in=(PracticeSprint.Status.ACTIVE, PracticeSprint.Status.PAUSED),
        )
        .select_related("protocol", "assessment_run")
        .first()
    )


@transaction.atomic
def start_practice(
    *,
    user,
    protocol: PracticeProtocol,
    person_or_context: str,
    start_date: date,
) -> PracticeSprint:
    if protocol.availability != PracticeProtocol.Availability.ACTIVE:
        raise PracticeWorkflowError("This practice is not yet available.")
    person_or_context = person_or_context.strip()
    if not person_or_context:
        raise PracticeWorkflowError("Choose a private label for the person or context.")
    today = timezone.localdate()
    if start_date < today or start_date > today + timedelta(days=14):
        raise PracticeWorkflowError("Choose a start date within the next two weeks.")
    if current_sprint_for(user) is not None:
        raise PracticeWorkflowError("Finish or stop the current practice before starting another.")
    assessment_run = AssessmentRun.objects.filter(user=user).first()
    if assessment_run is None:
        raise PracticeWorkflowError("Complete or import an assessment before starting a practice.")
    try:
        return PracticeSprint.objects.create(
            user=user,
            protocol=protocol,
            assessment_run=assessment_run,
            person_or_context=person_or_context,
            start_date=start_date,
            status=PracticeSprint.Status.ACTIVE,
            setup_completed_at=timezone.now(),
            boundaries_acknowledged_at=timezone.now(),
        )
    except IntegrityError as exc:
        raise PracticeWorkflowError(
            "Finish or stop the current practice before starting another."
        ) from exc


ALLOWED_TRANSITIONS = {
    PracticeSprint.Status.ACTIVE: {
        PracticeSprint.Status.PAUSED,
        PracticeSprint.Status.STOPPED,
    },
    PracticeSprint.Status.PAUSED: {
        PracticeSprint.Status.ACTIVE,
        PracticeSprint.Status.STOPPED,
    },
    PracticeSprint.Status.STOPPED: set(),
    PracticeSprint.Status.COMPLETED: set(),
}


@transaction.atomic
def transition_sprint(sprint: PracticeSprint, target_status: str) -> PracticeSprint:
    locked = PracticeSprint.objects.select_for_update().get(pk=sprint.pk)
    try:
        target_label = PracticeSprint.Status(target_status).label.lower()
    except ValueError as exc:
        raise PracticeWorkflowError("That practice status is not available.") from exc
    if target_status not in ALLOWED_TRANSITIONS[locked.status]:
        raise PracticeWorkflowError(
            f"A {locked.get_status_display().lower()} practice cannot move to {target_label}."
        )
    now = timezone.now()
    locked.status = target_status
    if target_status == PracticeSprint.Status.PAUSED:
        locked.paused_at = now
    elif target_status == PracticeSprint.Status.ACTIVE:
        locked.paused_at = None
    elif target_status == PracticeSprint.Status.STOPPED:
        locked.stopped_at = now
    locked.save()
    return locked


def completion_evidence(sprint: PracticeSprint) -> CompletionEvidence:
    action_ids = set(sprint.protocol.actions.values_list("stable_id", flat=True))
    submitted = sprint.check_ins.filter(status=PracticeCheckIn.Status.SUBMITTED)
    attempted_ids = set(submitted.filter(action_attempted=True).values_list("action_id", flat=True))
    completed_ids = set(submitted.filter(action_completed=True).values_list("action_id", flat=True))
    substantive = (
        submitted.filter(action_attempted=True)
        .filter(Q(moved_beyond_transactional=True) | Q(meaningful_information_shared=True))
        .exists()
    )
    all_attempted = bool(action_ids) and action_ids.issubset(attempted_ids)
    enough_completed = len(completed_ids) >= 2
    return CompletionEvidence(
        actions_attempted=len(attempted_ids & action_ids),
        actions_completed=len(completed_ids & action_ids),
        substantive_interaction_occurred=substantive,
        all_actions_attempted=all_attempted,
        enough_actions_completed=enough_completed,
        ready_for_review=all_attempted and enough_completed and substantive,
    )


@transaction.atomic
def save_check_in(
    *,
    sprint: PracticeSprint,
    cleaned_data: dict[str, Any],
    existing: PracticeCheckIn | None = None,
    submit: bool,
) -> PracticeCheckIn:
    locked_sprint = PracticeSprint.objects.select_for_update().get(pk=sprint.pk)
    if locked_sprint.status != PracticeSprint.Status.ACTIVE:
        raise PracticeWorkflowError("Check-ins can only be saved while a practice is active.")
    action = cleaned_data["action"]
    if action.protocol_id != locked_sprint.protocol_id:
        raise PracticeWorkflowError("The selected action does not belong to this practice.")
    if existing is not None:
        check_in = PracticeCheckIn.objects.select_for_update().get(pk=existing.pk)
        if check_in.sprint_id != locked_sprint.pk:
            raise PracticeWorkflowError("The draft does not belong to this practice.")
        if check_in.status != PracticeCheckIn.Status.DRAFT:
            raise PracticeWorkflowError("Submitted check-ins cannot be changed.")
    else:
        check_in = PracticeCheckIn(sprint=locked_sprint)

    editable_fields = (
        "action",
        "action_attempted",
        "action_completed",
        "user_initiated",
        "moved_beyond_transactional",
        "follow_up_question_asked",
        "meaningful_information_shared",
        "future_interaction_scheduled",
        "follow_up_within_seven_days",
        "internal_resistance",
        "expected_reciprocity",
        "observed_reciprocity",
        "support_level",
        "context_comparison",
        "evidence_direction",
        "contradictory_evidence",
        "note",
    )
    for field in editable_fields:
        setattr(check_in, field, cleaned_data[field])
    check_in.status = PracticeCheckIn.Status.SUBMITTED if submit else PracticeCheckIn.Status.DRAFT
    check_in.submitted_at = timezone.now() if submit else None
    if submit:
        missing = [
            label
            for field, label in (
                ("support_level", "support used"),
                ("context_comparison", "context comparison"),
                ("evidence_direction", "evidence direction"),
            )
            if not getattr(check_in, field)
        ]
        if missing:
            raise PracticeWorkflowError(f"Submitted evidence requires: {', '.join(missing)}.")
        has_prior = locked_sprint.check_ins.filter(status=PracticeCheckIn.Status.SUBMITTED).exists()
        if (
            check_in.context_comparison == PracticeCheckIn.ContextComparison.FIRST_RECORD
            and has_prior
        ):
            raise PracticeWorkflowError(
                "First record is only available before any evidence has been submitted."
            )
        if (
            check_in.context_comparison != PracticeCheckIn.ContextComparison.FIRST_RECORD
            and not has_prior
        ):
            raise PracticeWorkflowError(
                "The first submitted check-in must use first record for its context."
            )
        if (
            check_in.evidence_direction
            in (
                PracticeCheckIn.EvidenceDirection.MIXED,
                PracticeCheckIn.EvidenceDirection.CONTRADICTS,
            )
            and not check_in.contradictory_evidence.strip()
        ):
            raise PracticeWorkflowError(
                "Mixed or contradictory evidence requires a brief explanation."
            )
    try:
        check_in.full_clean()
    except ValidationError as exc:
        raise PracticeWorkflowError("; ".join(exc.messages)) from exc
    check_in.save()
    if submit:
        try:
            create_evidence_event(check_in)
        except EvidenceWorkflowError as exc:
            raise PracticeWorkflowError(str(exc)) from exc
    return check_in


@transaction.atomic
def complete_with_review(
    *,
    sprint: PracticeSprint,
    reflection: str,
    contradictory_evidence: str,
) -> PracticeReview:
    locked = PracticeSprint.objects.select_for_update().get(pk=sprint.pk)
    if locked.status not in (PracticeSprint.Status.ACTIVE, PracticeSprint.Status.PAUSED):
        raise PracticeWorkflowError("Only a current practice can be completed.")
    if PracticeReview.objects.filter(sprint=locked).exists():
        raise PracticeWorkflowError("This practice already has a final review.")
    evidence = completion_evidence(locked)
    if not evidence.ready_for_review:
        raise PracticeWorkflowError(
            "Completion requires all three actions attempted, at least two completed, "
            "and at least one substantive interaction."
        )
    review = PracticeReview.objects.create(
        sprint=locked,
        actions_attempted=evidence.actions_attempted,
        actions_completed=evidence.actions_completed,
        substantive_interaction_occurred=evidence.substantive_interaction_occurred,
        reflection=reflection,
        contradictory_evidence=contradictory_evidence,
        static_score_impact_preview={},
        submitted_at=timezone.now(),
    )
    locked.status = PracticeSprint.Status.COMPLETED
    locked.completed_at = timezone.now()
    locked.paused_at = None
    locked.save()
    return review
