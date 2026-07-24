from __future__ import annotations

from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.db import transaction

from growth.domain.evidence import (
    ALLOWED_OBSERVATION_FIELDS,
    EvidenceContractError,
    EvidenceInput,
    evaluate_evidence,
    replay_evidence,
)
from growth.models import EvidenceEvent, PracticeCheckIn


class EvidenceWorkflowError(ValueError):
    pass


@dataclass(frozen=True)
class EvidenceBackfillSummary:
    submitted_check_ins: int
    events_created: int
    events_already_present: int


def _input_for(check_in: PracticeCheckIn, repetition_index: int) -> EvidenceInput:
    return EvidenceInput(
        protocol_stable_id=check_in.sprint.protocol_id,
        action_stable_id=check_in.action_id,
        action_attempted=check_in.action_attempted,
        action_completed=check_in.action_completed,
        observations={
            field: bool(getattr(check_in, field)) for field in ALLOWED_OBSERVATION_FIELDS
        },
        internal_resistance=check_in.internal_resistance,
        expected_reciprocity=check_in.expected_reciprocity,
        observed_reciprocity=check_in.observed_reciprocity,
        support_level=check_in.support_level,
        context_comparison=check_in.context_comparison,
        evidence_direction=check_in.evidence_direction,
        contradiction_text_present=bool(check_in.contradictory_evidence.strip()),
        repetition_index=repetition_index,
    )


def repetition_index_for(check_in: PracticeCheckIn) -> int:
    ordered_ids = list(
        PracticeCheckIn.objects.filter(
            sprint_id=check_in.sprint_id,
            action_id=check_in.action_id,
            status=PracticeCheckIn.Status.SUBMITTED,
        )
        .order_by("submitted_at", "created_at", "stable_id")
        .values_list("stable_id", flat=True)
    )
    try:
        return ordered_ids.index(check_in.pk) + 1
    except ValueError as exc:
        raise EvidenceWorkflowError("The check-in is not a submitted evidence source.") from exc


def verify_evidence_event(event: EvidenceEvent) -> None:
    try:
        replayed = replay_evidence(event.input_snapshot)
    except EvidenceContractError as exc:
        raise EvidenceWorkflowError(f"{event.pk}: {exc}") from exc
    comparisons = {
        "algorithm_version": replayed.algorithm_version,
        "performance": replayed.performance,
        "quality": replayed.quality,
        "independence": replayed.independence,
        "context_breadth": replayed.context_breadth,
        "repetition_index": replayed.repetition_index,
        "repetition_multiplier": replayed.repetition_multiplier,
        "contradiction_level": replayed.contradiction_level,
        "base_evidence_mass": replayed.base_evidence_mass,
        "input_snapshot": replayed.input_snapshot,
        "explanation": replayed.explanation,
    }
    mismatches = [
        field for field, expected in comparisons.items() if getattr(event, field) != expected
    ]
    if mismatches:
        raise EvidenceWorkflowError(
            f"{event.pk}: stored evidence does not replay: {', '.join(mismatches)}."
        )


@transaction.atomic
def create_evidence_event(
    check_in: PracticeCheckIn,
    *,
    repetition_index: int | None = None,
) -> EvidenceEvent:
    source = (
        PracticeCheckIn.objects.select_related("sprint__protocol", "action")
        .select_for_update()
        .get(pk=check_in.pk)
    )
    if source.status != PracticeCheckIn.Status.SUBMITTED or source.submitted_at is None:
        raise EvidenceWorkflowError("Only a submitted check-in can create an evidence event.")
    existing = EvidenceEvent.objects.filter(check_in=source).first()
    if existing is not None:
        verify_evidence_event(existing)
        return existing
    if source.action.protocol_id != source.sprint.protocol_id:
        raise EvidenceWorkflowError("The check-in action does not belong to its practice.")

    resolved_index = repetition_index or repetition_index_for(source)
    try:
        result = evaluate_evidence(
            _input_for(source, resolved_index),
            source.action.evidence_rules,
        )
    except EvidenceContractError as exc:
        raise EvidenceWorkflowError(str(exc)) from exc

    event = EvidenceEvent(
        check_in=source,
        algorithm_version=result.algorithm_version,
        protocol_stable_id=source.sprint.protocol_id,
        action_stable_id=source.action_id,
        input_snapshot=result.input_snapshot,
        performance=result.performance,
        quality=result.quality,
        independence=result.independence,
        context_breadth=result.context_breadth,
        repetition_index=result.repetition_index,
        repetition_multiplier=result.repetition_multiplier,
        contradiction_level=result.contradiction_level,
        base_evidence_mass=result.base_evidence_mass,
        explanation=result.explanation,
    )
    try:
        event.full_clean()
    except ValidationError as exc:
        raise EvidenceWorkflowError("; ".join(exc.messages)) from exc
    event.save()
    return event


@transaction.atomic
def backfill_evidence_events(*, dry_run: bool = False) -> EvidenceBackfillSummary:
    submitted = list(
        PracticeCheckIn.objects.filter(status=PracticeCheckIn.Status.SUBMITTED)
        .select_related("sprint__protocol", "action")
        .order_by("sprint_id", "action_id", "submitted_at", "created_at", "stable_id")
    )
    counters: dict[tuple[object, str], int] = {}
    created = 0
    existing_count = 0
    for check_in in submitted:
        key = (check_in.sprint_id, check_in.action_id)
        counters[key] = counters.get(key, 0) + 1
        existing = EvidenceEvent.objects.filter(check_in=check_in).first()
        if existing is not None:
            if existing.repetition_index != counters[key]:
                raise EvidenceWorkflowError(
                    f"{check_in.pk}: stored repetition index does not match submission order."
                )
            verify_evidence_event(existing)
            existing_count += 1
            continue
        if dry_run:
            continue
        create_evidence_event(check_in, repetition_index=counters[key])
        created += 1

    return EvidenceBackfillSummary(
        submitted_check_ins=len(submitted),
        events_created=created,
        events_already_present=existing_count,
    )
