from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

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


EVIDENCE_EXPORT_SCHEMA_VERSION = "grounded-growth-evidence-export-v1"

EVIDENCE_DIRECTION_LABELS = {
    "supports": "Supported expected pattern",
    "mixed": "Mixed or unclear",
    "contradicts": "Contradicted expected pattern",
    "inconclusive": "Not enough happened to tell",
    "not_recorded": "Direction not recorded",
}


@dataclass(frozen=True)
class EvidenceBackfillSummary:
    submitted_check_ins: int
    events_created: int
    events_already_present: int


@dataclass(frozen=True)
class EvidenceVerificationSummary:
    submitted_check_ins: int
    events_verified: int


@dataclass(frozen=True)
class EvidenceLedgerSummary:
    total: int
    supports: int
    mixed: int
    contradicts: int
    inconclusive: int
    not_recorded: int


@dataclass(frozen=True)
class EvidenceLedgerRow:
    event: EvidenceEvent
    direction_key: str
    direction_label: str


@dataclass(frozen=True)
class EvidenceLedger:
    rows: tuple[EvidenceLedgerRow, ...]
    summary: EvidenceLedgerSummary
    active_direction: str


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
        "protocol_stable_id": replayed.input_snapshot["protocol_stable_id"],
        "action_stable_id": replayed.input_snapshot["action_stable_id"],
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
    if event.protocol_stable_id != event.check_in.sprint.protocol_id:
        raise EvidenceWorkflowError(
            f"{event.pk}: protocol stable ID does not match its submitted check-in."
        )
    if event.action_stable_id != event.check_in.action_id:
        raise EvidenceWorkflowError(
            f"{event.pk}: action stable ID does not match its submitted check-in."
        )
    if event.check_in.action.protocol_id != event.check_in.sprint.protocol_id:
        raise EvidenceWorkflowError(
            f"{event.pk}: check-in action does not belong to its practice protocol."
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


def verify_all_evidence_events() -> EvidenceVerificationSummary:
    """Replay every event and require complete, correctly ordered coverage."""

    submitted = list(
        PracticeCheckIn.objects.filter(status=PracticeCheckIn.Status.SUBMITTED)
        .select_related("sprint__protocol", "action", "evidence_event")
        .order_by("sprint_id", "action_id", "submitted_at", "created_at", "stable_id")
    )
    counters: dict[tuple[object, str], int] = {}
    verified = 0
    for check_in in submitted:
        key = (check_in.sprint_id, check_in.action_id)
        counters[key] = counters.get(key, 0) + 1
        try:
            event = check_in.evidence_event
        except EvidenceEvent.DoesNotExist as exc:
            raise EvidenceWorkflowError(
                f"{check_in.pk}: submitted check-in has no evidence event."
            ) from exc
        if event.repetition_index != counters[key]:
            raise EvidenceWorkflowError(
                f"{event.pk}: repetition index does not match submission order."
            )
        verify_evidence_event(event)
        verified += 1

    event_count = EvidenceEvent.objects.count()
    if event_count != verified:
        raise EvidenceWorkflowError(
            f"Database contains {event_count} evidence events for {verified} submitted check-ins."
        )
    return EvidenceVerificationSummary(
        submitted_check_ins=len(submitted),
        events_verified=verified,
    )


def _direction_key(event: EvidenceEvent) -> str:
    direction = event.input_snapshot.get("evidence_direction")
    if direction in EVIDENCE_DIRECTION_LABELS:
        return direction
    return "not_recorded"


def _events_for_user(user) -> list[EvidenceEvent]:
    return list(
        EvidenceEvent.objects.filter(check_in__sprint__user=user)
        .select_related(
            "check_in__action",
            "check_in__sprint__assessment_run",
            "check_in__sprint__protocol",
        )
        .order_by(
            "check_in__submitted_at",
            "check_in__created_at",
            "check_in__stable_id",
        )
    )


def _verified_events_for_user(user) -> list[EvidenceEvent]:
    events = _events_for_user(user)
    submitted_count = PracticeCheckIn.objects.filter(
        sprint__user=user,
        status=PracticeCheckIn.Status.SUBMITTED,
    ).count()
    if len(events) != submitted_count:
        raise EvidenceWorkflowError(
            "Submitted check-ins and evidence events are not in complete agreement."
        )

    repetition_counts: dict[tuple[object, str], int] = {}
    for event in events:
        key = (event.check_in.sprint_id, event.action_stable_id)
        repetition_counts[key] = repetition_counts.get(key, 0) + 1
        if event.repetition_index != repetition_counts[key]:
            raise EvidenceWorkflowError(
                f"{event.pk}: repetition index does not match submission order."
            )
        verify_evidence_event(event)
    return events


def build_evidence_ledger(user, *, direction: str = "all") -> EvidenceLedger:
    if direction != "all" and direction not in EVIDENCE_DIRECTION_LABELS:
        raise EvidenceWorkflowError("That evidence direction filter is not available.")

    all_rows = tuple(
        EvidenceLedgerRow(
            event=event,
            direction_key=_direction_key(event),
            direction_label=EVIDENCE_DIRECTION_LABELS[_direction_key(event)],
        )
        for event in reversed(_verified_events_for_user(user))
    )
    counts = Counter(row.direction_key for row in all_rows)
    rows = (
        all_rows
        if direction == "all"
        else tuple(row for row in all_rows if row.direction_key == direction)
    )
    return EvidenceLedger(
        rows=rows,
        summary=EvidenceLedgerSummary(
            total=len(all_rows),
            supports=counts["supports"],
            mixed=counts["mixed"],
            contradicts=counts["contradicts"],
            inconclusive=counts["inconclusive"],
            not_recorded=counts["not_recorded"],
        ),
        active_direction=direction,
    )


def _decimal_string(value: Decimal | None) -> str | None:
    return None if value is None else f"{value:.4f}"


def _privacy_safe_input(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Allowlist replay inputs that contain no user-authored text or identifiers."""

    rules = snapshot["evidence_rules"]
    observations = snapshot["observations"]
    return {
        "action_attempted": snapshot["action_attempted"],
        "action_completed": snapshot["action_completed"],
        "observations": {
            field: bool(observations[field]) for field in sorted(ALLOWED_OBSERVATION_FIELDS)
        },
        "internal_resistance": snapshot["internal_resistance"],
        "expected_reciprocity": snapshot["expected_reciprocity"],
        "observed_reciprocity": snapshot["observed_reciprocity"],
        "support_level": snapshot["support_level"],
        "context_comparison": snapshot["context_comparison"],
        "evidence_direction": snapshot["evidence_direction"],
        "contradiction_text_present": snapshot["contradiction_text_present"],
        "repetition_index": snapshot["repetition_index"],
        "evidence_rules": {
            "schema_version": rules["schema_version"],
            "primary_markers": list(rules["primary_markers"]),
            "supporting_markers": list(rules["supporting_markers"]),
        },
    }


def build_privacy_safe_evidence_export(user) -> dict[str, Any]:
    """Build a deterministic, text-free calibration export for one user."""

    events = _verified_events_for_user(user)
    exported_events = []
    for sequence, event in enumerate(events, start=1):
        exported_events.append(
            {
                "sequence": sequence,
                "algorithm_version": event.algorithm_version,
                "protocol_stable_id": event.protocol_stable_id,
                "action_stable_id": event.action_stable_id,
                "input": _privacy_safe_input(event.input_snapshot),
                "output": {
                    "performance": _decimal_string(event.performance),
                    "quality": _decimal_string(event.quality),
                    "independence": _decimal_string(event.independence),
                    "context_breadth": _decimal_string(event.context_breadth),
                    "repetition_index": event.repetition_index,
                    "repetition_multiplier": _decimal_string(event.repetition_multiplier),
                    "contradiction_level": _decimal_string(event.contradiction_level),
                    "base_evidence_mass": _decimal_string(event.base_evidence_mass),
                },
            }
        )

    return {
        "schema_version": EVIDENCE_EXPORT_SCHEMA_VERSION,
        "profile_scores_modified": False,
        "source": "structured_self_report",
        "privacy": {
            "contains_user_identity": False,
            "contains_record_ids": False,
            "contains_exact_timestamps": False,
            "contains_free_text": False,
            "excluded": [
                "user identity",
                "event, sprint, and check-in IDs",
                "person or context labels",
                "exact dates and times",
                "notes and contradiction detail",
                "assessment answers and share codes",
            ],
        },
        "event_count": len(exported_events),
        "events": exported_events,
    }
